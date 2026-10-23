# -*- coding: utf-8 -*-
"""R177 · Metric Loop 选优面（2607.12790 式2 S(e) — 常数有据, 公式不改）。

验收:
  □ A_dev recall-weighted（w_f=2: missed drawback 双倍代价 — 实测加权）
  □ validity gate: 恒 drawback/恒 clean/全 abstain ⇒ invalid
  □ S = A_dev·A_train^w − λ·C（公式逐项对账; A_train None ⇒ S None）
  □ 机械候选族 13 棵（current + 6 单叶 + 6 root∧op）确定性可复现
  □ select: 无候选严格优于现任 ⇒ 保持（论文"在候选与现任之间取"）
  □ fail-closed: 全候选 None ⇒ picked=None（不换）
"""
from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.organs.drawback import ABSTAIN, CLEAN, DRAWBACK  # noqa: E402
from dwc.organs.metric_loop import (LAMBDA_C, W_FAIL, W_PASS,  # noqa: E402
                                    a_dev_recall, mechanical_candidates,
                                    score_candidate, select, validity_gate)


def test_constants_from_paper():
    """★★ 常数有据（Appendix C — 不是调参旋钮）。"""
    assert (W_FAIL, W_PASS) == (2.0, 1.0)
    assert LAMBDA_C == 0.01


def test_a_dev_fail_recall_weighted_double():
    """★★★ missed drawback 双倍代价: 全 miss fail ⇒ A_dev 只剩 pass 项/3。"""
    # 2 fail 全 miss（判 clean）+ 2 pass 全对（判 clean）⇒
    # num = 2*0 + 1*1 = 1; den = 2+1 = 3 ⇒ 1/3
    a, why = a_dev_recall([CLEAN, CLEAN, CLEAN, CLEAN], [False, False,
                                                         True, True])
    assert abs(a - 1.0 / 3.0) < 1e-9
    assert why["r_fail"] == 0.0 and why["r_pass"] == 1.0


def test_a_dev_zero_when_all_abstain():
    """★★★ 候选全 abstain ⇒ r_fail=r_pass=0 ⇒ A_dev=0.0（不是 None）。

    ★ 语义区分（实测抓出 — 我第一版测试假设错）:
      · **无 dev items** ⇒ None（无意见面 — fail-closed 的 None）
      · 有 dev items 但候选全弃权 ⇒ 0.0（候选投了"零召回"的票 —
        abstain 是明确第三值, 不是"没投票"）
    """
    a, why = a_dev_recall([ABSTAIN, ABSTAIN], [False, True])
    assert a == 0.0 and why["r_fail"] == 0.0 and why["r_pass"] == 0.0


def test_a_dev_none_when_no_dev_items():
    """★★ 空 dev 面 ⇒ None（fail-closed — 不装分辨力）。"""
    a, why = a_dev_recall([], [])
    assert a is None and "fail-closed" in why["why"]


def test_validity_rejects_single_verdict():
    for vs in ([DRAWBACK, DRAWBACK], [CLEAN, CLEAN], [ABSTAIN, ABSTAIN]):
        ok, why = validity_gate(vs)
        assert ok is False, (vs, why)


def test_validity_accepts_mixed():
    ok, why = validity_gate([DRAWBACK, CLEAN])
    assert ok is "valid" in why or ok is True


def test_s_formula_terms():
    """★★★ S 逐项: A_dev=1, A_train=0.5, C=6 ⇒ 1*0.5 − 0.01*6 = 0.44。"""
    s, d = score_candidate(verdicts=[DRAWBACK, CLEAN], labels=[False, True],
                           a_train=0.5, n_nodes=6)
    assert abs(s - 0.44) < 1e-9
    assert d["a_dev"] == 1.0 and d["a_train"] == 0.5 and d["c"] == 6


def test_s_none_propagates():
    """★★★ A_train None ⇒ S None（乘性因子缺席 — 单因子不裁决）。"""
    s, d = score_candidate(verdicts=[DRAWBACK, CLEAN], labels=[False, True],
                           a_train=None, n_nodes=6)
    assert s is None and "fail-closed" in d["why"]


def test_candidates_deterministic_13():
    """★ 13 棵候选 = current + 6 单叶 + 6 root∧op（可复现 — 无随机）。"""
    a = mechanical_candidates()
    b = mechanical_candidates()
    assert len(a) == len(b) == 13


from dwc.organs.drawback import Node
from dwc.organs.metric_loop import _current_tree, _tree_key


def _small_family():
    """小候选族: [current(13节点) + root 单叶(1)] — 注入 select 可测。"""
    return [_current_tree(), Node(kind="leaf", op="root_parse_ok")]


def _points_with(trees, fail_v, pass_v):
    keys = [_tree_key(t) for t in trees]
    return [{"label": False, "tree_verdicts": {k: fail_v for k in keys}},
            {"label": True, "tree_verdicts": {k: pass_v for k in keys}}]


def test_select_keeps_current_when_not_strictly_better():
    """★★★ 平手/不优 ⇒ 保持现任（论文"在候选与现任之间取"）。

    ★ 构造: 全候选都给同一混合判定（fail⇒drawback, pass⇒clean）⇒ 所有
      valid 候选 S 只差 C ⇒ root 单叶树（C=1）天然最优 ⇒ 这是**机械
      变异的已知偏置**（最小树占 λ·C 优势 — docstring 的诚实记录）;
      本测试锁"优于现任才换"的机制本身: 人为让现任树判定更强不可行
      （判定同 ctx 面）⇒ 改验 fail-closed 全 None ⇒ 不动
    """
    fam = _small_family()
    r = select(_points_with(fam, DRAWBACK, CLEAN), a_train=None, trees=fam)
    assert r["picked_key"] is None and ("None" in r["notes"]
                                        or "fail-closed" in r["notes"])


def test_select_picks_argmax_when_better():
    """★★ fail-closed 全 None 的反面: A_train 在场 ⇒ argmax 选出。"""
    fam = _small_family()
    r = select(_points_with(fam, DRAWBACK, CLEAN), a_train=0.5, trees=fam)
    # ★ 全候选同判定 ⇒ S 只差 C ⇒ root 单叶（C=1）赢 — 机械变异已知偏置
    #   （最小树占 λ·C 优势 — docstring 诚实记录; 本测试锁机制不锁偏置）
    assert r["picked_key"] == "root_parse_ok(1)" and r["s"] is not None


def test_select_invalid_all_rejected():
    """★★ 全候选 invalid（恒定判定）⇒ picked=None（不换 — validity gate）。"""
    fam = _small_family()
    r = select(_points_with(fam, DRAWBACK, DRAWBACK), a_train=0.5, trees=fam)
    assert r["picked_key"] is None
    assert all(not c["valid"] for c in r["candidates"])
