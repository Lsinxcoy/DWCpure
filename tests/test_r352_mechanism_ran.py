# -*- coding: utf-8 -*-
"""★ R352 · Reflector gain crediting (mechanism_ran)."""
import importlib.util
import os
import sys

ROOT = "E:/Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "src"))


def _load():
    spec = importlib.util.spec_from_file_location(
        "evolver_r352", os.path.join(ROOT, "src", "dwc", "organs", "evolver.py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_r352_mechanism_ran_crediting():
    mod = _load()
    Ev = mod.Evolver
    P = mod.Proposal
    p = P(proposal_id="x", failure_signature={"m": "M"}, component="skill",
          target="t", patch="p", rationale="r", state="adopted_not_implemented")
    base = {"in_score": 0.0, "held_out_score": 0.0}
    cur = {"in_score": 1.0, "held_out_score": 1.0}
    r = Ev.accept(p, base, cur, improver_gain=True, mechanism_ran=True)
    assert r["gain_type"] == "both"
    assert r["mechanism_ran"] is True
    r2 = Ev.accept(p, base, cur, improver_gain=True, mechanism_ran=False)
    assert r2["gain_type"] == "capability (improver unverified)"
    assert r2["mechanism_ran"] is False
