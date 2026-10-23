# -*- coding: utf-8 -*-
"""★ D2 · envelope 声明（companion：search cost 与 envelope 分开列）。

锁：
1. 每轮 report 带 envelope：trial_rounds＝attempts 求和；by_mode＝trial
   mode 分布；llm_calls/tokens 诚实标 unmeasured（不编数）。
2. bool trial 归 legacy_bool（零 search 查表面）；dict trial 按其 mode。
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
        "evo_round_d2_test",
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


def _run(trial_ret, tmp_path):
    EVO = _load()
    db = str(tmp_path / "t.sqlite")
    _mkdb(db)
    rep = EVO.run_round(db, _Evolver(_sigs()), _Mu(), "ctx",
                        lambda task, patch, code=None: trial_ret,
                        False, rules_path="")
    return rep


def test_d2_envelope_bool(tmp_path):
    rep = _run(False, tmp_path)
    env = rep["envelope"]
    # False 触发默认 3 次重试 ⇒ trial_rounds＝attempts 求和＝3；
    # by_mode 按 results 行计（末次 trial mode），两者口径注释在实现侧。
    assert env["trial_rounds"] == 3
    assert rep["results"][0]["attempts"] == 3
    assert env["by_mode"] == {"legacy_bool": 1}
    assert "unmeasured" in env["llm_calls"]
    assert "unmeasured" in env["tokens"]
    assert "另列" in env["search_cost"]


def test_d2_envelope_modes(tmp_path):
    EVO = _load()
    db = str(tmp_path / "t.sqlite")
    _mkdb(db)
    seq = [{"success": True, "mode": "code"},
           {"success": False, "mode": "report"}]
    calls = []

    def _trial(task, patch, code=None):
        calls.append(task)
        return seq[min(len(calls) - 1, 1)]
    # 两簇：第二簇需两个 sig 行 —— 用同一 trial 返回补位只跑一簇时按单簇计
    rep = EVO.run_round(db, _Evolver(_sigs()), _Mu(), "ctx", _trial,
                        False, rules_path="", max_attempts=1)
    env = rep["envelope"]
    assert env["trial_rounds"] == sum(
        r["attempts"] for r in rep["results"])
    assert sum(env["by_mode"].values()) == len(rep["results"])
