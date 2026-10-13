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
import subprocess
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc import agent_rpc as R                               # noqa: E402

# ── ANSI（无依赖; NO_COLOR/管道自动关）────────────────────
_ON = sys.stdout.isatty() and not os.environ.get("NO_COLOR")
def _ansi_ok() -> bool:
    """★ ANSI 色支持检测: PS 5.1 无 VT ⇒ 不发色码（发了就是乱码 — 用户实测）。
    支持面: Windows Terminal / VSCode / ANSICON / ConEmu / TERM 非 dumb。"""
    if os.environ.get("NO_COLOR"):
        return False
    return bool(os.environ.get("WT_SESSION")
                or os.environ.get("WT_PROFILE_ID")
                or os.environ.get("ANSICON")
                or os.environ.get("ConEmuANSI") == "ON"
                or os.environ.get("TERM_PROGRAM")
                or os.environ.get("TERM") not in (None, "", "dumb")
                and os.name != "nt")


_ANSI = _ansi_ok()


def _c(code, s):
    if not _ANSI:
        return str(s)
    return "\033[%sm%s\033[0m" % (code, s) if _ON else s
def cyan(s):  return _c("36", s)
def dim(s):   return _c("2", s)
def green(s): return _c("32", s)
def yellow(s):return _c("33", s)
def red(s):   return _c("31", s)
def bold(s):  return _c("1", s)
def dim2(s):  return _c("90", s)             # ★ R238 次级灰（更沉的层级）


# ★ R238 设计语言（研究对齐: opencode 单色主导 + Claude Code 行型密度）
#   —— 一个主色(青) + 语义色; 层级用 ⎿ │ ─ 符号, 不靠框
#: ★ ASCII 艺术字（R238b: 制表符块字 █╗║ 在错码页/非等宽字体下会糊成
#:   "AN"形乱码 — 用户实测被坑 ⇒ 一律纯 ASCII, 任何终端零错位）
_LOGO = [
    " ####   #   #    ####   ",
    " #  #   #   #    #  #   ",
    " #  #   # # #    #  #   ",
    " #  #   # # #    #  #   ",
    " ####   #   #    ####   ",
]



