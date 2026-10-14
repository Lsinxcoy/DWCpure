# -*- coding: utf-8 -*-
"""R269 · RSIAgent 营养吸收（经验闭环/对账/语义停止/记忆快照/终态机）。

★ 全文件零真 LLM 调用；reconcile 的 LLM 点可注入 fake（llm=None 走规则后备）。
★ nightbench/agent_rpc 写操作一律经 conftest 的 DWC_VAR_DIR tmp 隔离。
"""
from __future__ import annotations

import json
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(_HERE)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import dwc_nightbench as NB
from dwc import agent_quality as Q


# ── Task 1 · 经验闭环 ─────────────────────────────────────────
class TestPromote:
    def test_success_row_promotes_success_pattern(self, monkeypatch):
        calls = []
        monkeypatch.setattr(
            Q, "record_lesson",
            lambda task_id, fail_mode, task, detail: calls.append(
                (task_id, fail_mode, task, detail)))
        row = NB._promote_row({"tid": "nb_01", "task_id": "rf01",
                               "kind": "read-fact",
                               "task": "字符码是什么", "ok": True,
                               "verify": "answer contains '0xfeff'"})
        assert row["mode"] == "success_pattern:read-fact"
        assert calls and calls[0][1] == "success_pattern:read-fact"

    def test_fail_row_uses_plain_mode(self, monkeypatch):
        calls = []
        monkeypatch.setattr(
            Q, "record_lesson",
            lambda task_id, fail_mode, task, detail: calls.append(
                (task_id, fail_mode, task, detail)))
        NB._promote_row({"tid": "nb_02", "task_id": "rf02",
                         "kind": "read-fact", "task": "快捷键是什么",
                         "ok": False, "verify": "answer contains 'Ctrl+P'"})
        assert calls and calls[0][1] == "nightbench_fail"

    def test_success_renders_its_own_header(self, tmp_path, monkeypatch):
        monkeypatch.setattr(Q, "VAR", str(tmp_path))
        monkeypatch.setattr(Q, "LESSONS",
                            os.path.join(str(tmp_path), "lessons.jsonl"))
        Q.record_lesson("rf01", "success_pattern:read-fact",
                        "字符码任务", "核对原文字符码")
        txt = Q.lessons_context("字符码任务")
        assert "成功做法" in txt


# ── Task 2 · 对账 ─────────────────────────────────────────────
class TestReconcile:
    FAKE = [
        {"task_id": "a1", "fail_mode": "m1", "task": "t",
         "detail": "d same"},
        {"task_id": "a1", "fail_mode": "m1", "task": "t",
         "detail": "d same"},
        {"task_id": "a2", "fail_mode": "m1", "task": "t",
         "detail": "d other"},
        {"task_id": "b1", "fail_mode": "m2", "task": "t2",
         "detail": "d2"},
    ]

    def test_group_by_mode(self):
        import dwc_lesson_reconcile as RC
        g = RC._group_by_mode(self.FAKE)
        assert set(g) == {"m1", "m2"} and len(g["m1"]) == 3

    def test_exact_dupes(self):
        import dwc_lesson_reconcile as RC
        d = RC._exact_dupes(self.FAKE)
        assert len(d) == 1 and d[0]["task_id"] == "a1"

    def test_rule_fallback_drops_only_dupes(self):
        import dwc_lesson_reconcile as RC
        r = RC._review_group("m1", self.FAKE[:3], llm=None)
        assert len(r["drop"]) == 1 and not r["merge"]

    def test_dry_run_writes_nothing(self, tmp_path, monkeypatch):
        import dwc_lesson_reconcile as RC
        lp = os.path.join(str(tmp_path), "lessons.jsonl")
        with open(lp, "w", encoding="utf-8") as fh:
            for row in self.FAKE:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        monkeypatch.setattr(RC, "LESSONS_PATH", lp)
        n = RC.main(["--dry-run"])
        assert n == 0
        assert len(open(lp, encoding="utf-8").readlines()) == 4


