# -*- coding: utf-8 -*-
"""R272 · TUI 五项细化（bg 回执/顶栏 LLM/历史落盘/动作展开/sparkline）。

★ G1：回执只读 cmd_query 照抄 state；展开只展示 ev 原文。
★ key 绝不读（顶栏只 host＋model 名）。
"""
from __future__ import annotations

import asyncio
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import dwc_tui  # noqa: E402
from dwc.organs import memory_view as MV  # noqa: E402


def _run_tui(fn):
    async def _go():
        app = dwc_tui.DwcApp()
        async with app.run_test(size=(120, 30)) as pilot:
            await fn(app, pilot)
    asyncio.run(_go())


# ── Task 1 · bg 回执 ──────────────────────────────────────────
class TestBgReceipt:
    def test_poll_done_card(self):
        seq = [{"state": "pending", "report": None},
               {"state": "done",
                "report": {"status": "done", "answer": "A" * 300}}]
        out = dwc_tui._poll_bg(lambda tid: seq.pop(0), "T_x", sleep_fn=None)
        assert "done" in out and ("A" * 200) in out

    def test_poll_unknown(self):
        out = dwc_tui._poll_bg(
            lambda tid: {"state": "unknown", "report": None},
            "T_nope", sleep_fn=None)
        assert "查无此单" in out

    def test_poll_cancelled_stops(self):
        out = dwc_tui._poll_bg(
            lambda tid: {"state": "cancelled", "report": None},
            "T_c", sleep_fn=None)
        assert "cancelled" in out

    def test_poll_timeout(self):
        out = dwc_tui._poll_bg(
            lambda tid: {"state": "pending", "report": None},
            "T_slow", sleep_fn=None, tries=3)
        assert "超时未归" in out


# ── Task 2 · 顶栏 LLM 位 ──────────────────────────────────────
class TestLlmSlot:
    def test_topbar_has_llm(self):
        async def _check(app, pilot):
            await pilot.pause(0.5)
            body = app.query_one("#topbar").content
            assert ("模" in body) or ("LLM" in body)
        _run_tui(_check)


# ── Task 3 · 历史落盘＋二级补全 ───────────────────────────────
class TestHistPersist:
    def test_roundtrip(self, tmp_path):
        p = str(tmp_path / "H.jsonl")
        dwc_tui._hist_save(p, ["做A任务", "做B任务"])
        assert dwc_tui._hist_load(p) == ["做A任务", "做B任务"]

    def test_save_dir_raises(self, tmp_path):
        with pytest.raises(OSError):
            dwc_tui._hist_save(str(tmp_path), ["x"])


class TestSubComplete:
    def test_mem_subs(self):
        got = dwc_tui._complete_cmd("/mem ")
        assert [f for _l, f in got] == [
            "/mem lessons", "/mem night", "/mem episodes", "/mem workflows"]

    def test_mem_prefix(self):
        assert [f for _l, f in dwc_tui._complete_cmd("/mem n")] == [
            "/mem night"]

    def test_update_flag(self):
        assert [f for _l, f in dwc_tui._complete_cmd("/update ")] == [
            "/update --check"]

    def test_unknown_empty(self):
        assert dwc_tui._complete_cmd("/xyz") == []
        with pytest.raises(TypeError):
            dwc_tui._complete_cmd(["/mem"])


# ── Task 4 · 失败动作行展开 ───────────────────────────────────
class TestActionExpand:
    def test_success_single_line(self):
        rows = dwc_tui._format_action(
            {"op": "read", "target": "a.py", "ok": True})
        assert len(rows) == 1 and "✓" in rows[0]

    def test_fail_with_why(self):
        rows = dwc_tui._format_action(
            {"op": "run", "target": "t.py", "ok": False,
             "why": "exit=1 超时"})
        assert len(rows) == 2
        assert "exit=1" in rows[1] and "t.py" in rows[1]

    def test_fail_full_target(self):
        long_t = "d/" + "x" * 80 + ".py"
        rows = dwc_tui._format_action(
            {"op": "run", "target": long_t, "ok": False})
        assert len(rows) == 2 and long_t in rows[1]


# ── Task 5 · sparkline ────────────────────────────────────────
class TestSpark:
    def _curve(self, n_ok, n_fail):
        return ([{"tid": "o%d" % i, "ok": True} for i in range(n_ok)]
                + [{"tid": "f%d" % i, "ok": False} for i in range(n_fail)])

    def test_bars_and_rate(self, tmp_path, monkeypatch):
        cp = str(tmp_path / "C.jsonl")
        with open(cp, "w", encoding="utf-8") as fh:
            for r in self._curve(6, 2):
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
        out = MV.sparkline(path=cp)
        assert out.count("▇") == 6 and out.count("▁") == 2
        assert "75%" in out

    def test_too_few(self, tmp_path, monkeypatch):
        cp = str(tmp_path / "C.jsonl")
        with open(cp, "w", encoding="utf-8") as fh:
            fh.write(json.dumps({"tid": "o0", "ok": True},
                                ensure_ascii=False) + "\n")
        assert "点太少" in MV.sparkline(path=cp)
        assert "点太少" in MV.sparkline(path=str(tmp_path / "n.jsonl"))
