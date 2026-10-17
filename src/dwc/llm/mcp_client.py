# -*- coding: utf-8 -*-
"""R224 · MCP 工具协议 client（stdio JSON-RPC 2.0 子集 — 发布级工具面）。

★★★ 定位（G1）: **DWC-AUTO** —— agent 对外工具生态的标准接入协议
  （Model Context Protocol: initialize → tools/list → tools/call）。
★★★ TRUTH_SOURCE: 无 —— 只转发工具调用与观察, 不产任何判定。

★ 范围（诚实边界）:
  · transport = stdio（JSON-RPC 2.0, Content-Length 头 framing 的两种形态
    都支持: 行分帧 newline-delimited 与 LSP 式头分帧 —— 市面 server 两派
    都有, 探测式兼容）
  · server 生命周期: lazy 启动 + 进程缓存（模块级池）+ atexit 统一终止 —
    每 call 起停太贵（握手几十 ms × 高频调用）; 泄漏由 atexit 兜底
  · 配置: config/mcp.json {"servers": {"name": {"command": [argv...]}}}
  · 安全: server 命令来自配置文件（维护者写, agent 只读 config — 结构性
    护栏）; tools/call 的 args 原样转发, 不注入不改写
"""
from __future__ import annotations

import atexit
import io
import json
import os
import subprocess
import threading
import time
from typing import Any, Dict, List, Optional

from dwc.foundation.paths import find_root
ROOT = find_root()
MCP_CONF = os.path.join(ROOT, "config", "mcp.json")

#: 进程池 {name: {"proc": Popen, "lock": Lock, "tools": [...]}}
_POOL: Dict[str, Dict[str, Any]] = {}
_POOL_LOCK = threading.Lock()
#: G7 静默计数（except: pass 必须有计数/日志 — 门判据）
_SILENT = [0]


def _hush(where: str, exc: Exception) -> None:
    """G7: 静默分支统一走这里 — 计数 + 前 3 次 stderr（不刷屏不留白）。"""
    _SILENT[0] += 1
    if _SILENT[0] <= 3:
        import sys as _sys
        _sys.stderr.write("mcp_client 静默×%d @%s: %s\n"
                          % (_SILENT[0], where, exc))


class McpError(Exception):
    pass


def load_config(path: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
    path = path or MCP_CONF      # ★ 运行时取模块属性（默认参数会绑死定义值）
    """读 mcp.json — 缺文件=空配置（不装有）; 坏文件大声报错。"""
    if not os.path.exists(path):
        return {}
    try:
        obj = json.load(io.open(path, encoding="utf-8"))
    except (ValueError, OSError) as exc:
        raise McpError("mcp.json 坏了（%s: %s）— 不许悄悄空配置开跑"
                       % (type(exc).__name__, exc))
    servers = obj.get("servers")
    if not isinstance(servers, dict):
        raise McpError("mcp.json 缺 servers 字典")
    for name, cfg in servers.items():
        if not (isinstance(cfg, dict) and isinstance(cfg.get("command"), list)
                and cfg["command"]):
            raise McpError("server %r 的 command 必须是非空 argv 列表" % name)
    return servers


def _framed(obj: dict) -> bytes:
    raw = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    return b"Content-Length: %d\r\n\r\n" % len(raw) + raw


def _read_msg(proc: subprocess.Popen, deadline: float) -> Optional[dict]:
    """读一条 JSON-RPC 消息（两种分帧探测: 头分帧优先, 行分帧兜底）。"""
    f = proc.stdout
    head = b""
    while time.time() < deadline:
        ch = f.read(1)
        if not ch:
            return None
        head += ch
        if head.endswith(b"\r\n\r\n") or head.endswith(b"\n\n"):
            break
    else:
        return None
    if b"Content-Length:" in head:
        try:
            n = int(head.split(b"Content-Length:")[1].split(b"\r")[0].strip())
        except ValueError:
            return None
        body = f.read(n)
    else:
        body = head                      # 行分帧: 头即整行
        while not body.endswith(b"\n"):
            ch = f.read(1)
            if not ch:
                break
            body += ch
    try:
        return json.loads(body.decode("utf-8", errors="replace").strip())
    except ValueError:
        return None


def _rpc(name: str, method: str, params: Optional[dict] = None,
         timeout: float = 30.0) -> Any:
    """向池内 server 发一发（每 server 串行 — lock; 多 server 天然并行）。"""
    cfg_servers = load_config(MCP_CONF)
    if name not in cfg_servers:
        raise McpError("未配置的 MCP server: %r（配置: %s）"
                       % (name, sorted(cfg_servers)))
    with _POOL_LOCK:
        entry = _POOL.get(name)
        if entry is None or entry["proc"].poll() is not None:
            if entry:                       # 死进程清池重建
                try:
                    entry["proc"].terminate()
                except OSError as exc:
                    _hush("池重建 terminate", exc)
            proc = subprocess.Popen(
                [str(x) for x in cfg_servers[name]["command"]],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL, cwd=ROOT)
            entry = {"proc": proc, "lock": threading.Lock(),
                     "id": 0, "tools": None}
            _POOL[name] = entry
    with entry["lock"]:
        entry["id"] += 1
        mid = entry["id"]
        msg = {"jsonrpc": "2.0", "id": mid, "method": method}
        if params is not None:
            msg["params"] = params
        try:
            entry["proc"].stdin.write(_framed(msg))
            entry["proc"].stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            raise McpError("server %r 管道断（%s）" % (name, exc))
        deadline = time.time() + timeout
        while time.time() < deadline:
            resp = _read_msg(entry["proc"], deadline)
            if resp is None:
                break
            if resp.get("id") == mid:
                if "error" in resp:
                    raise McpError("server %r %s 报错: %s"
                                   % (name, method, resp["error"]))
                return resp.get("result")
        raise McpError("server %r %s 超时（%.0fs）" % (name, method, timeout))


def initialize(name: str) -> dict:
    """握手: initialize → notifications/initialized（MCP 规范序）。"""
    r = _rpc(name, "initialize", {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "dwc", "version": "R224"}})
    with _POOL_LOCK:
        entry = _POOL.get(name)
    if entry:
        with entry["lock"]:
            try:
                n = {"jsonrpc": "2.0",
                     "method": "notifications/initialized"}
                entry["proc"].stdin.write(_framed(n))
                entry["proc"].stdin.flush()
            except (BrokenPipeError, OSError) as exc:
                _hush("initialized通知", exc)
    return r or {}


