# -*- coding: utf-8 -*-
"""★ R328 · trial 复现力分流（R327 live 实证：63 条 llm_asserted sigs，
trial 全满分 —— 生产挂的是 agent 执行侧自断言，trial 跑的是 judge
verifier，两条线；evo 只吃 verifier 可复现簇）。

锁：
1. 默认：llm_asserted* 不进簇（执行侧归 agent_quality 回路）。
2. reproducible_only=False：全收老路（预算自负）。
3. 正常 m：默认保留（分流只剔执行侧）。
4. run_round 透传：默认 True 过滤；False 全收。
"""
import importlib.util
import os
import sqlite3
import sys

ROOT = r"E:/Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "src"))


def _load():
    spec = importlib.util.spec_from_file_location(
        "evo_round_r328_test",
        os.path.join(ROOT, "scripts", "dwc_evo_round.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _mkdb(path, rows):
    con = sqlite3.connect(path)
    try:
        con.execute("CREATE TABLE failure_sig (c TEXT, q TEXT, m TEXT,"
                    " node_id TEXT)")
        for r in rows:
            con.execute("INSERT INTO failure_sig VALUES (?,?,?,?)", r)
        con.commit()
    finally:
        con.close()


class _Evolver:
    def diagnose(self, sigs):
        return {"unmapped": sigs}


def _collect(mod, db, **kw):
    return mod.collect_unmapped(
        db, _Evolver(), lambda r: "f", lambda r: "t", **kw)


def test_r328_filters_llm_asserted_by_default(tmp_path):
    mod = _load()
    db = str(tmp_path / "t.sqlite")
    _mkdb(db, [("E", "Q", "llm_asserted:0.15", "n1"),
               ("E", "Q", "M-normal", "n2")])
    cls = _collect(mod, db)
    assert len(cls) == 1
    assert cls[0]["sigs"][0]["node_id"] == "n2"


def test_r328_opt_out_keeps_all(tmp_path):
    mod = _load()
    db = str(tmp_path / "t.sqlite")
    _mkdb(db, [("E", "Q", "llm_asserted:0.15", "n1")])
    cls = _collect(mod, db, reproducible_only=False)
    assert len(cls) == 1


def test_r328_run_round_plumbs_flag(tmp_path):
    mod = _load()
    db = str(tmp_path / "t.sqlite")
    _mkdb(db, [("E", "Q", "llm_asserted:0.15", "n1")])
    rep = mod.run_round(db, _Evolver(), None, "ctx",
                        lambda task, patch, code=None: False,
                        False, rules_path="", max_attempts=1,
                        fn_of=lambda r: "f", task_of=lambda r: "t")
    assert rep["results"] == [] and rep["envelope"]["trial_rounds"] == 0
    rep = mod.run_round(db, _Evolver(), None, "ctx",
                        lambda task, patch, code=None: False,
                        False, rules_path="", max_attempts=1,
                        fn_of=lambda r: "f", task_of=lambda r: "t",
                        reproducible_only=False)
    assert len(rep["results"]) == 1
