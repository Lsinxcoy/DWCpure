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
