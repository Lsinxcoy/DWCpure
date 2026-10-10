# -*- coding: utf-8 -*-
"""R153 · 候选环入口（Candidate → 门组输入适配器）— 六门全拿真对象。

验收:
  □ to_facts: Candidate[] → TermFacts（edits/diff/词表投影, 逐字不重写）
  □ hunk 优先级: grounding diff id > patch 哨兵（显式降级入档）
  □ 契约: 空候选列表拒 / 无 component 拒 / 空 patch 拒
  □ run_candidate_gates: 候选形态下 ①⑥ 可判（R152 那边是 na/blocked）
  □ 门①词表外置: vocabulary 从调用方, 不从 patch 猜
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List

import pytest

ROOT = r"E:/Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.harness.candidate_bridge import (  # noqa: E402
    BRIDGE_MECHANICS, BridgeError, run_candidate_gates, to_facts)


@dataclass
class _Cand:
    """与 candidates.Candidate 同型的最小替身（字段同构 — 适配器解耦）。"""

    patch: str
    component: str
    grounding: List[Dict[str, Any]] = field(default_factory=list)


def test_to_facts_projection():
    """★ 投影: patch 逐字进 diff / (component, hunk) 进 edits。"""
    c = _Cand(patch="clean = 1", component="prompt",
              grounding=[{"diff_id": "d1"}])
    f = to_facts([c], vocabulary=("code_fix_001",))
    assert f.candidate_diff == "clean = 1"          # 逐字
    assert len(f.edits) == 1
    assert f.edits[0].component == "prompt"
    assert f.edits[0].hunk == "d1"                  # ★ grounding id 优先
    assert f.vocabulary == ("code_fix_001",)


def test_hunk_fallback_sentinel():
    """★ hunk 退化: 无 grounding id ⇒ patch 前 80 字符哨兵（显式降级）。"""
    long_patch = "x" * 200
    c = _Cand(patch=long_patch, component="config", grounding=[])
    f = to_facts([c])
    assert f.edits[0].hunk == "x" * 80 + "…"        # 哨兵形态


def test_bridge_contract_violations():
    """契约: 空列表 / 无 component / 空 patch ⇒ 显式拒。"""
    with pytest.raises(BridgeError):
        to_facts([])                                # 空候选列表
    with pytest.raises(BridgeError):
        to_facts([_Cand(patch="x", component="")])  # 无 component
    with pytest.raises(BridgeError):
        to_facts([_Cand(patch="", component="prompt")])   # 空 patch
    with pytest.raises(BridgeError):
        to_facts("not-list")                        # 非序列


def test_candidate_gates_pass_gate1_and_gate6():
    """★★ 候选形态: 门①（干净 diff）passed; 门⑥（申报编辑）可判。"""
    out = run_candidate_gates(
        [_Cand(patch="clean = 1", component="prompt",
               grounding=[{"diff_id": "d1"}])],
        pass_rate=1.0,                              # ③ 全过
        score_star=0.9, delta_s=0.05, delta_c=0.01,
        noise_band=0.01, domain_guard_ok=True)      # ⑤ 口径齐
    by = {g["gate"]: g["status"] for g in out["gates"]}
    assert by["leakage"] == "passed"                # ★ R152 那边 blocked
    assert by["budget"] == "passed"                 # ★ R152 那边 not_applicable
    assert by["drawback"] == "passed"
    assert by["noncomp"] == "passed"
    assert by["split"] == "not_applicable"          # 未给 split_verdict ⇒ 无对
    assert out["bridge"]["n_edits"] == 1


def test_candidate_gates_leak_veto():
    """★ 候选泄漏一票否决穿过门①（词表由调用方给）。"""
    out = run_candidate_gates(
        [_Cand(patch="x = 'eval003_answer'", component="prompt")],
        pass_rate=1.0,
        vocabulary=("eval003_answer",))
    by = {g["gate"]: g["status"] for g in out["gates"]}
    assert by["leakage"] == "blocked"               # 泄漏 ⇒ 链 blocked
    assert out["verdict"] == "blocked"
    assert "leakage" in out["blocked"]


def test_candidate_gates_budget_over():
    """★ 大量编辑 ⇒ 门⑥ blocked（t=0 宽预算仍可能超 — 归因面撑不住）。"""
    cands = [_Cand(patch="a%d = 1" % i, component="prompt",
                   grounding=[{"diff_id": "d%d" % i}])
             for i in range(20)]
    out = run_candidate_gates(cands, pass_rate=1.0)
    by = {g["gate"]: g["status"] for g in out["gates"]}
    assert by["budget"] == "blocked"                # 20 > b_max=8
    assert "budget" in out["blocked"]


def test_bridge_mechanics_documented():
    """降级/词表外置纪律在档。"""
    assert "哨兵" in BRIDGE_MECHANICS["edits_derivation"]
    assert "不从 patch 猜词" in BRIDGE_MECHANICS["vocabulary_external"]
