# -*- coding: utf-8 -*-
"""R152 · 门组入链（六门三态编排 + 口径桥 + 链级非补偿）。

验收:
  □ GATE_ORDER 六门顺序（§5.4 — 顺序即契约）
  □ 三态语义: passed / blocked（缺口径）/ not_applicable（无对象）
  □ 链 verdict: 一门 blocked ⇒ 全链 blocked（门间不可互偿）
  □ ① leakage: 无 diff ⇒ blocked（0 输入≠干净）
  □ ② contract: 空注册表 ⇒ blocked（没契约≠契约满足）
  □ ③ drawback: pass_rate 投影 + not_evaluated 带进链
  □ ④ split: 无候选对 ⇒ not_applicable; 有判定 ⇒ 引用不重造
  □ ⑤ noncomp: 缺 ΔS/δ ⇒ blocked（不硬设 0）
  □ ⑥ budget: 无申报编辑 ⇒ not_applicable
  □ stop_at_first_block: 前门 blocked ⇒ 短路（后续不跑）
"""
from __future__ import annotations

import os
import sys

import pytest

ROOT = r"E:/Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.harness.gates import (  # noqa: E402
    GATE_BLOCKED, GATE_CHAIN, GATE_ORDER, GATE_PASSED, GateChainError,
    TermFacts, install_registry, run_gates)


def _facts(**kw) -> TermFacts:
    base = dict(pass_rate=None, score_star=None, delta_s=None,
                delta_c=None, nu_str=None, noise_band=None,
                domain_guard_ok=None, not_evaluated=0, candidate_diff=None,
                vocabulary=(), edits=None, split_verdict=None)
    base.update(kw)
    return TermFacts(**base)


def test_order_and_no_compensation():
    """★ 六门顺序 + 链级非补偿语义在档。"""
    assert GATE_ORDER == ("leakage", "contract", "drawback", "split",
                          "noncomp", "budget")
    assert "不可互偿" in GATE_CHAIN["no_compensation"]
    assert "不重造" in GATE_CHAIN["split_by_reference"]


def test_empty_facts_all_blocked_or_na():
    """★ 全缺输入: 每门 blocked/not_applicable, 链 verdict=blocked。"""
    r = run_gates(_facts())
    assert r["verdict"] == GATE_BLOCKED
    by = {g["gate"]: g["status"] for g in r["gates"]}
    # ①④⑥ 无对象; ②空表/③未判/⑤缺口径 ⇒ blocked
    assert by["leakage"] == GATE_BLOCKED        # 无 diff ⇒ blocked（不猜）
    assert by["split"] == "not_applicable"      # 无候选对 ⇒ 无对象
    assert by["budget"] == "not_applicable"     # 无申报编辑 ⇒ 无对象
    assert by["drawback"] == GATE_BLOCKED       # 未判
    assert by["noncomp"] == GATE_BLOCKED        # 缺 ΔS/δ
    assert "不许落地" in r["note"]


def test_leakage_blocked_without_diff():
    """① 无 diff ⇒ blocked（0 输入≠干净 — 与 R147 同口径）。"""
    r = run_gates(_facts())
    g1 = [g for g in r["gates"] if g["gate"] == "leakage"][0]
    assert g1["status"] == GATE_BLOCKED
    assert "0 输入≠干净" in g1["detail"]["why"]


def test_leakage_passed_with_clean_diff():
    """① 有干净 diff ⇒ passed（通用改动过 — R147 语义）。"""
    r = run_gates(_facts(candidate_diff="clean = 1",
                         vocabulary=("code_fix_001",)))
    g1 = [g for g in r["gates"] if g["gate"] == "leakage"][0]
    assert g1["status"] == GATE_PASSED
    # 有词表词 ⇒ blocked（一票否决传进链）
    r2 = run_gates(_facts(candidate_diff="x = 'code_fix_001'",
                          vocabulary=("code_fix_001",)))
    g1b = [g for g in r2["gates"] if g["gate"] == "leakage"][0]
    assert g1b["status"] == GATE_BLOCKED


