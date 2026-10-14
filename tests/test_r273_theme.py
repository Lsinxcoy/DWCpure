# -*- coding: utf-8 -*-
"""R273 · TUI 改版 A(语义上色)B(边框化)C(换肤)D(呼吸感)。

★ G1：只换皮，不碰判定/执行/布局。deep 套 token 值＝现状 hex（零视觉回归）。
"""
from __future__ import annotations

import os
import re
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import dwc_theme as TH  # noqa: E402

HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


# ── Task A · token 表 ─────────────────────────────────────────
class TestTokens:
    NEED = ["accent", "success", "warn", "error", "muted", "surface"]

    def test_six_tokens_hex(self):
        for name in ("deep", "warm"):
            toks = TH.get(name)
            for k in self.NEED:
                assert HEX.match(toks[k]), (name, k, toks.get(k))

    def test_deep_matches_status_quo(self):
        d = TH.get("deep")
        assert d["accent"] == "#FFB86B"     # ★ 现状 amber，零回归锁
        assert d["success"] == "#5AF78E"
        assert d["error"] == "#FF5F56"

    def test_wrap_dim(self):
        import dwc_tui
        out = dwc_tui._wrap_dim("hello")
        assert out.startswith("[dim]") and out.endswith("[/]")
        assert "hello" in out


# ── Task B · 工具块边框 ───────────────────────────────────────
class TestCard:
    def test_four_states(self):
        for st, color in (("run", "#87afff"), ("pending", "#ffffaf"),
                          ("done", "#808080"), ("fail", "#fd5db1")):
            out = TH.card_block("T_%s" % st, ["a", "b"], state=st)
            assert "╭" in out and "╰" in out
            assert "T_%s" % st in out and color in out

    def test_empty_and_fallback(self):
        out = TH.card_block("空", [], state="weird")
        assert "╭" in out and "#808080" in out

    def test_cjk_align(self):
        import re
        out = TH.card_block("中文标题", ["短", "长一点的行"],
                            state="done")
        try:
            from rich.cells import cell_len
        except Exception:                            # noqa: BLE001
            cell_len = len
        widths = {cell_len(re.sub(r"\[[^\]]*\]", "", ln))
                  for ln in out.splitlines()}
        assert widths == {20} or len(widths) == 1, widths

    def test_bad_title_raises(self):
        with pytest.raises(TypeError):
            TH.card_block(["not", "str"], ["x"])


# ── Task B 接线 · 回执块＋渲染 ────────────────────────────────
class TestRender:
    def test_card_state_map(self):
        import dwc_tui
        assert dwc_tui._card_state_of("→ T 归：done · x") == "done"
        assert dwc_tui._card_state_of("→ T 归：fail · x") == "fail"
        assert dwc_tui._card_state_of("→ T 超时未归") == "pending"
        assert dwc_tui._card_state_of("→ T 查无此单") == "pending"

    def test_render_action_success_identical(self):
        import dwc_tui
        ev = {"op": "read", "target": "a.py", "ok": True}
        out = dwc_tui._render_action(ev, "12:00:00")
        assert len(out) == 1
        assert out[0] == "[dim]12:00:00[/] %s" % (
            dwc_tui._format_action(ev)[0])

    def test_render_action_fail_card(self):
        import dwc_tui
        out = dwc_tui._render_action(
            {"op": "run", "target": "t.py", "ok": False,
             "why": "exit=1"}, "12:00:00")
        assert len(out) == 1 and "╭" in out[0] and "#fd5db1" in out[0]

    def test_say_block_pilot(self):
        import asyncio
        import dwc_tui

        async def _go():
            app = dwc_tui.DwcApp()
            async with app.run_test(size=(120, 30)) as pilot:
                app._say_block("T9", "→ T9 归：done · 好")
                await pilot.pause(0.3)
                body = " ".join(
                    str(getattr(w, "content", ""))
                    for w in app.query("#msgs Static"))
                assert "╭" in body and "T9" in body
        asyncio.run(_go())


# ── Task C · 换肤 ─────────────────────────────────────────────
class TestSwitch:
    def test_warm_differs(self):
        d, w = TH.get("deep"), TH.get("warm")
        assert d["bg"] != w["bg"] and d["accent"] != w["accent"]
        assert w["bg"] == "#1a1200" and w["fg"] == "#ffb000"

    def test_bad_name_raises(self):
        with pytest.raises(ValueError):
            TH.set_current("nope", persist=False)

    def test_think_and_palette(self):
        assert len(TH.THINK_WORDS) == 12 and all(TH.THINK_WORDS)
        assert TH.think_line(0) == TH.THINK_WORDS[0]
        assert TH.think_line(13) == TH.THINK_WORDS[1]
        assert len(TH.SUBAGENT_COLORS) == 8

    def test_theme_pilot(self, tmp_path, monkeypatch):
        import asyncio
        import dwc_tui
        monkeypatch.setattr(TH, "_THEME_FILE", str(tmp_path / "T"))
        monkeypatch.setattr(TH, "_CURRENT", None)

        async def _go():
            app = dwc_tui.DwcApp()
            async with app.run_test(size=(120, 30)) as pilot:
                inp = app.query_one("#ask")
                app.on_input_submitted(type("E", (), {"value": "/theme warm",
                                                     "input": inp})())
                await pilot.pause(0.3)
                assert TH.current_name() == "warm"
                assert app.theme == "dwc-warm"
                body = " ".join(
                    str(getattr(w, "content", ""))
                    for w in app.query("#msgs Static"))
                assert "主题已切 warm" in body
                app.on_input_submitted(type("E", (), {"value": "/theme nope",
                                                     "input": inp})())
                await pilot.pause(0.3)
                assert TH.current_name() == "warm"
        asyncio.run(_go())
        TH._CURRENT = None  # ★ 恢复生产主题状态

    def test_status_secs_pilot(self):
        import asyncio
        import dwc_tui

        async def _go():
            app = dwc_tui.DwcApp()
            async with app.run_test(size=(120, 30)) as pilot:
                inp = app.query_one("#ask")
                app.on_input_submitted(type("E", (), {"value": "/status",
                                                     "input": inp})())
                await pilot.pause(0.3)
                body = " ".join(
                    str(getattr(w, "content", ""))
                    for w in app.query("#msgs Static"))
                assert "末轮耗时" in body and "未跑" in body
        asyncio.run(_go())
