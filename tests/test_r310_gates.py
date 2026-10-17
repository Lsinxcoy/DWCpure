# -*- coding: utf-8 -*-
"""R310-① · 门阵列：accept 附 gates 明细（decision 口径零改）。"""
import os
import sys
import types

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = r"E:/Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "src"))


def _p():
    return types.SimpleNamespace(proposal_id="PX", patch="p", code=None,
                                 state=None, failure_signature={},
                                 target="average")


def test_gates_all_pass_on_adopt():
    from dwc.organs.evolver import Evolver
    r = Evolver.accept(_p(), {"in_score": 0.5, "held_out_score": 0.5},
                       {"in_score": 0.8, "held_out_score": 0.6})
    assert r["decision"] == "adopted_not_implemented", r
    gs = {g["name"]: g for g in r["gates"]}
    assert gs["in_sample_scored"]["pass"] is True
    assert gs["held_out_present"]["pass"] is True
    assert gs["no_regression"]["pass"] is True
    assert gs["real_improvement"]["pass"] is True


def test_gates_pinpoint_blocked():
    from dwc.organs.evolver import Evolver
    r = Evolver.accept(_p(), {"in_score": 0.5, "held_out_score": None},
                       {"in_score": 0.8, "held_out_score": None})
    assert r["decision"] == "blocked", r
    gs = {g["name"]: g for g in r["gates"]}
    assert gs["in_sample_scored"]["pass"] is True
    assert gs["held_out_present"]["pass"] is False
    assert gs["no_regression"]["pass"] is None
    assert all(set(g) >= {"name", "pass", "detail"} for g in r["gates"])


def test_gates_not_evaluated_first_gate():
    from dwc.organs.evolver import Evolver
    r = Evolver.accept(_p(), {"in_score": None, "held_out_score": None},
                       {"in_score": None, "held_out_score": None})
    assert r["decision"] == "not_evaluated", r
    gs = {g["name"]: g for g in r["gates"]}
    assert gs["in_sample_scored"]["pass"] is False
