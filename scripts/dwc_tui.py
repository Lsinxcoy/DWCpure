# -*- coding: utf-8 -*-
"""R239 · DWC 全屏 TUI（textual — Python 版组件化界面, 参考 MiMoCode/OpenTUI 形态）。

★★★ 定位（G1）: **DWC-AUTO 用户界面层** — 只渲染与派单, 不做判定;
  执行核仍是 task_exec.execute_user_task（progress 事件直喂面板, 核零改动）。

★ 形态（对齐头部 agent 全屏 TUI）:
  · 左面板=对话区（问/答/流式答案）  · 右面板=工具动作日志（round/action/token 摘要）
  · 顶部=状态栏（agent 心跳/队列）   · 底部=输入行 + 快捷提示
  · 斜杠命令与 chat REPL 同一套（/status /help /bg /quit）

★ 降级纪律: textual 不可用/终端不支持 ⇒ 如实报错回退 dwc_chat（不硬撑）。
"""
from __future__ import annotations

import os
import sys
import threading
import time as _time

try:
    from textual.app import App, ComposeResult
    from textual.containers import Horizontal, Vertical
    from textual.widgets import Footer, Header, Input, RichLog, Static
    from textual.binding import Binding
    _TUI_OK = True
    _TUI_ERR = ""
except Exception as _e:                        # noqa: BLE001 — 降级必留痕
    _TUI_OK = False
    _TUI_ERR = "%s: %s" % (type(_e).__name__, _e)

_ROOT = (os.environ.get("DWC_ROOT", "").strip()
         or os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, os.path.join(_ROOT, "src"))

_BUSY = "●"
_ICON = {"read": "⌕", "write": "✎", "run": "▶", "final": "✓",
         "delegate": "⇄", "mcp": "⚙", "ask": "?"}


