# -*- coding: utf-8 -*-
"""★ B1 · 独立深挖（Cai Thm 3：007 50 次失败同任务，单独立簇深挖＋hint
换血 ξ —— 旧 patch 已证伪，池外无解）。

锁：
1. task_filter：只收目标 task，其余不进簇。
2. hint_mode="fresh"：不用 RULES 旧 patch，改喂簇内失败明细（含换血标记）；
   默认 "reuse" 老路（含旧 patch 段）。
3. cron --deep-task 接线在位（task＋fresh＋单簇）。
"""
import importlib.util
import os
import sqlite3
import sys
import types

ROOT = r"E:/Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "src"))


def _load():
    spec = importlib.util.spec_from_file_location(
        "evo_round_b1_test",
        os.path.join(ROOT, "scripts", "dwc_evo_round.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _mkdb(path):
    con = sqlite3.connect(path)
    try:
        con.execute("CREATE TABLE failure_sig (c TEXT, q TEXT, m TEXT,"
                    " node_id TEXT)")
        con.execute("INSERT INTO failure_sig VALUES ('E1','Q1','M1','n1')")
        con.execute("INSERT INTO failure_sig VALUES ('E2','Q2','M2','n2')")
        con.commit()
    finally:
        con.close()


class _Evolver:
    def diagnose(self, sigs):
        return {"unmapped": sigs}


class _Mu:
    def __init__(self):
        self.hints = []

    def propose_from_cluster(self, sigs, context, want_code=False,
                             learned_hint="", operator="improve"):
        self.hints.append(learned_hint)
        return types.SimpleNamespace(proposal_id="P1", patch="patch",
                                     code=None, state=None)


def _run(tmp_path, task_of, **kw):
    EVO = _load()
    db = str(tmp_path / "t.sqlite")
    _mkdb(db)
    mu = _Mu()
    rep = EVO.run_round(db, _Evolver(), mu, "ctx",
                        lambda task, patch, code=None: False,
                        False, rules_path="", max_attempts=1,
                        fn_of=lambda r: "f%d" % (r[3] == "n2"),
                        task_of=task_of, **kw)
    return rep, mu


def test_b1_filter(tmp_path):
    rep, _ = _run(tmp_path, lambda r: ("code_fix_007" if r[3] == "n1"
                                      else "reasoning_001"),
                  task_filter="code_fix_007")
    assert len(rep["results"]) == 1
    assert rep["results"][0]["n"] == 1  # 只收了 n1（007）
    assert rep["n_clusters"] == 1


def test_b1_fresh_hint(tmp_path):
    _, mu = _run(tmp_path, lambda r: "code_fix_007", hint_mode="fresh")
    assert mu.hints, "propose 应被调用"
    assert "换血" in mu.hints[0]
    assert "E1/Q1/M1" in mu.hints[0]


def test_b1_reuse_old_way(tmp_path):
    _, mu = _run(tmp_path, lambda r: "code_fix_007")
    # 无旧 RULES 条目 ⇒ hint 空（老路：有旧条目才有段）；两簇各一次
    assert mu.hints == ["", ""]


def test_b1_cron_wires_deep_task():
    src = open(os.path.join(ROOT, "scripts", "dwc_evo_round_cron.py"),
               encoding="utf-8").read()
    assert "--deep-task" in src
    assert 'hint_mode=("fresh" if _a.deep_task else "reuse")' in src
