# -*- coding: utf-8 -*-
"""R244 · Ctrl+P 命令面板 + 文件树 + 新会话锁。"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

import dwc_tui  # noqa: E402


def _run(fn):
    async def _go():
        app = dwc_tui.DwcApp()
        async with app.run_test(size=(120, 30)) as pilot:
            await fn(app, pilot)
    asyncio.run(_go())


def test_palette_opens_and_filters():
    """★★★ Ctrl+P 面板打开 + 模糊过滤锁。"""
    async def _check(app, pilot):
        await pilot.press("ctrl+p")
        await pilot.pause(0.1)
        scr = app.screen
        assert isinstance(scr, dwc_tui.PaletteScreen)
        inp = scr.query_one("#palette-input")
        inp.value = "quit"
        scr.on_input_changed(type("E", (), {"value": "quit"})())
        assert len(scr._matched("quit")) >= 1
        # ★ 判据: 过滤结果含 quit + 渲染不炸(RichLog 路径)
        assert any("quit" in lbl for lbl, _fn in scr._matched("quit"))
        await pilot.press("escape")
    _run(_check)


def test_palette_escape_closes():
    """★★★ Esc 关面板回到主界面锁。"""
    async def _check(app, pilot):
        await pilot.press("ctrl+p")
        await pilot.pause(0.1)
        assert isinstance(app.screen, dwc_tui.PaletteScreen)
        await pilot.press("escape")
        await pilot.pause(0.1)
        assert not isinstance(app.screen, dwc_tui.PaletteScreen)
    _run(_check)


def test_tree_renders():
    """★★★ 文件树侧栏渲染锁（目录分组 + 文件名）。"""
    async def _check(app, pilot):
        body = getattr(app.query_one("#tree"), "content", "")
        assert "dwc" in body          # src/dwc 分组
        assert "/" in body
    _run(_check)


def test_new_resets_context():
    """★★★ /new 新会话锁（上下文清零 + 消息流重置）。"""
    async def _check(app, pilot):
        app._hist = [("旧任务", "旧答案")]
        app._say_user("旧消息")
        _inp = app.query_one("#ask")
        app.on_input_submitted(type("E", (), {
            "value": "/new", "input": _inp})())
        await pilot.pause(0.05)
        assert app._hist == []
        # ★ Layer22 判据校准: 容器 render() 是 Blank — 扫子节点 content
        body = " ".join(getattr(n, "content", "") for n in app._msgs().children)
        assert "新会话" in body
        assert "旧消息" not in body
    _run(_check)


def test_compose_has_tree():
    """★★★ 六件套: 树/顶栏/消息/动作/输入/提示。"""
    async def _check(app, pilot):
        for wid in ("#tree-pane", "#topbar", "#msgs", "#tools",
                    "#ask", "#prompt-label"):
            assert app.query_one(wid) is not None, wid
    _run(_check)