def test_contract_empty_registry_blocked():
    """② 空注册表 ⇒ blocked（没契约≠契约满足）。

    ★★ R170 语义升级（契约变更 — 旧语义锁的是"None ⇒ blocked"）:
      · **显式装空表**（ContractRegistry() 空）⇒ blocked（纪律不变）
      · None（**未注入**）⇒ 回落 builtin（R167 已裁"各处默认装这个";
        R170 实证: 不回落则 run_round 链恒 blocked「缺契约」假阴性 —
        闭环永远落不了地）
      ⇒ 本意（"不许没装表就假 passed"）仍成立: builtin 装了仍真判
        （逐 check + violation veto — 见 R167 test_gate2_upgraded 三态）
    """
    from dwc.organs.contract import ContractRegistry
    install_registry(None)                    # 未注入 ⇒ 回落 builtin
    r = run_gates(_facts())
    g2 = [g for g in r["gates"] if g["gate"] == "contract"][0]
    assert g2["status"] == GATE_PASSED and g2["detail"]["n_registered"] == 1
    install_registry(ContractRegistry())      # 显式空表（真没契约）
    r2 = run_gates(_facts())
    g2b = [g for g in r2["gates"] if g["gate"] == "contract"][0]
    assert g2b["status"] == GATE_BLOCKED
    # 注册一条 ⇒ passed
    from dwc.organs.contract import ContractRegistry, bounded_param
    reg = ContractRegistry()
    reg.register(bounded_param(0.0, 1.0))
    install_registry(reg)
    r2 = run_gates(_facts())
    g2b = [g for g in r2["gates"] if g["gate"] == "contract"][0]
    assert g2b["status"] == GATE_PASSED
    install_registry(None)                    # 复位（防跨用例污染）


def test_drawback_projection_with_not_evaluated():
    """③ 投影 pass_rate + not_evaluated 带进链（没查≠干净）。"""
    r = run_gates(_facts(pass_rate=1.0, not_evaluated=9))
    g3 = [g for g in r["gates"] if g["gate"] == "drawback"][0]
    assert g3["status"] == GATE_PASSED
    assert g3["detail"]["not_evaluated"] == 9      # ★ 9/10 未判仍如实带
    # 非全过 ⇒ drawbacks found ⇒ blocked
    r2 = run_gates(_facts(pass_rate=0.5, not_evaluated=0))
    g3b = [g for g in r2["gates"] if g["gate"] == "drawback"][0]
    assert g3b["status"] == GATE_BLOCKED


def test_split_na_and_reference():
    """④ 无候选对 ⇒ not_applicable; 有判定 ⇒ 引用（adopted 才 passed）。"""
    r = run_gates(_facts())
    g4 = [g for g in r["gates"] if g["gate"] == "split"][0]
    assert g4["status"] == "not_applicable"
    r2 = run_gates(_facts(split_verdict={"decision": "adopted_not_implemented"}))
    g4b = [g for g in r2["gates"] if g["gate"] == "split"][0]
    assert g4b["status"] == GATE_PASSED
    r3 = run_gates(_facts(split_verdict={"decision": "rejected"}))
    g4c = [g for g in r3["gates"] if g["gate"] == "split"][0]
    assert g4c["status"] == GATE_BLOCKED


def test_noncomp_blocked_without_deltas():
    """⑤ 缺 ΔS/ΔC/δ ⇒ blocked（不硬设 0 — R150 纪律链级保持）。"""
    r = run_gates(_facts(pass_rate=1.0))
    g5 = [g for g in r["gates"] if g["gate"] == "noncomp"][0]
    assert g5["status"] == GATE_BLOCKED
    # 全口径给齐 ⇒ 可判（看 noncomp 自身结论）
    r2 = run_gates(_facts(pass_rate=0.95, score_star=0.9, delta_s=0.05,
                          delta_c=0.01, noise_band=0.01,
                          domain_guard_ok=True))
    g5b = [g for g in r2["gates"] if g["gate"] == "noncomp"][0]
    assert g5b["status"] == GATE_PASSED


def test_stop_at_first_block():
    """★ stop_at_first_block ⇒ ① blocked 即停（前门不过后门无意义）。"""
    r = run_gates(_facts(), stop_at_first_block=True)
    assert len(r["gates"]) == 1                # 只跑了 leakage
    assert r["gates"][0]["gate"] == "leakage"
    assert r["verdict"] == GATE_BLOCKED


def test_all_applicable_pass_verdict():
    """①③⑤ passed + ② registered + ④⑥ na ⇒ applicable_passed_with_na。"""
    from dwc.organs.contract import ContractRegistry, bounded_param
    reg = ContractRegistry()
    reg.register(bounded_param(0.0, 1.0))
    install_registry(reg)                       # ②有表 ⇒ passed
    # ★ pass_rate=1.0（全过 ⇒ ③ clean — 非全过 ⇒ drawback, 见 drawback 案例）
    r = run_gates(_facts(pass_rate=1.0, score_star=0.9, delta_s=0.05,
                         delta_c=0.01, noise_band=0.01,
                         domain_guard_ok=True, candidate_diff="clean = 1",
                         vocabulary=("t001",)))
    assert r["blocked"] == []                   # ★ 全 applicable 门 passed
    assert set(r["not_applicable"]) == {"split", "budget"}   # ④⑥ 无对象
    assert r["verdict"] == "applicable_passed_with_na"
    install_registry(None)                      # 复位（防跨用例污染）
