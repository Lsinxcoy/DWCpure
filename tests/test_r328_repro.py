# -*- coding: utf-8 -*-
"""★ R328 → **R437 重锚** · 进化输入分流。

★★★ 为什么重锚（不是删测试）：
    R328 当年按 `m.startswith("llm_asserted")` 判"能不能复现" —— 那是**猜**。
    实测（2026-10-23，2053 条生产签名）：
      · 2034 条全被这个前缀过滤掉；
      · 其中 code_fix_002 的 `E_VALUE/wrong_magnitude` **确实能复现**
        （破坏实现跑出来就是 wrong_magnitude），只是被前缀一刀切掉了。
    ⇒ 旧锁把"错误口径"锁成了正确行为。R437 改成**实测**：
      跑该任务的破坏实现，签名 (c,q) 对得上 ⇒ 代码车道；对不上 ⇒ 行为车道。

锁（新口径）：
1. 分流依据 = `probe_signatures(task)` 的实测结果，**不是** m 前缀。
2. `llm_asserted*` 只要签名对得上，**允许**进代码车道（旧锁禁止）。
3. 对不上的进 `filtered_out`（行为车道），不静默丢。
4. `reproducible_only=False`：全收老路。
5. `run_round` 透传不变。
"""
import importlib.util
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
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


def test_r437_lane_by_probe_not_prefix(tmp_path, monkeypatch):
    """★★★ 同一种 m 前缀：签名对得上进代码道，对不上进行为道。"""
    mod = _load()
    monkeypatch.setattr(mod, "probe_signatures", lambda t: {("E", "Q")})
    db = str(tmp_path / "t.sqlite")
    _mkdb(db, [("E", "Q", "llm_asserted:0.15", "n1"),
               ("E", "Q2", "M-normal", "n2")])
    beh = []
    cls = _collect(mod, db, filtered_out=beh)
    code_ids = [s["node_id"] for c in cls for s in c["sigs"]]
    assert code_ids == ["n1"]
    assert [s["node_id"] for s in beh] == ["n2"]


def test_r437_llm_asserted_can_enter_code_lane(tmp_path, monkeypatch):
    """★★★ 旧锁「llm_asserted 一律不进簇」被实测推翻 —— 能复现就进。"""
    mod = _load()
    monkeypatch.setattr(mod, "probe_signatures", lambda t: {("E", "Q")})
    db = str(tmp_path / "t.sqlite")
    _mkdb(db, [("E", "Q", "llm_asserted:0.15", "n1")])
    cls = _collect(mod, db)
    assert len(cls) == 1
    assert cls[0]["sigs"][0]["node_id"] == "n1"


def test_r328_opt_out_keeps_all(tmp_path):
    mod = _load()
    db = str(tmp_path / "t.sqlite")
    _mkdb(db, [("E", "Q", "llm_asserted:0.15", "n1")])
    cls = _collect(mod, db, reproducible_only=False)
    assert len(cls) == 1


def test_r437_run_round_plumbs_flag(tmp_path, monkeypatch):
    mod = _load()
    # 合成 task "t" 不在锚点集里；这里要测的是「分流开关透传」，
    # 所以把探针固定成空集（= 判为行为车道）。
    monkeypatch.setattr(mod, "probe_signatures", lambda t: set())
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
