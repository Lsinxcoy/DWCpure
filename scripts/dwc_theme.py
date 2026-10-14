# -*- coding: utf-8 -*-
"""★ R273-A · TUI 主题 token 表（纯数据＋纯函数，零 textual 依赖）。

两套主题：deep（Deep Space 现状，token 值＝旧 hex 零回归）
warm（Retro 琥珀暖底）。颜色只当语义 token 用，不散落 hex。
"""
from __future__ import annotations

import os

TOKENS = {
    "deep": {  # ★ 值＝R272 前现状（逐字零回归，见 on_mount 旧 Theme）
        "accent": "#FFB86B",
        "success": "#5AF78E",
        "warn": "#F3D99D",
        "error": "#FF5F56",
        "muted": "#8A8E94",
        "surface": "#2A2A2C",
        "bg": "#0B0F14",
        "fg": "#ECEDEE",
    },
    "warm": {  # ★ Retro 琥珀：暖黑底＋琥珀字
        "accent": "#ffcc00",
        "success": "#33ff00",
        "warn": "#ffcc00",
        "error": "#ff0033",
        "muted": "#665500",
        "surface": "#2a2000",
        "bg": "#1a1200",
        "fg": "#ffb000",
    },
}

#: ★ R273-B · 边框字符（deep 圆角 / warm 双线）
BORDER_CHARS = {
    "deep": {"tl": "╭", "tr": "╮", "bl": "╰", "br": "╯",
             "h": "─", "v": "│"},
    "warm": {"tl": "╔", "tr": "╗", "bl": "╚", "br": "╝",
             "h": "═", "v": "║"},
}

#: ★ R273-B · 四态边框色（抄 Gemini 语义：蓝跑/黄等/灰完/粉败）
BORDER_STATE = {
    "run": "#87afff",
    "pending": "#ffffaf",
    "done": "#808080",
    "fail": "#fd5db1",
}

#: ★ R273-D · 中文思考俏皮词（12 词，spinner hint 轮换）
THINK_WORDS = ["酝酿", "推演", "琢磨", "参透", "权衡", "溯源",
               "编织", "打磨", "深潜", "复盘", "勾连", "落子"]

#: ★ R273-D · 子代理色盘预留（Claude Code 八色，暂无子代理先占位）
SUBAGENT_COLORS = ["#ff6b6b", "#87afff", "#5AF78E", "#FFC107",
                   "#af87ff", "#ff9f43", "#fd5db1", "#87d7d7"]

_THEME_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "..", "var", "dwc_tui_theme")
_CURRENT = None


def get(name: str | None = None) -> dict:
    """★ 取某套 tokens（无参＝当前主题；坏文件→deep）。"""
    global _CURRENT
    if name is None:
        if _CURRENT in TOKENS:
            return TOKENS[_CURRENT]
        try:
            want = open(_THEME_FILE, encoding="utf-8").read().strip()
        except OSError:
            want = "deep"
        _CURRENT = want if want in TOKENS else "deep"
        return TOKENS[_CURRENT]
    return TOKENS[name]


def current_name() -> str:
    """★ 当前主题名。"""
    get()
    return _CURRENT or "deep"


def set_current(name: str, persist: bool = True) -> dict:
    """★ 切换主题（非法名抛 ValueError；默认持久化）。"""
    global _CURRENT
    if name not in TOKENS:
        raise ValueError("未知主题 %r（仅 deep|warm）" % name)
    _CURRENT = name
    if persist:
        try:
            with open(_THEME_FILE, "w", encoding="utf-8") as fh:
                fh.write(name + "\n")
        except OSError as exc:
            import sys
            sys.stderr.write("主题持久化失败: %s\n" % exc)
    return TOKENS[name]


def border() -> dict:
    """★ 当前主题边框字符。"""
    return BORDER_CHARS[current_name()]


def think_line(i: int) -> str:
    """★ R273-D · 第 i tick 的思考词（deterministic）。"""
    return THINK_WORDS[int(i) % len(THINK_WORDS)]


def _w(s: str) -> int:
    """★ 显示宽度（有 rich 用 cell_len，无则退 len；框对齐用）。"""
    try:
        from rich.cells import cell_len
        return cell_len(s)
    except Exception:                            # noqa: BLE001
        return len(s)


def card_block(title: str, lines: list, state: str = "done") -> str:
    """★ R273-B · 工具块边框（标题嵌框线，边框色按四态）。

    state: run/pending/done/fail（未知→done 灰，不炸）。
    """
    if not isinstance(title, str):
        raise TypeError("title 须为 str（实收 %s）" % type(title).__name__)
    b = border()
    color = BORDER_STATE.get(state, BORDER_STATE["done"])
    body = [str(x) for x in (lines or [])]
    width = max([_w(title) + 4] + [_w(x) + 4 for x in body] + [20])
    top = "%s─ %s %s%s" % (b["tl"], title, b["h"] * (width - _w(title) - 5),
                           b["tr"])
    rows = ["%s %s%s" % (b["v"], x, " " * (width - _w(x) - 2))
            for x in body]
    bot = "%s%s%s" % (b["bl"], b["h"] * (width - 2), b["br"])
    return "[%s]%s[/]\n%s\n[%s]%s[/]" % (
        color, top, "\n".join(rows), color, bot)
