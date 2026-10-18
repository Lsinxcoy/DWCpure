# -*- coding: utf-8 -*-
"""★ R360 · Delegation rate (MASS)."""
import importlib.util, os, sys
ROOT="E:/Divine Wisdom Core"; sys.path.insert(0, os.path.join(ROOT,"src"))
def _load():
    spec=importlib.util.spec_from_file_location("ev_r360", os.path.join(ROOT,"src","dwc","organs","evolver.py"))
    m=importlib.util.module_from_spec(spec); sys.modules[spec.name]=m; spec.loader.exec_module(m); return m
def test_r360_delegation():
    m=_load()
    traces=[{"worker_calls":1},{"worker_calls":0},{"delegated":True}]
    assert m.Mutator.delegation_rate(traces)==round(2/3,4)
    assert m.Mutator.delegation_rate([])==0.0
