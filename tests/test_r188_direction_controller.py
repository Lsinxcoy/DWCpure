# -*- coding: utf-8 -*-
"""R188 · DirectionController — 三方向停滞判定 + 序内 fallback + 全败终止。

论文出处（R186 搜到的, 逐条在测试里标）:
  R1 停滞即换    — EvoTS 2608.17933: "invalid or its improvement is no
                     greater than a threshold"
  R2 序内 fallback — 2609.04128 §5.5: "randomly order the three
                     directions ... fall back to the next direction"
  R3 全败记账终止 — 同原文 "The branch terminates only when all three
                     directions fail" + DWC "None 是合法结果"纪律

A×B 收敛（R187）: next_action(state) 一个函数同时吃"时间面"（attempt
  序列 = 何时该换了）吐"空间面"（direction = 换去哪里）。
"""
from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.organs.direction import (                        # noqa: E402
    DirectionAttempt,
    DirectionError,
    EvolutionDirection as D,
    NOISE_BAND,
    REVERSE_MAX_PATCH,
    ensure_direction,
    fallback_order,
    next_action,
    reverse_candidates,
    semantics_of,
    stagnant_of,
)
from dwc.organs.evolver import Mutator                   # noqa: E402


@pytest.fixture(autouse=True)
def _reset():
    yield


# ── R2 · fallback 序（04128 "randomly order"）───────────────
def test_order_is_deterministic_permutation():
    """★ 同 (round,task) ⇒ 同序, 且三方向全在内（不是子集）。"""
    for rn, tid in [(1, "code_fix_001"), (7, "reasoning_003")]:
        o = fallback_order(rn, tid)
        assert set(o) == set(D), "三方向必须在序内（锁3 — 不预删）"
        assert len(o) == 3
        assert o == fallback_order(rn, tid), "可复现（不用真随机）"


def test_order_varies_across_round_and_task():
    """★★ 04128 要 vary — 别每轮同首发方向（造成系统性偏置）。"""
    base = fallback_order(1, "code_fix_001")
    assert fallback_order(2, "code_fix_001") != base, "换轮要换序"
    assert fallback_order(1, "code_fix_002") != base, "换任务要换序"


def test_order_rejects_garbage_seed():
    """★ round_no/task_id 非类型 ⇒ DirectionError（不静默 stringify 兜底
    — 不可复现的序比炸更贵）。"""
    with pytest.raises(DirectionError):
        fallback_order(None, "t")           # type: ignore[arg-type]
    with pytest.raises(DirectionError):
        fallback_order("1", "t")            # type: ignore[arg-type]


# ── R1 · 停滞判定（EvoTS 原文三态）────────────────────────
def test_stagnant_covers_all_three_forms():
    """★★★ 无效 / 增益≤噪声带（含负） / 无候选 ⇒ 都停滞。"""
    assert stagnant_of(DirectionAttempt(D.FORWARD, verdict="blocked"))
    assert stagnant_of(DirectionAttempt(D.FORWARD, verdict="error"))
    assert stagnant_of(DirectionAttempt(D.FORWARD, score_gain=0.0))
    assert stagnant_of(DirectionAttempt(D.FORWARD, score_gain=-0.4))
    assert stagnant_of(DirectionAttempt(
        D.FORWARD, score_gain=NOISE_BAND))          # 边界值也停
    assert stagnant_of(DirectionAttempt(D.FORWARD, n_candidates=0))


def test_not_stagnant_when_no_info_or_real_gain():
    """★★★ 首试（全 None）与真增益 ⇒ **不**停滞（没信息不下判）。"""
    assert not stagnant_of(DirectionAttempt(D.FORWARD)), "首试不下'无增益'判"
    assert not stagnant_of(DirectionAttempt(
        D.FORWARD, verdict="idle", score_gain=None, n_candidates=-1))
    assert not stagnant_of(DirectionAttempt(
        D.FORWARD, score_gain=NOISE_BAND + 1e-6, verdict="all_applicable_passed",
        n_candidates=2))


