# -*- coding: utf-8 -*-
"""★ R356 · Pairwise workflow preference (MASS)."""
import importlib.util, os, sys
ROOT="E:/Divine Wisdom Core"; sys.path.insert(0, os.path.join(ROOT,"src"))
def _load():
    spec=importlib.util.spec_from_file_location("ev_r356", os.path.join(ROOT,"src","dwc","organs","evolver.py"))
    m=importlib.util.module_from_spec(spec); sys.modules[spec.name]=m; spec.loader.exec_module(m); return m
def test_r356_preference():
    m=_load()
    assert m.Mutator.workflow_preference({"score":0.8},{"score":0.3})=="a"
    assert m.Mutator.workflow_preference({"score":0.1},{"score":0.9})=="b"
    assert m.Mutator.workflow_preference({"score":0.5},{"score":0.5})=="tie"
