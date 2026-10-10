# -*- coding: utf-8 -*-
"""R156 · 五面合流（bridge→gates→adoption→credit 一次跑通）— 只编排不新增判定。

验收:
  □ 顺序: 投影 → 链 → 迁移 → 记账（每步产物是下步输入）
  □ 链 blocked ⇒ 不记 ℒ_t（没赢家）但 adoption 仍迁 rejected
  □ 赢家记账: a_i=1 + lost_not_recorded=True（陪跑面缺席显式标）
  □ ΔS 均摊: 未逐编辑给 ⇒ 近似口径入 notes（不隐式默认）
  □ layer 未知组件 ⇒ ValueError 显式炸（pipeline 不猜词表）
  □ 维度越界 ⇒ PipelineError（九维外拒）
  □ 空候选列表 ⇒ PipelineError
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List

import pytest

ROOT = r"E:/Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.harness.pipeline import (  # noqa: E402
    PIPELINE_MECHANICS, PipelineError, RoundResult, run_round)


@dataclass
class _Cand:
    patch: str
    component: str
    grounding: List[Dict[str, Any]] = field(default_factory=list)
    dimension: str = "D1"


@dataclass
class _FakeProposal:
    proposal_id: str
    state: str = "draft"
    gate_verdict: Any = None


from dwc.organs.credit import CreditLedger


def _full(**kw) -> Dict[str, Any]:
    """让五门全过的输入（② contract 另需注册表 — 本文件用安装）。"""
    base = dict(pass_rate=1.0, score_star=0.9, delta_s=0.05, delta_c=0.01,
                noise_band=0.01, domain_guard_ok=True)
    base.update(kw)
    return base


def test_full_round_records_winner():
    """★ 全过一轮: 链 passed → 迁移 gated → ℒ_t 记赢家。"""
    from dwc.harness.gates import install_registry
    from dwc.organs.contract import ContractRegistry, bounded_param
    reg = ContractRegistry()
    reg.register(bounded_param(0.0, 1.0))
    install_registry(reg)
    led = CreditLedger()
    p = _FakeProposal("pp")
    cands = [_Cand(patch="clean = 1", component="prompt",
                   grounding=[{"diff_id": "d1"}], dimension="D1")]
    r = run_round(cands, t=3, proposal=p, ledger=led,
                  vocabulary=("t001",), **_full())
    assert isinstance(r, RoundResult)
    assert r.chain["verdict"] == "applicable_passed_with_na"
    assert p.state == "gated"
    assert len(led.entries()) == 1                     # 赢家记一笔
    e = led.entries()[0]
    assert e.adopted == 1 and e.t == 3 and e.layer == "assets"
    assert r.credit_entries[0]["hunk"] == "d1"
    assert r.as_dict()["lost_not_recorded"] is True     # ★ 陪跑面缺席显式
    install_registry(None)


def test_blocked_short_circuit_no_credit():
    """★ 链 blocked ⇒ 不记 ℒ_t; 但 adoption 仍迁 rejected（留痕完整）。"""
    led = CreditLedger()
    p = _FakeProposal("pb")
    cands = [_Cand(patch="x = 'eval003_answer'", component="prompt",
                   grounding=[{"diff_id": "d1"}])]
    r = run_round(cands, t=1, proposal=p, ledger=led,
                  vocabulary=("eval003_answer",), **_full())   # 泄漏 ⇒ blocked
    assert r.chain["verdict"] == "blocked"
    assert p.state == "rejected"
    assert len(led.entries()) == 0                     # ★ 没赢家不记账
    assert "没赢家" in r.notes[0]


def test_delta_even_split_marks_approx():
    """★ ΔS 未逐编辑给 ⇒ 均摊 + notes 标『近似口径』（不隐式默认）。"""
    from dwc.harness.gates import install_registry
    from dwc.organs.contract import ContractRegistry, bounded_param
    reg = ContractRegistry()
    reg.register(bounded_param(0.0, 1.0))
    install_registry(reg)
    led = CreditLedger()
    cands = [_Cand(patch="a = 1", component="prompt",
                   grounding=[{"diff_id": "d1"}]),
             _Cand(patch="b = 2", component="config",
                   grounding=[{"diff_id": "d2"}])]
    r = run_round(cands, t=1, proposal=_FakeProposal("ps"), ledger=led,
                  **_full())                             # 无 *_by_edit 映射
    assert any("均摊" in n for n in r.notes)
    ds_sum = sum(e.delta_s for e in led.entries())
    assert abs(ds_sum - 0.05) < 1e-12                   # 均摊保总
    install_registry(None)


def test_delta_per_edit_preferred():
    """★ 逐编辑口径优先（精确归因 > 均摊）。"""
    from dwc.harness.gates import install_registry
    from dwc.organs.contract import ContractRegistry, bounded_param
    reg = ContractRegistry()
    reg.register(bounded_param(0.0, 1.0))
    install_registry(reg)
    led = CreditLedger()
    cands = [_Cand(patch="a = 1", component="prompt",
                   grounding=[{"diff_id": "d1"}]),
             _Cand(patch="b = 2", component="prompt",
                   grounding=[{"diff_id": "d2"}])]
    r = run_round(cands, t=1, proposal=_FakeProposal("pe"), ledger=led,
                  # ΔS 逐编辑; ΔC 仍整候选 ⇒ 混合口径（ΔS 精 / ΔC 摊）
                  delta_s_by_edit={"d1": 0.04, "d2": 0.01},
                  **_full())
    got = {e.hunk: e.delta_s for e in led.entries()}
    assert got == {"d1": 0.04, "d2": 0.01}              # ★ ΔS 精确, 非均摊
    # 混合口径如实标（ΔC 均摊的 note 在场 — 不是"全精确"的谎）
    assert any("ΔC" in n and "均摊" in n for n in r.notes)
    assert not any("ΔS" in n for n in r.notes)          # ΔS 无均摊 note
    install_registry(None)


def test_unknown_component_raises():
    """★ 组件词表外 ⇒ layer_of ValueError 显式炸（pipeline 不猜层）。"""
    from dwc.harness.gates import install_registry
    from dwc.organs.contract import ContractRegistry, bounded_param
    reg = ContractRegistry()
    reg.register(bounded_param(0.0, 1.0))
    install_registry(reg)
    led = CreditLedger()
    cands = [_Cand(patch="a = 1", component="bogus_xyz",
                   grounding=[{"diff_id": "d1"}])]
    with pytest.raises(ValueError):
        run_round(cands, t=1, proposal=_FakeProposal("pu"), ledger=led,
                  **_full())
    install_registry(None)


def test_bad_dimension_rejected():
    """★ 维度不在九维 ⇒ PipelineError（不是记了再说）。"""
    from dwc.harness.gates import install_registry
    from dwc.organs.contract import ContractRegistry, bounded_param
    reg = ContractRegistry()
    reg.register(bounded_param(0.0, 1.0))
    install_registry(reg)
    led = CreditLedger()
    cands = [_Cand(patch="a = 1", component="prompt", dimension="D99",
                   grounding=[{"diff_id": "d1"}])]
    with pytest.raises(PipelineError):
        run_round(cands, t=1, proposal=_FakeProposal("pd"), ledger=led,
                  **_full())
    install_registry(None)


def test_empty_candidates_rejected():
    """空候选 ⇒ PipelineError（没候选≠干净 — R 家族纪律）。"""
    with pytest.raises(PipelineError):
        run_round([], t=1, proposal=_FakeProposal("px"),
                  ledger=CreditLedger(), **_full())


def test_mechanics_documented():
    """顺序/短路/陪跑标注/均摊口径在档。"""
    assert "缺≠赢" not in PIPELINE_MECHANICS["winner_only"]
    assert "均摊" in PIPELINE_MECHANICS["delta_split"]
