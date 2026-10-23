# -*- coding: utf-8 -*-
"""★ R338 · Proposal 原子算子字段（OpenRSI Draft/Improve/Debug/Crossover）。"""
import importlib.util
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))


def _load():
    spec = importlib.util.spec_from_file_location(
        "evolver_r338", os.path.join(ROOT, "src", "dwc", "organs", "evolver.py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_r338_operator_default_and_field():
    mod = _load()
    P = mod.Proposal
    p = P(proposal_id="x", failure_signature={}, component="skill",
          target="t", patch="p", rationale="r")
    assert p.operator == "improve"
    p2 = P(proposal_id="x2", failure_signature={}, component="skill",
           target="t", patch="p", rationale="r", operator="debug")
    assert p2.operator == "debug"
