# -*- coding: utf-8 -*-
"""R239 · DWC 全屏 TUI（textual — 参考 MiMoCode/OpenTUI 形态）。

★★★ 定位（G1）: **DWC-AUTO 用户界面层** — 只渲染与派单, 不做判定;
  执行核仍是 task_exec.execute_user_task（progress 事件直喂面板, 核零改动）。

★ R240 设计语言 · "Deep Space Terminal"（DESIGN 纪律: 一个主色 + 一个点缀,
  层级靠留白与细线不靠框, 品牌要有记忆点）:
  · 主色 teal 青 #7EE0E6（线条/标题/图标） · 点缀 amber 橙 #FFB86B（❯/焦点/切模式）
  · 深空底 #0B0F14 → surface #11161D → panel #161D26（三级灰阶纵深）
  · 面板**去框** — 只留 1px 细竖线分隔（避免"两个方框"平庸病）
  · 顶栏品牌条 ◆ DWC ┊ 模式 ┊ 心跳 ┊ 时钟 · 首屏块字记忆点 · 动作行带时间戳

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
    from textual.widgets import Footer, Input, RichLog, Static
    from textual.binding import Binding
    from textual.theme import Theme
    _TUI_OK = True
    _TUI_ERR = ""
except Exception as _e:                        # noqa: BLE001 — 降级必留痕
    _TUI_OK = False
    _TUI_ERR = "%s: %s" % (type(_e).__name__, _e)

_ROOT = (os.environ.get("DWC_ROOT", "").strip()
         or os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, os.path.join(_ROOT, "src"))

_ICON = {"read": "⌕", "write": "✎", "run": "▶", "final": "✓",
         "delegate": "⇄", "mcp": "⚙", "ask": "?"}

#: ★ 首屏品牌记忆点（纯 ASCII — 任何码页零错位）
_MARK = ["   ####   #   #    ####",
         "   #  #   # # #    #  #",
         "   ####   #   #    ####"]


class DwcApp(App):
    """★ 全屏 TUI: 品牌顶栏 | 对话区 ╎ 动作区 | 底线输入。"""

    CSS = """
    /* ── R240 · Deep Space Terminal ───────────────────────── */
    Screen { background: $background; }
    #topbar {
        dock: top; height: 1;
        background: $panel;
        color: $primary;
        text-style: bold;
        padding: 0 1;
    }
    #body { height: 1fr; }
    #chat-pane { width: 3fr; background: $background; padding: 0 1; }
    #tool-pane {
        width: 2fr;
        background: $background;
        border-left: solid $panel;        /* 细竖线分隔 — 不用方框 */
        padding: 0 1;
    }
    #empty-hint {
        color: $text-muted;
        padding: 0 0 1 1;
    }
    .pane-title {
        color: $primary; text-style: bold;
        background: $panel; padding: 0 1;
    }
    #chat, #tools {
        background: $background;
        height: 1fr;
        scrollbar-color: $panel;
    }
    #inputbar {
        dock: bottom; height: 3;
        background: $surface;
        border-top: solid $primary;      /* 主色分隔线 — 输入区一眼可见 */
        padding: 0 1;
    }
    #prompt-label {
        width: 3;
        content-align: left middle;
        color: $accent;               /* amber 焦点 — 输入的视觉锚 */
        text-style: bold;
    }
    #ask {
        width: 1fr;
        background: $surface;
        border: none;
        border-bottom: tall $primary; /* 底线式 — 去框留呼吸 */
        height: 2;
    }
    #ask:focus { border-bottom: tall $accent; }
    #hint { color: $text-muted; width: 34; content-align: right middle; }
    Footer { background: $surface; color: $text-muted; }
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
        yield Static(self._topbar_text(), id="topbar")
        with Horizontal(id="body"):
            with Vertical(id="chat-pane"):
                yield Static("  ─ 对话 ", classes="pane-title")
                yield RichLog(id="chat", wrap=True, highlight=False, markup=True)
                yield Static("   [dim]输入任务开始对话 · 答案将在这里逐字流出[/]",
                             id="empty-hint")
            with Vertical(id="tool-pane"):
                yield Static("  ─ 动作 ─ 实时 ", classes="pane-title")
                yield RichLog(id="tools", wrap=True, markup=True)
        with Horizontal(id="inputbar"):
            yield Static("❯", id="prompt-label")
            yield Input(placeholder="输入任务，回车执行…", id="ask")
            yield Static("/help  ·  /bg 后台", id="hint")
        yield Footer()

    # ── 生命周期 ──────────────────────────────────────

    def on_mount(self) -> None:
        try:
            self.register_theme(Theme(
                name="dwc-deep-space",
                primary="#7EE0E6",       # 主色: teal 青
                secondary="#4A6670",
                accent="#FFB86B",        # 点缀: amber 橙
                success="#5AF78E",
                error="#FF5F56",
                warning="#F3D99D",
                background="#0B0F14",    # 深空底
                surface="#11161D",
                panel="#161D26",
                foreground="#C9D1D9",
                dark=True))
            self.theme = "dwc-deep-space"
        except Exception:                       # noqa: BLE001 — 主题失败用默认
            pass
        chat = self.query_one("#chat", RichLog)
        for ln in _MARK:
            chat.write("[bold #7EE0E6]%s[/]" % ln)
        chat.write("[bold]DIVINE WISDOM CORE[/]  "
                   "[dim]· 独立常驻 agent · v0.1.0[/]")
        chat.write("[dim]输入任务回车即执行 · /help 全部命令[/]")
        chat.write("")
        self._refresh_status()
        self.set_interval(15.0, self._refresh_status)

    def _topbar_text(self) -> str:
        mode = "[#FFB86B]bg 投单[/]" if self._bg_mode else "[#7EE0E6]同步[/]"
        clock = _time.strftime("%H:%M")
        return ("  [bold #FFB86B]◆[/] [bold]D W C[/]   "
                "[on #1E2733] %s [/]  [on #1E2733] %s [/]  [dim]ctrl+c[/]"
                % (mode, clock))

    def _set_topbar(self) -> None:
        self.query_one("#topbar", Static).update(self._topbar_text())

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
        mark = ("[#5AF78E]●[/] agent alive" if s.get("pid")
                else "[#FF5F56]●[/] agent down")
        mode = "[#FFB86B]bg 投单[/]" if self._bg_mode else "[#7EE0E6]同步[/]"
        clock = _time.strftime("%H:%M")
        self.query_one("#topbar", Static).update(
            "  [bold #FFB86B]◆[/] [bold]D W C[/]   "
            "[on #1E2733] %s [/]  [on #1E2733] %s·%s·%s/%s [/]  "
            "[on #1E2733] %s [/]  [dim]ctrl+c[/]"
            % (mark, mode, hb.get("terms", "─"),
               q.get("pending", 0), q.get("done", 0), clock))

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
            self._set_topbar()
            chat.write("[#FFB86B]✦ 已切后台投单模式[/] "
                       "[dim]（常驻 agent 消费）[/]")
            return
        if line == "/fg":
            self._bg_mode = False
            self._set_topbar()
            chat.write("[#7EE0E6]✦ 已切同步直驱模式[/]")
            return
        if line == "/help":
            chat.write("[dim]/bg /fg 模式 · /status 刷新 · /quit 退出 · "
                       "直接输入任务=同步执行[/]")
            return
        if line == "/status":
            self._refresh_status()
            return
        chat.write("")
        chat.write("[bold #FFB86B]❯[/] [bold]%s[/]" % line)
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
                _post("[dim]%s │  轮 %d · 思考中…[/]"
                      % (_time.strftime("%H:%M:%S"), ev.get("n", 0)), True)
            elif kind == "action":
                mark = ("[#5AF78E]✓[/]" if ev.get("ok")
                        else "[#FF5F56]✗[/]")
                _post("[dim]%s[/] [bold #7EE0E6]%-2s[/] %-5s %s %s"
                      % (_time.strftime("%H:%M:%S"),
                         _ICON.get(ev.get("op"), "·"), ev.get("op", ""),
                         str(ev.get("target", ""))[:50], mark), True)

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
                _post("[bold #5AF78E]── ✓ 完成[/]"
                      "[dim]  · %d 轮 · %.1fs[/]"
                      % (rep.get("rounds", 0), secs))
            else:
                _post("[bold #FF5F56]── ✗ %s[/]"
                      "[dim]  · %d 轮 · %.1fs · %s[/]"
                      % (rep.get("status"), rep.get("rounds", 0), secs,
                         str(rep.get("why", ""))[:140]))
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
    # ★ R241 抖动修: textual Windows 驱动开 1003h(任何鼠标事件都上报) ⇒
    #   点击/移动全进程序触发重绘风暴(用户实测整屏抖)。本 TUI 键盘导向 ⇒
    #   默认关鼠标(终端原生行为不再进程序); 想开: DWC_TUI_MOUSE=1。
    app.run(mouse=(os.environ.get("DWC_TUI_MOUSE", "").strip() == "1"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