class DwcApp(App):
    """★ 全屏 TUI: 对话区 | 动作区 | 输入 | 状态栏。"""

    CSS = """
    #body { height: 1fr; }
    #chat-pane { width: 2fr; border: solid $accent; }
    #tool-pane { width: 1fr; border: solid $panel; }
    #status { height: 1; background: $panel; color: $text-muted; padding: 0 1; }
    Input { dock: bottom; }
    """
    BINDINGS = [
        Binding("ctrl+c", "quit", "退出"),
        Binding("ctrl+d", "quit", "退出"),
    ]

    def __init__(self):
        super().__init__()
        self._hist = []                 # 多轮上下文（chat 同款）
        self._busy = False
        self._bg_mode = False

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static("  探测 agent…", id="status")
        with Horizontal(id="body"):
            with Vertical(id="chat-pane"):
                yield RichLog(id="chat", wrap=True, highlight=True)
            with Vertical(id="tool-pane"):
                yield RichLog(id="tools", wrap=True)
        yield Input(placeholder="说点什么执行 · /help 命令 · /bg 切后台投单",
                    id="ask")
        yield Footer()

    # ── 生命周期 ──────────────────────────────────────

    def on_mount(self) -> None:
        chat = self.query_one("#chat", RichLog)
        chat.write("[bold cyan]  D W C  [/] [dim]· 全屏 TUI · "
                   "左=对话 右=动作 · 输入任务回车即执行[/]")
        self._refresh_status()
        self.set_interval(15.0, self._refresh_status)

    def _refresh_status(self) -> None:
        # ★ 走线程 + call_from_thread（thread-safe 回 UI — 不依赖 worker 协议）
        def _work():
            try:
                from dwc import agent_rpc as R
                s = R.cmd_status() or {}
            except Exception:                       # noqa: BLE001
                s = {}
            try:
                self.call_from_thread(self._apply_status, s)
            except Exception:                       # noqa: BLE001 — 刷新失败不炸
                pass
        threading.Thread(target=_work, daemon=True).start()

    def _apply_status(self, s: dict) -> None:
        q = s.get("queue") or {}
        hb = s.get("heartbeat") or {}
        mark = ("[bold green]● alive[/]" if s.get("pid")
                else "[bold red]● down[/]")
        mode = "[yellow]bg投单[/]" if self._bg_mode else "[cyan]同步直驱[/]"
        self.query_one("#status", Static).update(
            " %s · pid=%s · terms=%s · queue p=%s d=%s · 模式=%s"
            % (mark, s.get("pid"), hb.get("terms", "-"),
               q.get("pending", 0), q.get("done", 0), mode))

    # ── 输入处理 ──────────────────────────────────────

    def on_input_submitted(self, ev: Input.Submitted) -> None:
        line = (ev.value or "").strip()
        ev.input.value = ""
        if not line:
            return
        chat = self.query_one("#chat", RichLog)
        if line in ("/quit", "/exit", "/q"):
            self.exit()
            return
        if line == "/bg":
            self._bg_mode = True
            chat.write("[yellow]已切后台投单模式（常驻 agent 消费）[/]")
            return
        if line == "/fg":
            self._bg_mode = False
            chat.write("[cyan]已切同步直驱模式[/]")
            return
        if line == "/help":
            chat.write("[dim]/bg /fg 模式切换 · /status 刷新 · /quit 退出 · "
                       "直接输入任务=同步执行 · /bg 后=投单[/]")
            return
        if line == "/status":
            self._refresh_status()
            return
        chat.write("[bold]❯ %s[/]" % line)
        if self._bg_mode:
            self._submit_bg(line)
        else:
            self._run_sync(line)

    # ── 同步执行（线程 + call_from_thread 回 UI） ──────

    def _run_sync(self, task: str) -> None:
        if self._busy:
            self.query_one("#chat", RichLog).write(
                "[yellow]上一个任务还在跑 — 等它完成[/]")
            return
        self._busy = True
        ctx = None
        if self._hist:
            last = self._hist[-1]
            ctx = "上轮对话摘要: 任务=%s; 答案要点=%s" % (
                last["task"][:120], str(last.get("answer", ""))[:400])

        def _post(msg: str, tool: bool = False) -> None:
            try:
                self.call_from_thread(
                    self.query_one("#tools" if tool else "#chat", RichLog).write,
                    msg)
            except Exception:                       # noqa: BLE001
                pass

        def _progress(ev: dict) -> None:
            kind = ev.get("ev")
            if kind == "round":
                _post("[dim]│ 轮 %d · 思考中…[/]" % ev.get("n", 0), True)
            elif kind == "action":
                mark = "[green]✓[/]" if ev.get("ok") else "[red]✗[/]"
                _post("%s [cyan]%s[/] %s %s"
                      % (_ICON.get(ev.get("op"), "·"), ev.get("op", ""),
                         str(ev.get("target", ""))[:60], mark), True)
            elif kind == "token":
                self._buf = getattr(self, "_buf", "") + ev.get("t", "")

        def _work():
            from dwc.llm.client import LLMClient
            from dwc.llm.task_exec import execute_user_task
            self._buf = ""
            t0 = _time.time()
            rep = execute_user_task(task, llm=LLMClient(), ctx=ctx,
                                    progress=_progress)
            secs = round(_time.time() - t0, 1)
            ans = str(rep.get("answer", ""))
            if rep.get("status") == "done":
                _post("[bold green]── ✓ 完成[/][dim]  · %d 轮 · %.1fs[/]"
                      % (rep.get("rounds", 0), secs))
            else:
                _post("[bold red]── ✗ %s[/][dim]  · %d 轮 · %.1fs[/]  %s"
                      % (rep.get("status"), rep.get("rounds", 0), secs,
                         str(rep.get("why", ""))[:160]))
            if ans:
                for ln in ans.splitlines() or [""]:
                    _post(ln)
            self._hist.append({"task": task, "answer": ans,
                               "status": rep.get("status")})
            del self._hist[:-8]
            self._busy = False

        threading.Thread(target=_work, daemon=True).start()

    def _submit_bg(self, task: str) -> None:
        def _work():
            try:
                from dwc import agent_rpc as R
                r = R.cmd_submit(task) or {}
                self.call_from_thread(
                    self.query_one("#chat", RichLog).write,
                    "[green]→ 已投单 %s[/]" % r.get("id", "?"))
            except Exception as e:                  # noqa: BLE001 — 如实报
                self.call_from_thread(
                    self.query_one("#chat", RichLog).write,
                    "[red]投单失败: %s[/]" % e)
        threading.Thread(target=_work, daemon=True).start()


def main(argv=None) -> int:
    if not _TUI_OK:
        sys.stderr.write(
            "textual 不可用（%s）— 回退 chat REPL。若在老控制台: "
            "请用 Windows Terminal 运行（textual 需要现代终端渲染）。\n"
            % _TUI_ERR)
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import dwc_chat
        return dwc_chat.main(["dwc_chat"] + list(argv or []))
    app = DwcApp()
    app.run()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
