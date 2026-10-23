# -*- coding: utf-8 -*-
"""★ R358 · Trace distillation (MASS)."""
import importlib.util, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
def _load():
    spec=importlib.util.spec_from_file_location("ev_r358", os.path.join(ROOT,"src","dwc","organs","evolver.py"))
    m=importlib.util.module_from_spec(spec); sys.modules[spec.name]=m; spec.loader.exec_module(m); return m
def test_r358_distill():
    m=_load()
    sk=m.Mutator.distill_trace({"task":"t1","workflow_prompt":"p","trajectory":"traj","worker_calls":2,"deliverable_coverage":0.7})
    assert sk["name"]=="t1" and sk["source"]=="mass_trace"
    assert "t1" in m.Mutator.SKILLS