HELP = """可用斜杠命令（输入 / 再输字母可过滤）:
  /status        agent 状态（pid/心跳/冻结/队列/当日成本）
  /list          任务列表          /query <id>   查单（+报告）
  /watch <id>    跟踪任务直到完成（实时状态）
  /cancel <id>   撤单              /cost         当日 term 成本台账
  /history [n]   台账尾 n 条        /doctor       自检（db/真值源/LLM/备份）
  /freeze        冻结 agent        /unfreeze     解冻
  /approve <词>  授权 ask 类操作（飞书审批落点）   /deny <词>  拒绝
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


BG_MODE = False          # ★ R236: False=同步直驱(默认, 对话感); True=异步投单
_HISTORY = []            # 多轮上下文: 上轮任务+答案摘要进下轮 ctx


class _AnswerStream:
    """★ R237 · answer 流状态机（模块级 — 可测的真码, 不是闭包副本）。
    增量 raw JSON 中只打印 answer 字段的值, 转义还原, 闭合即止。"""

    def __init__(self):
        self.raw = ""
        self.in_ans = False

    def feed(self, piece: str, out=None) -> None:
        import sys as _s
        out = out or _s.stdout
        self.raw += piece
        raw = self.raw
        if not self.in_ans:
            key = '"answer":'
            i = raw.find(key)
            if i < 0:
                self.raw = raw[-64:]         # 只留可能跨包的尾部
                return
            j = raw.find('"', i + len(key))
            if j < 0:
                return
            self.in_ans = True
            raw = raw[j + 1:]
        emit, i = [], 0
        while i < len(raw):
            ch = raw[i]
            if ch == "\\" and i + 1 < len(raw):
                nx = raw[i + 1]
                emit.append({"n": "\n", "t": "\t", '"': '"', "b": "\b",
                             "f": "\f", "r": "\r"}.get(nx, nx))
                i += 2
                continue
            if ch == '"':
                self.in_ans = False
                self.raw = ""                 # ★ 闭合即清（尾部 } 无信息 —
                break                         #   否则 streamed 误报, 测试抓到）
            emit.append(ch)
            i += 1
        else:
            self.raw = ""
        if emit:
            out.write("".join(emit))
            out.flush()

    @property
    def streamed(self) -> bool:
        return bool(self.raw or self.in_ans)

    def reset(self) -> None:
        self.raw = ""
        self.in_ans = False


def _md(text: str) -> str:
    """★ 轻 markdown 渲染: 代码块保原 + 标题上色/粗体标记去除（零依赖 ANSI）。"""
    out, in_code = [], False
    for ln in str(text).splitlines():
        if ln.strip().startswith("```"):
            in_code = not in_code
            out.append(cyan(ln))
            continue
        if in_code:
            out.append("  " + ln)
            continue
        if ln.startswith("#"):
            out.append(bold(ln.lstrip("#").strip()))
        else:
            out.append(ln.replace("**", ""))
    return "\n".join(out)


def _run_sync(task: str) -> None:
    """★ 同步直驱: 本进程直接执行, 过程逐动作实时打印（Claude Code 式）。"""
    global _HISTORY
    import sys as _sys, time as _time
    root = os.environ.get("DWC_ROOT", "").strip() or os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))
    if root not in _sys.path:
        _sys.path.insert(0, os.path.join(root, "src"))
    from dwc.llm.client import LLMClient
    from dwc.llm.task_exec import execute_user_task
    ctx = None
    if _HISTORY:
        last = _HISTORY[-1]
        ctx = "上轮对话摘要: 任务=%s; 答案要点=%s" % (
            last["task"][:120], str(last.get("answer", ""))[:400])
    _ICON = {"read": "⌕", "write": "✎", "run": "▶", "final": "✓",
             "delegate": "⇄", "mcp": "⚙", "ask": "?"}

    astream = _AnswerStream()                 # ★ R237 answer 流状态机（可测真码）

    def _prog(ev):
        kind = ev.get("ev")
        if kind == "token":
            astream.feed(ev.get("t", ""))
            return
        if kind == "round":
            if astream.streamed:
                sys.stdout.write("\n")
            print("  %s %s" % (dim("│"),
                               dim2("轮 %d · 思考中…" % ev.get("n", 0))))
            return
        if kind == "action":
            if astream.streamed:
                sys.stdout.write("\n")
            astream.reset()
            mark = green("✓") if ev.get("ok") else red("✗")
            icon = _ICON.get(ev.get("op"), "·")
            tgt = dim(str(ev.get("target", ""))[:64])
            # ★ Claude Code 行型: ⎿ 支线引导 + 右置结果符（层级靠符号）
            print("  %s %s %s %s" % (dim("⎿"), cyan(icon), tgt, mark))
    print(dim("▸ 执行中（同步直驱 — 过程实时; /bg 切异步投单）"))
    t0 = _time.time()
    rep = execute_user_task(task, llm=LLMClient(), ctx=ctx, progress=_prog)
    secs = round(_time.time() - t0, 1)
    status = rep.get("status", "?")
    streamed = astream.streamed
    if streamed:
        print()                                  # 流式已逐字打 — 只补结尾换行
    elif rep.get("answer"):
        print(_md(rep["answer"]))
    if rep.get("why") and status != "done":
        print(dim("  " + str(rep.get("why"))[:260]))
    # ★ 完成块（R238 尾块密度）: 分隔线状态 + 次级信息右随
    tail = dim2("  ·  %d 轮 · %.1fs" % (rep.get("rounds", 0), secs))
    if status == "done":
        print(green("\n  ── ✓ 完成") + tail)
    else:
        print(red("\n  ── ✗ %s" % status) + tail)
    _HISTORY.append({"task": task, "answer": rep.get("answer", ""),
                     "status": status})
    if len(_HISTORY) > 8:
        _HISTORY = _HISTORY[-8:]


def handle(line: str) -> bool:
    """处理一行; 返回 False = 退出。"""
    line = line.strip()
    if not line:
        return True
    if line == "/bg":
        globals()["BG_MODE"] = True
        print(yellow("已切异步投单模式（常驻 agent 消费; /fg 切回同步）"))
        return True
    if line == "/fg":
        globals()["BG_MODE"] = False
        print(green("已切同步直驱模式（对话感 — 输入即执行）"))
        return True
    if line.split()[0] in ("/update", "/u"):      # ★ R248 自更新
        from dwc.foundation.updater import check, update
        if "--check" in line or "-c" in line:
            st = check()
            if not st.get("ok"):
                print(red("✗ 检查失败: %s" % st.get("why")))
            elif st.get("update_available"):
                print(yellow("⬆ 可更新: 落后 %d 个提交 (本地 %s → 远端 %s)"
                             % (st["behind"], st["local"][:9],
                                st["remote"][:9])))
            else:
                print(green("✓ 已是最新 (%s)" % st.get("local", "")[:9]))
        else:
            rep2 = update()
            if rep2.get("changed"):
                ag = rep2.get("agent", {})
                print(green("✓ 已更新 %s → %s (%d 个提交) · %s"
                            % (rep2["from"], rep2["to"], rep2["commits"],
                               "agent 已重启(pid=%s)" % ag.get("pid")
                               if ag.get("ok") else "agent: " + ag.get("why", "?"))))
                if rep2.get("deps_changed"):
                    print(yellow("⚠ 依赖变更: %s" % rep2["deps_hint"]))
            else:
                print("— 未更新: %s" % rep2.get("why", "?"))
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
            "/approve": lambda: _answer(arg, True),
            "/deny": lambda: _answer(arg, False),
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
    # ★ R236: 默认同步直驱（Claude Code 式: 输入即执行, 过程实时可见）;
    #   /bg 切回异步投单模式（常驻 agent 消费 — 两种形态都在）
    if not BG_MODE:
        _run_sync(line)
        return True
    r = call("submit", task=line)
    tid = (r or {}).get("id")
    if not tid:
        print(red("投单失败: %s" % _fmt(r)))
        return True
    print("%s 已投单 %s — 跟踪中（/watch %s 随时重看）"
          % (green("→"), bold(tid), tid))
    watch(tid)
    return True


def _answer(word, approve):
    """★ R225 · 审批答复（/approve git push → RPC ask_answer 落答复文件）。"""
    if not word:
        print(red("用法: /approve <操作词> 或 /deny <操作词>"))
        return
    r = call("ask_answer", word=word, approve=approve)
    print(_fmt(r))


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


def banner() -> None:
    """★ 启动画面（R238: 块字主标 + 语义色状态点 — 对齐头部 agent splash）。"""
    print()
    for ln in _LOGO:
        print("  " + (cyan(ln) if _ANSI else ln))
    print()
    print("  " + bold("DIVINE WISDOM CORE")
          + dim2("   独立常驻 agent · 自我强化 · v0.1.0"))
    print("  " + status_bar())


def _force_utf8_console() -> None:
    """★ R238b: 启动即切终端到 UTF-8（直接 python dwc_chat.py 不经 launcher
    也保中文不乱 — chcp 幂等, 失败静默为好过崩）。"""
    if os.name == "nt":
        try:
            subprocess.call(["chcp", "65001"], stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL, timeout=5)
        except Exception:                      # noqa: BLE001 — 自愈尽力而为
            pass


def repl() -> int:
    banner()
    print(dim("输入 /help 看命令 · 直接说话=执行 · /quit 退出"))
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
    # ★ R237 乱码修: 控制台统一 UTF-8 输出（936 码页下图标/ANSI 必乱 — 用户实测）
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    _force_utf8_console()
    if len(argv) > 1 and argv[1] in ("-c", "--cmd"):
        line = " ".join(argv[2:])
        if not line.startswith("/"):
            banner()
        return 0 if handle(line) else 0
    if len(argv) > 1:                        # 自然语言单发参数
        banner()
        return 0 if handle(" ".join(argv[1:])) else 0
    return repl()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
