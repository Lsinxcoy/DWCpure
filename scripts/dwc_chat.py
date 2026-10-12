# -*- coding: utf-8 -*-
"""DWC · 交互式 CLI 界面（R211 — 学 GitHub 头部 agent 的交互形态）。

★★ 研究依据（2026-10-12 GitHub 实搜, star 数当日值）:
  OpenCode ~200k★ / Claude Code ~142k★ / Codex ~125k / Gemini CLI ~107k
  / Goose ~54k / Aider ~49k —— 共性交互模式全部落进本界面:
  ① 无参启动 = 交互 REPL（OpenCode "by default starts the TUI"）
  ② 斜杠命令: / 触发列表 + 字母过滤（Claude Code "type / to see commands"）
  ③ 非交互单发: -c/--cmd（= opencode run "msg" 的地位, 旗标只做单发）
  ④ 状态栏 + 成本显示（/cost 模式: 台账真值）
  ⑤ 后端走 RPC（= OpenCode client-server; agent 活着走网, 死了本地直调降级）
  ⑥ readline ↑ 历史（Windows 无 readline 则优雅降级）

★ 用法:
  python scripts/dwc_chat.py            # 交互 REPL
  python scripts/dwc_chat.py -c "/doctor"     # 非交互单发（脚本/CI）
  python scripts/dwc_chat.py -c "读 core.py 总结给我"   # 单发投单并等结果
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc import agent_rpc as R                               # noqa: E402

# ── ANSI（无依赖; NO_COLOR/管道自动关）────────────────────
_ON = sys.stdout.isatty() and not os.environ.get("NO_COLOR")
def _c(code, s):
    return "\033[%sm%s\033[0m" % (code, s) if _ON else s
def cyan(s):  return _c("36", s)
def dim(s):   return _c("2", s)
def green(s): return _c("32", s)
def yellow(s):return _c("33", s)
def red(s):   return _c("31", s)
def bold(s):  return _c("1", s)

BANNER = """
  ██████╗ ██████╗ ██╗ ██████╗███████╗
  ██╔══██╗██╔══██╗██║██╔════╝██╔════╝
  ██║  ██║██████╔╝██║██║     █████╗
  ██║  ██║██╔══██╗██║██║     ██╔══╝
  ╚█████╔╝██║  ██║██║╚██████╗███████╗
   ╚════╝ ╚═╝  ╚═╝╚═╝ ╚═════╝╚══════╝   独立 agent · 交互界面
"""

HELP = """可用斜杠命令（输入 / 再输字母可过滤）:
  /status        agent 状态（pid/心跳/冻结/队列/当日成本）
  /list          任务列表          /query <id>   查单（+报告）
  /watch <id>    跟踪任务直到完成（实时状态）
  /cancel <id>   撤单              /cost         当日 term 成本台账
  /history [n]   台账尾 n 条        /doctor       自检（db/真值源/LLM/备份）
  /freeze        冻结 agent        /unfreeze     解冻
  /help          本帮助            /quit /q /exit  退出
★ 直接输入自然语言 = 自动投单并跟踪到完成（结果在这里显示）
★ 非交互单发: dwc_chat.py -c "内容\""""


def _rpc(method, params=None, timeout=20):
    """走网（agent RPC）; 不通返回 None ⇒ 调用方降级本地直调。"""
    try:
        tok = R.load_or_make_token()
        body = json.dumps({"method": method,
                           "params": params or {}}).encode()
        req = urllib.request.Request("http://127.0.0.1:%d/rpc" % R.RPC_PORT,
                                     data=body,
            headers={"Content-Type": "application/json", "X-DWC-Token": tok})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            out = json.loads(resp.read().decode())
        return out.get("result") if out.get("ok") else {
            "_error": out.get("error")}
    except Exception:                          # noqa: BLE001 — 网断=降级
        return None


def call(method, **params):
    """RPC 优先; agent 没起 ⇒ 本地直调同一套指令核心（单实现两前端）。"""
    r = _rpc(method, params)
    if r is not None:
        return r
    fn = R.METHODS.get(method)
    if fn is None:
        return {"_error": "未知指令 %r" % method}
    try:
        return fn(**params)
    except Exception as exc:                   # noqa: BLE001
        return {"_error": "%s: %s" % (type(exc).__name__, exc)}


def status_bar() -> str:
    s = call("status")
    if not isinstance(s, dict) or "_error" in s:
        return dim("DWC · agent 离线（本地模式）")
    pid = s.get("pid")
    hb = s.get("heartbeat") or {}
    q = s.get("queue") or {}
    mode = red("FROZEN") if s.get("frozen") else (
        green("alive") if pid else red("down"))
    return ("DWC · %s pid=%s · terms=%s pass=%s · queue p=%s d=%s · %s" % (
        mode, pid, hb.get("terms", "-"), hb.get("pass_rate", "-"),
        q.get("pending", 0), q.get("done", 0),
        dim(str(s.get("db_bytes", 0)) + "B")))


def watch(tid: str, max_wait: int = 180):
    """跟踪任务到终态（学 /watch: 实时状态而非刮文件）。"""
    t0 = time.time()
    last = None
    while time.time() - t0 < max_wait:
        q = call("query", id=tid)
        state = (q or {}).get("state")
        if state != last:
            print("  %s %s" % (dim("[%5.0fs]" % (time.time() - t0)),
                               yellow("state=" + str(state))))
            last = state
        if state in ("done", "incomplete", "cancelled"):
            rep = (q or {}).get("report") or {}
            if state == "done":
                print(green("\n✓ 完成（%s 轮）:") % rep.get("rounds"))
                print(rep.get("answer", ""))
                if rep.get("artifacts"):
                    print(dim("  产物: " + ", ".join(rep["artifacts"])))
            elif state == "incomplete":
                print(red("\n✗ 未完成: ") + str(rep.get("why", "")))
            return
        time.sleep(3)
    print(yellow("\n超时（%ds）仍未终态 — 用 /query %s 随时查" % (max_wait, tid)))


