# -*- coding: utf-8 -*-
"""★ R335 · temporal scope 字段随 landed 条目落盘。"""
import importlib.util
import os
import sys
import tempfile

ROOT = "E:/Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "src"))


def _load():
    spec = importlib.util.spec_from_file_location(
        "evolver_r335", os.path.join(ROOT, "src", "dwc", "organs", "evolver.py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_r335_temporal_scope_landed():
    mod = _load()
    M = mod.Mutator
    Ev = mod.Evolver
    with tempfile.TemporaryDirectory() as d:
        M.LEARNED_PATH = os.path.join(d, "rules.json")
        M.ARCHIVE_PATH = os.path.join(d, "archive.json")
        M.RULES.clear()
        M.ARCHIVE.clear()
        ev = Ev(mutator=M)
        sig = {"c": "E_VALUE", "q": "wrong_magnitude", "m": "M-wrong",
               "fn": "average", "task": "code_fix_007"}
        p = mod.Proposal(
            proposal_id="p1", failure_signature=sig,
            component="skill", target="average",
            patch="def average(xs): return sum(xs)/len(xs)",
            rationale="fix", state="adopted_not_implemented")
        r = ev._land_adopted(p, admission_round="2026-10-19")
        assert r["outcome"] == "landed"
        entry = M.RULES[r["key"]]
        ts = entry["provenance"]["temporal_scope"]
        assert ts["effective_from"] == "2026-10-19"
        assert ts["scope"] == "cross-task"
        assert ts["rollback_trigger"] == "held-out regression"
        assert ts["expires"] is None
        # reload check
        M.RULES.clear()
        M.load_learned()
        assert M.RULES[r["key"]]["provenance"]["temporal_scope"]["scope"] == "cross-task"
