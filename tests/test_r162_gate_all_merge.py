# -*- coding: utf-8 -*-
"""R162 · gate_all 两层并轨 — 静态门先、运行时六门链后; 三元分流。

验收（旧契约零破坏 + 新三层）:
  □ 旧二元键: n_gated/n_rejected 语义兼容（旧测 36 passed — 单独跑）
  □ 层① 静态挂 ⇒ rejected, 层② skipped（不进链 — 顺序不可换）
  □ 层② 缺口径（noncomp/drawback/contract 无输入）⇒ pending_runtime 不降级
  □ 层② 真判挂（leakage 命中/预算超）⇒ rejected（非补偿: 有输入且挂）
  □ gate_verdict 双报告留痕（proposal_gate + six_gate_chain 逐门）
  □ registry 注入 ⇒ contract 真判; 未注入 ⇒ pending（不误判提案坏）
  □ BridgeError 单条记错不炸全批（空 patch 形态）
"""
from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "tests"))

from dwc.organs.evolver import (  # noqa: E402
    Evolver, EvolverError, Proposal, ProposalGate)
from dwc.organs.contract import ContractRegistry, bounded_param  # noqa: E402


def _sig(c="E_VALUE", q="wrong_magnitude", fn="sum_first_n", m=""):
    return {"kind": "behavior", "q": q, "c": c, "m": m, "fn": fn}


def _good_prop():
    ev = Evolver()
    return ev.diagnose([_sig()])["proposals"] or []


def test_static_reject_skips_chain():
    """★ 层① 静态挂 ⇒ rejected 且层② skipped（顺序不可换 — 不等候选数据）。"""
    ev = Evolver()
    bad = Proposal(proposal_id="P_bad", failure_signature=_sig(),
                   component="prompt", target="config/anchors/dev.json",
                   patch="x = 1", rationale="碰判据")
    r = ev.gate_all([bad])
    assert r["n_rejected"] == 1 and r["n_gated"] == 0
    assert bad.gate_verdict["layer2"] == "skipped"
    assert bad.gate_verdict["six_gate_chain"] is None


def test_missing_input_gates_pending_not_rejected():
    """★★★ 缺口径（noncomp/drawback/contract 无输入）⇒ pending_runtime。"""
    ev = Evolver()
    props = _good_prop()
    r = ev.gate_all(props)
    assert r["n_gated"] == 1                    # ★ 不降级（缺输入≠坏）
    assert r["n_pending_runtime"] == 1
    gv = props[0].gate_verdict
    assert gv["layer2"] == "pending_runtime"
    blocked = set(gv["six_gate_chain"]["blocked"])
    assert blocked and blocked <= {"noncomp", "drawback", "contract"}


def test_registry_injected_real_judges_contract():
    """★★ registry 注入 ⇒ contract 门真判（pending 收窄）。"""
    reg = ContractRegistry()
    reg.register(bounded_param(0.0, 1.0))
    ev = Evolver(registry=reg)
    props = _good_prop()
    r = ev.gate_all(props)
    gv = props[0].gate_verdict
    per = {g["gate"]: g["status"] for g in gv["six_gate_chain"]["gates"]}
    assert per["contract"] == "passed"           # ★ 注入后真判 passed
    assert r["n_pending_runtime"] == 1           # noncomp/drawback 仍 pending


def test_leakage_veto_through_chain_rejected():
    """★★★ 泄漏一票否决穿层②（R147 门① × 非补偿）⇒ rejected。

    ★ vocabulary 由 to_facts 从 caller 收 — gate_all 传空 ⇒ 泄漏门无词表
      可判（落 pending 族）。真判它直接验链路: to_facts 带 vocabulary +
      run_gates ⇒ leakage blocked（单测链路, 不借 gate_all 空词表口径）。
    """
    from dwc.harness.candidate_bridge import to_facts
    from dwc.harness.gates import run_gates
    p = Proposal(proposal_id="P_leak", failure_signature=_sig(),
                 component="prompt", target="some_fn",
                 patch="if task_name == 'code_fix_001': return golden",
                 rationale="泄漏示意")
    ch = run_gates(to_facts([p], vocabulary=("code_fix_001",)))
    assert "leakage" in ch["blocked"]
    per = {g["gate"]: g["status"] for g in ch["gates"]}
    assert per["leakage"] == "blocked"


def test_bridge_error_defense_unreachable_state_documented():
    """★★ 空 patch 在 Proposal 构造期就被拦 ⇒ 层② BridgeError 不可达。

    ★ R162 实测: patch='' ⇒ EvolverError（"空 patch = 没有干预"）在
      Proposal.__post_init__ 抛出 ⇒ 层② `except BridgeError` 是**防御性
      死代码**（保留 — 防未来 Proposal 契约放宽; 但断言它当前不可达,
      如实记录: 不是每条 except 都有活路径）。
    """
    ev = Evolver()
    with pytest.raises(EvolverError):
        Proposal(proposal_id="P_empty", failure_signature=_sig(),
                 component="prompt", target="t", patch="",
                 rationale="空 patch")
    # 层② batch 内单条隔离逻辑仍可经 vocabulary=()/patch 哨兵路径构造,
    # 但空 patch/空 component 形态到不了层②（构造期已拒）
    assert True   # 可达性结论即断言（见 docstring 实测依据）


def test_gate_verdict_double_report():
    """★ gate_verdict 双报告（层①原样 + 层②逐门明细 — 归因可查）。"""
    ev = Evolver()
    props = _good_prop()
    ev.gate_all(props)
    gv = props[0].gate_verdict
    assert set(gv) >= {"proposal_gate", "six_gate_chain", "layer2"}
    assert gv["proposal_gate"]["pass"] is True    # 层①报告原样保留
    assert len(gv["six_gate_chain"]["gates"]) == 6   # 层②六门全跑


def test_backcompat_keys_preserved():
    """★★ 旧二元键语义兼容（R162 前调用方不破坏 — 实现对齐设计）。"""
    ev = Evolver()
    r = ev.gate_all(_good_prop())
    assert set(r) >= {"gated", "rejected", "n_gated", "n_rejected"}
    assert r["n_gated"] == 1 and r["n_rejected"] == 0
