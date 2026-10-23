# -*- coding: utf-8 -*-
"""★ R348 · accept 记录 paired_screen (Raven paired improvement)。"""
import importlib.util
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))


def _load():
    spec = importlib.util.spec_from_file_location(
        "evolver_r348", os.path.join(ROOT, "src", "dwc", "organs", "evolver.py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_r348_paired_screen_recorded():
    mod = _load()
    Ev = mod.Evolver
    P = mod.Proposal
    p = P(proposal_id="x", failure_signature={"m": "M"}, component="skill",
          target="t", patch="p", rationale="r", state="adopted_not_implemented")
    base = {"in_score": 0.0, "held_out_score": 0.0}
    cur = {"in_score": 1.0, "held_out_score": 1.0}
    r = Ev.accept(p, base, cur, paired_screen=True)
    assert "paired_screen" in r
    assert r["paired_screen"] is True
