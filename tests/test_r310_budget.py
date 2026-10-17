# -*- coding: utf-8 -*-
"""R310-⑤ · 重试预算：单簇 trial 非 True 最多试 max_attempts 次（默认 3）。"""
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
        "evo_round_b_under_test",
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


def _run(db_sigs, trial_seq, max_attempts, tmp_path):
    EVO = _load_evo_round()
    db = str(tmp_path / "t.sqlite")
    _mkdb(db)
    calls = []

    def _trial(task, patch, code=None):
        calls.append(task)
        return trial_seq[min(len(calls) - 1, len(trial_seq) - 1)]

    rep = EVO.run_round(db, _Evolver(db_sigs), _Mu(), "ctx", _trial, False,
                        rules_path="", max_attempts=max_attempts)
    return rep, calls


def _sigs():
    return [{"c": "C1", "q": "Q1", "m": "M1", "fn": "average",
             "task": "code_fix_007", "node_id": "n1"}]


def test_retry_until_true(tmp_path):
    rep, calls = _run(_sigs(), [False, False, True], 3, tmp_path)
    assert len(calls) == 3, calls
    assert rep["results"][0]["trial"] is True
    assert rep["results"][0]["attempts"] == 3


def test_budget_exhausted_stops(tmp_path):
    rep, calls = _run(_sigs(), [False], 2, tmp_path)
    assert len(calls) == 2, calls
    r = rep["results"][0]
    assert r["trial"] is False and r["attempts"] == 2
    assert "预算" in r.get("reason", ""), r


def test_default_budget_is_three(tmp_path):
    EVO = _load_evo_round()
    import inspect as _ins
    assert _ins.signature(EVO.run_round).parameters[
        "max_attempts"].default == 3


class _MuHint:
    def __init__(self):
        self.hints = []

    def propose_from_cluster(self, sigs, context, want_code=False,
                             learned_hint=""):
        self.hints.append(learned_hint)
        return types.SimpleNamespace(proposal_id="P1", patch="patch",
                                     code=None, state=None)


def test_fix_rerun_failed_cluster(tmp_path):
    EVO = _load_evo_round()
    db = str(tmp_path / "t.sqlite")
    _mkdb(db)
    ledger = tmp_path / "ledger.jsonl"
    import datetime as _dt
    today = _dt.date.today().isoformat()
    k = "K_FIX"
    ledger.write_text(json.dumps({"date": today, "key": k, "ok": False,
                                  "note": "沙箱拒：禁 import"}) + "\n",
                      encoding="utf-8")
    sigs = [{"c": "C1", "q": "Q1", "m": "M1", "fn": "average",
             "task": "code_fix_007", "node_id": "n1"}]
    # key_for 不可控，改用 ledger key 匹配：直接测 _read_done 语义＋hint 注入
    mu = _MuHint()
    calls = []

    def _trial(task, patch, code=None):
        calls.append(task)
        return True

    # 用 monkeypatch key：把 sigs 的 key 算出来再写 ledger
    from dwc.organs.evolver import Mutator
    real_k = Mutator.key_for({"c": "C1", "q": "Q1", "fn": "average"})
    ledger.write_text(json.dumps({"date": today, "key": real_k, "ok": False,
                                  "note": "沙箱拒：禁 import"}) + "\n",
                      encoding="utf-8")
    rep = EVO.run_round(db, _Evolver(sigs), mu, "ctx", _trial, False,
                        rules_path="", ledger_path=str(ledger),
                        ledger_date=today)
    assert len(calls) == 1, calls
    assert any("沙箱拒" in h for h in mu.hints), mu.hints


def test_ok_true_still_skips(tmp_path):
    EVO = _load_evo_round()
    db = str(tmp_path / "t.sqlite")
    _mkdb(db)
    import datetime as _dt
    today = _dt.date.today().isoformat()
    from dwc.organs.evolver import Mutator
    real_k = Mutator.key_for({"c": "C1", "q": "Q1", "fn": "average"})
    ledger = tmp_path / "ledger.jsonl"
    ledger.write_text(json.dumps({"date": today, "key": real_k,
                                  "ok": True}) + "\n", encoding="utf-8")
    sigs = [{"c": "C1", "q": "Q1", "m": "M1", "fn": "average",
             "task": "code_fix_007", "node_id": "n1"}]
    calls = []

    def _trial(task, patch, code=None):
        calls.append(task)
        return True

    EVO.run_round(db, _Evolver(sigs), _Mu(), "ctx", _trial, False,
                  rules_path="", ledger_path=str(ledger), ledger_date=today)
    assert calls == []
