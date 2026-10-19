# -*- coding: utf-8 -*-
"""★ C3 · RULES provenance＋withdraw（companion §9.7：毒规则必须可撤回
⇒ 先有来源才有撤回）。

锁：
1. _land_adopted 落条目带 provenance＝{task, admission_round}。
2. admission_round 缺席 ⇒ None（诚实缺席，不编轮号）。
3. withdraw：有 key ⇒ True＋返回含 provenance 的条目＋RULES 删除；
   无 key ⇒ False（幂等，不抛）。
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.organs.evolver import Evolver, Mutator, Proposal


def _proposal():
    return Proposal(
        proposal_id="P_C3TEST", failure_signature={"c": "E", "q": "q"},
        component="control_flow", target="c3_tmp_fn", patch="p",
        rationale="r", state="adopted_not_implemented")


def _clean(*keys):
    for k in keys:
        Mutator.RULES.pop(k, None)


def test_c3_provenance_landed():
    key = "E:q:c3_tmp_fn"
    _clean(key)
    try:
        ev = Evolver()
        out = ev._land_adopted(_proposal(), admission_round="2026-10-18")
        assert out["outcome"] == "landed"
        prov = Mutator.RULES[key]["provenance"]
        assert prov["task"] == "c3_tmp_fn"
        assert prov["admission_round"] == "2026-10-18"
        # ★ R340 · temporal scope 四字段必须落盘
        #   （无回滚触发条件的改进不算可持久 — RSI 审计纪律）
        ts = prov["temporal_scope"]
        assert set(ts) == {"effective_from", "scope",
                           "rollback_trigger", "expires"}
        assert ts["effective_from"] == "2026-10-18"
        assert ts["rollback_trigger"], "回滚触发条件不许为空"
    finally:
        _clean(key)


def test_c3_provenance_absent_is_none():
    key = "E:q:c3_tmp_fn"
    _clean(key)
    try:
        ev = Evolver()
        ev._land_adopted(_proposal())  # 不传轮号
        assert Mutator.RULES[key]["provenance"]["admission_round"] is None
    finally:
        _clean(key)


def test_c3_withdraw():
    key = "E:q:c3_tmp_fn"
    _clean(key)
    try:
        Evolver()._land_adopted(_proposal(), admission_round="R-X")
        r = Mutator.withdraw(key, reason="毒规则演练")
        assert r["withdrawn"] is True
        assert r["entry"]["provenance"]["admission_round"] == "R-X"
        assert key not in Mutator.RULES
        r2 = Mutator.withdraw(key)
        assert r2["withdrawn"] is False  # 幂等，不抛
    finally:
        _clean(key)
    assert Mutator.withdraw("根本不存在:key")["withdrawn"] is False
