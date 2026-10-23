# -*- coding: utf-8 -*-
"""R161 · e2e 接通 splitfeed — split 门从"只吃预置"到"真产双 split 判分"。

验收（三条链路坐实 + 边界如实）:
  □ to_facts/pipeline 透传 baseline/current（R159 pair ⇒ R160 feed 弹药）
  □ feed_pair tasks 收窄（演示集只覆盖 4 条 ⇒ 显式限定, 不编数据）
  □ frozen TermFacts 构造期传入（不能事后赋值 — 实测 FrozenInstanceError）
  □ e2e 真跑: baseline/current 真产出, split 门按 accept 判（ho 缺席⇒na 如实）
  □ ho 在场 ⇒ 必须真判 passed/blocked（不许 na 混过）
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.harness.candidate_bridge import to_facts  # noqa: E402


@dataclass
class _Cand:
    patch: str
    component: str
    grounding: List[Dict[str, Any]] = field(default_factory=list)


def test_pipeline_accepts_split_pair():
    """★ run_round 透传 baseline/current ⇒ TermFacts 带 pair（R159 可判）。"""
    from dwc.harness.gates import install_registry, run_gates
    from dwc.harness.pipeline import run_round
    from dwc.organs.contract import ContractRegistry, bounded_param
    from dwc.organs.credit import CreditLedger
    reg = ContractRegistry()
    reg.register(bounded_param(0.0, 1.0))
    install_registry(reg)
    led = CreditLedger()
    out = run_round([_Cand(patch="clean = 1", component="prompt",
                           grounding=[{"diff_id": "d1"}])],
                    t=1, proposal=_FakeP(), ledger=led,
                    pass_rate=1.0, score_star=0.5,
                    delta_s=0.5, delta_c=0.01, noise_band=0.01,
                    domain_guard_ok=True,
                    baseline={"in_score": 0.5, "held_out_score": 0.5},
                    current={"in_score": 1.0, "held_out_score": 1.0})
    g4 = [g for g in out.chain["gates"] if g["gate"] == "split"][0]
    assert g4["status"] == "passed"                 # ★ ho 在场 ⇒ 真判 passed
    install_registry(None)


def test_frozen_facts_require_construction_time():
    """★ frozen TermFacts: pair 必须构造期传入（事后赋值 FrozenInstanceError）。"""
    f = to_facts([_Cand(patch="x", component="prompt")],
                 baseline={"in_score": 0.0, "held_out_score": 0.0},
                 current={"in_score": 1.0, "held_out_score": 1.0})
    assert f.baseline["in_score"] == 0.0
    import dataclasses
    with pytest.raises(dataclasses.FrozenInstanceError):
        f.baseline = {}


def test_feed_pair_tasks_narrowing():
    """★ tasks 收窄: 演示集只覆盖 dev 4 条 ⇒ ho 无覆盖 ⇒ None 如实（不编数据）。"""
    from dwc.organs.judge import Judge
    from dwc.harness.splitfeed import feed_pair
    j = Judge()
    tasks = ("code_fix_001", "code_fix_002", "code_fix_003", "code_fix_004")
    # ★ observed 契约（judge._diff L860 实测）: dict{fn: [(args, result), ...]}
    #   — R161 首版传裸 lambda 被实测打回（TypeError 'function' not iterable）;
    #   契约先读判据源再写, 不猜
    b, c = feed_pair(
        j,
        lambda tid: {"sum_first_n": [(0, 0), (1, 1), (5, 10)],
                     "average": [([], 0.0)],
                     "factorial": [(0, 1), (1, 1)],
                     "fibonacci": [(0, 0), (1, 1)]},
        lambda tid: {"sum_first_n": [(0, 0), (1, 2), (5, 15)],
                     "average": [([], 0.0)],
                     "factorial": [(0, 1), (1, 1)],
                     "fibonacci": [(0, 0), (1, 1)]},
        tasks=tasks)
    assert b["held_out_score"] is None             # test 无这 4 条 ⇒ 缺席
    assert b["in_score"] is not None               # dev 这 4 条真判过


@dataclass
class _FakeP:
    proposal_id: str = "p"
    state: str = "draft"
    gate_verdict: Any = None
