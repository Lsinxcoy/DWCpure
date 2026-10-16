# -*- coding: utf-8 -*-
"""R295-Task2 · 起草写码化（code_repair 出可执行 code，不出建议文本）。

★ 测试零真 LLM（fake llm 回固定 JSON）；raises 配额见末尾。
"""
from __future__ import annotations

import pytest


def _sigs():
    return [{"c": "E_VALUE", "q": "wrong_magnitude", "fn": "average",
             "m": "llm_asserted:0.15", "task": "code_fix_007"}]


def test_r295_draft_code_present_when_wanted():
    """★★ want_code=True⇒prompt 含写码指令＋Proposal.code 为可执行函数。"""
    from dwc.organs.evolver import LLMMutator
    mu = LLMMutator(llm=lambda p: (
        '{"component":"control_flow","dimension":"D7",'
        '"target_layer":"assets","target":"average","m":"exact_float",'
        '"patch":"return sum(xs)/len(xs)","rationale":"r",'
        '"code":"def average(xs):\\n    return sum(xs)/len(xs) if xs else 0.0\\n"}'
    ))
    pr = mu.propose_from_cluster(_sigs(), "ctx", want_code=True)
    assert pr is not None
    assert pr.code is not None and pr.code.startswith("def average")


def test_r295_draft_code_absent_without_want():
    """★ 默认不求 code（behavior 老路零变，prompt 不加指令）。"""
    from dwc.organs.evolver import LLMMutator
    seen = {}
    def _fake(p):
        seen["prompt"] = p
        return ('{"component":"prompt","dimension":"D7","target_layer":"assets",'
                '"target":"average","m":"x","patch":"p","rationale":"r"}')
    mu = LLMMutator(llm=_fake)
    pr = mu.propose_from_cluster(_sigs(), "ctx")
    assert pr is not None and pr.code is None
    assert "沙箱真跑" not in seen["prompt"]  # ★ 无写码指令（老路 prompt 零变）


def test_r295_draft_code_missing_retries_then_none():
    """★ want_code 但 3 次都没码⇒起草 None＋留痕（不带残码进 trial 错配通道）。"""
    from dwc.organs.evolver import LLMMutator
    mu = LLMMutator(llm=lambda p: (
        '{"component":"control_flow","dimension":"D7",'
        '"target_layer":"assets","target":"average","m":"x",'
        '"patch":"p","rationale":"r"}'))
    pr = mu.propose_from_cluster(_sigs(), "ctx", want_code=True)
    assert pr is None
    assert "code" in mu.last_reason, mu.last_reason


def test_r295_draft_code_retry_then_success():
    """★ 第一次无码第二次有码⇒重试成功（max_attempts 内救回）。"""
    from dwc.organs.evolver import LLMMutator
    _calls = []
    def _fake(p):
        _calls.append(p)
        if len(_calls) == 1:
            return ('{"component":"control_flow","dimension":"D7",'
                    '"target_layer":"assets","target":"average","m":"x",'
                    '"patch":"p","rationale":"r"}')
        return ('{"component":"control_flow","dimension":"D7",'
                '"target_layer":"assets","target":"average","m":"x",'
                '"patch":"p","rationale":"r",'
                '"code":"def average(xs):\\n    return sum(xs)/len(xs)\\n"}')
    mu = LLMMutator(llm=_fake)
    pr = mu.propose_from_cluster(_sigs(), "ctx", want_code=True)
    assert pr is not None and pr.code.startswith("def average")
    assert len(_calls) == 2, len(_calls)


def test_r295_raises_quota_bad_component():
    """★ raises 配额：component 非法⇒构造期 EvolverError（门 ②）。"""
    from dwc.organs.evolver import Proposal, EvolverError
    with pytest.raises(EvolverError):
        Proposal(proposal_id="P_x",
                 failure_signature={"c": "E", "q": "q", "m": "m"},
                 component="no_such_comp", target="average",
                 patch="p", rationale="r")