# ── Task 3 · 语义停止 ─────────────────────────────────────────
class TestStopping:
    def test_three_ok_stops(self):
        hist = [{"ok": True, "verify": "a"} for _ in range(3)]
        stop, reason = NB._should_stop(hist)
        assert stop and reason == "SATURATED"

    def test_fail_breaks_streak(self):
        hist = [{"ok": True, "verify": "a"}, {"ok": True, "verify": "a"},
                {"ok": False, "verify": "b"}]
        stop, _ = NB._should_stop(hist)
        assert not stop

    def test_empty_never_stops(self):
        assert NB._should_stop([]) == (False, "")

    def test_bonus_capped_at_two(self):
        n = 0
        for _ in range(4):
            if NB._unseen_fail(False, "new-fail-xyz", set(), n):
                n += 1
        assert n == 2

    def test_seen_fail_no_bonus(self):
        assert not NB._unseen_fail(False, "known", {"known"}, 0)
        assert not NB._unseen_fail(True, "new", set(), 0)


# ── Task 4 · 记忆快照 ─────────────────────────────────────────
class TestSnapshot:
    def test_hash_stable(self, tmp_path, monkeypatch):
        monkeypatch.setattr(Q, "VAR", str(tmp_path))
        monkeypatch.setattr(Q, "LESSONS",
                            os.path.join(str(tmp_path), "lessons.jsonl"))
        monkeypatch.setattr(Q, "SKILLS_DIR", str(tmp_path))
        Q.record_lesson("a", "m", "task one", "detail one")
        assert Q.memory_snapshot_hash() == Q.memory_snapshot_hash()

    def test_hash_changes(self, tmp_path, monkeypatch):
        monkeypatch.setattr(Q, "VAR", str(tmp_path))
        monkeypatch.setattr(Q, "LESSONS",
                            os.path.join(str(tmp_path), "lessons.jsonl"))
        monkeypatch.setattr(Q, "SKILLS_DIR", str(tmp_path))
        Q.record_lesson("a", "m", "task one", "detail one")
        h1 = Q.memory_snapshot_hash()
        Q.record_lesson("b", "m", "task two", "detail two")
        assert Q.memory_snapshot_hash() != h1

    def test_missing_file_empty(self, tmp_path, monkeypatch):
        monkeypatch.setattr(Q, "VAR", str(tmp_path))
        monkeypatch.setattr(Q, "LESSONS",
                            os.path.join(str(tmp_path), "nope.jsonl"))
        monkeypatch.setattr(Q, "SKILLS_DIR",
                            os.path.join(str(tmp_path), "nope_dir"))
        assert Q.memory_snapshot_hash() == "empty"


# ── Task 5 · 终态机 ───────────────────────────────────────────
class TestTerminal:
    def test_done(self):
        assert NB._terminal_state(True, {"status": "done"}) == "DONE"

    def test_fail(self):
        assert NB._terminal_state(False, {"status": "done"}) == "FAIL"

    def test_stalled_empty_report(self):
        assert NB._terminal_state(False, {}) == "STALLED"
        assert NB._terminal_state(False, None) == "STALLED"

    def test_stalled_escalates_to_inbox(self, monkeypatch):
        calls = []
        monkeypatch.setattr(NB, "_inbox_push",
                            lambda task, tid: calls.append((task, tid)))
        st = NB._terminal_state(False, {}, tid="nb_1014_01",
                                task="做X任务")
        assert st == "STALLED"
        assert calls and "STALLED" in calls[0][0] and "nb_1014_01" in calls[0][0]

    def test_done_no_escalation(self, monkeypatch):
        calls = []
        monkeypatch.setattr(NB, "_inbox_push",
                            lambda task, tid: calls.append((task, tid)))
        NB._terminal_state(True, {"status": "done"})
        assert calls == []


# ── 破坏性路径（Rule E：raises 占比 ≥5%） ──────────────────────
class TestDestructive:
    def test_reconcile_bogus_flag_exits_2(self):
        import dwc_lesson_reconcile as RC
        with pytest.raises(SystemExit) as ei:
            RC.main(["--bogus-flag"])
        assert ei.value.code == 2

    def test_snapshot_lessons_is_dir_raises(self, tmp_path, monkeypatch):
        monkeypatch.setattr(Q, "VAR", str(tmp_path))
        monkeypatch.setattr(Q, "LESSONS", str(tmp_path))  # 目录非文件
        monkeypatch.setattr(Q, "SKILLS_DIR", str(tmp_path))
        with pytest.raises(OSError):
            Q.memory_snapshot_hash()
