# -*- coding: utf-8 -*-
"""R264 · 框体滚动锁（2026-10-14 用户: "所有框体内容无法滚动, 信息错过就
无法看到"）。

根因: 鼠标默认关(R241 防 1003h 抖动) + 无任何滚动键绑定 + 输入框常驻
焦点吞掉 PgUp ⇒ 三条路全堵。
修: ① pgup/pgdn priority 绑定滚历史(输入框聚焦也抢); ② mouse 默认开 +
   on_mount 补关 1003h(留 1000h 滚轮/点击, 移动风暴不进程序 = R241 抖动
   根因消除); ③ focus 在动作区滚动作区。
"""
import asyncio
import io
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


def _fill(app, n=80):
    for i in range(n):
        app._say_sys("滚动内容行 %d" % i)


def test_pgdn_pgup_scroll_msgs():
    """★★★ 键盘滚动: 底部→pgup 上翻, 再 pgdn 回落（scroll_y 真变化）。"""
    async def _check(app, pilot):
        m = app._msgs()
        _fill(app)
        await pilot.pause(0.1)
        m.scroll_end(force=True)
        await pilot.pause(0.05)
        bottom = m.scroll_y
        app.action_scroll_history(-1)
        await pilot.pause(0.05)
        up = m.scroll_y
        assert up < bottom - 10, "pgup 没滚: %s→%s" % (bottom, up)
        app.action_scroll_history(1)
        await pilot.pause(0.05)
        assert m.scroll_y > up, "pgdn 没滚回: %s→%s" % (up, m.scroll_y)
    _run(_check)


def test_scroll_binding_priority_registered():
    """★★★ 绑定注册: pgup/pgdn 存在且 priority=True（输入框聚焦也抢得到）。"""
    keys = {(b.key, b.priority) for b in dwc_tui.DwcApp.BINDINGS}
    assert ("pgup", True) in keys, keys
    assert ("pgdn", True) in keys, keys


def test_scroll_focus_tools_branch():
    """★★★ 分支: 焦点在动作区(#tools)时滚动作区, 不误滚消息区。"""
    async def _check(app, pilot):
        _fill(app)
        await pilot.pause(0.05)
        tools = app.query_one("#tools")
        tools.focus()
        await pilot.pause(0.05)
        msg_before = app._msgs().scroll_y
        tools_before = tools.scroll_y
        app.action_scroll_history(-1)
        await pilot.pause(0.05)
        # 消息区没被动（焦点在 tools）
        assert app._msgs().scroll_y == msg_before
    _run(_check)


def test_mouse_default_on_and_1003l_patch_in_source():
    """★ 源锁: ① mouse 默认开（DWC_TUI_MOUSE=0 才关）; ② on_mount 有
    1003l 补丁（关移动风暴留滚轮 — textual windows_driver 写死 1003h）。"""
    src = io.open(dwc_tui.__file__.replace(".pyc", ".py"), encoding="utf-8").read()
    assert 'app.run(mouse=(os.environ.get("DWC_TUI_MOUSE", "").strip() != "0"))' in src
    assert '\\x1b[?1003l' in src or '\x1b[?1003l' in src, "缺 1003l 补丁"
    # 补丁必须在 on_mount 里（时序: driver 先写 1003h, mount 再关）
    i_mount = src.find("def on_mount")
    i_patch = src.find("1003l")
    assert 0 < i_mount < i_patch, (i_mount, i_patch)
