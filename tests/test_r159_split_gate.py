# -*- coding: utf-8 -*-
"""R159 · split 门三态精化 — 真调 evolver.accept() + blocked⇒na 的族属裁决。

验收:
  □ 判定真源: baseline/current 在场 ⇒ 走 Evolver.accept()（不重造）
  □ 四决策映射: adopted_no_impl⇒passed / rejected⇒blocked
    / blocked(held_out缺)⇒**na** / 缺两份判分⇒na
  □ 预置 verdict 路保留（e2e 既有形态不破坏）
  □ 裁决理由: held_out 未落地=系统级缺对象（非调用方疏忽）— 在档可查
"""
from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.harness.gates import (  # noqa: E402
    GATE_BLOCKED, GATE_NOT_APPLICABLE, GATE_PASSED, TermFacts,
    install_registry, run_gates)


def _f(**kw) -> TermFacts:
    base = dict(pass_rate=1.0)              # 让③过（聚焦④）
    base.update(kw)
    return TermFacts(**base)


def _g4(out) -> dict:
    return {g["gate"]: g for g in out["gates"]}["split"]


def test_accept_called_when_pair_present():
    """★★ baseline/current 在场 ⇒ 真调 Evolver.accept()（判定唯一真源）。"""
    install_registry(None)                  # 聚焦④（② blocked 无所谓 — 只看④）
    out = run_gates(_f(baseline={"in_score": 0.5, "held_out_score": 0.5},
                       current={"in_score": 0.7, "held_out_score": 0.6}))
    g4 = _g4(out)
    assert g4["status"] == GATE_PASSED
    assert g4["detail"]["split"]["decision"] == "adopted_not_implemented"
    assert g4["detail"]["split"]["delta_in"] == pytest.approx(0.2)


def test_accept_rejected_blocks():
    """★ accept 判 rejected（退化）⇒ ④ blocked。"""
    out = run_gates(_f(baseline={"in_score": 0.8, "held_out_score": 0.7},
                       current={"in_score": 0.7, "held_out_score": 0.65}))
    assert _g4(out)["status"] == GATE_BLOCKED
    assert _g4(out)["detail"]["split"]["decision"] == "rejected"


def test_accept_blocked_maps_na():
    """★★★ held_out 缺 ⇒ accept blocked ⇒ **na**（系统级缺对象≠调用方疏忽）。"""
    out = run_gates(_f(baseline={"in_score": 0.5},
                       current={"in_score": 0.7}))
    g4 = _g4(out)
    assert g4["status"] == GATE_NOT_APPLICABLE
    assert "held_out" in g4["detail"]["why"]
    assert "na, 不记 blocked" in g4["detail"]["why"]


def test_no_pair_stays_na():
    """★ 两份判分都不给 ⇒ na（无对象 — R152 原生形态保留）。"""
    out = run_gates(_f())
    assert _g4(out)["status"] == GATE_NOT_APPLICABLE
    assert "无 baseline/current" in _g4(out)["detail"]["why"]


def test_preset_verdict_path_preserved():
    """★ 预置 verdict 路保留（e2e R158 跑的形态 — 不破坏已通车轨）。"""
    out = run_gates(_f(split_verdict={"decision": "adopted_not_implemented"}))
    assert _g4(out)["status"] == GATE_PASSED
    out2 = run_gates(_f(split_verdict={"decision": "rejected"}))
    assert _g4(out2)["status"] == GATE_BLOCKED
    out3 = run_gates(_f(split_verdict={"decision": "blocked"}))
    assert _g4(out3)["status"] == GATE_NOT_APPLICABLE


def test_pair_takes_precedence_over_preset():
    """★ 两路都给 ⇒ pair 真判优先（真源 > 快照 — 引用深化为调用）。"""
    out = run_gates(_f(baseline={"in_score": 0.5, "held_out_score": 0.5},
                       current={"in_score": 0.7, "held_out_score": 0.6},
                       split_verdict={"decision": "rejected"}))
    g4 = _g4(out)
    assert g4["status"] == GATE_PASSED          # 真判 adopted, 预置 rejected 被覆盖
    assert g4["detail"]["split"]["decision"] == "adopted_not_implemented"


def test_no_change_rejected_not_adopted():
    """★ 无变化（Δ=0）⇒ accept 拒（max>0 第三条件 — R 家族已知口径）。"""
    out = run_gates(_f(baseline={"in_score": 0.5, "held_out_score": 0.5},
                       current={"in_score": 0.5, "held_out_score": 0.5}))
    assert _g4(out)["status"] == GATE_BLOCKED
    assert "max" in _g4(out)["detail"]["split"]["why"] or "空过" in \
        _g4(out)["detail"]["split"]["why"]
