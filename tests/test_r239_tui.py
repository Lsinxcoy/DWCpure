# -*- coding: utf-8 -*-
"""R239 · 全屏 TUI：headless 渲染 / 输入派发 / 模式切换 / 降级回退。"""
from __future__ import annotations

import asyncio
import os
import sys

ROOT = r"E:\Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import dwc_tui as T                                               # noqa: E402


def _run(app_fn):
    """★ textual headless 测试环（run_test — 不占真终端）。"""
    async def _go():
        app = T.DwcApp()
        async with app.run_test() as pilot:   # run_test 自动 mount
            await pilot.pause()
            await app_fn(app, pilot)
    asyncio.run(_go())


def test_widgets_compose():
    """★★★ 五件套合成锁: 品牌顶栏/对话区/动作区/输入/提示行（全屏骨架）。
    ★ R240 结构校准: #status 状态行并入品牌顶栏 #topbar（锁跟结构语义）。"""
    async def _check(app, pilot):
        assert app.query_one("#topbar") is not None
        assert app.query_one("#msgs") is not None      # ★ R242 消息容器
        assert app.query_one("#tools") is not None
        assert app.query_one("#ask") is not None
        assert app.query_one("#prompt-label") is not None
        # 主题注册成功（R273 起双主题 deep|warm，默认 deep）
        assert app.theme == "dwc-deep"
    _run(_check)


def test_input_dispatches_sync_task(monkeypatch):
    """★★★ 派发锁: 输入任务行 ⇒ 打印 ❯ 行 + 线程执行 execute_user_task
    （LLM 打桩 — 测 UI 不触网）。"""
    calls = {}

    def _fake_exec(task, *, llm, ctx=None, progress=None):
        calls["task"] = task
        progress({"ev": "round", "n": 1})
        progress({"ev": "action", "round": 1, "op": "read",
                  "target": "x.py", "ok": True, "detail": ""})
        from types import SimpleNamespace
        return {"status": "done", "rounds": 1, "answer": "假答案",
                "actions_log": []}
    import dwc.llm.task_exec as TE
    monkeypatch.setattr(TE, "execute_user_task", _fake_exec)

    async def _go(app, pilot):
        await pilot.click("#ask")
        await pilot.press(*list("任务X"))
        await pilot.press("enter")
        for _ in range(30):
            await pilot.pause(0.05)
            if calls.get("task"):
                break
        assert calls.get("task") == "任务X"
        # ★ R242: 用户消息以卡片 widget 入流（非日志行）
        await pilot.pause(0.1)
        users = app.query(".msg-user")
        assert len(users) >= 1, "用户消息卡未生成"
    _run(_go)


def test_mode_toggle_and_quit(monkeypatch):
    """★★ /bg /fg 模式切换 + /quit 退出（REPL 同一套命令面）。"""
    async def _go(app, pilot):
        await pilot.click("#ask")
        await pilot.press(*list("/bg"))
        # ★ R243 行为语义: 候选打开时 Enter=补全(关浮层), 再 Enter 执行
        await pilot.press("enter")
        await pilot.press("enter")
        await pilot.pause()
        assert app._bg_mode is True
        await pilot.click("#ask")
        await pilot.press(*list("/fg"))
        await pilot.press("enter")   # 补全
        await pilot.press("enter")   # 执行
        await pilot.pause()
        assert app._bg_mode is False
        await pilot.click("#ask")
        await pilot.press(*list("/quit"))
        await pilot.pause()
    _run(_go)


def test_fallback_when_tui_unavailable(monkeypatch):
    """★★ 降级锁: textual 不可用 ⇒ main 回退 dwc_chat（降级不硬撑, 留痕）。"""
    monkeypatch.setattr(T, "_TUI_OK", False)
    monkeypatch.setattr(T, "_TUI_ERR", "模拟不可用")
    called = {}

    def _fake_chat_main(argv):
        called["argv"] = argv
        return 0
    import dwc_chat as CH
    monkeypatch.setattr(CH, "main", _fake_chat_main)
    rc = T.main([])
    assert rc == 0 and called["argv"][0] == "dwc_chat"
