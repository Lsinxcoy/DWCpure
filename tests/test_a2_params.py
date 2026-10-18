# -*- coding: utf-8 -*-
"""★ A2 · 门参数 (λ,δ,γ) 显式化（Cai Cor 1，判分零改）。

锁：
1. 默认：过门返回带 T＝{lam:0.0, delta:eps, gamma:0.0}。
2. 显式传 lam/delta/gamma：T 透出传入值，但 decision 与默认逐字相同
   （判分零改实证）——显式化只记录，不改判。
3. blocked/not_evaluated 出口同样带 T（口径齐）。
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.organs.evolver import Evolver


def _base_cur():
    return ({"in_score": 0.4, "held_out_score": 0.4},
            {"in_score": 0.6, "held_out_score": 0.5})


def test_a2_default_T():
    b, c = _base_cur()
    r = Evolver.accept(None, b, c)
    assert r["decision"] == "adopted_not_implemented"
    assert r["T"] == {"lam": 0.0, "delta": 0.0, "gamma": 0.0}


def test_a2_explicit_no_judge_change():
    b, c = _base_cur()
    r0 = Evolver.accept(None, dict(b), dict(c))
    r1 = Evolver.accept(None, dict(b), dict(c),
                        lam=0.5, delta=0.1, gamma=0.2)
    assert r1["T"] == {"lam": 0.5, "delta": 0.1, "gamma": 0.2}
    assert r1["decision"] == r0["decision"]  # 判分零改
    assert r1["delta_in"] == r0["delta_in"]
    assert [g["pass"] for g in r1["gates"]] == \
        [g["pass"] for g in r0["gates"]]


def test_a2_all_exits_carry_T():
    r = Evolver.accept(None, {"in_score": None},
                       {"in_score": 0.6, "held_out_score": 0.5})
    assert r["decision"] == "not_evaluated"
    assert r["T"] == {"lam": 0.0, "delta": 0.0, "gamma": 0.0}
    r = Evolver.accept(None, {"in_score": 0.4},
                       {"in_score": 0.6, "held_out_score": None})
    assert r["decision"] == "blocked"
    assert r["T"]["delta"] == 0.0
    b, c = _base_cur()
    r = Evolver.accept(None, dict(b), {"in_score": 0.1,
                                       "held_out_score": 0.2}, eps=0.05)
    assert r["decision"] == "rejected"  # d_in=-0.3<-eps：退化拒
    assert r["T"]["delta"] == 0.05  # delta 取 eps
