# -*- coding: utf-8 -*-
"""R210 · DWC agent 指令核心 + HTTP RPC（独立 agent 的独立交互面）。

★★★ 定位（G1）: **DWC-AUTO** —— agent 的对外指令协议面。
★★★ TRUTH_SOURCE: 无判定面（判分在 judge）——本模块只编排文件协议与
  进程状态查询, 不产任何评分/结论。

★ 设计（用户 2026-10-12 拍板案①）:
  · 指令语义**单实现**于本模块（纯函数, 全走 var/ 文件协议）
  · HTTP RPC server（agent 进程内 daemon 线程, POST /rpc, 默认 8802）
    与 CLI 壳（dwc_cli.py 直调函数）两个前端共用
  · ★ 线程安全: RPC handler **不碰 DWC 核心对象** — 投单/冻结走文件,
    状态走只读文件 ⇒ 主循环线程零共享内存（freeze/inbox 现有模式延伸）
  · 认证: var/dwc_rpc_token（agent 启动时生成随机 hex; 请求头 X-DWC-Token）
    —— 本机文件面认证, 不是网络安全边界（诚实声明）

★ 指令集 v1: status / submit / query / list / cancel / freeze /
  unfreeze / history / doctor
"""
from __future__ import annotations

import json
import os
import secrets
import time
from typing import Any, Dict, List, Optional

ROOT = r"E:/Divine Wisdom Core"
#: ★ 测试/多实例隔离: DWC_VAR_DIR 环境变量覆盖 var 根（subprocess 测试与
#:   生产 agent 的台账/db/pid 全隔离 — 间歇竞态根治, 2026-10-12 全量复现）
VAR = os.environ.get("DWC_VAR_DIR") or os.path.join(ROOT, "var")
DB = os.path.join(VAR, "dwc_prod.sqlite")
LOG = os.path.join(VAR, "dwc_prod_log.jsonl")
PID = os.path.join(VAR, "dwc_agent.pid")
HB = os.path.join(VAR, "dwc_agent_heartbeat.json")
FROZEN = os.path.join(VAR, "dwc_agent_frozen")
INBOX = os.path.join(VAR, "dwc_inbox.jsonl")
INBOX_DONE = os.path.join(VAR, "dwc_inbox_done.json")
REPORTS = os.path.join(VAR, "dwc_reports")
TOKEN = os.path.join(VAR, "dwc_rpc_token")
RPC_PORT = 8802                      # 8899 已被占（2026-10-12 netstat 实测）


# ── 文件协议原语 ──────────────────────────────────────────
def _read_json(p: str, default):
    try:
        with open(p, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:                          # noqa: BLE001
        return default


def _done_state() -> Dict[str, str]:
    return _read_json(INBOX_DONE, {})


def _log_tail(n: int) -> List[Dict[str, Any]]:
    if not os.path.exists(LOG):
        return []
    lines = [x for x in open(LOG, encoding="utf-8").read().splitlines()
             if x.strip()]
    out = []
    for ln in lines[-n:]:
        try:
            out.append(json.loads(ln))
        except Exception:                      # noqa: BLE001
            out.append({"raw": ln[:120]})
    return out


# ── 指令实现（单实现 — CLI 与 RPC 共用）────────────────────
def cmd_status() -> Dict[str, Any]:
    st = _done_state()
    inbox_ids = []
    if os.path.exists(INBOX):
        for ln in open(INBOX, encoding="utf-8").read().splitlines():
            if ln.strip():
                try:
                    inbox_ids.append(json.loads(ln).get("id"))
                except Exception:              # noqa: BLE001
                    pass
    pending = [i for i in inbox_ids if i and i not in st]
    hb = _read_json(HB, {})
    tail = _log_tail(6)
    today_terms = sum(1 for x in tail if "agent_term" in x)
    return {"pid": (open(PID).read().strip() if os.path.exists(PID) else None),
            "frozen": os.path.exists(FROZEN), "heartbeat": hb,
            "queue": {"pending": len(pending), "pending_ids": pending[:10],
                      "done": sum(1 for v in st.values() if v == "done"),
                      "total_seen": len(set(inbox_ids))},
            "recent_terms_in_tail6": today_terms,
            "db_bytes": os.path.getsize(DB) if os.path.exists(DB) else 0}


def cmd_submit(task: str, ctx: Optional[str] = None,
               id: Optional[str] = None) -> Dict[str, Any]:
    if not task or not str(task).strip():
        return {"ok": False, "error": "task 不能为空"}
    tid = id or ("T_" + time.strftime("%m%d_%H%M%S"))
    st = _done_state()
    if tid in st:
        return {"ok": False, "error": "id 已存在（done 态）: %s" % tid}
    os.makedirs(VAR, exist_ok=True)
    with open(INBOX, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"id": tid, "task": task, "ctx": ctx,
                             "by": "rpc",
                             "ts": time.strftime("%Y-%m-%dT%H:%M:%S+08:00")},
                            ensure_ascii=False) + "\n")
    return {"ok": True, "id": tid,
            "note": "agent 下轮优先消费; 报告在 var/dwc_reports/%s.json" % tid}


