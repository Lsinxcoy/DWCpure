# -*- coding: utf-8 -*-
"""★ R351 · Cross-branch recombination (Evo² crossover)."""
import importlib.util
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))


def _load():
    spec = importlib.util.spec_from_file_location(
        "evolver_r351", os.path.join(ROOT, "src", "dwc", "organs", "evolver.py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_r351_select_donor():
    mod = _load()
    Mu = mod.Mutator
    Mu.GENE_BANK.clear()
    Mu.gene_bank_update("runtime|code", {"target_layer": "runtime", "task": "code_fix_007",
                                        "in_score": 0.8, "baseline_in": 0.5,
                                        "mechanism": "empty_list_guard"})
    d = Mu.select_donor("code_fix_007")
    assert d is not None
    assert d["mechanism"] == "empty_list_guard"
    assert "observed_effect" in d


def test_r351_donor_none():
    mod = _load()
    Mu = mod.Mutator
    Mu.GENE_BANK.clear()
    assert Mu.select_donor("code_fix_007") is None
