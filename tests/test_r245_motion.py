# -*- coding: utf-8 -*-
"""R245 · 动效打磨锁（spinner · 智能滚动跟随 · 忙态占位）。"""
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


def test_spinner_busy_and_idle():
    """★★★ spinner 锁: 忙=转字符+执行中占位; 闲=恢复提示。"""
    async def _check(app, pilot):
        hint = app.query_one("#hint")
        inp = app.query_one("#ask")
        # 闲态
        app._busy = False
        app._spin_tick()
        assert "/help" in str(hint.content)
        assert not inp.placeholder.startswith("执行中")
        # 忙态
        app._busy = True
        app._spin_tick()
        body = str(hint.content)
        assert "执行中" in body
        assert any(ch in body for ch in "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏")
        assert inp.placeholder.startswith("执行中")
        # 恢复
        app._busy = False
        app._spin_tick()
        assert "/help" in str(hint.content)
        assert not inp.placeholder.startswith("执行中")
    _run(_check)


def test_follow_at_bottom():
    """★★★ 智能滚动锁①: 视口在底部时新消息跟随。"""
    async def _check(app, pilot):
        m = app._msgs()
        await pilot.pause(0.05)
        m.scroll_end(force=True)
        await pilot.pause(0.05)
        before = m.scroll_y
        app._say_sys("底部跟随测试行")
        await pilot.pause(0.1)
        assert m.scroll_y >= before
        assert m.scroll_y >= m.max_scroll_y - 2
    _run(_check)


def test_no_hijack_mid_history():
    """★★★ 智能滚动锁②: 阅读历史(视口在顶)时新消息不强行拉底。"""
    async def _check(app, pilot):
        m = app._msgs()
        # 灌多行撑出滚动
        for i in range(60):
            app._say_sys("历史行 %d" % i)
        await pilot.pause(0.1)
        m.scroll_to(y=0, animate=False)       # 用户翻到顶部看历史
        await pilot.pause(0.05)
        top_y = m.scroll_y
        app._say_sys("新输出不该把视口拽到底")
        await pilot.pause(0.1)
        # 视口仍在上部（没有被 scroll_end 拽到底）
        assert m.scroll_y < m.max_scroll_y - 2, \
            (m.scroll_y, m.max_scroll_y, top_y)
    _run(_check)
