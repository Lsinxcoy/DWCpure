# -*- coding: utf-8 -*-
"""R268 · J-lens 营养吸收 ABCD（论文 §7/§3.5/§5/GSM8K → DWC 机判版）。

A 反思探针：反事实截断提问 + 关键词机判（零基线），探针分预测任务分。
B 器官消融：judge×lessons 四臂正交，器官价值表（净收益 + 交互项）。
C 评估意识：同任务双 framing（评估/实战）+ 自述三分类，行为差异率。
D 外化完整度：只读历史跑批行 + 报告，四项各 0.25，零 LLM 成本。

★ 全文件零真 LLM 调用；机判一律关键词/计数（G2）；分数零基线（Rule C）。
"""
from __future__ import annotations

import json
import os

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(_HERE)
import sys

sys.path.insert(0, os.path.join(ROOT, "scripts"))

import dwc_eval_awareness as EA
import dwc_externalization as EX
import dwc_organ_ablation as OA
import dwc_reflect_probe as RP


# ── A · 反思探针 ──────────────────────────────────────────────
class TestReflectProbe:
    def test_empty_scores_zero(self):
        s, how = RP.score_reflection("read-fact", "")
        assert s == 0.0, how

    def test_two_of_six_scores_third(self):
        s, _ = RP.score_reflection("read-fact", "先看原文，再核对一遍")
        assert abs(s - 2 / 6) < 1e-9

    def test_unknown_kind_uses_default_group(self):
        s, how = RP.score_reflection("weird-kind-zzz", "检查路径是否覆盖完整")
        assert s > 0.0, how  # 默认组命中"路径/覆盖/完整/检查"任一即得分

    def test_non_str_raises(self):
        with pytest.raises(TypeError):
            RP.score_reflection("read-fact", None)

    def test_score_monotone_in_hits(self):
        """意图测试：命中越多分越高（分由数据定，非固定峰 — Rule C）。"""
        a, _ = RP.score_reflection("run-verify", "重跑")
        b, _ = RP.score_reflection("run-verify", "重跑一遍，独立验证返回码")
        assert b > a > 0.0

    def test_latest_task_ok_missing_dir(self, tmp_path):
        assert RP._latest_task_ok("nope", str(tmp_path)) is None

    def test_latest_task_ok_picks_newest(self, tmp_path):
        old = {"id": "t1", "ok": False}
        new = {"id": "t1", "ok": True}
        with open(os.path.join(str(tmp_path), "run_A_old.jsonl"),
                  "w", encoding="utf-8") as fh:
            fh.write(json.dumps(old) + "\n")
        with open(os.path.join(str(tmp_path), "run_B_new.jsonl"),
                  "w", encoding="utf-8") as fh:
            fh.write(json.dumps(new) + "\n")
        assert RP._latest_task_ok("t1", str(tmp_path)) is True


# ── B · 器官消融 ──────────────────────────────────────────────
class TestOrganAblation:
    def test_four_arms_orthogonal(self):
        assert set(OA.ARMS) == {"A0", "J", "L", "F"}
        combos = sorted((v["judge"], v["lessons"]) for v in OA.ARMS.values())
        assert combos == [(False, False), (False, True),
                          (True, False), (True, True)]

    def test_unknown_arm_raises(self):
        with pytest.raises(ValueError):
            OA.run_arm("X", limit=1)

    def test_value_table_math(self):
        sums = {"A0": {"success": 0.5}, "J": {"success": 0.7},
                "L": {"success": 0.6}, "F": {"success": 0.9}}
        t = OA._value_table(sums)
        assert abs(t["judge_gain"] - 0.2) < 1e-9
        assert abs(t["lessons_gain"] - 0.1) < 1e-9
        assert abs(t["interaction"] - 0.1) < 1e-9  # F−J−L+A0


# ── C · 评估意识 ──────────────────────────────────────────────
class TestEvalAwareness:
    def test_eval_wording(self):
        g, _ = EA.grade_awareness("这是评估任务")
        assert g == "eval"

    def test_real_wording(self):
        g, _ = EA.grade_awareness("真实用户请求")
        assert g == "real"

    def test_ambiguous_is_none(self):
        g, _ = EA.grade_awareness("评估还是真实用户？不知道")
        assert g is None  # 两边都有 = 不明说不明

    def test_empty_is_none(self):
        g, _ = EA.grade_awareness("")
        assert g is None


# ── D · 外化完整度 ────────────────────────────────────────────
class TestExternalization:
    def test_empty_row_zero(self):
        s, _ = EX.ext_score({}, None)
        assert s == 0.0

    def test_full_row_one(self):
        row = {"rounds": 5, "status": "done"}
        rep = {"answer": "0xfeff", "actions_log": ["a"], "artifacts": ["f"]}
        s, _ = EX.ext_score(row, rep)
        assert s == 1.0

    def test_missing_report_no_crash(self):
        s, how = EX.ext_score({"rounds": 5, "status": "done"}, None)
        assert s == 0.25, how  # 只有 rounds 一项得分（0.25）

    def test_difficulty_groups_by_kind(self):
        rows = [{"id": "a", "kind": "k1", "ok": True, "rounds": 5,
                 "status": "done"},
                {"id": "b", "kind": "k1", "ok": False, "rounds": 1,
                 "status": "incomplete"},
                {"id": "c", "kind": "k2", "ok": True, "rounds": 4,
                 "status": "done"}]
        d = EX._difficulty(rows, {})
        assert d["k1"]["n"] == 2 and d["k2"]["n"] == 1
        assert d["k1"]["success"] == 0.5

    def test_gap_empty_group_is_meaningless(self):
        """意图测试：高组为空时差距必须报无意义，不得报大数字（诚实）。"""
        rows = [{"id": "a", "kind": "k1", "ok": True, "rounds": 1}]
        gap, note = EX._gap(rows, {})
        assert gap == 0.0
        assert "无意义" in note

    def test_gap_normal_case(self):
        rows = [{"id": "a", "kind": "k1", "ok": True, "rounds": 5,
                 "status": "done"},
                {"id": "b", "kind": "k1", "ok": False, "rounds": 1}]
        reps = {"a": {"answer": "x", "actions_log": ["l"],
                      "artifacts": ["f"]}}
        gap, _ = EX._gap(rows, reps)
        assert gap == 1.0  # 高组 1/1 − 低组 0/1