def tools_list(name: str, ttl_s: float = 300) -> List[Dict[str, Any]]:
    """工具清单（缓存于池 entry; 供 system prompt 注入摘要）。

    ★ R309-② · 缓存 TTL：过期重探（防 stale 工具表永不过期）。
    """
    import time as _t
    with _POOL_LOCK:
        entry = _POOL.get(name)
    if entry and entry.get("tools") is not None:
        _ts = entry.get("tools_ts") or 0
        try:
            _fresh = (_t.time() - float(_ts)) < float(ttl_s)
        except (TypeError, ValueError):
            _fresh = False
        if _fresh:
            return entry["tools"]
    initialize(name)
    r = _rpc(name, "tools/list", {})
    tools = list((r or {}).get("tools", []))
    with _POOL_LOCK:
        e2 = _POOL.get(name)
        if e2:
            e2["tools"] = tools
            e2["tools_ts"] = _t.time()
    return tools


def probe(name: str, timeout: float = 5) -> bool:
    """★ R309-② · 轻量探活：通⇒True，不通⇒False。永不抛错。"""
    try:
        tools_list(name, ttl_s=0)
        return True
    except Exception as exc:
        _hush("probe", exc)
        return False


def tools_call(name: str, tool: str, arguments: Optional[dict] = None,
               timeout: float = 60.0, ttl_s: float = 300) -> Dict[str, Any]:
    """★ task_exec 'mcp' 动作的落点: 调用工具 → 原样观察。"""
    tools_list(name, ttl_s=ttl_s)          # 未握手先握手（幂等；TTL 过期重探）
    r = _rpc(name, "tools/call",
             {"name": tool, "arguments": arguments or {}}, timeout=timeout)
    out: Dict[str, Any] = {"ok": True, "server": name, "tool": tool}
    if isinstance(r, dict):
        texts = []
        for c in r.get("content", []) or []:
            if isinstance(c, dict) and c.get("type") == "text":
                texts.append(str(c.get("text", ""))[:6000])
        out["text"] = "\n".join(texts)[:8000]
        if r.get("isError"):
            out["ok"] = False
    else:
        out["raw"] = str(r)[:2000]
    return out


def shutdown_all() -> None:
    """atexit 兜底: 终止全部池内 server（不许留孤儿进程）。"""
    with _POOL_LOCK:
        entries = list(_POOL.values())
        _POOL.clear()
    for e in entries:
        try:
            e["proc"].terminate()
        except OSError as exc:
            _hush("shutdown 循环", exc)


atexit.register(shutdown_all)
