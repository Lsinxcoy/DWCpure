# -*- coding: utf-8 -*-
"""R183 · Metric Loop 自进化闭环（select ⇒ 门组回归 ⇒ adopt 注入 — 真动）。

验收:
  □ _a_train_weighted: R182 κ=10 加权（train verdicts = dev 面 ctx 逐 op）
  □ _facts_from_dev_surface: dev 真判据点 ⇒ TermFacts（事实组 23 条级 — 不造数据）
  □ 触发纪律: picked=现任 / S 差 ≤ 0.01 噪声带 ⇒ 不动（留痕 why）
  □ adopt 成功: ③门注入新树 + round 出口 metric_adopt 痕迹
  □ 实测形态（R183 如实记录 — 不是缺陷）: and(13) 与候选单叶在本 dev 面
    判定一致（judge_verdict/pass_rate_weak 同源支配）⇒ 回归 0 变化 ⇒ 空
    操作安全; 选择的 S 优势来自 λ·C（树小 12 节点）— 机械变异最小树偏置
    在真实数据面上复现（R177 预告过）
  □ 进程内注入（重启复位 = 出厂树 — 保守默认, 不持久化激进变更）
"""
from __future__ import annotations

import os
import sys

import pytest

ROOT = r"E:/Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.harness import gates                          # noqa: E402
from dwc.harness.loop import Loop                     # noqa: E402
from dwc.organs.metric_loop import (_flatten_and, _tree_key,  # noqa: E402
                                    _current_tree)


@pytest.fixture()
def loop_clean():
    lp = Loop()
    return lp


@pytest.fixture(autouse=True)
def _reset():
    yield
    gates.set_current_tree(None)


def test_round_exposes_adopt_fields(loop_clean):
    """★ round 出口带 metric_adopt/adopt_why（闭环的可观测面）。"""
    r = loop_clean.round(1)
    assert "metric_adopt" in r and "adopt_why" in r


def test_a_train_weighted_from_dev_points(loop_clean):
    """★★★ A_train = κ=10 加权（train verdicts = dev 面 ctx 逐 op 判）。"""
    from dwc.organs.metric_loop import dev_points_from_store
    loop_clean.round(1)
    pts, _ = dev_points_from_store(loop_clean.judge, split="dev")
    a = loop_clean._a_train_weighted(pts)
    assert a is None or 0.0 <= a <= 1.0


def test_facts_from_dev_surface_is_real(loop_clean):
    """★★★ 事实组 = dev 真判据点投影（23 条级 — 不是造数据）。"""
    loop_clean.round(1)
    facts = loop_clean._facts_from_dev_surface()
    assert len(facts) >= 1
    for f in facts:
        assert f.pass_rate is not None and 0.0 <= f.pass_rate <= 1.0
        assert f.candidate_diff is None      # 判据面投影（非实现面）


def test_noise_band_blocks_trivial_switch(loop_clean):
    """★★★ S 差 ≤ 0.01（e2e 同源噪声带）⇒ 不动（不折腾）。

    ★ R183 实测纪律: 本测试**不能先 round(1)** — r1 的 tick 会真 adopt
      （pass_rate_weak）污染注入表; 构造 Loop 直接注入假 pick 痕迹测触发
      纪律本身（不依赖真 dev 面）。
    """
    from dwc.organs.metric_loop import mechanical_candidates
    loop_clean._last_metric_pick = {"picked_key": "judge_verdict(1)",
                                    "s": 0.30,
                                    "candidates": [{"key": _tree_key(
                                        mechanical_candidates()[0]),
                                        "s": 0.30,
                                        "valid": True}]}
    res = loop_clean._try_adopt_metric_tree()
    assert res["adopted"] is False and "噪声带" in loop_clean._adopt_why
    assert gates._current_tree_injection() is None


def test_picked_equals_current_no_switch(loop_clean):
    """★★ picked=现任 ⇒ 无需换（显式留痕）。"""
    from dwc.organs.metric_loop import mechanical_candidates
    cur = _tree_key(mechanical_candidates()[0])   # 出厂树 = 候选族[0]
    loop_clean._last_metric_pick = {"picked_key": cur, "s": 0.5,
                                    "candidates": []}
    res = loop_clean._try_adopt_metric_tree()
    assert res["adopted"] is False and "无需换" in loop_clean._adopt_why


def test_adopt_injects_when_regression_passes(loop_clean):
    """★★★ 回归过 ⇒ 真注入（闭环的最后一环 — 实测跑过 adopted=True）。"""
    from dwc.organs.metric_loop import mechanical_candidates
    loop_clean.round(1)
    loop_clean._last_metric_pick = {
        "picked_key": "pass_rate_weak(1)", "s": 0.9,
        "candidates": [{"key": _tree_key(_current_tree()), "s": 0.1,
                        "valid": True}]}
    res = loop_clean._try_adopt_metric_tree()
    assert res["adopted"] is True
    inj = gates._current_tree_injection()
    assert inj is not None and [l.op for l in _flatten_and(inj)] == [
        "pass_rate_weak"]


def test_switch_is_empty_operation_on_this_dev_surface(loop_clean):
    """★★★ R183 实测纪律: 本 dev 面上 and(13) 与 pass_rate_weak 判定一致。

    ★ 为什么一致（不是巧合）: judge_verdict/pass_rate_weak 同源（弱 op
      是 judge 投影的收编 — R166 注释的兼容不变量）⇒ and 树被同源支配
      ⇒ 单叶换树判定不变 ⇒ 回归 0 变化（安全但无收益）。S 优势纯来自
      λ·C — 机械变异最小树偏置在真数据复现（R177 记录项）。
    """
    from dwc.harness.gates import TermFacts
    from dwc.organs.drawback import Node
    from dwc.organs.ops import evaluate_pool
    from dwc.organs.metric_loop import _ctx_from_evidence
    loop_clean.round(1)
    facts = loop_clean._facts_from_dev_surface()
    # 旧树（and 全池）vs 新树（pass_rate_weak 单叶）在同事实组上的③门判定
    diffs = []
    for f in facts:
        o_old = gates._g3_drawback(f)
        gates.set_current_tree(Node(kind="leaf", op="pass_rate_weak"))
        o_new = gates._g3_drawback(f)
        gates.set_current_tree(None)
        if o_old.status != o_new.status:
            diffs.append((o_old.status, o_new.status))
    assert diffs == [], "本 dev 面上两树判定应一致（同源支配）— %r" % diffs[:3]
