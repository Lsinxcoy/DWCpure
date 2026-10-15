# -*- coding: utf-8 -*-
"""R160 · held_out 数据面 — split 门 na⇒passed 的通路（dev × test 两真 split）。

验收:
  □ _tasks_of: dev ⇒ judge.anchors / test ⇒ judge.sealed（真实属性 — R160 核实）
  □ _ 元键排除（_provenance/_split 不是任务）
  □ feed: 两 split 各聚合出 in/ho 口径（缺席 ⇒ None, 不造 0.0）
  □ feed_pair: baseline/current 一对 ⇒ accept 弹药（in_score 缺席即拒）
  □ split 组合裁决在档（A 案: 不切 dev）
  □ test 锁定纪律在档（防泄漏 — R147 同族精神）
  □ 接 R159: 真配 baseline/current ⇒ split 门从 na 变 passed（端到端）
"""
from __future__ import annotations

import os
import sys

import pytest

ROOT = r"E:/Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.harness.splitfeed import (  # noqa: E402
    HELD_IN_SPLIT, HELD_OUT_SPLIT, SPLITFEED_MECHANICS, SplitFeedError,
    SplitScores, feed, feed_pair)


class _StubJudge:
    """最小 judge 替身（只持 anchors/sealed + evaluate 计数面）。"""

    def __init__(self, anchors, sealed=None, pass_all=False):
        self.anchors = anchors
        self.sealed = sealed
        self._pass_all = pass_all
        self.calls = []

    def evaluate(self, task_id, split, observed=None):
        from dwc.organs.judge import Verdict
        self.calls.append((task_id, split))
        # ★ overall_score 吃 n_checks/k_passed（micro 平均 — 不是 success）
        return Verdict(task_id=task_id, split=split,
                       success=bool(self._pass_all), reason="stub",
                       n_checks=2, k_passed=(2 if self._pass_all else 0))


def _anchors(n):
    return dict([("_provenance", {"note": "meta"}),
                 ("_split", {"val": []})] +
                [("t_%d" % i, {"kind": "behavior"}) for i in range(n)])


def test_tasks_of_real_judge():
    """★★ 真 judge: dev/test 任务数从 anchors 实算（R160 核实的真实 split）。"""
    from dwc.organs.judge import Judge
    from dwc.harness.splitfeed import _tasks_of
    j = Judge()
    dev = _tasks_of(j, "dev")
    tst = _tasks_of(j, "test")
    # ★ R287-E · 动态口径（anchor+3 根因：dev 13→16。test split 未动。
    #   意图是"两 split 真实划分"，数字实算 —— 下次 anchor+1 不炸。）
    _n_dev = len([k for k in j.anchors if not str(k).startswith("_")])
    assert len(dev) == _n_dev and len(tst) == 10, (len(dev), len(tst))
    assert not any(t.startswith("_") for t in dev + tst)   # 元键排除
    assert set(dev) & set(tst) == set()                   # 互不相交


def test_feed_aggregates_both_splits():
    """★ feed: dev+test 两 split 都跑 ⇒ in_score/held_out_score 双口径。"""
    j = _StubJudge(_anchors(3), sealed=_anchors(2), pass_all=True)
    s = feed(j, lambda tid: {"x": 1})
    assert isinstance(s, SplitScores)
    assert s.in_score == 1.0 and s.held_out_score == 1.0
    assert len(j.calls) == 5                     # 3 dev + 2 test 真跑过
    assert s.in_detail["n_tasks"] == 3


def test_absent_split_none_not_zero():
    """★★ test_sealed 缺席 ⇒ ho 口径 None（不拼 0.0 — accept 会判 blocked）。"""
    j = _StubJudge(_anchors(3), sealed=None, pass_all=True)
    s = feed(j, lambda tid: {"x": 1})
    assert s.in_score == 1.0                      # in 真判过
    assert s.held_out_score is None               # ★ ho 缺席 ⇒ None 不是 0.0
    assert "不拼 dev 副本" in s.held_out_detail["note"]


def test_feed_pair_ok_and_in_absent_rejected():
    """★ feed_pair: 双 split 齐 ⇒ 一对 accept 弹药; in 缺席 ⇒ 显式拒。"""
    j_ok = _StubJudge(_anchors(2), sealed=_anchors(2), pass_all=True)
    base, cur = feed_pair(j_ok, lambda t: {"x": 1}, lambda t: {"x": 2})
    assert base.keys() == {"in_score", "held_out_score"}
    assert base["in_score"] == 1.0 and base["held_out_score"] == 1.0
    j_bad = _StubJudge({}, sealed=None)          # 无 dev 锚
    with pytest.raises(SplitFeedError):
        feed_pair(j_bad, lambda t: {}, lambda t: {})


def test_split_gate_flips_na_to_passed():
    """★★★ R159 × R160 闭环: feed_pair 产弹 ⇒ split 门 na ⇒ passed。"""
    from dwc.harness.gates import TermFacts, run_gates
    j = _StubJudge(_anchors(4), sealed=_anchors(4), pass_all=True)
    base, cur = feed_pair(j, lambda t: {"x": 1}, lambda t: {"x": 2})
    out = run_gates(TermFacts(pass_rate=1.0, baseline=base, current=cur))
    g4 = [g for g in out["gates"] if g["gate"] == "split"][0]
    # base == cur（stub 全过同分）⇒ max(Δ)=0 ⇒ accept 拒 ⇒ blocked
    #   — 这是对的口径（无变化 = 空过）, 不是 na!
    assert g4["status"] == "blocked"
    assert g4["detail"]["split"]["decision"] == "rejected"
    # 再验: cur 真的更高 ⇒ passed
    cur2 = {"in_score": 1.0, "held_out_score": 1.0}
    base2 = {"in_score": 0.5, "held_out_score": 0.5}
    out2 = run_gates(TermFacts(pass_rate=1.0, baseline=base2, current=cur2))
    g4b = [g for g in out2["gates"] if g["gate"] == "split"][0]
    assert g4b["status"] == "passed"


def test_mechanics_documented():
    """A 案裁决 + test 锁定 + 同口径对在档。"""
    assert "dev(10 条)" in SPLITFEED_MECHANICS["split_combo"]
    assert "metric evolution" in SPLITFEED_MECHANICS["test_lock"]
    assert "同口径" in SPLITFEED_MECHANICS["same_judge_pair"]
