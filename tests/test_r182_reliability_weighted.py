# -*- coding: utf-8 -*-
"""R182 · A_train 精化（reliability-weighted 共识 — κ=10 有据, 论文逐字）。

论文（2607.12790 §2.4 逐字）:
  "共识是 reliability-weighted: 每个 opining op 的票按
   1/(1+κ·max(0,m_o)) 缩放, m_o 是该 op 的锚定 leave-one-out marginal"
  ⇒ "anchor-proven ops lead and unproven ops vote near-neutrally"
  Appendix C: κ = 10; grace = 2 轮（非正边际退役）

验收:
  □ loo_marginal_dev: 拿掉 op 前后 dev 判定变化率; 固定 root 不可拿
  □ reliability_weight: m=None ⇒ 1.0（中性）; m 大 ⇒ 权重趋 0（κ=10 实算）
  □ a_train_weighted: abstain 不进分子分母; 全 abstain ⇒ None（fail-closed）
  □ 手工对账公式: Σ w_o·clean / Σ w_o（不放水 — 实测数字逐位核过）
  □ R176 三态纪律延续: 无 train ⇒ None（不是 0）
"""
from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.organs.drawback import Node                     # noqa: E402
from dwc.organs.metric_loop import (a_train_weighted,    # noqa: E402
                                    loo_marginal_dev,
                                    reliability_weight)

INC = None


def _inc():
    from dwc.organs.metric_loop import _current_tree
    return _current_tree()


def _pt(pr, diff="", comp="prompt"):
    return {"label": pr < 1.0,
            "ctx": {"judge_success": pr >= 1.0, "pass_rate": pr,
                    "candidate_diff": diff, "vocabulary": (),
                    "component": comp, "parsed_ok": True}}


def test_reliability_weight_kappa10():
    """★★★ κ=10 实算（论文常数 — 不是调参旋钮）。"""
    assert reliability_weight(None) == 1.0          # 无 marginal ⇒ 中性票
    assert reliability_weight(0.0) == 1.0           # 零边际 ⇒ 锚定证明过
    # m=0.25 ⇒ 1/(1+2.5) = 0.2857…
    assert abs(reliability_weight(0.25) - 0.2857142857) < 1e-6
    assert reliability_weight(1.0) < 0.1            # 全不一致 ⇒ 近零票


def test_loo_marginal_root_not_droppable():
    """★★★ 固定 root 不可拿（构造保证 — 论文 fixed root conjoined）。"""
    m = loo_marginal_dev([_pt(0.5)], "root_parse_ok", _inc())
    assert m is None                               # 不造 marginal


def test_loo_marginal_absent_op_none():
    """★ 树不含该 op ⇒ None（无 marginal 可算 — 缺席≠0）。"""
    m = loo_marginal_dev([_pt(0.5)], "no_such_op", _inc())
    assert m is None


def test_loo_marginal_empty_dev_none():
    """★ 无 dev 点 ⇒ None（fail-closed）。"""
    assert loo_marginal_dev([], "judge_verdict", _inc()) is None


def test_loo_marginal_zero_when_and_tree_unmoved():
    """★★ and 树上单 op 边际多为 0（其余 op 已判 drawback ⇒ 支配）。

    ★ 这是 and 树的真实性质 — LOO 要抓的正是它: 现任表达式已被锚定,
      单 op 拿不拿都不改判定 ⇒ m=0 ⇒ 权重 1（anchor-proven）。
    """
    m = loo_marginal_dev([_pt(0.5), _pt(1.0)], "judge_verdict", _inc())
    assert m == 0.0 or m is None


def test_a_train_abstain_excluded():
    """★★★ abstain 不进分子分母（三值第三态 — 不是同意也不是反对）。"""
    tree = Node(kind="leaf", op="golden_leak")     # 该 op 多数 ctx abstain
    tv = {"golden_leak": "abstain"}
    assert a_train_weighted([tv], tree, {}) is None


def test_a_train_manual_arithmetic():
    """★★★ 公式手工对账: Σ w·clean / Σ w（实测数字逐位核过 — 不放水）。

    ops: root(clean,w=1) + nonempty(clean,w=1/3.5≈0.2857)
         + judge(drawback,w=1) ⇒ num=1.2857, den=3.2857 ⇒ 0.3913…
    """
    tree = Node(kind="and", children=(
        Node(kind="and", children=(Node(kind="leaf", op="root_parse_ok"),
                                   Node(kind="leaf", op="nonempty_diff"))),
        Node(kind="leaf", op="judge_verdict")))
    tv = {"root_parse_ok": "clean", "nonempty_diff": "clean",
          "judge_verdict": "drawback"}
    marg = {"nonempty_diff": 0.25}                 # w=0.2857
    a = a_train_weighted([tv], tree, marg)
    expect = (1.0 + (1.0 / 3.5)) / (1.0 + (1.0 / 3.5) + 1.0)
    assert abs(a - expect) < 1e-9


def test_a_train_no_train_none_fail_closed():
    """★★★ 无 train ⇒ None（R176 三态纪律 — 缺席不是 0, 不造共识）。"""
    assert a_train_weighted([], _inc(), {}) is None
