# -*- coding: utf-8 -*-
"""★ B3 · 火力转攻（reasoning 组 pass 0.888 验证贵 → code_fix 组主攻）。

锁：
1. priority_prefixes＝("code_fix",)：后入库的 code_fix 簇排前，
   reasoning 簇保原序在后（稳定排序）。
2. 默认 None＝老路插入序（旧调用零变）。
3. run_round 透传；cron 生产传 ("code_fix",)（源码在位锁）。
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
        "evo_round_b3_test",
        os.path.join(ROOT, "scripts", "dwc_evo_round.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _mkdb(path, tasks):
    con = sqlite3.connect(path)
    try:
        con.execute("CREATE TABLE failure_sig (c TEXT, q TEXT, m TEXT,"
                    " node_id TEXT)")
        for i, t in enumerate(tasks):
            con.execute("INSERT INTO failure_sig VALUES ('C%d','Q1','M1',"
                        "'n%d')" % (i, i))
        con.commit()
    finally:
        con.close()


class _Evolver:
    def __init__(self, tasks):
        self._tasks = tasks

    def diagnose(self, sigs):
        return {"unmapped": sigs}


def _run(tasks, task_of, tmp_path, **kw):
    EVO = _load()
    db = str(tmp_path / "t.sqlite")
    _mkdb(db, tasks)
    by_task = dict(zip(["C0", "C1"], task_of))

    def _fn_of(r):
        return "f"

    def _task_of(r):
        return by_task.get(r[0], r[0])

    # ★ R437 · 本文件测优序，不测车道策略；合成 task 关掉分流。
    kw.setdefault("reproducible_only", False)
    return EVO.collect_unmapped(db, _Evolver([]), _fn_of, _task_of, **kw)


def test_b3_priority(tmp_path):
    cls = _run(["x", "y"], ["reasoning_001", "code_fix_007"], tmp_path,
               priority_prefixes=("code_fix",))
    tasks = [c["sigs"][0]["task"] for c in cls]
    assert tasks == ["code_fix_007", "reasoning_001"]


def test_b3_default_old_order(tmp_path):
    cls = _run(["x", "y"], ["reasoning_001", "code_fix_007"], tmp_path)
    tasks = [c["sigs"][0]["task"] for c in cls]
    assert tasks == ["reasoning_001", "code_fix_007"]  # 老路插入序


def test_b3_cron_wires_priority():
    src = open(os.path.join(ROOT, "scripts", "dwc_evo_round_cron.py"),
               encoding="utf-8").read()
    assert 'priority_prefixes=("code_fix",)' in src
