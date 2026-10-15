# -*- coding: utf-8 -*-
"""★★★ R278 · LLM-Mutator（第二个 Mutator，可插拔）。

★ 隔离：llm 可注入 fake（零真调用）；只新增，不改 diagnose/propose。
★ 纪律：坏 JSON/缺字段 ⇒ None + 留痕（禁静默）；llm 抛异常 ⇒ 大声。
"""
import json as _json

import pytest

from dwc.organs.evolver import LLMMutator, Mutator


def _sig007():
    return {"c": "E_VALUE", "q": "wrong_magnitude",
            "m": "llm_asserted:0.15", "fn": "average",
            "split": "dev", "task": "code_fix_007"}


_GOOD_RULE = {
    "component": "prompt", "dimension": "D7",
    "target_layer": "assets", "target": "average",
    "m": "float_repr", "m_source": "llm",
    "patch": "观测 prompt 必须明示浮点逐位精确，禁四舍五入约值",
    "rationale": "average([0.1,0.2])真值0.15000000000000002，模型写0.15",
}


class TestLLMMutator:
    def test_good_json_yields_proposal(self):
        mu = LLMMutator(llm=lambda p: _json.dumps(_GOOD_RULE))
        p = mu.propose_from_cluster([_sig007(), _sig007()])
        assert p is not None
        assert p.failure_signature.get("task") == "code_fix_007"
        key = Mutator.key_for(_sig007())
        assert key not in Mutator.SEED_KEYS  # 新键，非种子
        assert key == "E_VALUE:wrong_magnitude:average"

    def test_garbage_json_returns_none_loud(self):
        mu = LLMMutator(llm=lambda p: "这不是JSON")
        assert mu.propose_from_cluster([_sig007()]) is None
        assert mu.last_reason  # 留痕，禁静默

    def test_missing_fields_returns_none(self):
        mu = LLMMutator(llm=lambda p: _json.dumps({"component": "x"}))
        assert mu.propose_from_cluster([_sig007()]) is None
        assert "缺字段" in (mu.last_reason or "")

    def test_llm_raises_is_loud(self):
        def _boom(p):
            raise RuntimeError("端点炸了")
        mu = LLMMutator(llm=_boom)
        with pytest.raises(RuntimeError):
            mu.propose_from_cluster([_sig007()])

    def test_empty_cluster_is_none(self):
        mu = LLMMutator(llm=lambda p: _json.dumps(_GOOD_RULE))
        assert mu.propose_from_cluster([]) is None


def test_context_enters_prompt():
    """★ context 对照事实必须进 prompt（防 LLM 编造数量级）。"""
    seen = {}
    mu = LLMMutator(llm=lambda p: (seen.update({"p": p}), _json.dumps(_GOOD_RULE))[1])
    ctx = "average([0.1,0.2]): 真值=0.15000000000000002, 断言=0.15"
    p = mu.propose_from_cluster([_sig007()], context=ctx)
    assert p is not None
    assert "0.15000000000000002" in seen["p"]


def test_retry_then_success():
    """★ 一次废稿+一次好稿 ⇒ 提案照出（重试是代码的事）。"""
    calls = {"n": 0}

    def _flaky(p):
        calls["n"] += 1
        if calls["n"] == 1:
            return "废话前言，无JSON"
        return _json.dumps(_GOOD_RULE)

    mu = LLMMutator(llm=_flaky)
    p = mu.propose_from_cluster([_sig007()], max_attempts=2)
    assert p is not None
    assert calls["n"] == 2


def test_prompt_bounds_thinking():
    """★ prompt 必须锁思考长度（防截断吞 JSON）。"""
    mu = LLMMutator(llm=lambda p: _json.dumps(_GOOD_RULE))
    p = mu._prompt([_sig007()], context="x")
    assert "200字" in p and "JSON" in p


def test_stray_braces_in_preamble_ignored():
    """★ 前言杂散括号/引号不许吞真 JSON（raw_decode 倒序真解析）。"""
    mu = LLMMutator(llm=lambda p: (
        '前言如 D7} "DWC" 模型的 \'average\' 想法：\n' + _json.dumps(_GOOD_RULE)))
    p = mu.propose_from_cluster([_sig007()])
    assert p is not None
    assert p.component == "prompt"
