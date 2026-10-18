# -*- coding: utf-8 -*-
"""★ R353 · U-shaped parent sampling (Evo²)."""
import importlib.util
import os
import sys

ROOT = "E:/Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "src"))


def _load():
    spec = importlib.util.spec_from_file_location(
        "evolver_r353", os.path.join(ROOT, "src", "dwc", "organs", "evolver.py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_r353_ushape_weight():
    mod = _load()
    Mu = mod.Mutator
    Mu.ARCHIVE.clear()
    Mu.archive_candidate("k", {"target_layer": "runtime", "task": "code_fix_007",
                              "in_score": 0.9})
    Mu.archive_candidate("k", {"target_layer": "runtime", "task": "code_fix_007",
                              "in_score": 0.1})
    # best/worst selection
    assert Mu.select_parent("k", strategy="best")["in_score"] == 0.9
    assert Mu.select_parent("k", strategy="worst")["in_score"] == 0.1
    # ushape weight: extremes > middle
    assert Mu.ushape_weight({"in_score": 0.9}) > Mu.ushape_weight({"in_score": 0.5})
    assert Mu.ushape_weight({"in_score": 0.1}) > Mu.ushape_weight({"in_score": 0.5})
