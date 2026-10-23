# -*- coding: utf-8 -*-
"""★ B4 · 候选池 N（Cai Thm 3 Eq.8：N 进界 —— 池子里没有，验证再松也
收不到；单进程串行试，无真并行）。

锁：
1. pool_n＝单簇候选池上限：pool_n=1 时 attempts 至多 1（恒 False 也停）。
2. pool_n=None ⇒ max_attempts 老路（默认 3，旧调用零变）。
3. envelope 带 pool_N；cron --pool-n 接线在位。
"""
import importlib.util
import os
import sqlite3
import sys
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))


def _load():
    spec = importlib.util.spec_from_file_location(
        "evo_round_b4_test",
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
    def propose_from_cluster(self, sigs, context, want_code=False,
                             learned_hint="", operator="improve"):
        return types.SimpleNamespace(proposal_id="P1", patch="patch",
                                     code=None, state=None)


def _sigs():
    return [{"c": "C1", "q": "Q1", "m": "M1", "fn": "average",
             "task": "code_fix_007", "node_id": "n1"}]


def _run(tmp_path, **kw):
    EVO = _load()
    db = str(tmp_path / "t.sqlite")
    _mkdb(db)
    return EVO.run_round(db, _Evolver(_sigs()), _Mu(), "ctx",
                         lambda task, patch, code=None: False,
                         False, rules_path="", max_attempts=3,
                         fn_of=lambda r: "f", task_of=lambda r: "t", **kw)


def test_b4_pool_caps_attempts(tmp_path):
    rep = _run(tmp_path, pool_n=1)
    assert rep["results"][0]["attempts"] == 1
    assert rep["envelope"]["pool_N"] == 1


def test_b4_default_old_way(tmp_path):
    rep = _run(tmp_path)
    assert rep["results"][0]["attempts"] == 3  # max_attempts 老路
    assert rep["envelope"]["pool_N"] == 3


def test_b4_cron_wires_pool_n():
    src = open(os.path.join(ROOT, "scripts", "dwc_evo_round_cron.py"),
               encoding="utf-8").read()
    assert '"--pool-n"' in src
    assert "pool_n=_a.pool_n" in src
