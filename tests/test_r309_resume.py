# -*- coding: utf-8 -*-
"""R309-⑦ · evo 断点续跑：epoch ledger＋resume。"""
import importlib.util
import json
import os
import sqlite3
import sys
import types

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = r"E:/Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "src"))


def _load_evo_round():
    spec = importlib.util.spec_from_file_location(
        "evo_round_under_test",
        os.path.join(ROOT, "scripts", "dwc_evo_round.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _mkdb(path):
    con = sqlite3.connect(path)
    try:
        con.execute("CREATE TABLE failure_sig (c TEXT, q TEXT, m TEXT,"
                    " node_id TEXT)")
        con.execute("INSERT INTO failure_sig VALUES ('C1','Q1','M1','n1')")
        con.execute("INSERT INTO failure_sig VALUES ('C2','Q2','M2','n2')")
        con.commit()
    finally:
        con.close()


class _Evolver:
    def __init__(self, sigs):
        self._sigs = sigs

    def diagnose(self, sigs):
        return {"unmapped": self._sigs}


class _Mu:
    def __init__(self):
        self.n = 0

    def propose_from_cluster(self, sigs, context, want_code=False,
                             learned_hint=""):
        self.n += 1
        return types.SimpleNamespace(proposal_id="P%d" % self.n,
                                     patch="patch", code=None, state=None)


def test_resume_skips_done_cluster(tmp_path):
    EVO = _load_evo_round()
    db = str(tmp_path / "t.sqlite")
    _mkdb(db)
    from dwc.organs.evolver import Mutator
    sigs = [{"c": "C1", "q": "Q1", "m": "M1", "fn": "average",
             "task": "code_fix_007", "node_id": "n1"},
            {"c": "C2", "q": "Q2", "m": "M2", "fn": "average",
             "task": "code_fix_007", "node_id": "n2"}]
    k1 = Mutator.key_for({"c": "C1", "q": "Q1", "fn": "average"})
    ledger = tmp_path / "ledger.jsonl"
    ledger.write_text(json.dumps({"date": "2026-10-17", "key": k1}) + "\n",
                      encoding="utf-8")
    calls = []

    def _trial(task, patch, code=None):
        calls.append(task)
        return True

    rep = EVO.run_round(db, _Evolver(sigs), _Mu(), "ctx", _trial, False,
                        rules_path="", ledger_path=str(ledger),
                        resume=True, ledger_date="2026-10-17")
    assert len(calls) == 1, calls
    assert rep["n_clusters"] == 2
    done_keys = [r["key"] for r in rep["results"]]
    assert k1 in done_keys


def test_no_ledger_runs_all(tmp_path):
    EVO = _load_evo_round()
    db = str(tmp_path / "t.sqlite")
    _mkdb(db)
    sigs = [{"c": "C1", "q": "Q1", "m": "M1", "fn": "average",
             "task": "code_fix_007", "node_id": "n1"}]
    calls = []

    def _trial(task, patch, code=None):
        calls.append(task)
        return True

    rep = EVO.run_round(db, _Evolver(sigs), _Mu(), "ctx", _trial, False,
                        rules_path="",
                        ledger_path=str(tmp_path / "none.jsonl"))
    assert len(calls) == 1


def test_bad_ledger_line_skipped(tmp_path):
    EVO = _load_evo_round()
    db = str(tmp_path / "t.sqlite")
    _mkdb(db)
    sigs = [{"c": "C1", "q": "Q1", "m": "M1", "fn": "average",
             "task": "code_fix_007", "node_id": "n1"}]
    ledger = tmp_path / "ledger.jsonl"
    ledger.write_text("not json\n", encoding="utf-8")
    calls = []

    def _trial(task, patch, code=None):
        calls.append(task)
        return True

    EVO.run_round(db, _Evolver(sigs), _Mu(), "ctx", _trial, False,
                  rules_path="", ledger_path=str(ledger))
    assert len(calls) == 1
