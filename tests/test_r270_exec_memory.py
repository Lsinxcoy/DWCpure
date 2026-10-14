# -*- coding: utf-8 -*-
"""R270 · 跨任务执行记忆（touch/分层/写门/模板/遗忘/episode/效用）。

★ 全文件零真 LLM 调用。
★ recall_lessons 排序键冻结（-overlap, not contrast）；touch/utility/tier
  只进返回字段与下游，不动排序。
"""
from __future__ import annotations

import json
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(_HERE)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from dwc import agent_quality as Q


def _mklessons_file(tmp_path, rows):
    p = os.path.join(str(tmp_path), "lessons.jsonl")
    with open(p, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    return p


# ── Task 1 · touch ────────────────────────────────────────────
class TestTouch:
    def test_touch_increments(self, tmp_path, monkeypatch):
        lp = _mklessons_file(tmp_path, [
            {"task_id": "a", "fail_mode": "m", "task": "t", "detail": "d"},
            {"task_id": "b", "fail_mode": "m", "task": "t", "detail": "d"}])
        monkeypatch.setattr(Q, "LESSONS", lp)
        assert Q.touch_lessons(["a", "nope"]) == 1
        rows = {r["task_id"]: r for r in
                (json.loads(l) for l in open(lp, encoding="utf-8"))}
        assert rows["a"]["use_count"] == 1
        assert rows["a"]["last_used"] != ""
        assert rows["b"].get("use_count", 0) == 0

    def test_recall_carries_use_count(self, tmp_path, monkeypatch):
        lp = _mklessons_file(tmp_path, [
            {"task_id": "a", "fail_mode": "m", "task": "字符码任务",
             "detail": "d", "use_count": 7}])
        monkeypatch.setattr(Q, "LESSONS", lp)
        hits = Q.recall_lessons("字符码任务")
        assert hits and hits[0]["use_count"] >= 7  # touch 后 +1


# ── Task 2 · 分层晋升 ─────────────────────────────────────────
class TestTiers:
    def _rows(self):
        rows = []
        for i in range(3):
            rows.append({"task_id": "hot%d" % i, "fail_mode": "m",
                         "task": "t", "detail": "d%d" % i, "use_count": 7})
        rows.append({"task_id": "warm", "fail_mode": "m", "task": "t",
                     "detail": "dw", "use_count": 1})
        for i in range(2):
            rows.append({"task_id": "cold%d" % i, "fail_mode": "z",
                         "task": "t", "detail": "dc%d" % i, "use_count": 0})
        return rows

    def test_promote_by_use(self, tmp_path, monkeypatch):
        lp = _mklessons_file(tmp_path, self._rows())
        monkeypatch.setattr(Q, "LESSONS", lp)
        r = Q.promote_lessons()
        assert r["to_medium"] == 3 and r["long_hints"] == 1
        rows = {x["task_id"]: x for x in
                (json.loads(l) for l in open(lp, encoding="utf-8"))}
        assert rows["hot0"]["tier"] == "medium"
        assert rows["warm"]["tier"] == "short"

    def test_enforce_capacity_archives_tail(self, tmp_path, monkeypatch):
        lp = _mklessons_file(tmp_path, self._rows())
        ap = os.path.join(str(tmp_path), "arch.jsonl")
        monkeypatch.setattr(Q, "LESSONS", lp)
        monkeypatch.setattr(Q, "LESSONS_ARCHIVE", ap)
        n = Q.enforce_tier_capacity(short=2)
        assert n == 4
        assert len(open(lp, encoding="utf-8").readlines()) == 2
        assert len(open(ap, encoding="utf-8").readlines()) == 4


# ── Task 3 · 写门 ─────────────────────────────────────────────
class TestGate:
    def test_empty_drops(self):
        r = Q.score_lesson_quality("", [])
        assert r["verdict"] == "drop" and r["quality"] == 0.0

    def test_good_row_passes(self):
        r = Q.score_lesson_quality(
            "成功做法（answer contains '0xfeff'）：核对原文字符码", [])
        assert r["verdict"] == "pass"

    def test_bench_short_row_passes(self):
        """旧调用点兼容：bench.py:230 的短 verdict 行必须过门。"""
        r = Q.score_lesson_quality(
            "verdict=命中类名 0/2 status=incomplete", [])
        assert r["verdict"] in ("pass", "review")

    def test_duplicate_consistency_zero(self):
        hist = ["核对原文字符码再作答"]
        r = Q.score_lesson_quality("核对原文字符码再作答", hist)
        assert r["factors"]["consistency"] == 0.0

    def test_record_gate_drops_empty(self, tmp_path, monkeypatch,
                                     capsys):
        lp = os.path.join(str(tmp_path), "lessons.jsonl")
        monkeypatch.setattr(Q, "VAR", str(tmp_path))
        monkeypatch.setattr(Q, "LESSONS", lp)
        Q.record_lesson("x", "m", "t", "")
        assert not os.path.exists(lp)
        assert "drop" in capsys.readouterr().err

    def test_repeat_signal_survives_gate(self, tmp_path, monkeypatch):
        """去重与计数并存：同 detail 不同 task_id 全留行（SKILL_MIN 靠它）。"""
        lp = os.path.join(str(tmp_path), "lessons.jsonl")
        monkeypatch.setattr(Q, "VAR", str(tmp_path))
        monkeypatch.setattr(Q, "LESSONS", lp)
        for i in range(3):
            Q.record_lesson("tid%d" % i, "m", "task%d" % i, "例证 same")
        rows = [json.loads(l) for l in open(lp, encoding="utf-8")]
        assert len(rows) == 3


# ── Task 5 · 遗忘四策 ─────────────────────────────────────────
class TestForgetting:
    def _row(self, tid, **kw):
        r = {"task_id": tid, "fail_mode": "m", "task": "t",
             "detail": "d_" + tid, "use_count": 0, "last_used": "",
             "utility": 0.5, "tier": "short", "quality": 0.5,
             "at": "2026-01-01T00:00:00+08:00"}
        r.update(kw)
        return r

    def test_four_bands(self):
        import dwc_lesson_reconcile as RC
        hot = self._row("hot", use_count=9, quality=0.9,
                        last_used="2026-10-14T00:00:00+08:00")
        assert RC.forget_score(hot, "2026-10-15T00:00:00+08:00")[1] == "keep"
        mid = self._row("mid", use_count=2, quality=0.6,
                        last_used="2026-09-01T00:00:00+08:00")
        assert RC.forget_score(mid, "2026-10-15T00:00:00+08:00")[1] \
            == "archive"
        assert RC.forget_score(
            self._row("old", use_count=0, quality=0.4,
                      last_used="2026-01-01T00:00:00+08:00"),
            "2026-10-15T00:00:00+08:00")[1] == "drop"

    def test_merge_marks_origin(self):
        import dwc_lesson_reconcile as RC
        a = self._row("a", detail="第一句。第二句。", quality=0.5,
                      use_count=1, last_used="2026-10-01T00:00:00+08:00")
        b = self._row("b", detail="第二句。第三句。", quality=0.5,
                      use_count=1, last_used="2026-10-01T00:00:00+08:00")
        m = RC._merge_rows([a, b])
        assert "merged_from:2" in m["detail"]
        assert "第一句" in m["detail"] and "第三句" in m["detail"]
        assert len(m["detail"]) <= 300

    def test_protection_period(self):
        """保护期：14 天内的新行不判 archive 以下。"""
        import dwc_lesson_reconcile as RC
        young = self._row("young", use_count=0, quality=0.4,
                          last_used="2026-10-13T00:00:00+08:00")
        assert RC.forget_score(young, "2026-10-15T00:00:00+08:00")[1] \
            in ("keep", "archive")


# ── Task 4 · 程序模板 ─────────────────────────────────────────
class TestTemplates:
    STEPS = [{"desc": "读文档", "op": "read"},
             {"desc": "联网查", "op": "search", "condition": "has_network=true"},
             {"desc": "猜测", "op": "ask", "condition": "mystery=1"}]

    def test_resolve_hit(self, tmp_path):
        from dwc.organs import workflow_templates as WT
        p = str(tmp_path / "wf.jsonl")
        WT.store_template("bench", "read-fact", self.STEPS, path=p)
        got = WT.suggest_workflow("read-fact", {"has_network": "true"},
                                  path=p)
        assert got is not None
        assert [s["op"] for s in got] == ["read", "search", "ask"]
        assert got[2]["unknown_condition"] == "mystery=1"

    def test_resolve_miss(self, tmp_path):
        from dwc.organs import workflow_templates as WT
        p = str(tmp_path / "wf.jsonl")
        WT.store_template("bench", "read-fact", self.STEPS, path=p)
        got = WT.suggest_workflow("read-fact", {"has_network": "false"},
                                  path=p)
        assert [s["op"] for s in got] == ["read", "ask"]

    def test_empty_store_none(self, tmp_path):
        from dwc.organs import workflow_templates as WT
        assert WT.suggest_workflow("zzz", {}, path=str(tmp_path / "n.jsonl")) \
            is None

    def test_empty_steps_raises(self, tmp_path):
        from dwc.organs import workflow_templates as WT
        with pytest.raises(ValueError):
            WT.store_template("empty", "k", [], path=str(tmp_path / "n.jsonl"))

    def test_outcome_moving_average(self, tmp_path):
        from dwc.organs import workflow_templates as WT
        p = str(tmp_path / "wf.jsonl")
        t = WT.store_template("bench", "k", [{"desc": "d", "op": "read"}],
                              path=p)
        assert WT.record_workflow_outcome(t["template_id"], True, path=p)
        assert WT.record_workflow_outcome(t["template_id"], False, path=p)
        got = WT.suggest_workflow("k", {}, path=p)
        assert got is not None
        rows = WT._load(p)
        assert rows[0]["success"] == 0.5  # 0.5→1.0→0.5
        assert not WT.record_workflow_outcome("nope", True, path=p)


# ── Task 6 · Episode 链 ───────────────────────────────────────
class TestEpisodes:
    def test_chain_and_bfs(self, tmp_path):
        import dwc_episodes as EP
        p = str(tmp_path / "ep.jsonl")
        EP.append_episode("t1", "k1", False, path=p)
        EP.append_episode("t2", "k1", False, path=p)
        EP.append_episode("t3", "k1", True, path=p)
        EP.append_episode("x1", "k2", True, path=p)
        EP.append_episode("t4", "k1", True, path=p)
        got = EP.related("t2", depth=1, path=p)
        tids = [r["task_id"] for r in got]
        assert tids == ["t1", "t2", "t3"]  # 前/自/后，异 kind 不在内

    def test_empty_none(self, tmp_path):
        import dwc_episodes as EP
        assert EP.related("nope", path=str(tmp_path / "n.jsonl")) == []


# ── Task 7 · 效用 ─────────────────────────────────────────────
class TestUtility:
    def _lp(self, tmp_path, n_used, n_fresh=0):
        import dwc_memory_utility as MU
        p = str(tmp_path / "lessons.jsonl")
        rows = []
        for i in range(n_used):
            rows.append({"task_id": "u%d" % i, "fail_mode": "m",
                         "task": "字符码 任务", "detail": "d",
                         "use_count": 3, "utility": 0.6})
        for i in range(n_fresh):
            rows.append({"task_id": "f%d" % i, "fail_mode": "m",
                         "task": "别的", "detail": "d", "use_count": 0,
                         "utility": 0.5})
        with open(p, "w", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
        return MU, p

    def test_hit_ok_up_fail_flat(self, tmp_path):
        MU, p = self._lp(tmp_path, 1, 1)
        r = MU.update_utility([{"task": "字符码 任务是什么", "ok": True},
                               {"task": "别的 任务", "ok": False}],
                              lessons_path=p)
        assert r["updated"] == 1
        rows = {x["task_id"]: x for x in
                (json.loads(l) for l in open(p, encoding="utf-8"))}
        assert rows["u0"]["utility"] == round(0.7 * 0.99, 4)
        assert rows["f0"]["utility"] == round(0.5 * 0.99, 4)

    def test_readiness_gate(self, tmp_path):
        MU, p = self._lp(tmp_path, 3)
        ok, why = MU.readiness(p)
        assert not ok and "继续积累" in why
        MU2, p2 = self._lp(tmp_path, 20)
        assert MU2.readiness(p2)[0]

    def test_utility_tiebreak(self, tmp_path, monkeypatch):
        """效用次级键：同 use_count 时 utility 高者留。"""
        lp = _mklessons_file(tmp_path, [
            {"task_id": "lo", "fail_mode": "m", "task": "t", "detail": "d",
             "use_count": 5, "utility": 0.5},
            {"task_id": "hi", "fail_mode": "m", "task": "t", "detail": "d",
             "use_count": 5, "utility": 0.9}])
        ap = os.path.join(str(tmp_path), "arch.jsonl")
        monkeypatch.setattr(Q, "LESSONS", lp)
        monkeypatch.setattr(Q, "LESSONS_ARCHIVE", ap)
        assert Q.enforce_tier_capacity(short=1) == 1
        rows = [json.loads(l) for l in open(lp, encoding="utf-8")]
        assert [r["task_id"] for r in rows] == ["hi"]


# ── 破坏性路径（Rule E：raises 占比 ≥5%） ──────────────────────
class TestDestructive:
    def test_merge_empty_raises(self):
        import dwc_lesson_reconcile as RC
        with pytest.raises(ValueError):
            RC._merge_rows([])
