# -*- coding: utf-8 -*-
"""★ R349 · Reconstructive retrieval (DWC 内部)。"""
import importlib.util
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))


def _load():
    spec = importlib.util.spec_from_file_location(
        "evolver_r349", os.path.join(ROOT, "src", "dwc", "organs", "evolver.py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_r349_reconstruct_context_returns_str():
    mod = _load()
    Mu = mod.Mutator
    Mu.ARCHIVE.clear()
    Mu.archive_candidate("k1", {"target_layer": "runtime", "task": "code_fix_007",
                               "success": True, "partial": 1.0, "patch": "def x(): pass"})
    rc = Mu.reconstruct_context("code_fix_007")
    assert isinstance(rc, str)
    assert "code_fix_007" in rc
    assert "Reconstructed" in rc


def test_r349_reconstruct_empty():
    mod = _load()
    Mu = mod.Mutator
    Mu.ARCHIVE.clear()
    rc = Mu.reconstruct_context("code_fix_007")
    assert rc == ""
