# -*- coding: utf-8 -*-
"""★ C2 · carried 率（RULES 记"被后轮 propose 引用次数"，companion Eq.11
activation 第三级）。

锁：
1. propose 直接命中 ⇒ carried＋1（连调两次＋2）。
2. propose_lateral 近亲引用 ⇒ 归因到被借的 kin（本 fn 无规则不计数）。
3. 脏 key 不崩不断主路；落盘 round-trip 保留 carried（learned 跨重启累计）。
"""
from __future__ import annotations

import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.organs.evolver import Mutator

SEED = "E_VALUE:wrong_magnitude:sum_first_n"


@pytest.fixture()
def clean_seed():
    Mutator.RULES[SEED].pop("carried", None)
    yield
    Mutator.RULES[SEED].pop("carried", None)


def _sig(fn="sum_first_n"):
    return {"c": "E_VALUE", "q": "wrong_magnitude", "fn": fn}


def test_c2_direct_hit(clean_seed):
    mu = Mutator()
    assert mu.propose(_sig()) is not None
    assert mu.propose(_sig()) is not None
    assert Mutator.RULES[SEED]["carried"] == 2


def test_c2_lateral_attributes_to_kin():
    kin = "E_VALUE:wrong_magnitude:pow2"  # 同族 sorted 首个（确定性）
    Mutator.RULES[kin].pop("carried", None)
    try:
        mu = Mutator()
        p = mu.propose_lateral(_sig(fn="other_fn"))
        assert p is not None
        assert Mutator.RULES[kin].get("carried", 0) >= 1
        assert "other_fn" not in Mutator.RULES  # 本 fn 无规则，不建条目
    finally:
        Mutator.RULES[kin].pop("carried", None)


def test_c2_dirty_key_never_breaks():
    Mutator._carry("不存在:key")
    Mutator._carry("")
    assert "不存在:key" not in Mutator.RULES


def test_c2_persist_roundtrip(tmp_path, monkeypatch):
    key = "E_VALUE:wrong_magnitude:c2_tmp_fn"
    rule = {"component": "control_flow", "dimension": "D7",
            "target": "t", "patch": "p", "rationale": "r"}
    Mutator.RULES[key] = dict(rule)
    try:
        monkeypatch.setattr(Mutator, "LEARNED_PATH",
                            str(tmp_path / "rules.json"))
        assert Mutator().propose(_sig(fn="c2_tmp_fn")) is not None
        assert Mutator.RULES[key]["carried"] == 1
        Mutator.persist_learned()
        on_disk = json.load(
            open(str(tmp_path / "rules.json"), encoding="utf-8"))
        assert on_disk["learned"][key]["carried"] == 1
        del Mutator.RULES[key]
        assert Mutator.load_learned() >= 1
        assert Mutator.RULES[key]["carried"] == 1  # 跨重启累计不断
    finally:
        Mutator.RULES.pop(key, None)
