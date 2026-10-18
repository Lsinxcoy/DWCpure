# -*- coding: utf-8 -*-
"""★ R357 · Structural guardrails (MASS)."""
import importlib.util, os, sys
ROOT="E:/Divine Wisdom Core"; sys.path.insert(0, os.path.join(ROOT,"src"))
def _load():
    spec=importlib.util.spec_from_file_location("ev_r357", os.path.join(ROOT,"src","dwc","organs","evolver.py"))
    m=importlib.util.module_from_spec(spec); sys.modules[spec.name]=m; spec.loader.exec_module(m); return m
def test_r357_guardrails():
    m=_load()
    ok=m.Mutator.guardrails_ok({"worker_calls":3,"deliverable_coverage":0.8,"trajectory":"t"})
    assert ok["ok"] is True
    bad=m.Mutator.guardrails_ok({"worker_calls":0,"deliverable_coverage":0.2,"loop_detected":True})
    assert bad["ok"] is False and len(bad["reasons"])>=2
