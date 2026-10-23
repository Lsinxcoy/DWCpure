# -*- coding: utf-8 -*-
"""★ R350 · DWC-internal skill system (register/select/evolve)。"""
import importlib.util
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))


def _load():
    spec = importlib.util.spec_from_file_location(
        "evolver_r350", os.path.join(ROOT, "src", "dwc", "organs", "evolver.py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_r350_skill_register_select():
    mod = _load()
    Mu = mod.Mutator
    Mu.SKILLS.clear()
    r = Mu.skill_register("skill_code_fix", "fix average", "handle empty list", "code_fix")
    assert r["registered"] is True
    assert r["version"] == 1
    r2 = Mu.skill_register("skill_code_fix", "fix average v2", "handle empty list v2", "code_fix")
    assert r2["version"] == 2
    sk = Mu.skill_select("code_fix_007")
    assert sk is not None
    assert sk["name"] == "skill_code_fix"


def test_r350_skill_evolve_from_sig():
    mod = _load()
    Mu = mod.Mutator
    Mu.SKILLS.clear()
    r = Mu.skill_evolve_from_sig({"task": "code_fix_007"}, patch="def x(): pass",
                                 rationale="empty list guard")
    assert r["registered"] is True
    sk = Mu.skill_select("code_fix_007")
    assert sk is not None
    assert "empty list guard" in sk["content"]