def handle(line: str) -> bool:
    """处理一行; 返回 False = 退出。"""
    line = line.strip()
    if not line:
        return True
    if line in ("/quit", "/q", "/exit"):
        return False
    if line in ("/help", "/h", "/?"):
        print(HELP)
        return True
    if line.startswith("/"):
        parts = line.split(None, 1)
        cmd, arg = parts[0], (parts[1] if len(parts) > 1 else None)
        m = {
            "/status": lambda: print(_fmt(call("status"))),
            "/list": lambda: _fmt_list(call("list")),
            "/doctor": lambda: _fmt(call("doctor")),
            "/history": lambda: _hist(arg),
            "/cost": lambda: _hist("12", cost=True),
            "/freeze": lambda: print(yellow(_fmt(call("freeze")))),
            "/unfreeze": lambda: print(green(_fmt(call("unfreeze")))),
            "/watch": lambda: watch(arg) if arg else print(red("用法: /watch <id>")),
            "/query": lambda: _fmt(call("query", id=arg)) if arg
                             else print(red("用法: /query <id>")),
            "/cancel": lambda: print(_fmt(call("cancel", id=arg))) if arg
                               else print(red("用法: /cancel <id>")),
            "/submit": lambda: _submit(arg) if arg
                               else print(red("用法: /submit <任务>")),
        }.get(cmd)
        if m is None:
            # / 字母过滤（Claude Code 模式: 输 / 报列表）
            hits = [c for c in ("/help", "/status", "/list", "/query",
                                "/watch", "/cancel", "/submit", "/freeze",
                                "/unfreeze", "/history", "/cost", "/doctor",
                                "/quit") if c.startswith(cmd)]
            print(("候选: " + " ".join(hits)) if hits else red("未知命令 " + cmd))
        else:
            m()
        return True
    # 自然语言 = 投单 + 跟踪（结果在这里显示）
    r = call("submit", task=line)
    tid = (r or {}).get("id")
    if not tid:
        print(red("投单失败: %s" % _fmt(r)))
        return True
    print("%s 已投单 %s — 跟踪中（/watch %s 随时重看）"
          % (green("→"), bold(tid), tid))
    watch(tid)
    return True


def _submit(task):
    r = call("submit", task=task)
    print(_fmt(r))
    tid = (r or {}).get("id")
    if tid:
        watch(tid)


def _fmt(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=1)[:1800]


def _fmt_list(out):
    if not isinstance(out, dict):
        print(_fmt(out))
        return
    for x in out.get("items", []):
        c = green if x["state"] == "done" else (
            red if x["state"] == "cancelled" else yellow)
        print("  %s %-14s %s %s" % (c("%-10s" % x["state"]), x["id"],
                                    dim(str(x.get("ts", ""))[5:19]),
                                    str(x.get("task", ""))[:60]))
    if not out.get("items"):
        print(dim("  （空）"))


def _hist(n_arg, cost=False):
    n = int(n_arg) if n_arg else (12 if cost else 20)
    out = call("history", n=n)
    rows = (out or {}).get("tail", [])
    total = 0.0
    for x in rows:
        tag = ("cost" if "cost" in x else "event" if "event" in x else
               "task" if "agent_term" in x else "?")
        if cost and "cost" in x:
            total += float(x["cost"] or 0)
        print("  %s %s" % (dim(str(x.get("ts", ""))[11:19]),
                           json.dumps({k: v for k, v in x.items()
                                       if k != "ts"},
                                      ensure_ascii=False)[:110]))
    if cost:
        print(bold("  台账尾 %d 行 cost 合计: %.1f" % (len(rows), total)))


def repl() -> int:
    print(BANNER)
    print(status_bar())
    print(dim("输入 /help 看命令 · 直接说话=投单 · /quit 退出"))
    try:
        import readline                      # ↑ 历史（Windows 缺则降级）
        try:
            hist = os.path.join(R.VAR, ".dwc_chat_history")
            os.makedirs(R.VAR, exist_ok=True)
            if os.path.exists(hist):
                readline.read_history_file(hist)
            readline.set_history_length(500)
        except Exception:                    # noqa: BLE001
            pass
    except ImportError:
        pass
    while True:
        try:
            line = input(cyan("DWC ❯ "))
        except (EOFError, KeyboardInterrupt):
            print()
            break
        try:
            if not handle(line):
                break
            if line.strip() and not line.startswith("/"):
                print(dim(status_bar()))
        except Exception as exc:             # noqa: BLE001 — REPL 不崩
            print(red("内部错误: %s: %s" % (type(exc).__name__, exc)))
    try:
        hist = os.path.join(R.VAR, ".dwc_chat_history")
        readline.write_history_file(hist)
    except Exception:                        # noqa: BLE001
        pass
    print(dim("再见。"))
    return 0


def main(argv) -> int:
    if len(argv) > 1 and argv[1] in ("-c", "--cmd"):
        line = " ".join(argv[2:])
        return 0 if handle(line) else 0
    if len(argv) > 1:                        # 自然语言单发参数
        return 0 if handle(" ".join(argv[1:])) else 0
    return repl()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
