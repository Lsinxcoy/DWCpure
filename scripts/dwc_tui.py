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
    import dwc_theme as _TH  # ★ R273-A · 主题 token（颜色只走 token）
except ImportError:  # ★ R263b fallback：无 textual/单文件运行时退回字面
    _TH = None


def _C(k: str) -> str:
    """★ 当前主题 token 值（失败→deep 回退，不炸）。"""
    try:
        return _TH.get()[k] if _TH is not None else _FALLBACK[k]
    except Exception:                            # noqa: BLE001
        return _FALLBACK[k]


_FALLBACK = {"accent": "#FFB86B", "success": "#5AF78E",
             "error": "#FF5F56", "muted": "#8A8E94",
             "surface": "#2A2A2C", "warn": "#F3D99D",
             "bg": "#0B0F14", "fg": "#ECEDEE"}


def _wrap_dim(text: str) -> str:
    """★ R273-A · done 褪色（文本包 dim）。"""
    return "[dim]%s[/]" % text

try:
    from textual.app import App, ComposeResult
    from textual.screen import ModalScreen
    from textual.containers import Horizontal, Vertical, VerticalScroll
    from textual.widgets import Footer, Input, Markdown, RichLog, Static
    from textual.binding import Binding
    from textual.theme import Theme
    _TUI_OK = True
    _TUI_ERR = ""
