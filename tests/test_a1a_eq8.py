# -*- coding: utf-8 -*-
"""★ A1a · 18813 Eq.8 四数显式化（m/KT/T/δ，判分零改 —— fresh 集另轮 A1b）。

锁：
1. 默认 Eq8＝{m:None, KT:1, T 默认, delta:0.05, hoeffding:None}（缺席不编数）。
2. 显式 m=2/k=1/δ=0.05 ⇒ hoeffding＝√(2ln(20)/2)≈1.7308。
3. 显式传大 m/k 不改 decision/gates（判分零改实证）。
4. blocked/not_evaluated 出口同样带 Eq8（口径齐）。
"""
from __future__ import annotations

import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.organs.evolver import Evolver


def _base_cur():
    return ({"in_score": 0.4, "held_out_score": 0.4},
            {"in_score": 0.6, "held_out_score": 0.5})


def test_a1a_default():
    b, c = _base_cur()
    r = Evolver.accept(None, b, c)
    assert r["Eq8"] == {"m": None, "KT": 1, "T": r["T"], "delta": 0.05,
                        "hoeffding": None}
    assert r["T"] == {"lam": 0.0, "delta": 0.0, "gamma": 0.0}


def test_a1a_hoeffding_value():
    b, c = _base_cur()
    r = Evolver.accept(None, b, c, m=2, k_comparisons=1, delta_conf=0.05)
    assert abs(r["Eq8"]["hoeffding"]
               - math.sqrt(2.0 * math.log(1 / 0.05) / 2)) < 1e-9
    assert r["Eq8"]["KT"] == 1


def test_a1a_no_judge_change():
    b, c = _base_cur()
    r0 = Evolver.accept(None, dict(b), dict(c))
    r1 = Evolver.accept(None, dict(b), dict(c), m=50, k_comparisons=4,
                        delta_conf=0.01)
    assert r1["decision"] == r0["decision"]
    assert [g["pass"] for g in r1["gates"]] == \
        [g["pass"] for g in r0["gates"]]


def test_a1a_all_exits_carry_eq8():
    r = Evolver.accept(None, {"in_score": None},
                       {"in_score": 0.6, "held_out_score": 0.5})
    assert r["decision"] == "not_evaluated"
    assert r["Eq8"]["m"] is None
    r = Evolver.accept(None, {"in_score": 0.4},
                       {"in_score": 0.6, "held_out_score": None})
    assert r["decision"] == "blocked"
    assert r["Eq8"]["KT"] == 1
    assert "T" in r["Eq8"]
