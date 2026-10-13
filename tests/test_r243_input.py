# -*- coding: utf-8 -*-
"""R243 · 输入升级锁（/ 命令补全 · @ 文件补全 · ↑ 历史 · 焦点不抖）。"""
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


def test_slash_suggests_commands():
    """★★★ / 触发命令候选锁。"""
    async def _check(app, pilot):
        inp = app.query_one("#ask")
        inp.value = "/"
        app.on_input_changed(type("E", (), {"value": "/"})())
        await pilot.pause(0.05)
        sug = app.query_one("#suggest")
        assert sug.display is True
        assert "/help" in str(sug.render())
        assert "/quit" in str(sug.render())
    _run(_check)


def test_tab_completes():
    """★★★ Tab 应用候选 + 浮层关闭。"""
    async def _check(app, pilot):
        inp = app.query_one("#ask")
        inp.value = "/he"
        app.on_input_changed(type("E", (), {"value": "/he"})())
        await pilot.pause(0.05)
        assert app._sug, "候选为空"
        app._suggest_apply()
        assert inp.value == "/help"
        assert app.query_one("#suggest").display is False
    _run(_check)


def test_at_suggests_files():
    """★★★ @ 触发文件候选锁（过滤 + 上限）。"""
    async def _check(app, pilot):
        inp = app.query_one("#ask")
        inp.value = "@predictor"
        app.on_input_changed(type("E", (), {"value": "@predictor"})())
        await pilot.pause(0.05)
        body = str(app.query_one("#suggest").render())
        assert "predictor" in body
        assert len(app._sug) <= 8
    _run(_check)


def test_up_recalls_history():
    """★★★ ↑ 输入历史锁（提交入史 — 命令不入）。"""
    async def _check(app, pilot):
        inp = app.query_one("#ask")
        app._in_hist = ["任务甲", "任务乙"]
        app.on_input_changed(type("E", (), {"value": ""})())
        # 无候选态 ↑
        ev = type("K", (), {"key": "up", "stopped": False,
                            "prevent": False,
                            "stop": lambda self: None,
                            "prevent_default": lambda self: None})()
        app.on_key(ev)
        assert inp.value == "任务乙", inp.value
        app.on_key(ev)
        assert inp.value == "任务甲", inp.value
    _run(_check)


def test_suggest_keeps_focus_in_input():
    """★★★ 焦点不抖锁: 候选期焦点恒在输入框（用户报的点击抖动同族防护）。"""
    async def _check(app, pilot):
        inp = app.query_one("#ask")
        inp.value = "/"
        app.on_input_changed(type("E", (), {"value": "/"})())
        await pilot.pause(0.05)
        assert app.focused is inp
    _run(_check)
