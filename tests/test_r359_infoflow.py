# -*- coding: utf-8 -*-
"""★ R359 · Information-flow metric (MASS)."""
import importlib.util, os, sys
ROOT="E:/Divine Wisdom Core"; sys.path.insert(0, os.path.join(ROOT,"src"))
def _load():
    spec=importlib.util.spec_from_file_location("ev_r359", os.path.join(ROOT,"src","dwc","organs","evolver.py"))
    m=importlib.util.module_from_spec(spec); sys.modules[spec.name]=m; spec.loader.exec_module(m); return m
def test_r359_info_flow():
    m=_load()
    wg=m.Mutator.workflow_graph([{"agent_id":"a","role":"coder","instruction":"code it"}], contracts={"a":"src/x.py"})
    v=m.Mutator.information_flow(wg)
    assert v>0
