# -*- coding: utf-8 -*-
"""★ A1b · fresh 独立验证集 V_k 首版（18813 Eq.8：判分接入 fresh split
另轮 A1b-2；本轮任务集＋隔离锁）。

锁：
1. fresh.json 5 任务，judge._load 全校验通过（形态合法）。
2. 零交集：fresh 的 fn/args/expected 与 dev＋sealed＋pairing 全无交集
   （E1 硬约束：fresh 形态不进 trial/peer prompt —— 交集即红）。
3. Eq.8 m 首用：provenance 声明 m=5（accept m 参数 A1a 已就绪）。
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.organs.judge import Judge

FRESH = os.path.join(ROOT, "config", "anchors", "fresh.json")


def _load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def test_a1b_loads_clean():
    data = Judge()._load(FRESH, "fresh")
    tasks = [k for k in data if not k.startswith("_")]
    assert len(tasks) == 5
    for t in tasks:
        rec = data[t]
        assert rec["verifier_kind"] == "behavior"
        for c in rec["checks"]:
            assert c["fn"] and c["args"] and c["expected"]


def test_a1b_zero_overlap():
    fresh = _load(FRESH)
    dev = _load(os.path.join(ROOT, "config", "anchors", "dev.json"))
    sealed = _load(os.path.join(ROOT, "config", "anchors",
                                "test_sealed.json"))
    pairing = _load(os.path.join(ROOT, "config", "anchors",
                                 "dev_sealed_pairing.json"))
    old_fns, old_args, old_exps = set(), set(), set()
    for src in (dev, sealed):
        for tid, rec in src.items():
            if tid.startswith("_") or not isinstance(rec, dict):
                continue
            for c in rec.get("checks", []) or []:
                old_fns.add(c.get("fn"))
                old_args.add(c.get("args"))
                old_exps.add(c.get("expected"))
    old_fns |= set(pairing.keys()) | set(pairing.values())
    for tid, rec in fresh.items():
        if tid.startswith("_"):
            continue
        for c in rec["checks"]:
            assert c["fn"] not in old_fns, c["fn"]
            assert c["fn"].startswith("fresh_")
            assert c["args"] not in old_args, c["args"]
            assert c["expected"] not in old_exps, c["expected"]


def test_a1b_m_declared():
    fresh = _load(FRESH)
    assert fresh["_provenance"]["m"] == 5
    assert "Eq.8" in fresh["_provenance"]["why"]


# ★ R330/N2 · fresh split 判分接入（Eq.8 V_k 的 m 有了真实来源 ——
#   judge.evaluate(split="fresh") 走同 behavior 路；DWC 自有第 4 面，
#   论文三元组不动）。
def _judge():
    from dwc.organs.judge import Judge, SPLIT_FRESH
    return Judge(), SPLIT_FRESH


def test_a1b2_fresh_pass():
    j, fr = _judge()
    v = j.evaluate("fresh_range_sum", fr, observed={
        "fresh_range_sum": [[[2, 6], 20], [[3, 7], 25]]})
    assert v.success is True


def test_a1b2_fresh_fail():
    j, fr = _judge()
    v = j.evaluate("fresh_range_sum", fr, observed={
        "fresh_range_sum": [[[2, 6], 21], [[3, 7], 25]]})
    assert v.success is False
    assert v.failure_signature is not None


def test_a1b2_fresh_unevaluated_and_cross_split_raise():
    import pytest
    from dwc.organs.judge import JudgeError
    j, fr = _judge()
    assert j.evaluate("fresh_range_sum", fr,
                      observed=None).success is None
    with pytest.raises(JudgeError):
        j.evaluate("fresh_range_sum", "dev", observed={})
    with pytest.raises(JudgeError):
        j.evaluate("code_fix_001", fr, observed={})


def test_a1b2_fresh_missing_raises_no_substitute():
    import pytest
    from dwc.organs.judge import Judge, JudgeError
    j = Judge(fresh_path=os.path.join(ROOT, "no_such_fresh.json"))
    assert j.fresh is None
    with pytest.raises(JudgeError):
        j.evaluate("fresh_range_sum", "fresh", observed={})
