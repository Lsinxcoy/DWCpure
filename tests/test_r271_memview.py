# -*- coding: utf-8 -*-
"""R271 · 记忆看板（纯函数＋TUI 接线）。

★ 看板只读 var/ JSONL，不判定（G1）；数字全从行里数出来。
★ TUI 测试沿 R244 惯例（run_test pilot）。
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

from dwc.organs import memory_view as MV  # noqa: E402


def _write(path, rows):
    with open(path, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")


def _lessons():
    rows = []
    spec = [("a", "short", 0), ("b", "short", 0), ("c", "medium", 7),
            ("d", "medium", 7), ("e", "long", 1), ("f", "long", 9)]
    for tid, tier, use in spec:
        rows.append({"task_id": tid, "fail_mode": "m", "task": "t",
                     "detail": "d", "tier": tier, "use_count": use,
                     "quality": 0.8})
    return rows


# ── Task 1 · lessons＋night ────────────────────────────────────
class TestLessonsView:
    def test_tiers_top_readiness(self, tmp_path, monkeypatch):
        lp = str(tmp_path / "L.jsonl")
        _write(lp, _lessons())
        monkeypatch.setattr(MV, "LESSONS_PATH", lp)
        monkeypatch.setattr(MV, "ARCHIVE_PATH", str(tmp_path / "A.jsonl"))
        out = MV.lessons_panel()
        assert "medium 2" in out and "long 2" in out
        assert out.index("f") < out.index("c")  # top 首位 use 9
        assert "休眠" in out  # use>0 仅 4 行＜20

    def test_missing_files_dashes(self, tmp_path, monkeypatch):
        monkeypatch.setattr(MV, "LESSONS_PATH", str(tmp_path / "n.jsonl"))
        monkeypatch.setattr(MV, "ARCHIVE_PATH", str(tmp_path / "a.jsonl"))
        assert "—" in MV.lessons_panel()


class TestNightView:
    def _curve(self):
        return [
            {"tid": "t%d" % i, "kind": "k", "ok": True,
             "terminal": "DONE"} for i in range(3)
        ] + [{"tid": "f1", "kind": "k", "ok": False, "terminal": "FAIL"},
             {"tid": "s1", "kind": "k", "ok": False, "terminal": "STALLED",
              "saturated_early_stop": True}]

    def test_terminal_counts(self, tmp_path, monkeypatch):
        cp = str(tmp_path / "C.jsonl")
        _write(cp, self._curve())
        monkeypatch.setattr(MV, "CURVE_PATH", cp)
        out = MV.night_panel()
        assert "DONE 3" in out and "FAIL 1" in out and "STALLED 1" in out
        assert "60%" in out and "早停 1" in out

    def test_empty_curve(self, tmp_path, monkeypatch):
        monkeypatch.setattr(MV, "CURVE_PATH", str(tmp_path / "n.jsonl"))
        assert "暂无数据" in MV.night_panel()


# ── Task 2 · episodes＋workflows ───────────────────────────────
class TestEpisodeView:
    def _eps(self):
        return [
            {"ep": "ep_%05d" % i, "task_id": t, "kind": k, "ok": ok,
             "prev": p}
            for i, (t, k, ok, p) in enumerate([
                ("t1", "k1", False, ""), ("t2", "k1", False, "ep_00000"),
                ("t3", "k1", True, "ep_00001"), ("x1", "k2", True, ""),
            ])]

    def test_latest_chains(self, tmp_path, monkeypatch):
        ep = str(tmp_path / "E.jsonl")
        _write(ep, self._eps())
        monkeypatch.setattr(MV, "EPISODES_PATH", ep)
        out = MV.episode_panel()
        assert "✗→✗→✓" in out and "k1" in out

    def test_related_chain(self, tmp_path, monkeypatch):
        ep = str(tmp_path / "E.jsonl")
        _write(ep, self._eps())
        monkeypatch.setattr(MV, "EPISODES_PATH", ep)
        sys.path.insert(0, os.path.join(ROOT, "scripts"))
        out = MV.episode_panel(task_id="t2")
        assert "t1" in out and "t2" in out and "t3" in out
        assert "x1" not in out


class TestWorkflowView:
    def test_empty_templates(self, tmp_path, monkeypatch):
        monkeypatch.setattr(MV, "WORKFLOWS_PATH",
                            str(tmp_path / "n.jsonl"))
        assert "暂无模板" in MV.workflow_panel()

    def test_template_rows(self, tmp_path, monkeypatch):
        from dwc.organs import workflow_templates as WT
        p = str(tmp_path / "W.jsonl")
        WT.store_template("bench", "read-fact",
                          [{"desc": "读", "op": "read"}], path=p)
        monkeypatch.setattr(MV, "WORKFLOWS_PATH", p)
        out = MV.workflow_panel()
        assert "bench" in out and "read-fact" in out


# ── Task 3 · TUI 接线 ─────────────────────────────────────────
def _msgs_body(app) -> str:
    parts = []
    for w in app.query("#msgs Static"):
        try:
            parts.append(str(w.content))
        except Exception:                            # noqa: BLE001
            pass
    for w in app.query("#msgs Markdown"):
        try:
            parts.append(str(w._markdown) if hasattr(w, "_markdown")
                         else w.renderable)
        except Exception:                            # noqa: BLE001
            pass
    return "\n".join(str(p) for p in parts)


def _run_tui(fn):
    async def _go():
        import dwc_tui
        app = dwc_tui.DwcApp()
        async with app.run_test(size=(120, 30)) as pilot:
            await fn(app, pilot)
    asyncio.run(_go())


class TestTuiWiring:
    def test_mem_lessons_card(self):
        async def _check(app, pilot):
            inp = app.query_one("#ask")
            inp.value = "/mem lessons"
            app.on_input_submitted(type("E", (), {"value": "/mem lessons",
                                                 "input": inp})())
            await pilot.pause(0.3)
            assert "记忆 lessons" in _msgs_body(app)
        _run_tui(_check)

    def test_mem_unknown_hints_views(self):
        async def _check(app, pilot):
            inp = app.query_one("#ask")
            app.on_input_submitted(type("E", (), {"value": "/mem blah",
                                                 "input": inp})())
            await pilot.pause(0.3)
            body = _msgs_body(app)
            assert "episodes" in body and "workflows" in body
        _run_tui(_check)

    def test_topbar_has_mem(self):
        async def _check(app, pilot):
            await pilot.pause(0.5)
            assert "记" in app.query_one("#topbar").content
        _run_tui(_check)


# ── 破坏性路径（Rule E：raises 占比 ≥5%） ──────────────────────
class TestDestructive:
    def test_lessons_dir_raises(self, tmp_path):
        with pytest.raises(OSError):
            MV.lessons_panel(path=str(tmp_path))

    def test_episode_bad_task_type_raises(self, tmp_path, monkeypatch):
        monkeypatch.setattr(MV, "EPISODES_PATH",
                            str(tmp_path / "n.jsonl"))
        with pytest.raises(TypeError):
            MV.episode_panel(task_id=["not", "a", "str"])
