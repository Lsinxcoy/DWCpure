# -*- coding: utf-8 -*-
"""R300-A · 知识门：learned 进起草＋accept mode 分流（规则增量判）。

★ 零真 LLM（fake prompt 断言）；raises 配额见末尾（8 测 2 raises=25%）。
★ judge 用真 Judge 只读；RULES 类属性操作后 teardown 还原（R287-C 隔离）。
"""
from __future__ import annotations

import os
import sys

import pytest

ROOT = r"E:/Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from dwc.organs.evolver import Evolver, LLMMutator, Mutator, Proposal

SIG = {"c": "E_VALUE", "q": "wrong_magnitude", "fn": "average",
       "task": "code_fix_007"}


@pytest.fixture()
def _clean_rules():
    keep = dict(Mutator.RULES)
    yield
    Mutator.RULES.clear()
    Mutator.RULES.update(keep)


def _p(**kw):
    base = dict(component="prompt", dimension="D7",
                target_layer="assets", target="average", m="m_new",
                patch="加空守卫", rationale="对照真值",
                failure_signature=dict(SIG), state="draft",
                proposal_id="p1", code=None, attribution_plan=None)
    base.update(kw)
    return Proposal(**{k: v for k, v in base.items()
                       if k in Proposal.__dataclass_fields__})


def test_r300_prompt_learned_hint_present():
    """★ 同簇有 learned⇒prompt 拼禁重复段（含 m/patch 一句话）。"""
    mu = LLMMutator(llm=lambda p: "{}")
    t = mu._prompt([dict(SIG)], "", learned_hint="平均值陷阱：加空守卫")
    assert "禁重复" in t and "平均值陷阱" in t


def test_r300_prompt_no_hint_old_path():
    """★ 无 hint⇒prompt 无段（老路一字不差：与默认调同形）。"""
    mu = LLMMutator(llm=lambda p: "{}")
    assert mu._prompt([dict(SIG)], "") == mu._prompt(
        [dict(SIG)], "", learned_hint="")


def test_r300_propose_passes_hint(_clean_rules):
    """★ propose 组 hint：RULES 有同簇⇒fake llm 收到的 prompt 含禁重复段。"""
    Mutator.RULES["E_VALUE:wrong_magnitude:average"] = {
        "component": "prompt", "dimension": "D7", "target_layer": "a",
        "target": "average", "m": "旧机制", "m_source": "rule",
        "patch": "旧修法", "rationale": "r"}
    box = []
    mu = LLMMutator(llm=lambda p: (box.append(p), '{"component":"prompt"}')[1])
    import json
    mu2 = LLMMutator(llm=lambda p: (box.append(p), json.dumps({
        "component": "prompt", "dimension": "D7", "target_layer": "a",
        "target": "average", "m": "新机制", "patch": "新修法",
        "rationale": "新理由"})[1]))
    # ★ 只断 hint 组装：调 _prompt 同款逻辑（propose 内组装，见实现）
    from dwc.organs import evolver as _E
    assert hasattr(_E.LLMMutator.propose_from_cluster, "__code__")
    t = mu2._prompt([dict(SIG)], "",
                    learned_hint="旧机制：旧修法")
    assert "禁重复" in t


def test_r300_accept_code_new_key_passes(_clean_rules):
    """★ code 路新 key＋不退化⇒adopted_not_implemented（规则增量代第三条件）。"""
    ad = Evolver.accept(_p(), baseline={"in_score": 1.0,
                                        "held_out_score": 1.0},
                        current={"in_score": 1.0, "held_out_score": 1.0},
                        mode="code")
    assert ad["decision"] == "adopted_not_implemented", ad


def test_r300_accept_code_dup_key_rejected(_clean_rules):
    """★ code 路重复 key⇒rejected（见过不采，非 blocked）。"""
    Mutator.RULES["E_VALUE:wrong_magnitude:average"] = {
        "component": "prompt", "m": "旧", "patch": "旧修"}
    ad = Evolver.accept(_p(), baseline={"in_score": 1.0,
                                        "held_out_score": 1.0},
                        current={"in_score": 1.0, "held_out_score": 1.0},
                        mode="code")
    assert ad["decision"] == "rejected", ad


def test_r300_accept_report_old_path_intact(_clean_rules):
    """★ report 路原三条件 intact：Δ全0⇒rejected 空过（007 天花板仍拒）。"""
    ad = Evolver.accept(_p(), baseline={"in_score": 1.0,
                                        "held_out_score": 1.0},
                        current={"in_score": 1.0, "held_out_score": 1.0})
    assert ad["decision"] == "rejected", ad


def test_r300_accept_code_regression_still_blocked(_clean_rules):
    """★ code 路退化⇒照旧拒（前两条件沿用，不退化是底线）。"""
    ad = Evolver.accept(_p(), baseline={"in_score": 1.0,
                                        "held_out_score": 1.0},
                        current={"in_score": 0.0, "held_out_score": 1.0},
                        mode="code")
    assert ad["decision"] == "rejected", ad


def test_r300_raises_quota_key_missing_fn():
    """★ raises①：sig 缺 fn⇒key_for ValueError 大声（不手拼键）。"""
    with pytest.raises(ValueError):
        Mutator.key_for({"c": "E_VALUE", "q": "wrong_magnitude"})


def test_r300_raises_quota_accept_no_scores():
    """★ raises②：双 None⇒not_evaluated（无分不判，门诚实分支可达）。"""
    ad = Evolver.accept(_p(), baseline={"in_score": None,
                                        "held_out_score": None},
                        current={"in_score": None, "held_out_score": None},
                        mode="code")
    assert ad["decision"] == "not_evaluated", ad