except Exception as _e:                        # noqa: BLE001 — 降级必留痕
    _TUI_OK = False
    _TUI_ERR = "%s: %s" % (type(_e).__name__, _e)
    # ★ 降级哨兵（全量 — class DwcApp 的**类体**也用 Binding 等裸名,
    #   只补 App 会 NameError 于类体（测试抓到）— 13 名与 try 块导入集
    #   一致, 有源锁保证不漂移）
    class _Any:                      # 吃任意参数/属性 — 类体 Binding(...) 调用
        def __init__(self, *_a, **_k):
            pass
        def __call__(self, *_a, **_k):
            return self
        def __getattr__(self, _n):
            return _Any()
        @classmethod
        def __class_getitem__(cls, _x):
            return cls
    for _n in ("App", "ComposeResult", "ModalScreen", "Horizontal", "Vertical",
               "VerticalScroll", "Footer", "Input", "Markdown", "RichLog",
               "Static", "Binding", "Theme"):
        globals()[_n] = _Any
    # ★ 降级哨兵（2026-10-14 用户实测"dwc 无法唤醒": .dwc venv 缺 textual 时
    #   import 失败 → 模块级 class DwcApp(App) 在 main() 回退**之前**就
    #   NameError 短路 — 回退设计有但永远到不了。哨兵让 class 定义过,
    #   实际回退仍由 main() 的 if not _TUI_OK 执行（App 不会实例化）。

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
    /* ── R244 · 文件树侧栏 + Ctrl+P 命令面板 ── */
    #tree-pane {
        width: 20%;
        min-width: 22;
        background: $background;
        border-right: solid $panel;
        padding: 0 1;
    }
    #tree { background: $background; height: 1fr; }
    PaletteScreen { align: center middle; background: $background 45%; }
    #palette-box {
        width: 72; max-width: 90%;
        height: auto;
        background: $surface;
        border: tall $accent;
        padding: 1;
    }
    #palette-input { border: none; border-bottom: tall $accent; background: $surface; }
    #palette-list { height: 10; margin-top: 1; }
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
    #: ★ R244: 关闭 textual 内置面板 — 其自动注入 priority=True 的
    #:   ctrl+p 绑定会抢走我们的绑定（实测开的是内置 CommandPalette）。
    ENABLE_COMMAND_PALETTE = False
    BINDINGS = [
        Binding("ctrl+c", "quit", "退出"),
        Binding("ctrl+d", "quit", "退出"),
        Binding("ctrl+p", "palette", "面板"),
        Binding("ctrl+l", "clear_chat", "清屏"),
        # ★ R264 · 滚动兜底(2026-10-14 用户: "所有框体无法滚动, 信息错过就
        #   看不到"): pgup/pgdn priority — 输入框聚焦时也抢过来滚历史区。
        Binding("pgup", "scroll_history(-1)", "上翻", priority=True),
        Binding("pgdn", "scroll_history(1)", "下翻", priority=True),
    ]

    def __init__(self):
        super().__init__()
        self._hist = []                 # 多轮上下文（chat 同款）
        self._busy = False
        self._bg_mode = False

    def compose(self) -> ComposeResult:
        yield Static(self._topbar_text(), id="topbar")
        with Horizontal(id="body"):
            with Vertical(id="tree-pane"):
                yield Static("  ─ 工作区 ", classes="pane-title")
                yield Static("", id="tree")
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
            for _tn in ("deep", "warm"):  # ★ R273-C · 双主题注册（token 驱动）
                _t = _TH.get(_tn)
                self.register_theme(Theme(
                    name="dwc-%s" % _tn,
                    primary=_t["fg"],        # 主体字色
                    secondary=_t["muted"],   # 中性次级灰
                    accent=_t["accent"],      # 点缀
                    success=_t["success"],
                    error=_t["error"],
                    warning=_t["warn"],
                    background=_t["bg"],
                    surface=_t["surface"],
                    panel=_t["surface"],
                    foreground=_t["fg"],
                    dark=True,
                    variables={"text-muted": _t["muted"]}))
            self.theme = "dwc-%s" % _TH.current_name()
        except Exception:                       # noqa: BLE001 — 主题失败用默认
            pass
        msgs = self.query_one("#msgs", VerticalScroll)
        try:
            self.query_one("#empty-hint").remove()
        except Exception:                       # noqa: BLE001 — 已移除不炸
            pass
        head = ("[bold black on " + _C("accent") + "] D W C [/]  "
                "[bold]DIVINE WISDOM CORE[/]  "
                "[dim]· 独立常驻 agent · v0.1.0[/]\n"
                "[dim]输入任务回车即执行 · /help 全部命令[/]")
        msgs.mount(Static(head, classes="msg-sys"))
        self._refresh_status()
        self.set_interval(15.0, self._refresh_status)
        # ★ R243: @ 文件候选缓存（glob 一次）+ 输入历史 + 补全状态
        self._files = _scan_repo_files()
        self._in_hist = _hist_load()      # ★ R272-③ · 历史落盘恢复
        self._sug = []              # [(展示, 填充值)]
        self._sug_idx = -1
        self.query_one("#ask", Input).focus()   # ★ 启动即可输入(免 Tab)
        self._render_tree()
        # ★ R245: 思考 spinner（120ms 轮转 — 忙时输入区右侧动效）
        self._spin_i = 0
        self._spin_t = self.set_interval(0.12, self._spin_tick)
        # ★ R264 · 鼠标滚动可用化: textual windows_driver 无差别写
        #   1000h+1003h+1015h — 1003h(ANY_EVENT 移动全上报)正是 R241 整屏
        #   抖动的根因 ⇒ 开滚轮必须**补关** 1003h: 1000h 留下按钮+滚轮,
        #   移动不再进程序 ⇒ 滚轮能滚且无重绘风暴。
        try:
            sys.stdout.write("\x1b[?1003l")
            sys.stdout.flush()
        except Exception as exc:              # noqa: BLE001 — 补丁失败留痕
            sys.stderr.write("关1003h失败: %s\n" % exc)

    # ── R248 · 自更新（GitHub 为源） ────────────────────────────

    def _update_flow(self, check_only: bool) -> None:
        """线程 fetch/pull — 完成回 UI 显示（不冻界面）。"""
        import threading

        def _work():
            from dwc.foundation import updater
            rep2 = updater.check() if check_only else updater.update()

            def _show():
                if check_only:
                    if not rep2.get("ok"):
                        self._say_sys("✗ 更新检查失败: %s" % rep2.get("why"))
                    elif rep2.get("update_available"):
                        self._say_sys("⬆ 可更新: 落后 %d 个提交 "
                                      "(本地 %s → 远端 %s) — 敲 /update 执行"
                                      % (rep2["behind"], rep2["local"][:9],
                                         rep2["remote"][:9]))
                    else:
                        self._say_sys("✓ 已是最新 (%s)"
                                      % rep2.get("local", "")[:9])
                elif rep2.get("changed"):
                    msg = ("✓ 已更新 %s → %s (%d 个提交)"
                           % (rep2["from"], rep2["to"], rep2["commits"]))
                    ag = rep2.get("agent", {})
                    if ag.get("ok"):
                        msg += " · agent 已重启(pid=%s)" % ag.get("pid")
                    else:
                        msg += " · agent 重启: %s" % ag.get("why", "?")
                    if rep2.get("deps_changed"):
                        msg += " · ⚠ 依赖变更: %s" % rep2["deps_hint"]
                    self._say_sys(msg)
                else:
                    self._say_sys("— 未更新: %s" % rep2.get("why", "?"))
            self.call_from_thread(_show)
        threading.Thread(target=_work, daemon=True).start()
        self._say_sys("⏳ %s…" % ("检查更新(fetch origin)" if check_only
                                   else "从 GitHub 更新"))

    # ── R245 · 动效打磨（spinner · 智能滚动 · 忙态占位） ──────────

    _SPIN = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"      # braille 族(UTF-8 终端标准)

    def _spin_tick(self) -> None:
        """★ 忙: hint 行转 spinner+轮态; 闲: 恢复快捷提示。"""
        try:
            hint = self.query_one("#hint", Static)
            inp = self.query_one("#ask", Input)
        except Exception:                       # noqa: BLE001 — 已卸载
            return
        if self._busy:
            self._spin_i = (self._spin_i + 1) % len(self._SPIN)
            _shimmer = _C("accent") if self._spin_i % 2 == 0 else "#FFD9A0"
            _word = (_TH.think_line(self._spin_i) if _TH is not None
                 else "执行中")  # ★ R273-D · 俏皮思考词＋微光
            hint.update("[%s]%s[/] %s…" % (_shimmer, self._SPIN[self._spin_i],
                                           _word))
            if not inp.placeholder.startswith("执行中"):
                inp.placeholder = "执行中… 输入将排队"
        else:
            hint.update("/help · /bg")
            if inp.placeholder.startswith("执行中"):
                inp.placeholder = "输入任务，回车执行…  / 命令 · @ 文件 · ↑ 历史"

    def _follow(self) -> None:
        """★ 智能滚动: 仅当视口已在底部才跟随新消息
        （阅读历史时新输出不强行拉底 — R245）。"""
        m = self._msgs()
        if m.scroll_y >= m.max_scroll_y - 2:
            m.scroll_end(force=True)

    # ── R244 · Ctrl+P 面板 / 文件树 / 新会话 ───────────────────

    def action_palette(self) -> None:
        """★ Ctrl+P: 命令面板（全部命令 + 常用动作）。"""
        def _run(fn):
            if callable(fn):
                fn()
        self.push_screen(PaletteScreen(self._palette_items()), _run)

    def action_command_palette(self) -> None:
        """★ R244 双保险: textual 内置 action 真名是 command_palette
        （曾误覆盖 toggle_command_palette — 无效）。覆盖之。"""
        self.action_palette()

    def _palette_items(self):
        # ★ R244 实测: acts 与同名命令文字近重复(新会话/查看状态 vs
        #   /new /status) ⇒ 底部两行看着"重叠实为冗余"。只留无命令
        #   等价的动作, 面板=命令本身。
        return [(c + " — " + d, self._mk_cmd(c)) for c, d in _CMDS]

    def _mk_cmd(self, cmd: str):
        def _go():
            inp = self.query_one("#ask", Input)
            inp.value = cmd
            self.on_input_submitted(type("E", (), {"value": cmd})())
        return _go

    def action_scroll_history(self, delta: int) -> None:
        """★ R264 · 滚历史: 焦点在动作区滚动作区, 否则滚消息区。
        每步 ~6 行（pgup/pgdn 连按即连续翻页）。"""
        step = 6 * int(delta)
        try:
            focused = self.focused
            if focused is not None and focused.id == "tools":
                focused.scroll_relative(y=step * 3, animate=False)
                return
            m = self.query_one("#msgs", VerticalScroll)
            m.scroll_relative(y=step * 6, animate=False)
            # 手动翻页时暂停自动跟底, 翻回底部恢复（_follow 只在底才续跟）
            if delta < 0 and m.scroll_y < m.max_scroll_y - 2:
                pass                          # 保持当前位置（不强制回底）
        except Exception as exc:              # noqa: BLE001 — 滚动失败留痕
            sys.stderr.write("scroll 失败: %s: %s\n" % (type(exc).__name__, exc))

    def action_clear_chat(self) -> None:
        """★ R244 /new: 新会话 — 清多轮上下文 + 清对话流(留品牌头)。"""
        self._hist = []
        msgs = self._msgs()
        msgs.remove_children()
        msgs.mount(Static(
            "[bold black on " + _C("accent") + "] D W C [/]  [dim]新会话 · "
            "输入任务回车即执行[/]", classes="msg-sys"))

    def _render_tree(self) -> None:
        """★ R244: 文件树侧栏（按目录分组缩进 — 展示态, 选择走 @）。"""
        lines = []
        last_dir = None
        for f in getattr(self, "_files", [])[:120]:
            d = f.rsplit("/", 1)[0] if "/" in f else "."
            if d != last_dir:
                lines.append("[#8A8E94]%s/[/]" % d)
                last_dir = d
            lines.append("  %s" % f.rsplit("/", 1)[-1])
        self.query_one("#tree", Static).update("\n".join(lines) or "—")

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
                rows.append("[%s bold]%s%s[/]" % (_C("accent"), mark, label))
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
        elif text.startswith("/") and " " in text:
            # ★ R272-③ · 二级补全（/mem lessons…）
            try:
                self._suggest_show(_complete_cmd(text))
            except Exception as exc:             # noqa: BLE001 — 补全坏不炸
                sys.stderr.write("二级补全失败: %s\n" % exc)
                self._suggest_show([])
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
        self._follow()

    def _say_sys(self, text: str) -> None:
        self._msgs().mount(Static(text, classes="msg-sys"))
        self._follow()

    def _say_ans(self, markdown: str) -> None:
        """★ 助手答案: Markdown 组件渲染（标题/代码块/列表 — 质变点）。"""
        self._msgs().mount(Markdown(markdown, classes="msg-ans"))
        self._follow()

    def _say_block(self, tid: str, card_text: str) -> None:
        """★ R273-B · 回执块（四态边框卡；done 褪色 dim）。"""
        if _TH is None:  # ★ fallback：无主题退回裸行
            self._msgs().mount(Static(card_text, classes="msg-sys"))
            self._follow()
            return
        st = _card_state_of(card_text)
        block = _TH.card_block("后台回执 %s · %s" % (tid, st),
                               card_text.splitlines() or [card_text],
                               state=st)
        if st == "done":
            block = _wrap_dim(block)
        self._msgs().mount(Static(block, classes="msg-sys"))
        self._follow()

    def _stream_open(self) -> Static:
        """★ 流式临时区: 逐字打; 完成后 remove 并换 Markdown 卡。"""
        w = Static("", classes="msg-stream", id="streaming")
        self._msgs().mount(w)
        self._follow()
        return w

    def _stream_close(self) -> None:
        try:
            self.query_one("#streaming").remove()
        except Exception:                       # noqa: BLE001
            pass

    def _topbar_text(self) -> str:
        mode = ("[" + _C("accent") + "]bg 投单[/]" if self._bg_mode
                else "同步")
        clock = _time.strftime("%H:%M")
        return (("  ◆ [bold black on " + _C("accent") + "] D W C [/]  "
                 "[on " + _C("surface") + "] %s [/]  [on " + _C("surface")
                 + "] %s [/]  [dim]ctrl+c[/]")
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

    def _show_mem(self, args: list) -> None:
        """★ R271 · /mem 子视图分发（纯函数出 markdown → 答案卡）。"""
        try:
            from dwc.organs import memory_view as _MV
        except Exception as exc:                 # noqa: BLE001 — 降级留痕
            self._say_sys("记忆看板不可用：%s" % exc)
            return
        sub = (args[0].lower() if args else "lessons")
        if sub == "lessons":
            self._say_ans(_MV.lessons_panel())
        elif sub == "night":
            self._say_ans(_MV.night_panel())
        elif sub in ("ep", "episodes"):
            tid = args[1] if len(args) > 1 else None
            self._say_ans(_MV.episode_panel(task_id=tid))
        elif sub in ("wf", "workflows"):
            self._say_ans(_MV.workflow_panel())
        else:
            self._say_sys("/mem 视图：lessons · night · "
                          "episodes(ep <task>) · workflows")

    def _apply_theme(self, name: str) -> None:
        """★ R273-C · /theme 换肤（非法名提示不炸；即时生效）。"""
        try:
            _TH.set_current(name)
            self.theme = "dwc-%s" % name
            self._set_topbar()
            self._say_sys("→ 主题已切 %s（%s）" % (name, _C("bg")))
        except ValueError:
            self._say_sys("/theme 用法：/theme deep|warm（当前 %s）"
                          % _TH.current_name())
        except Exception as exc:                 # noqa: BLE001 — 换肤坏不炸
            sys.stderr.write("换肤失败: %s\n" % exc)
            self._say_sys("换肤失败，已保持当前主题")

    def _mem_summary(self) -> str:
        """★ R271 · 顶栏记忆摘要（记M·触T，失败记—）。"""
        try:
            from dwc.agent_quality import load_lessons
            rows = load_lessons()
            used = sum(1 for r in rows
                       if int(r.get("use_count", 0) or 0) > 0)
            return "记%d·触%d" % (len(rows), used)
        except Exception:                        # noqa: BLE001
            return "记—"

    def _llm_summary(self) -> str:
        """★ R272-② · 顶栏 LLM 位（只 model 名＋host，key 绝不碰）。"""
        try:
            from dwc.llm.client import LLMClient
            c = LLMClient()
            if not getattr(c, "configured", False):
                return "LLM—"
            host = c._host_only() if hasattr(c, "_host_only") else ""
            return "模%s·%s" % (getattr(c, "_model", "?"), host or "?")
        except Exception:                        # noqa: BLE001
            return "LLM—"

    def _apply_status(self, s: dict) -> None:
        q = s.get("queue") or {}
        hb = s.get("heartbeat") or {}
        mark = ("[" + _C("success") + "]●[/] agent alive" if s.get("pid")
                else "[" + _C("error") + "]●[/] agent down")
        mode = ("[" + _C("accent") + "]bg 投单[/]" if self._bg_mode
                else "同步")
        clock = _time.strftime("%H:%M")
        self.query_one("#topbar", Static).update(
            (("  ◆ [bold black on " + _C("accent") + "] D W C [/]  "
              "[on " + _C("surface") + "] %s [/]  [on " + _C("surface")
              + "] %s·%s·%s/%s [/]  "
              "[on " + _C("surface") + "] %s [/]  [on " + _C("surface")
              + "] %s [/]  [on " + _C("surface") + "] %s [/]  "
              "[dim]ctrl+c[/]")
             % (mark, mode, hb.get("terms", "─"),
                q.get("pending", 0), q.get("done", 0), self._mem_summary(),
                self._llm_summary(), clock)))

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
            _s = getattr(self, "_last_secs", None)  # ★ R273-D · 末轮耗时
            self._say_sys("末轮耗时：%s" % (
                ("%.1fs" % _s) if _s is not None else "—（本会话未跑）"))
            return
        if line.split()[0] == "/mem":   # ★ R271 · 记忆看板（只渲染不判定）
            self._show_mem(line.split()[1:])
            return
        if line.split()[0] == "/theme":  # ★ R273-C · 换肤 deep|warm
            self._apply_theme((line.split()[1:] or [""])[0])
            return
        if line in ("/new", "/clear"):
            self.action_clear_chat()
            return
        if line.split()[0] in ("/update", "/u"):   # ★ R248 自更新
            self._update_flow("--check" in line)
            return
        if not line.startswith("/"):
            self._in_hist.append(line)     # ★ R243 历史(命令不入)
            if len(self._in_hist) > 200:
                self._in_hist = self._in_hist[-200:]
            try:  # ★ R272-③ · 历史落盘（失败留痕，内存照用）
                _hist_save(_HIST_PATH, self._in_hist)
            except OSError as exc:
                sys.stderr.write("tui hist 落盘失败: %s\n" % exc)
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
        self._spin_tick()          # ★ 立即切忙态视觉(不等 120ms)
        ctx = None
        if self._hist:
            last = self._hist[-1]
            ctx = "上轮对话摘要: 任务=%s; 答案要点=%s" % (
                last["task"][:120], str(last.get("answer", ""))[:400])
        from dwc.agent_quality import chat_ctx as _chat_ctx  # ★ R274-① 聊天读口
        ctx = _chat_ctx(task, ctx)

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
                self._follow()
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
                for row in _render_action(
                        ev, _time.strftime("%H:%M:%S")):
                    _post_tool(row)
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
            self._last_secs = secs  # ★ R273-D · 末轮耗时（本地实测）
            ans = str(rep.get("answer", ""))
            from dwc.agent_quality import record_chat_outcome  # ★ R274-② 写口
            record_chat_outcome(task, rep)

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
                tid = r.get("id", "?")
                self.call_from_thread(self._say_sys,
                                      "→ 已投单 %s（结果自动回填）" % tid)
                card = _poll_bg(R.cmd_query, tid, sleep_fn=_time.sleep)
                self.call_from_thread(self._say_block, tid, card)
            except Exception as e:                  # noqa: BLE001 — 如实报
                self.call_from_thread(self._say_sys, "投单失败: %s" % e)
        threading.Thread(target=_work, daemon=True).start()


def _poll_bg(query_fn, tid: str, sleep_fn=None, tries: int = 60) -> str:
    """★ R272-① · bg 回执轮询（纯逻辑，可单测；线程里跑）。

    state 照抄不重判；report 摘要前 200 字；60 轮不到→超时提示。
    sleep_fn=None 时测试零等待（生产传 time.sleep）。
    """
    _sleep = sleep_fn if sleep_fn is not None else (lambda s: None)
    last = ""
    for _ in range(max(1, tries)):
        try:
            r = query_fn(tid) or {}
        except Exception as exc:                 # noqa: BLE001 — 记次不炸
            last = "查询失败：%s" % exc
            _sleep(5)
            continue
        state = str(r.get("state", "?"))
        rep = r.get("report")
        if state == "unknown" and rep is None:
            return "→ %s 查无此单（可能已被消费清走）" % tid
        if rep is not None or state in ("done", "fail", "failed",
                                          "cancelled"):
            ans = ""
            if isinstance(rep, dict):
                ans = str(rep.get("answer", rep.get("why", "")))[:200]
            return "→ %s 归：%s%s" % (
                tid, state, (" · " + ans) if ans else "")
        last = state
        _sleep(5)
    return "→ %s 超时未归（末态 %s，可 /status 查）" % (tid, last)


def _render_action(ev: dict, ts: str) -> list:
    """★ R273-B · 动作行渲染（成功＝旧单行逐字；失败＝整块粉框卡）。

    成功路径复用 _format_action（零重复）；失败卡无时间戳前缀
    （块级元素，边框对齐要求）。
    """
    rows = _format_action(ev)
    if ev.get("ok") or _TH is None:  # ★ fallback 无主题时走旧两行
        return ["[dim]%s[/] %s" % (ts, r) for r in rows]
    title = "%s %s" % (ev.get("op", ""), str(ev.get("target", ""))[:30])
    lines = [str(ev.get("target", ""))]
    if ev.get("why"):
        lines.append("· " + str(ev.get("why"))[:120])
    return [_TH.card_block(title, lines, state="fail")]


def _card_state_of(card_text: str) -> str:
    """★ R273-B · 回执卡文本→四态（显示映射，不重判）。"""
    if "归：done" in card_text or "归：cancelled" in card_text:
        return "done"
    if "归：fail" in card_text:
        return "fail"
    return "pending"


def _format_action(ev: dict) -> list:
    """★ R272-④ · 动作行格式化（成功单行现状；失败追加 dim 详情行）。

    只展示 ev 原文字段（target 全文＋why），不推断。成功行与旧格式
    逐字一致（时间戳由调用方加）。
    """
    mark = ("[" + _C("success") + "]✓[/]" if ev.get("ok")
            else "[" + _C("error") + "]✗[/]")
    first = ("[bold]%-2s[/] %-5s %s %s"
             % (_ICON.get(ev.get("op"), "·"), ev.get("op", ""),
                str(ev.get("target", ""))[:50], mark))
    if ev.get("ok"):
        return [first]
    detail = "  [dim]↳ %s%s[/]" % (
        str(ev.get("target", "")),
        (" · " + str(ev.get("why", ""))[:120]) if ev.get("why") else "")
    return [first, detail]


#: ★ R243: / 命令候选表（展示, 说明）
_CMDS = [("/bg", "切后台投单模式"),
         ("/fg", "切同步直驱模式"),
         ("/help", "全部命令"),
         ("/status", "刷新状态"),
         ("/mem", "记忆看板 lessons|night|episodes|workflows"),
         ("/theme", "换肤 deep|warm"),
         ("/new", "新会话(清上下文)"),
            ("/update", "从 GitHub 拉取更新并重启 agent"),
         ("/quit", "退出")]

#: ★ R272-③ · 二级补全表（命令＋空格 → 参数候选）
_SUBS = {"/mem": ["lessons", "night", "episodes", "workflows"],
         "/update": ["--check"],
         "/theme": ["deep", "warm"]}

_HIST_PATH = os.path.join(_ROOT, "var", "dwc_tui_hist.jsonl")


def _hist_load(path: str = _HIST_PATH, limit: int = 200) -> list:
    """★ 历史读盘（缺席→[]，坏行跳过计数留痕）。"""
    import json as _j
    if not os.path.exists(path):
        return []
    out = []
    for ln in open(path, encoding="utf-8").read().splitlines():
        if ln.strip():
            try:
                out.append(str(_j.loads(ln)))
            except ValueError as exc:
                sys.stderr.write("tui hist 坏行跳过: %s\n" % exc)
    return out[-limit:]


def _hist_save(path: str, items: list) -> None:
    """★ 历史落盘（全量覆写 200 封顶；目录等 OSError 大声抛）。"""
    import json as _j
    with open(path, "w", encoding="utf-8") as fh:
        for t in list(items)[-200:]:
            fh.write(_j.dumps(t, ensure_ascii=False) + "\n")


def _complete_cmd(text: str) -> list:
    """★ R272-③ · / 二级补全纯函数（[(展示, 填充值)]）。"""
    if not isinstance(text, str):
        raise TypeError("text 须为 str（实收 %s）" % type(text).__name__)
    if not text.startswith("/") or " " not in text:
        return []
    cmd, rest = text.split(" ", 1)
    cands = _SUBS.get(cmd, [])
    q = rest.lower()
    return [("%s %s" % (cmd, s), "%s %s" % (cmd, s))
            for s in cands if s.startswith(q)]


class PaletteScreen(ModalScreen):
    """★ R244 · Ctrl+P 命令面板（居中浮层 — 模糊过滤 + ↑↓ 选 + Enter 执行）。"""

    CSS = """
    PaletteScreen { align: center middle; background: $background 45%; }
    #palette-box { width: 72; height: auto;
        background: $surface; border: tall $accent; padding: 1; }
    #palette-input { border: none; border-bottom: tall $accent;
        background: $surface; }
    #palette-list { height: 10; margin-top: 1; }
    """

    def __init__(self, items):
        super().__init__()
        self._items = items            # [(展示, callable)]
        self._idx = 0

    def compose(self) -> ComposeResult:
        with Vertical(id="palette-box"):
            yield Input(placeholder="过滤…", id="palette-input")
            yield RichLog(id="palette-list", auto_scroll=False,
                          markup=True, wrap=False)

    def on_mount(self) -> None:
        self.query_one("#palette-input", Input).focus()
        self._render_palette("")

    def _matched(self, q: str):
        if not q:
            return self._items
        ql = q.lower()
        return [it for it in self._items if ql in it[0].lower()]

    def _render_palette(self, q: str) -> None:
        # ★ RichLog 路径（Static 多行 update 实测底部行重叠 — 弃用）
        log = self.query_one("#palette-list", RichLog)
        log.clear()
        for i, (label, _fn) in list(enumerate(self._matched(q)))[:12]:
            mark = "▸ " if i == self._idx else "  "
            if i == self._idx:
                log.write("[%s bold]%s%s[/]" % (_C("accent"), mark, label))
            else:
                log.write("%s%s" % (mark, label))

    def on_input_changed(self, ev) -> None:
        self._idx = 0
        self._render_palette(ev.value or "")

    def on_key(self, ev) -> None:
        q = self.query_one("#palette-input", Input).value
        n = len(self._matched(q))
        if not n:
            return
        if ev.key == "down":
            self._idx = (self._idx + 1) % n
            self._render_palette(q); ev.stop(); ev.prevent_default()
        elif ev.key == "up":
            self._idx = (self._idx - 1) % n
            self._render_palette(q); ev.stop(); ev.prevent_default()
        elif ev.key in ("enter", "tab"):
            _label, fn = self._matched(q)[self._idx]
            self.dismiss(fn)
            ev.stop(); ev.prevent_default()
        elif ev.key == "escape":
            self.dismiss(None)
            ev.stop(); ev.prevent_default()


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
    # ★ R264 · 默认开鼠标（用户: 框体全不能滚 ⇒ 滚轮是刚需）。R241 的抖动
    #   根因(textual 无条件写 1003h ANY_EVENT)由 on_mount 的 1003l 补丁
    #   关掉 — 留 1000h 滚轮/点击。DWC_TUI_MOUSE=0 关回纯键盘（旧默认）。
    app.run(mouse=(os.environ.get("DWC_TUI_MOUSE", "").strip() != "0"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
