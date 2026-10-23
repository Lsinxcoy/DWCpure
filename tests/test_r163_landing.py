# -*- coding: utf-8 -*-
"""R163 · 采纳后自动落地（landing 分发器）— gated/adopted ⇒ applier 真写。

验收:
  □ 四道闸: state 白名单 / 双报告在 / 分派 / 读回（缺一即拒）
  □ state 终态 adopted（第五态反面 — 不造第六态）
  □ 落地失败不退化 rejected（判决与落地分离）
  □ 分派: assets+rule_key ⇒ land_rule; 其余 ⇒ commit
  □ evidence 缺 success ⇒ 拒（没验证不许固化 — applier 闸②同族）
  □ 批量: 单条失败 raise（不跳过 — 黑箱跳过比炸严重）
  □ R156 pipeline 采纳面与之合流（gated ⇒ land ⇒ adopted）
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.harness.landing import (  # noqa: E402
    LANDING_MECHANICS, LandingError, LandingRecord, land, land_batch)


@dataclass
class _P:
    proposal_id: str = "P1"
    state: str = "gated"
    gate_verdict: Any = None
    target_layer: str = ""
    patch: str = "x = 1"
    component: str = "prompt"


class _StubApplier:
    """最小 applier 替身（readback_ok=True 的 AppliedResult 同款）。"""

    def __init__(self, fail=False):
        self.fail = fail
        self.calls = []

    def commit(self, pid, target, patch):
        from dwc.organs.applier import AppliedResult
        self.calls.append(("commit", pid))
        if self.fail:
            raise RuntimeError("写失败")
        target._set(patch)                 # ★ 真写（与 applier.commit 同形态）
        return AppliedResult(proposal_id=pid, action="commit",
                             readback_ok=True, old_value="old",
                             new_value=patch)

    def land_rule(self, target, key, entry, evidence, check_fn=None):
        from dwc.organs.applier import AppliedResult
        self.calls.append(("land_rule", key))
        if self.fail:
            raise RuntimeError("固化失败")
        return AppliedResult(proposal_id=key, action="commit",
                             readback_ok=True)


def _target():
    """真 applier.Target（内存态 — 读回真跑）。"""
    from dwc.organs.applier import Target
    box = {"v": "old"}
    return Target(getter=lambda: box.get("v"),
                  setter=lambda x: box.__setitem__("v", x),
                  has_fn=lambda: "v" in box), box


def test_four_gates_and_state_terminal():
    """★★ 四道闸过 ⇒ state=gated → adopted（第五态反面）。"""
    ap = _StubApplier()
    tgt, box = _target()
    p = _P(gate_verdict={"proposal_gate": {"pass": True},
                         "six_gate_chain": {"verdict": "applicable_passed_with_na"},
                         "layer2": "passed"})
    rec = land(p, ap, {"success": True, "reason": "judge v2"}, target=tgt)
    assert isinstance(rec, LandingRecord)
    assert p.state == "adopted"                     # ★ 不造第六态
    assert rec.readback_ok and rec.state_before == "gated"
    assert box["v"] == "x = 1"                       # 真写进了可写面


def test_state_whitelist_rejects():
    """★ draft/rejected 不许落（闸① — 没过门的提案）。"""
    ap = _StubApplier()
    tgt, _ = _target()
    for bad in ("draft", "rejected"):
        p = _P(state=bad, gate_verdict={"proposal_gate": {"pass": True}})
        with pytest.raises(LandingError):
            land(p, ap, {"success": True}, target=tgt)


def test_double_report_required():
    """★★ 裸 gated（无链结论）⇒ 拒落（黑箱落地禁 — R162 纪律）。"""
    ap = _StubApplier()
    tgt, _ = _target()
    p = _P(gate_verdict=None)                        # 无双报告
    with pytest.raises(LandingError):
        land(p, ap, {"success": True}, target=tgt)
    p2 = _P(gate_verdict={"layer2": "passed"})       # 只有一半报告
    with pytest.raises(LandingError):
        land(p2, ap, {"success": True}, target=tgt)


def test_adoption_chain_report_schema_accepted():
    """★★★ R154 adoption 链报告（{chain,via}）也是合法报告形态 — R163 接缝。

    ★ R163 首版闸②只认 proposal_gate（R162 schema）⇒ pipeline 形态
      （走 adoption.apply_chain）永远落不了地 — 实测抓到后收编两种 schema。
    """
    ap = _StubApplier()
    tgt, _ = _target()
    p = _P(gate_verdict={"chain": {"verdict": "applicable_passed_with_na"},
                         "via": "adoption.apply_chain"})
    rec = land(p, ap, {"success": True}, target=tgt)
    assert p.state == "adopted"


def test_bare_gated_without_any_chain_rejected():
    """★ 无任何链结论的裸 gated ⇒ 拒（黑箱落地禁 — 与上条互补）。"""
    ap = _StubApplier()
    tgt, _ = _target()
    p = _P(gate_verdict={"layer2": "passed"})       # 无 chain/six_gate_chain
    with pytest.raises(LandingError):
        land(p, ap, {"success": True}, target=tgt)


def test_evidence_must_cite_success():
    """★ evidence 缺 success ⇒ 拒（没验证不许固化）。"""
    ap = _StubApplier()
    tgt, _ = _target()
    p = _P(gate_verdict={"proposal_gate": {"pass": True}})
    with pytest.raises(LandingError):
        land(p, ap, {"reason": "no success key"}, target=tgt)


def test_dispatch_rule_vs_commit():
    """★★ 分派: assets+rule_key ⇒ land_rule; 其余 ⇒ commit。"""
    ap = _StubApplier()
    tgt, _ = _target()
    gv = {"proposal_gate": {"pass": True},
          "six_gate_chain": {"verdict": "applicable_passed_with_na"}}
    p_rule = _P(target_layer="assets",
                gate_verdict=dict(gv))
    land(p_rule, ap, {"success": True}, target=tgt,
         rule_key="K1", rule_entry={"patch": "s", "m": "m1"})
    assert ap.calls[-1][0] == "land_rule"
    p_gen = _P(target_layer="architecture", gate_verdict=dict(gv))
    land(p_gen, ap, {"success": True}, target=tgt)
    assert ap.calls[-1][0] == "commit"


def test_landing_failure_keeps_gated():
    """★★ 落地失败 ⇒ 保持原 state（**不退化 rejected** — 分离判决与落地）。"""
    ap = _StubApplier(fail=True)
    tgt, _ = _target()
    p = _P(gate_verdict={"proposal_gate": {"pass": True}})
    with pytest.raises(Exception):
        land(p, ap, {"success": True}, target=tgt)
    assert p.state == "gated"                        # ★ 不退化


def test_batch_raises_not_skips():
    """★★ 批量: 单条失败 raise（不跳过 — 黑箱跳过比炸严重）。"""
    ap = _StubApplier(fail=True)
    tgt, _ = _target()
    items = [(_P(proposal_id="A", gate_verdict={"proposal_gate": {}}),
              {"success": True})]
    with pytest.raises(Exception):
        land_batch(items, ap, target=tgt)


def test_mechanics_documented():
    """四道闸/终态/不退化/分派在档。"""
    assert "adopted" in LANDING_MECHANICS["state_terminal"]
    assert "退化" in LANDING_MECHANICS["no_regression"]
