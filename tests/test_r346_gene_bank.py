# -*- coding: utf-8 -*-
"""★ R346 · Raven Gene Bank cell + elite (quality-diversity)。"""
import importlib.util
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))


def _load():
    spec = importlib.util.spec_from_file_location(
        "evolver_r346", os.path.join(ROOT, "src", "dwc", "organs", "evolver.py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_r346_gene_bank_cell_and_elite():
    mod = _load()
    Mu = mod.Mutator
    Mu.GENE_BANK.clear()
    Mu.archive_candidate("k1", {"target_layer": "runtime", "task": "code_fix_007",
                               "in_score": 0.5})
    Mu.archive_candidate("k2", {"target_layer": "runtime", "task": "code_fix_007",
                               "in_score": 0.8})
    cell = Mu.cell_of({"target_layer": "runtime", "task": "code_fix_007"})
    assert cell in Mu.GENE_BANK
    assert Mu.GENE_BANK[cell]["in_score"] == 0.8


def test_r346_cell_of_format():
    mod = _load()
    Mu = mod.Mutator
    assert Mu.cell_of({"target_layer": "skill", "task": "reasoning_001"}) == "skill|reasoning"
