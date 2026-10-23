# -*- coding: utf-8 -*-
"""R179 · Metric Loop 真数据面（judge.task_scores(dev) ⇒ dev_points ⇒ select）。

验收（本地全可复现 — 用协议级假 store; 真 store 走 e2e 街）:
  □ _ctx_from_evidence: verdict dict ⇒ op ctx（success/pass_rate 投影 —
    label 唯一源 = success, 不用 score 阈值造第二口径）
  □ dev_points_from_store: 每点 label + 每树 _eval 三态判定
  □ 缺席诚实化: evidence 不可解析 / success=None ⇒ 跳过并计数
  □ fail-closed: 无 dev 点 ⇒ MetricLoopError（不拿空集当"全过"）
  □ select 在真选择集: validity 拦恒定/全 abstain ⇒ 取有效 argmax
"""
from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.organs.metric_loop import (MetricLoopError,  # noqa: E402
                                    _ctx_from_evidence, dev_points_from_store,
                                    select)


class _P:
    def __init__(self, tid, ref, score):
        self.task_id = tid
        self.evidence_ref = ref
        self.score = score


EVI = {
    "ev#1": {"success": False, "k_passed": 2, "n_checks": 4,
             "candidate_diff": "x", "vocabulary": ("D1",),
             "checks": [{"component": "control_flow"}]},
    "ev#2": {"success": True, "k_passed": 4, "n_checks": 4,
             "candidate_diff": "", "vocabulary": (),
             "checks": [{"component": "prompt"}]},
    "ev#3": {"success": None, "k_passed": 1, "n_checks": 4,
             "candidate_diff": "", "vocabulary": (),
             "checks": [{"component": "prompt"}]},
}


class FakeStore:
    """协议级替身（task_scores + evidence 两个方法的形态对齐）。"""

    def __init__(self, points):
        self._pts = points

    def task_scores(self, split=None, wm_version=None):
        return self._pts[:]

    def evidence(self, ref):
        return EVI[ref]


def test_ctx_from_evidence_projections():
    """★ ctx 投影: success 原样 · pass_rate=k/n · diff/vocab/component。"""
    c = _ctx_from_evidence(EVI["ev#1"])
    assert c["judge_success"] is False
    assert c["pass_rate"] == 0.5
    assert c["component"] == "control_flow"
    assert c["parsed_ok"] is True             # verdict 在场即解析过


def test_ctx_missing_fields_none():
    """★ 缺字段 ⇒ None（op 对该面 abstain — 三值第三态, 不造值）。"""
    c = _ctx_from_evidence({"success": True, "k_passed": 1, "n_checks": 1})
    assert c["candidate_diff"] is None and c["component"] is None


def test_dev_points_labels_and_three_valued():
    """★★★ label=success（唯一源 — score 阈值不造第二口径）。

    ★ ev#3 success=None ⇒ 跳过并计数（judge record 同纪律 — None 不记）
    """
    st = FakeStore([_P("t1", "ev#1", 0.5), _P("t2", "ev#2", 1.0),
                    _P("t3", "ev#3", 0.25)])
    pts, notes = dev_points_from_store(st, split="dev")
    assert [p["label"] for p in pts] == [False, True]
    assert notes["n_points"] == 2 and notes["n_skipped"] == 1
    # ★★ 三态在场: 每点的树判定集合 ⊆ {clean,drawback,abstain}
    for p in pts:
        assert set(p["tree_verdicts"].values()) <= {"clean", "drawback",
                                                    "abstain"}


def test_dev_points_zero_points_fail_closed():
    """★★★ 无 dev 点 ⇒ MetricLoopError（不拿空集当'全过' — unselectable）。"""
    with pytest.raises(MetricLoopError) as e:
        dev_points_from_store(FakeStore([_P("t3", "ev#3", 0.25)]))
    assert "fail-closed" in str(e.value) or "unselectable" in str(e.value)


def test_dev_points_evidence_unresolvable_all_fail_closed():
    """★★★ evidence 全不可解析 ⇒ 无点 ⇒ raise（fail-closed 不例外）。

    ★ R179 实测纠偏: 我第一版此测试期待"返回 n_skipped=2" — 错: 全炸时
      正确行为是 **raise**（与 zero_points 同一条 fail-closed 纪律 — 半
      可用点集会返回带 n_skipped 的真数据, 但全不可解析 = 无数据面）
    """

    class _BadStore(FakeStore):
        def evidence(self, ref):
            raise KeyError(ref)

    st = _BadStore([_P("t1", "ev#1", 0.5), _P("t2", "ev#2", 1.0)])
    with pytest.raises(MetricLoopError) as e:
        dev_points_from_store(st)
    assert "fail-closed" in str(e.value)


def test_dev_points_partial_skip_returns_real_data():
    """★★ 部分点可解析 ⇒ 返回真数据 + n_skipped（不是全或无）。"""

    class _HalfStore(FakeStore):
        def evidence(self, ref):
            if ref == "ev#2":
                raise KeyError(ref)
            return EVI[ref]

    st = _HalfStore([_P("t1", "ev#1", 0.5), _P("t2", "ev#2", 1.0)])
    pts, notes = dev_points_from_store(st)
    assert notes["n_points"] == 1 and notes["n_skipped"] == 1


def test_select_on_real_dev_surface():
    """★★★ 真数据面 select: validity 拦全 abstain ⇒ 有效集中 argmax。"""
    st = FakeStore([_P("t1", "ev#1", 0.5), _P("t2", "ev#2", 1.0)])
    pts, _ = dev_points_from_store(st)
    r = select(pts, a_train=0.5)
    valid = [c for c in r["candidates"] if c["valid"]]
    assert valid, "至少应有有效候选"
    if r["picked_key"] is not None:
        # ★ argmax 纪律: picked 是 valid 中 S 最大者
        best = max(valid, key=lambda c: (c["s"], c["key"]))
        assert r["s"] == best["s"]
