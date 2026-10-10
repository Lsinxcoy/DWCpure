# -*- coding: utf-8 -*-
"""R157 · 停滞激活探索编排（σ_t/𝒰_t 接 pipeline — 伪码 line 9 三元素齐才激活）。

验收:
  □ 三元素齐备才 active: σ_t=1 ∧ 𝒰_t≠∅ ∧ draft 在位
  □ σ_t 无效（历史不足）⇒ 不激活（数据不够≠停滞 — G7 同族）
  □ 𝒰_t 来自 evolver 真源（liquidity 优先; 近似 T_source 透出）
  □ reserve_fraction ∈ [0,1]; 激进 1.0 也合法但 notes 明说（不做道德审查）
  □ 打标: 组件 ∈ 𝒰_t ⇒ explore; 否则 exploit
  □ 未激活 ⇒ why_inactive 在场（不报成『没有探索面』）
  □ 契约: f 越界拒 / 非序列历史走 evolver 校验
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

import pytest

ROOT = r"E:/Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.harness.exploration import (  # noqa: E402
    EXPLORATION_MECHANICS, TAG_EXPLOIT, TAG_EXPLORE, ExplorationError,
    ExplorationPlan, plan, tag_candidates)


@dataclass
class _Cand:
    component: str


def test_stalled_activates_exploration():
    """★ 停滞（σ_t=1）+ 𝒰_t 非空 ⇒ active + 探索预算保留。"""
    p = plan([0.5, 0.5, 0.5], window=2, delta=0.01,
             accepted_rules=[{"component": "prompt", "layer": "assets"}],
             reserve_fraction=0.5)
    assert p.active is True
    assert p.explore_budget == 50
    assert len(p.explore_components) > 0
    # 未探索组件含序列里没出现的（accepted 只收了 prompt）
    assert "prompt" not in p.explore_components
    assert any("σ_t=1" in n for n in p.notes)


def test_insufficient_history_not_active():
    """★★ 历史不足 window+1 ⇒ σ_t 无效 ⇒ 不激活（数据不够≠停滞）。"""
    p = plan([0.5], window=3, delta=0.01, accepted_rules={})
    assert p.active is False
    assert p.explore_budget == 0
    assert "历史" in p.notes[0] or "不足以" in p.notes[0]


def test_progress_not_active_honest_reason():
    """★ 有进展（σ_t=0）⇒ 不激活 + why_inactive 说清（不是『没有探索面』）。"""
    p = plan([0.5, 0.6, 0.9], window=2, delta=0.01,
             accepted_rules=[{"component": "prompt", "layer": "assets"}])
    assert p.active is False
    assert "未停滞" in p.notes[0]
    assert p.explore_components == ()


def test_tag_candidates():
    """★ 打标: 𝒰_t 内 ⇒ explore; 外 ⇒ exploit。"""
    p = plan([0.5, 0.5, 0.5], window=2, delta=0.01,
             accepted_rules=[{"component": "prompt", "layer": "assets"}],
             reserve_fraction=0.3)
    tags = tag_candidates([_Cand("memory"), _Cand("prompt")], p)
    got = dict(tags)
    assert got["prompt"] == TAG_EXPLOIT            # 已探索（在 accepted）
    assert got["memory"] == TAG_EXPLORE            # 未探索


def test_u_source_transparent():
    """★ 𝒰_t 数据源透出（liquidity 真源 vs 近似 — 不混报）。"""
    p_liq = plan([0.5, 0.5], window=1, delta=0.01, accepted_rules={},
                 liquidity=[{"component": "prompt", "round": 1}])
    assert any("liquidity" in n for n in p_liq.notes)
    p_apx = plan([0.5, 0.5], window=1, delta=0.01, accepted_rules={})
    assert any("近似" in n for n in p_apx.notes)


def test_reserve_fraction_contract():
    """reserve_fraction ∈ [0,1]（越界拒 — 管理参数也守值域）。"""
    for bad in (-0.1, 1.5):
        with pytest.raises(ExplorationError):
            plan([0.5, 0.5], window=1, delta=0.01, accepted_rules={},
                 reserve_fraction=bad)


def test_mechanics_documented():
    """三元素/真源/不重算/诚实 why 在档。"""
    assert "三元素" in EXPLORATION_MECHANICS["trigger"]
    assert "不重算" in EXPLORATION_MECHANICS["not_recompute"]


def test_plan_serializable():
    """as_dict 可入台账（JSON 化无自定义对象泄漏）。"""
    p = plan([0.5, 0.5], window=1, delta=0.01, accepted_rules={})
    d = p.as_dict()
    assert set(d) == {"active", "explore_components", "explore_budget",
                      "notes", "sigma"}