def test_stagnant_n_candidates_unset_is_not_zero():
    """★★ 未填（-1）≠ 0（R188 smoke 抓到: 默认0让首试被误判形态③）。"""
    assert not stagnant_of(DirectionAttempt(D.FORWARD, n_candidates=-1))
    assert stagnant_of(DirectionAttempt(D.FORWARD, n_candidates=0))


# ── R2+R3 · 链推进与全败终止 ────────────────────────────────
def test_chain_picks_untried_then_advances():
    """★★★ 首发未试方向; 首发停滞 ⇒ 序内下一个（不回退）。"""
    state: list = []
    d1 = next_action(state, 1, "t").direction
    assert d1 in set(D)
    state.append(DirectionAttempt(d1, verdict="blocked"))     # 首发停滞
    d2 = next_action(state, 1, "t").direction
    assert d2 != d1, "停滞过的不再选（fall back 不回头）"
    state.append(DirectionAttempt(d2, verdict="blocked"))
    d3 = next_action(state, 1, "t").direction
    assert len({d1, d2, d3}) == 3, "三方向各试一次"


def test_all_three_stagnant_raises_terminal():
    """★★★ R3 全败 ⇒ DirectionError（调用方记账, 不造第四方向）。"""
    st = [DirectionAttempt(d, verdict="blocked") for d in D]
    with pytest.raises(DirectionError):
        next_action(st, 1, "t")


def test_chain_does_not_repeat_when_candidate_found():
    """★★ R188 smoke 抓到的真 bug: 生成过候选的方向必须入链,
    否则下轮又从同方向起跳（fall back 语义被破）。"""
    st: list = []
    d1 = next_action(st, 1, "t").direction
    st.append(DirectionAttempt(d1, n_candidates=2))          # 有候选 ⇒ 入链
    d2 = next_action(st, 1, "t").direction
    assert d2 != d1


# ── R3 的 REVERSE 半边 · 诚实边界 ───────────────────────────
def test_reverse_candidates_empty_on_real_rules():
    """★★★ 现 RULES 7 条无"更简单"类 ⇒ 如实 []（不编造候选）。"""
    rules = Mutator.__dict__.get("RULES") or Mutator._RULES
    for comp in {r.get("component") for r in rules.values()}:
        assert reverse_candidates(rules, comp) == [], (
            "REVERSE 不可假装有候选 — 现 RULES 修法全是补全/追加")


def test_reverse_candidates_needs_short_patch():
    """★★ 「更简单」代理 = patch 短（≤阈值）; 长 patch 不收。"""
    rules = {"long": {"component": "c", "patch": "x" * (REVERSE_MAX_PATCH + 1)},
             "short": {"component": "c", "patch": "a+b"}}
    got = reverse_candidates(rules, "c")
    assert got == ["short|a+b"]


def test_reverse_candidates_no_component_means_empty():
    """★ 无 component（None/空串）⇒ []（fail-closed 不猜）。"""
    assert reverse_candidates({"k": {"component": "c", "patch": "x"}}, "") == []
    assert reverse_candidates({"k": {"component": "c", "patch": "x"}},
                              None) == []          # type: ignore[arg-type]


# ── 反例锁: 值域与语义锁死 ─────────────────────────────────
def test_no_fourth_direction():
    """★ 锁 3 — DEDUP L254 校正后口径, 第 4 个值是历史错误。"""
    assert len(D) == 3
    with pytest.raises(Exception):
        ensure_direction("DIAGONAL")                # 大小写/未知都拒
    with pytest.raises(Exception):
        ensure_direction(None)                      # None 不是第四方向
    with pytest.raises(Exception):
        ensure_direction("forward")                 # 精确匹配, 不 casefold


def test_semantics_unchanged_after_controller():
    """★★ R188 只加选择逻辑, 不动逐字语义（名字与实现对齐）。"""
    assert semantics_of("FORWARD") == "前进 (在现有基础上改进)"
    assert semantics_of("LATERAL") == "横向 (换一个方向试)"
    assert semantics_of("REVERSE") == "后退 (回退到更简单的方案)"
