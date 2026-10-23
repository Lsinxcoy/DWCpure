# -*- coding: utf-8 -*-
"""★ R361-R368 · SwarmRSI absorption."""
import importlib.util, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
def _load():
    spec=importlib.util.spec_from_file_location("ev_swarm", os.path.join(ROOT,"src","dwc","organs","evolver.py"))
    m=importlib.util.module_from_spec(spec); sys.modules[spec.name]=m; spec.loader.exec_module(m); return m

def test_r361_mutation_type():
    m=_load()
    assert m.Mutator.mutation_type({"component":"code","patch":"x"})=="P"
    assert m.Mutator.mutation_type({"component":"hypothesis","operator":"H"})=="H"

def test_r362_state_graph():
    m=_load()
    g=m.Mutator.research_state_graph()
    g.add_record({"hypothesis":"h1","program":"p1","evidence":"e","need":"n"})
    a=g.assemble()
    assert a["n_records"]==1 and "h1" in a["hypotheses"]

def test_r363_rebase():
    m=_load()
    r=m.Mutator.rebase("h1","base2")
    assert r["source"]=="rebase" and r["program"]["rebased"] is True

def test_r364_crossover():
    m=_load()
    r=m.Mutator.crossover("parent", ["d1","d2"], {"k":0.5})
    assert r["source"]=="crossover" and r["donors"]

def test_r365_ucb():
    m=_load()
    assert m.Mutator.hp_ucb({"H":{"mu":0.1,"psi":0},"P":{"mu":0.2,"psi":0}}, N_H=1, N_P=1) in ("H","P")
    assert m.Mutator.hp_ucb({}, N_H=0, N_P=1)=="H"

def test_r366_audit_credit():
    m=_load()
    r=m.Mutator.audit_credit({"success":True,"score":0.5}, {"execution_ok":True,"artifact_valid":True}, {"flagged":False})
    assert r["credit"] is True
    r2=m.Mutator.audit_credit({"success":False,"score":0}, {"execution_ok":False}, {"flagged":True})
    assert r2["credit"] is False

def test_r367_emit_requests():
    m=_load()
    assert "deepen" in m.Mutator.emit_requests({"status":"failure"})
    assert "broaden" in m.Mutator.emit_requests({"status":"ok","per_instance_gains":[1,-1]})

def test_r368_transfer():
    m=_load()
    g=m.Mutator.research_state_graph()
    g.add_record({"hypothesis":"h","program":"p"})
    t=m.Mutator.transfer_state(g,"task2")
    assert t["target"]=="task2" and t["records"]
