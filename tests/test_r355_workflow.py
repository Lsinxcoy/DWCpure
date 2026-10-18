# -*- coding: utf-8 -*-
"""★ R355 · Workflow-as-graph primitive (MASS)."""
import importlib.util, os, sys
ROOT="E:/Divine Wisdom Core"; sys.path.insert(0, os.path.join(ROOT,"src"))
def _load():
    spec=importlib.util.spec_from_file_location("ev_r355", os.path.join(ROOT,"src","dwc","organs","evolver.py"))
    m=importlib.util.module_from_spec(spec); sys.modules[spec.name]=m; spec.loader.exec_module(m); return m
def test_r355_workflow_graph():
    m=_load()
    wg=m.Mutator.workflow_graph(
        [{"agent_id":"a","role":"coder","instruction":"code it","output_contract":"src/x.py"}],
        routing={"a":[]}, contracts={"a":{"file":"src/x.py"}})
    assert wg.validate()==[]
    p=m.Mutator.encode_workflow(wg)
    assert "coder" in p and "output_contract" in p
def test_r355_validate_errors():
    m=_load()
    wg=m.Mutator.workflow_graph([{"agent_id":"a","role":""}])
    assert wg.validate()