def cmd_query(id: str) -> Dict[str, Any]:
    st = _done_state()
    rep = _read_json(os.path.join(REPORTS, id + ".json"), None)
    if rep is not None:
        state = rep.get("status", "unknown")
    elif id in st:
        state = st[id]
    else:
        state = "pending" if _id_in_inbox(id) else "unknown"
    return {"id": id, "state": state, "report": rep}


def _id_in_inbox(id: str) -> bool:
    if not os.path.exists(INBOX):
        return False
    for ln in open(INBOX, encoding="utf-8").read().splitlines():
        if ln.strip():
            try:
                if json.loads(ln).get("id") == id:
                    return True
            except Exception:                  # noqa: BLE001
                pass
    return False


def cmd_list(kind: str = "all") -> Dict[str, Any]:
    st = _done_state()
    items = []
    if os.path.exists(INBOX):
        for ln in open(INBOX, encoding="utf-8").read().splitlines():
            if not ln.strip():
                continue
            try:
                it = json.loads(ln)
            except Exception:                  # noqa: BLE001
                continue
            tid = it.get("id")
            state = st.get(tid, "pending")
            items.append({"id": tid, "state": state,
                          "task": str(it.get("task", ""))[:80],
                          "ts": it.get("ts")})
    seen, uniq = set(), []
    for x in reversed(items):                  # 后投先列
        if x["id"] not in seen:
            seen.add(x["id"])
            uniq.append(x)
    if kind == "pending":
        uniq = [x for x in uniq if x["state"] == "pending"]
    elif kind == "done":
        uniq = [x for x in uniq if x["state"] == "done"]
    return {"n": len(uniq), "items": uniq[:50]}


def cmd_cancel(id: str) -> Dict[str, Any]:
    st = _done_state()
    if st.get(id):
        return {"ok": False, "error": "已在终态 %s, 不可撤" % st[id]}
    if not _id_in_inbox(id):
        return {"ok": False, "error": "inbox 无此单: %s" % id}
    st[id] = "cancelled"                       # take_inbox 跳过 done 态任意键
    with open(INBOX_DONE, "w", encoding="utf-8") as fh:
        json.dump(st, fh, ensure_ascii=False)
    return {"ok": True, "id": id, "state": "cancelled"}


def cmd_freeze() -> Dict[str, Any]:
    os.makedirs(VAR, exist_ok=True)
    with open(FROZEN, "w", encoding="utf-8") as fh:
        fh.write(time.strftime("%c"))
    return {"ok": True, "frozen": True,
            "note": "agent 下轮优雅停, 守夜人不拉活"}


def cmd_unfreeze() -> Dict[str, Any]:
    if os.path.exists(FROZEN):
        os.remove(FROZEN)
    return {"ok": True, "frozen": False,
            "note": "守夜人 2h 内拉活, 或手动启动"}


def cmd_history(n: int = 20) -> Dict[str, Any]:
    return {"n": n, "tail": _log_tail(int(n))}


