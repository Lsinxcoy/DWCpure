# -*- coding: utf-8 -*-
"""R239 · DWC 全屏 TUI（textual — 参考 MiMoCode/OpenTUI 形态）。

★★★ 定位（G1）: **DWC-AUTO 用户界面层** — 只渲染与派单, 不做判定;
  执行核仍是 task_exec.execute_user_task（progress 事件直喂面板, 核零改动）。

★ R240 设计语言 · "Deep Space Terminal"（DESIGN 纪律: 一个主色 + 一个点缀,
  层级靠留白与细线不靠框, 品牌要有记忆点）:
  · 字色纯白 #ECEDEE（R242c: 不要蓝字） · 点缀 amber 橙 #FFB86B（❯/焦点/色块字标）
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
    from textual.containers import Horizontal, Vertical, VerticalScroll
    from textual.widgets import Footer, Input, Markdown, RichLog, Static
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
    /* ── R242 · 消息组件系统（告别日志流 — 每条消息一个 widget） ── */
    #chat-pane { width: 3fr; background: $background; padding: 0 1; }
    #msgs {
        background: $background;
        height: 1fr;
        scrollbar-color: $panel;
        padding: 0 1;
    }
    .msg-user {
        background: $surface;
        border-left: tall $accent;
        padding: 0 1;
        margin: 1 0;
        text-style: bold;
    }
    .msg-ans {
        background: $background;
        padding: 0 1;
        margin: 0 0 1 0;
    }
    .msg-sys {
        color: $text-muted;
        padding: 0 1;
        margin: 0 0 1 0;
    }
    .msg-stream {
        background: $background;
        padding: 0 1;
        margin: 0 0 1 0;
    }
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
    #suggest {
        height: auto; max-height: 9;
        background: $panel;
        border-top: solid $accent;
        padding: 0 1;
    }
    #inputrow {
        height: 3;
        background: $surface;
        padding: 0 1;
    }
    #inputbar { dock: bottom; height: auto; background: $surface;
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
                with VerticalScroll(id="msgs"):
                    yield Static("   [dim]输入任务开始对话 · "
                                 "答案将在这里渲染[/]", id="empty-hint")
            with Vertical(id="tool-pane"):
                yield Static("  ─ 动作 ─ 实时 ", classes="pane-title")
                yield RichLog(id="tools", wrap=True, markup=True)
        with Vertical(id="inputbar"):
            yield Static("", id="suggest")     # ★ R243 补全浮层(输入行上方)
            with Horizontal(id="inputrow"):
                yield Static("❯", id="prompt-label")
                yield Input(placeholder="输入任务，回车执行…"
                             "  / 命令 · @ 文件 · ↑ 历史", id="ask")
                yield Static("/help · /bg", id="hint")
        yield Footer()

    # ── 生命周期 ──────────────────────────────────────

    def on_mount(self) -> None:
        try:
            self.register_theme(Theme(
                name="dwc-deep-space",
                primary="#ECEDEE",       # 主体字色: 纯白(R242c 用户: 字用白不要蓝)
                secondary="#8A8E94",   # 中性次级灰(原蓝绿灰)
                accent="#FFB86B",        # 点缀: amber 橙
                success="#5AF78E",
                error="#FF5F56",
                warning="#F3D99D",
                background="#0B0F14",    # 深空底
                surface="#11161D",
                panel="#24282E",      # 中性深灰(蓝灰被看成蓝线)
                foreground="#ECEDEE",  # 纯白主文字
                dark=True,
                variables={"text-muted": "#9B9B9B"}))
            self.theme = "dwc-deep-space"
        except Exception:                       # noqa: BLE001 — 主题失败用默认
            pass
        msgs = self.query_one("#msgs", VerticalScroll)
        try:
            self.query_one("#empty-hint").remove()
        except Exception:                       # noqa: BLE001 — 已移除不炸
            pass
        head = ("[bold black on #FFB86B] D W C [/]  "
                "[bold]DIVINE WISDOM CORE[/]  "
                "[dim]· 独立常驻 agent · v0.1.0[/]\n"
                "[dim]输入任务回车即执行 · /help 全部命令[/]")
        msgs.mount(Static(head, classes="msg-sys"))
        self._refresh_status()
        self.set_interval(15.0, self._refresh_status)
        # ★ R243: @ 文件候选缓存（glob 一次）+ 输入历史 + 补全状态
        self._files = _scan_repo_files()
        self._in_hist = []
        self._sug = []              # [(展示, 填充值)]
        self._sug_idx = -1
        self.query_one("#ask", Input).focus()   # ★ 启动即可输入(免 Tab)

    # ── R243 · 输入升级（/ 命令补全 · @ 文件补全 · ↑ 历史） ──────

    def _suggest_show(self, items) -> None:
        """★ 候选浮层: [(展示, 填充值)]; 空列表=隐藏。"""
        w = self.query_one("#suggest", Static)
        self._sug = items
        self._sug_idx = 0
        if not items:
            w.update("")
            w.display = False
            return
        rows = []
        for i, (label, _fill) in enumerate(items):
            mark = "▸ " if i == 0 else "  "
            # ★ tag 先闭合再放文字(曾拼进 tag → 样式码泄露实测);
            #   非选中行无开 tag ⇒ 不写闭合(曾致 MarkupError)
            if i == 0:
                rows.append("[#FFB86B bold]%s%s[/]" % (mark, label))
            else:
                rows.append("%s%s" % (mark, label))
        w.update("\n".join(rows))
        w.display = True

    def _suggest_apply(self) -> None:
        """★ Tab/Enter: 选中项填入输入框（候选关闭 — 再回车执行）。"""
        if not self._sug or self._sug_idx < 0:
            return
        _label, fill = self._sug[self._sug_idx]
        inp = self.query_one("#ask", Input)
        self._sug_applied = fill      # ★ 吞掉 setter 触发的同值 Changed(防重开)
        inp.value = fill
        inp.cursor = len(fill)
        self._suggest_show([])

    def on_input_changed(self, ev) -> None:
        """★ 输入变化驱动候选: / 开头=命令; @ 开头=文件。"""
        text = ev.value or ""
        if text == getattr(self, "_sug_applied", ""):
            self._sug_applied = None  # ★ 应用候选引发的 Changed — 不重开浮层
            return
        if text.startswith("/") and " " not in text:
            q = text[1:].lower()
            items = [(c + "  [dim]" + d + "[/]", c)
                     for c, d in _CMDS if c[1:].startswith(q)]
            self._suggest_show(items)
        elif text.startswith("@") and " " not in text:
            q = text[1:].lower()
            hits = [f for f in self._files
                    if q and (q in f.lower() or f.lower().startswith(q))]
            self._suggest_show([(f, "@" + f) for f in hits[:8]])
        else:
            self._suggest_show([])

    def on_key(self, ev) -> None:
        """★ 候选导航(↓↑) + Tab/Enter 补全 + Esc 关 + ↑ 历史(无候选时)。
        焦点始终在输入框（不跳焦 — 避免布局抖动）。"""
        k = ev.key
        if self._sug:
            if k in ("down",):
                self._sug_idx = (self._sug_idx + 1) % max(len(self._sug), 1)
                self.on_input_changed(
                    type("E", (), {"value": self.query_one("#ask", Input).value})())
                ev.stop(); ev.prevent_default(); return
            if k in ("up",):
                self._sug_idx = (self._sug_idx - 1) % max(len(self._sug), 1)
                self.on_input_changed(
                    type("E", (), {"value": self.query_one("#ask", Input).value})())
                ev.stop(); ev.prevent_default(); return
            if k in ("tab", "enter"):
                self._suggest_apply()
                ev.stop(); ev.prevent_default(); return
            if k == "escape":
                self._suggest_show([])
                ev.stop(); ev.prevent_default(); return
        # 无候选: ↑↓ = 输入历史（光标行导航默认行为已被单行 Input 废）
        if k == "up" and self._in_hist:
            hist = list(reversed(self._in_hist))
            cur = self.query_one("#ask", Input).value
            try:
                idx = hist.index(cur) + 1
            except ValueError:
                idx = 0
            if idx < len(hist):
                inp = self.query_one("#ask", Input)
                inp.value = hist[idx]
                inp.cursor = len(hist[idx])
            ev.stop(); ev.prevent_default(); return
        if k == "down" and self._in_hist:
            hist = list(reversed(self._in_hist))
            cur = self.query_one("#ask", Input).value
            try:
                idx = hist.index(cur) - 1
                inp = self.query_one("#ask", Input)
                inp.value = hist[idx] if idx >= 0 else ""
                inp.cursor = len(inp.value)
            except ValueError:
                pass
            ev.stop(); ev.prevent_default(); return

    # ── R242 · 消息卡 API（mount widget 而非日志行） ──────────

    def _msgs(self) -> VerticalScroll:
        return self.query_one("#msgs", VerticalScroll)

    def _say_user(self, text: str) -> None:
        """★ 用户消息卡: accent 左条 + surface 底 + 粗体。"""
        self._msgs().mount(Static("❯ " + text, classes="msg-user"))
        self._msgs().scroll_end(force=True)

    def _say_sys(self, text: str) -> None:
        self._msgs().mount(Static(text, classes="msg-sys"))
        self._msgs().scroll_end(force=True)

    def _say_ans(self, markdown: str) -> None:
        """★ 助手答案: Markdown 组件渲染（标题/代码块/列表 — 质变点）。"""
        self._msgs().mount(Markdown(markdown, classes="msg-ans"))
        self._msgs().scroll_end(force=True)

    def _stream_open(self) -> Static:
        """★ 流式临时区: 逐字打; 完成后 remove 并换 Markdown 卡。"""
        w = Static("", classes="msg-stream", id="streaming")
        self._msgs().mount(w)
        self._msgs().scroll_end(force=True)
        return w

    def _stream_close(self) -> None:
        try:
            self.query_one("#streaming").remove()
        except Exception:                       # noqa: BLE001
            pass

    def _topbar_text(self) -> str:
        mode = "[#FFB86B]bg 投单[/]" if self._bg_mode else "同步"
        clock = _time.strftime("%H:%M")
        return ("  ◆ [bold black on #FFB86B] D W C [/]  "
                "[on #2A2A2C] %s [/]  [on #2A2A2C] %s [/]  [dim]ctrl+c[/]"
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
        mode = "[#FFB86B]bg 投单[/]" if self._bg_mode else "同步"
        clock = _time.strftime("%H:%M")
        self.query_one("#topbar", Static).update(
            "  ◆ [bold black on #FFB86B] D W C [/]  "
            "[on #2A2A2C] %s [/]  [on #2A2A2C] %s·%s·%s/%s [/]  "
            "[on #2A2A2C] %s [/]  [dim]ctrl+c[/]"
            % (mark, mode, hb.get("terms", "─"),
               q.get("pending", 0), q.get("done", 0), clock))

    # ── 输入处理 ──────────────────────────────────────

    def on_input_submitted(self, ev: Input.Submitted) -> None:
        line = (ev.value or "").strip()
        ev.input.value = ""
        if not line:
            return
        if line in ("/quit", "/exit", "/q"):
            self.exit()
            return
        if line == "/bg":
            self._bg_mode = True
            self._set_topbar()
            self._say_sys("✦ 已切后台投单模式（常驻 agent 消费）")
            return
        if line == "/fg":
            self._bg_mode = False
            self._set_topbar()
            self._say_sys("✦ 已切同步直驱模式")
            return
        if line == "/help":
            self._say_sys("/bg /fg 模式 · /status 刷新 · /quit 退出 · "
                          "直接输入任务=同步执行")
            return
        if line == "/status":
            self._refresh_status()
            return
        if not line.startswith("/"):
            self._in_hist.append(line)     # ★ R243 历史(命令不入)
            if len(self._in_hist) > 200:
                self._in_hist = self._in_hist[-200:]
        self._say_user(line)
        if self._bg_mode:
            self._submit_bg(line)
        else:
            self._run_sync(line)

    # ── 同步执行（线程 + call_from_thread 回 UI） ──────

    def _run_sync(self, task: str) -> None:
        if self._busy:
            self._say_sys("⏳ 上一个任务还在跑 — 等它完成")
            return
        self._busy = True
        ctx = None
        if self._hist:
            last = self._hist[-1]
            ctx = "上轮对话摘要: 任务=%s; 答案要点=%s" % (
                last["task"][:120], str(last.get("answer", ""))[:400])

        def _post_tool(msg: str) -> None:
            try:
                self.call_from_thread(
                    self.query_one("#tools", RichLog).write, msg)
            except Exception:                       # noqa: BLE001
                pass

        def _stream_put(text: str) -> None:
            """★ 流式逐字（线程 → UI）: 累进临时卡。"""
            def _do():
                w = getattr(self, "_stream_w", None)
                if w is None or not w.is_attached:
                    self._stream_w = self._stream_open()
                    w = self._stream_w
                base = getattr(w, "_acc", "") + text
                w._acc = base
                w.update(base)
                self._msgs().scroll_end(force=True)
            try:
                self.call_from_thread(_do)
            except Exception:                       # noqa: BLE001
                pass

        def _progress(ev: dict) -> None:
            kind = ev.get("ev")
            if kind == "round":
                _post_tool("[dim]%s │  轮 %d · 思考中…[/]"
                           % (_time.strftime("%H:%M:%S"), ev.get("n", 0)))
            elif kind == "action":
                mark = ("[#5AF78E]✓[/]" if ev.get("ok")
                        else "[#FF5F56]✗[/]")
                _post_tool("[dim]%s[/] [bold]%-2s[/] %-5s %s %s"
                           % (_time.strftime("%H:%M:%S"),
                              _ICON.get(ev.get("op"), "·"), ev.get("op", ""),
                              str(ev.get("target", ""))[:50], mark))
            elif kind == "token":
                _stream_put(ev.get("t", ""))

        def _work():
            from dwc.llm.client import LLMClient
            from dwc.llm.task_exec import execute_user_task
            self._buf = ""
            t0 = _time.time()
            rep = execute_user_task(task, llm=LLMClient(), ctx=ctx,
                                    progress=_progress)
            secs = round(_time.time() - t0, 1)
            ans = str(rep.get("answer", ""))

            def _finalize():
                self._stream_close()
                self._stream_w = None
                if ans:
                    self._say_ans(ans)           # ★ 流式终态 → Markdown 卡
                if rep.get("status") == "done":
                    self._say_sys("── ✓ 完成 · %d 轮 · %.1fs"
                                  % (rep.get("rounds", 0), secs))
                else:
                    self._say_sys("── ✗ %s · %d 轮 · %.1fs · %s"
                                  % (rep.get("status"), rep.get("rounds", 0),
                                     secs, str(rep.get("why", ""))[:140]))
            try:
                self.call_from_thread(_finalize)
            except Exception:                       # noqa: BLE001
                pass
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
                self.call_from_thread(self._say_sys,
                                      "→ 已投单 %s" % r.get("id", "?"))
            except Exception as e:                  # noqa: BLE001 — 如实报
                self.call_from_thread(self._say_sys, "投单失败: %s" % e)
        threading.Thread(target=_work, daemon=True).start()


#: ★ R243: / 命令候选表（展示, 说明）
_CMDS = [("/bg", "切后台投单模式"),
         ("/fg", "切同步直驱模式"),
         ("/help", "全部命令"),
         ("/status", "刷新状态"),
         ("/quit", "退出")]


def _scan_repo_files(limit=400):
    """★ R243: @ 文件候选源（src+scripts+config+根文档 — 一次 glob）。"""
    from dwc.foundation.paths import find_root
    try:
        root = find_root()
    except Exception:                       # noqa: BLE001 — 降级空表留痕
        sys.stderr.write("dwc_tui: 找不到仓库根 — @ 文件候选为空\n")
        return []
    out = []
    for pat in ("src/dwc/**/*.py", "scripts/*.py",
                "config/*.yaml", "config/*.json", "*.md"):
        import glob as _g
        for f in _g.glob(root + "/" + pat, recursive=True):
            rel = f.replace("\\", "/").replace(root + "/", "")
            out.append(rel)
            if len(out) >= limit:
                break
        if len(out) >= limit:
            break
    return sorted(set(out))[:limit]


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
