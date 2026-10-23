# -*- coding: utf-8 -*-
"""R154 · 采纳面（链裁决 → Proposal 状态机）— 与 ProposalGate 两层互补。

验收:
  □ verdict 三终态映射 gated/rejected（evolver 五态内, 不造新态）
  □ blocked ⇒ rejected（不进判分 — ΔS 归因不污染）
  □ error ⇒ rejected（失败≠通过 — G7）
  □ 契约: 未知 verdict 拒 / 空 gates 拒 / 长度错位拒
  □ gate_verdict 留痕（链全文入 Proposal — 可回放）
  □ 分工在档: 静态门 vs 运行时链
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.harness.adoption import (  # noqa: E402
    ADOPTION_MECHANICS, AdoptionError, AdoptionRecord, apply_chain,
    apply_chain_batch)


@dataclass
class _FakeProposal:
    """最小 Proposal 替身（只持状态面 — adoption 只碰这些）。"""

    proposal_id: str
    state: str = "draft"
    gate_verdict: Any = None


def _chain(verdict: str, *, blocked=(), na=(), n=6) -> Dict[str, Any]:
    return {"verdict": verdict, "gates": [{"gate": "g%d" % i,
                                          "status": "passed"} for i in range(n)],
            "blocked": list(blocked), "not_applicable": list(na)}


def test_pass_verdict_transitions_to_gated():
    """★ applicable_passed_with_na ⇒ gated（进 evolver.accept 判 split）。"""
    p = _FakeProposal("p1")
    rec = apply_chain(p, _chain("applicable_passed_with_na",
                                na=("split", "budget")))
    assert p.state == "gated"
    assert rec.state_before == "draft" and rec.state_after == "gated"
    # ★ 链全文留痕（可回放 — 不是只存 verdict 字符串）
    assert p.gate_verdict["chain"]["verdict"] == "applicable_passed_with_na"
    assert "adoption.apply_chain" in p.gate_verdict["via"]


def test_blocked_verdict_rejects():
    """★ blocked ⇒ rejected（不进判分 — 一门 blocked 全链 blocked）。"""
    p = _FakeProposal("p2")
    rec = apply_chain(p, _chain("blocked", blocked=("leakage",)))
    assert p.state == "rejected"
    assert rec.blocked == ("leakage",)
    assert p.gate_verdict is not None             # 拒也留痕（不是静默）


def test_error_verdict_rejects():
    """★ error ⇒ rejected（失败≠通过 — G7 留痕）。"""
    p = _FakeProposal("p3")
    apply_chain(p, _chain("error"))
    assert p.state == "rejected"


def test_contract_violations():
    """契约: 未知 verdict / 空 gates / 无 proposal_id ⇒ 显式拒。"""
    p = _FakeProposal("p4")
    with pytest.raises(AdoptionError):
        apply_chain(p, _chain("all_good"))            # 非三终态
    with pytest.raises(AdoptionError):
        apply_chain(p, {"verdict": "blocked", "gates": []})   # 空链
    with pytest.raises(AdoptionError):
        apply_chain(_FakeProposal(""), _chain("blocked"))     # 无 id


def test_batch_alignment():
    """★ 批量: 长度一致才跑; 错位 ⇒ 拒整批（A 裁决写 B 头禁止）。"""
    ps = [_FakeProposal("a"), _FakeProposal("b")]
    cs = [_chain("blocked"), _chain("applicable_passed_with_na")]
    recs = apply_chain_batch(ps, cs)
    assert [p.state for p in ps] == ["rejected", "gated"]
    assert isinstance(recs[0], AdoptionRecord)
    with pytest.raises(AdoptionError):
        apply_chain_batch(ps, cs[:1])              # 错位


def test_state_within_evolver_five():
    """★ 只迁到 evolver 五态内（不造第六态 — 与 R14 状态机兼容）。"""
    from dwc.organs.evolver import PROPOSAL_STATES
    assert "gated" in PROPOSAL_STATES and "rejected" in PROPOSAL_STATES
    p = _FakeProposal("p5")
    apply_chain(p, _chain("applicable_passed_with_na"))
    assert p.state in PROPOSAL_STATES
    p2 = _FakeProposal("p6")
    apply_chain(p2, _chain("blocked"))
    assert p2.state in PROPOSAL_STATES


def test_mechanics_documented():
    """分工与纪律在档。"""
    assert "静态" in ADOPTION_MECHANICS["two_layer_gates"]
    assert "污染" in ADOPTION_MECHANICS["blocked_rejects"]
