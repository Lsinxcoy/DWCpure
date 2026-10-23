# -*- coding: utf-8 -*-
"""★ R340 · accept 记录 gain_type（capability vs improver）。"""
import importlib.util
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))


def _load():
    spec = importlib.util.spec_from_file_location(
        "evolver_r340", os.path.join(ROOT, "src", "dwc", "organs", "evolver.py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_r340_gain_type_capability():
    mod = _load()
    Ev = mod.Evolver
    P = mod.Proposal
    p = P(proposal_id="x", failure_signature={"m": "M"}, component="skill",
          target="t", patch="p", rationale="r", state="adopted_not_implemented")
    # accepted case: in_score 0->1, held_out 0->1
    base = {"in_score": 0.0, "held_out_score": 0.0}
    cur = {"in_score": 1.0, "held_out_score": 1.0}
    r = Ev.accept(p, base, cur)
    assert r["decision"] in ("accepted", "adopted_not_implemented")
    assert "gain_type" in r
    assert r["gain_type"].startswith("capability")


def test_r340_gain_type_none_for_rejected():
    mod = _load()
    Ev = mod.Evolver
    P = mod.Proposal
    p = P(proposal_id="x", failure_signature={"m": "M"}, component="skill",
          target="t", patch="p", rationale="r", state="adopted_not_implemented")
    base = {"in_score": 1.0, "held_out_score": 1.0}
    cur = {"in_score": 0.0, "held_out_score": 0.0}
    r = Ev.accept(p, base, cur)
    assert r["decision"] != "accepted"
    assert r["gain_type"] == "none"