def cmd_doctor() -> Dict[str, Any]:
    checks = {}
    checks["db"] = "ok" if os.path.exists(DB) and os.path.getsize(DB) > 0 \
        else "MISSING"
    dev = os.path.join(ROOT, "config", "anchors", "dev.json")
    checks["truth_dev_json"] = "ok" if os.path.exists(dev) else "MISSING"
    try:
        from dwc.harness.anchor_drift import epoch_of
        checks["epoch"] = epoch_of(ROOT)
    except Exception as exc:                    # noqa: BLE001
        checks["epoch"] = "ERROR: %s" % exc
    try:
        from dwc.llm.client import LLMClient
        c = LLMClient()
        checks["llm_configured"] = bool(getattr(c, "configured", False))
        pr = c.probe() if checks["llm_configured"] else None
        checks["llm_probe"] = (bool(getattr(pr, "ok", False))
                               if pr is not None else "skipped")
    except Exception as exc:                    # noqa: BLE001
        checks["llm"] = "ERROR: %s" % exc
    bdir = os.path.join(VAR, "backup")
    try:
        subs = sorted(os.listdir(bdir))
        newest = subs[-1] if subs else None
        age_h = ((time.time() - os.path.getmtime(
            os.path.join(bdir, newest))) / 3600) if newest else None
        checks["backup"] = ({"newest": newest,
                             "age_h": round(age_h, 1)} if newest else "NONE")
    except Exception:                           # noqa: BLE001
        checks["backup"] = "NONE"
    checks["agent_alive"] = bool(_agent_alive())
    return checks


def _agent_alive():
    if not os.path.exists(PID):
        return False
    try:
        pid = int(open(PID, encoding="utf-8").read().strip())
        import psutil
        return psutil.pid_exists(pid)
    except Exception:                           # noqa: BLE001
        return False


#: 指令表（RPC method 名 → 函数; CLI 同源）
METHODS = {
    "status": cmd_status, "submit": cmd_submit, "query": cmd_query,
    "list": cmd_list, "cancel": cmd_cancel, "freeze": cmd_freeze,
    "unfreeze": cmd_unfreeze, "history": cmd_history, "doctor": cmd_doctor,
}


def load_or_make_token() -> str:
    tok = _read_json(TOKEN, None)
    if isinstance(tok, dict) and tok.get("token"):
        return tok["token"]
    t = secrets.token_hex(16)
    os.makedirs(VAR, exist_ok=True)
    with open(TOKEN, "w", encoding="utf-8") as fh:
        json.dump({"token": t, "created": time.strftime("%c")}, fh)
    return t


def serve(port: int = RPC_PORT):
    """★ RPC server（agent 进程内 daemon 线程用）: POST /rpc JSON。
    认证: 头 X-DWC-Token == var/dwc_rpc_token（本机文件面）。"""
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    token = load_or_make_token()

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):             # 静默访问日志（G7 族）
            pass

        def do_POST(self):                      # noqa: N802
            if self.path != "/rpc":
                self._reply(404, {"ok": False, "error": "not /rpc"})
                return
            if self.headers.get("X-DWC-Token") != token:
                self._reply(401, {"ok": False, "error": "token 不符"})
                return
            try:
                n = int(self.headers.get("Content-Length", "0"))
                body = json.loads(self.rfile.read(n).decode("utf-8"))
                method = body.get("method")
                fn = METHODS.get(method)
                if fn is None:
                    self._reply(200, {"ok": False, "error":
                                      "未知指令 %r（表: %s）"
                                      % (method, sorted(METHODS))})
                    return
                result = fn(**(body.get("params") or {}))
                self._reply(200, {"ok": True, "method": method,
                                  "result": result})
            except TypeError as exc:
                self._reply(200, {"ok": False, "error": "参数不符: %s" % exc})
            except Exception as exc:            # noqa: BLE001
                self._reply(200, {"ok": False, "error":
                                  "%s: %s" % (type(exc).__name__, exc)})

        def _reply(self, code: int, obj: dict):
            raw = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

    class _Srv(ThreadingHTTPServer):
        allow_reuse_address = False   # ★ 禁复用: 双绑时请求会随机路由到两个
                                      #   agent —— 宁可 bind 失败留痕
    srv = _Srv(("127.0.0.1", port), H)
    import threading
    t = threading.Thread(target=srv.serve_forever, daemon=True,
                         name="dwc-rpc")
    t.start()
    return srv
