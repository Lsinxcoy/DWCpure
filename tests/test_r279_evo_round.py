# -*- coding: utf-8 -*-
"""★★★ R279 · 进化收尾链（读库→聚簇→起草→试跑→报告，默认不落盘）。

★ 隔离：sqlite 用 tmp 库；llm/trial 全 fake；禁碰生产。
★ 落盘默认关（--apply 才写，且先备份）。
"""
import io
import json as _json
import os
import sqlite3
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(_HERE)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import dwc_evo_round as EVO
from dwc.organs.evolver import Evolver, LLMMutator


def _tmpdb(path):
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE failure_sig(c,q,m,node_id)")
    con.execute("INSERT INTO failure_sig VALUES(?,?,?,?)",
                ("E_VALUE", "wrong_magnitude", "M-wrong", "n1"))
    con.execute("INSERT INTO failure_sig VALUES(?,?,?,?)",
                ("E_VALUE", "wrong_magnitude", "M-wrong", "n2"))
    con.commit()
    con.close()
    return path


def _sig():
    return {"c": "E_VALUE", "q": "wrong_magnitude",
            "m": "M-wrong", "fn": "average", "task": "code_fix_007"}


_GOOD = {"component": "prompt", "dimension": "D7",
         "target_layer": "assets", "target": "average",
         "m": "float_repr", "patch": "p", "rationale": "r"}


class TestCollect:
    def test_unmapped_cluster_found(self, tmp_path):
        db = _tmpdb(str(tmp_path / "p.sqlite"))
        cls = EVO.collect_unmapped(db, Evolver(), fn_of=lambda r: "zzz_norule_fn",
                                   task_of=lambda r: "zzz_norule_task")
        assert len(cls) == 1 and len(cls[0]["sigs"]) == 2

    def test_empty_db_no_clusters(self, tmp_path):
        con = sqlite3.connect(str(tmp_path / "e.sqlite"))
        con.execute("CREATE TABLE failure_sig(c,q,m,node_id)")
        con.commit()
        con.close()
        assert EVO.collect_unmapped(str(tmp_path / "e.sqlite"), Evolver(),
                                    fn_of=lambda r: "x",
                                    task_of=lambda r: "y") == []

    def test_bad_db_loud(self):
        with pytest.raises(Exception):
            EVO.collect_unmapped("/nonexistent/x.sqlite", Evolver(),
                                 fn_of=lambda r: "x", task_of=lambda r: "y")


class TestMechAdvise:
    def test_mech_advise_wired(self, tmp_path, monkeypatch):
        # ★ 审计黄① · mech_log 传了⇒轮尾 advise，低分立案进 report；
        #   不传⇒老路零变（mech_advise=[]）。
        import dwc_evo_round as _E
        log = tmp_path / "mech.jsonl"
        with open(str(log), "w", encoding="utf-8") as fh:
            for _ in range(10):
                fh.write('{"mech": "monitor_skip", "event": "skip",'
                         ' "ok": false}\n')
        monkeypatch.setattr(_E, "collect_unmapped", lambda *a, **k: [])
        rep = _E.run_round("x", Evolver(), None, context="",
                           trial_fn=lambda t, p, code=None: True,
                           apply=False, rules_path="y",
                           mech_log=str(log))
        assert any(a["mech"] == "monitor_skip" for a in rep["mech_advise"])
        rep0 = _E.run_round("x", Evolver(), None, context="",
                            trial_fn=lambda t, p, code=None: True,
                            apply=False, rules_path="y")
        assert rep0["mech_advise"] == []


class TestRound:
    def test_draft_and_trial_pass(self, tmp_path):
        db = _tmpdb(str(tmp_path / "p.sqlite"))
        mu = LLMMutator(llm=lambda p: _json.dumps(_GOOD))
        rep = EVO.run_round(db, Evolver(), mu, context="",
                            trial_fn=lambda task, patch, code=None: True, apply=False,
                            rules_path=str(tmp_path / "rules.json"),
                            fn_of=lambda r: "zzz_norule_fn",
                            task_of=lambda r: "zzz_norule_task")
        assert rep["n_clusters"] == 1
        assert rep["results"][0]["drafted"] is True
        assert rep["results"][0]["trial"] is True
        assert rep["results"][0]["landed"] is False  # 默认不落
        assert not os.path.exists(str(tmp_path / "rules.json"))

    def test_apply_lands_with_backup(self, tmp_path):
        # ★ R291-P4 Task 3 新语义：bool trial 无分数 ⇒ 门未判 ⇒ 不落地。
        #   （legacy 直落已删；门判过才落 —— 见 test_r291 Task 2/3。）
        db = _tmpdb(str(tmp_path / "p.sqlite"))
        rp = str(tmp_path / "rules.json")
        mu = LLMMutator(llm=lambda p: _json.dumps(_GOOD))
        rep = EVO.run_round(db, Evolver(), mu, context="",
                            trial_fn=lambda task, patch, code=None: True, apply=True,
                            rules_path=rp,
                            backup_dir=str(tmp_path),
                            fn_of=lambda r: "zzz_norule_fn",
                            task_of=lambda r: "zzz_norule_task")
        assert rep["results"][0]["landed"] is False
        assert rep["results"][0]["adopt"] == "not_evaluated"
        assert "reason" in rep["results"][0]

    def test_trial_fail_never_lands(self, tmp_path):
        db = _tmpdb(str(tmp_path / "p.sqlite"))
        rp = str(tmp_path / "rules.json")
        mu = LLMMutator(llm=lambda p: _json.dumps(_GOOD))
        rep = EVO.run_round(db, Evolver(), mu, context="",
                            trial_fn=lambda task, patch, code=None: False, apply=True,
                            rules_path=rp,
                            backup_dir=str(tmp_path),
                            fn_of=lambda r: "zzz_norule_fn",
                            task_of=lambda r: "zzz_norule_task")
        assert rep["results"][0]["trial"] is False
        assert rep["results"][0]["landed"] is False
        assert not os.path.exists(rp)


class TestRootPointer:
    def test_pointer_dir_resolves_repo(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        cp = tmp_path / "cp"
        cp.mkdir()
        (cp / ".dwc_repo").write_text(str(repo), encoding="utf-8")
        assert EVO._code_root(start=str(cp)) == str(repo)

    def test_broken_pointer_falls_back_to_self(self, tmp_path):
        cp = tmp_path / "cp2"
        cp.mkdir()
        (cp / ".dwc_repo").write_text("Z:/不存在/nowhere", encoding="utf-8")
        assert EVO._code_root(start=str(cp)) == str(cp)

    def test_nightbench_same_discipline(self, tmp_path):
        import dwc_nightbench as NB
        repo = tmp_path / "r2"
        repo.mkdir()
        cp = tmp_path / "c2"
        cp.mkdir()
        (cp / ".dwc_repo").write_text(str(repo), encoding="utf-8")
        assert NB._find_root(start=str(cp)) == str(repo)


def test_draft_raise_does_not_kill_round(tmp_path):
    """★ 单簇端点抖 ⇒ 留痕继续，不掀整轮（cron 体质）。"""
    db = tmp_path / "p.sqlite"
    con = sqlite3.connect(str(db))
    con.execute("CREATE TABLE failure_sig(c,q,m,node_id)")
    con.execute("INSERT INTO failure_sig VALUES(?,?,?,?)",
                ("E_VALUE", "wrong_magnitude", "m", "n1"))
    con.commit()
    con.close()

    def _boom(p):
        raise RuntimeError("端点抖")

    mu = LLMMutator(llm=_boom)
    rep = EVO.run_round(str(db), Evolver(), mu, context="",
                        trial_fn=lambda t, pa, code=None: True, apply=False,
                        rules_path=str(tmp_path / "rules.json"),
                        fn_of=lambda r: "zzz_norule_fn",
                        task_of=lambda r: "zzz_norule_task")
    assert rep["n_clusters"] == 1
    assert rep["results"][0]["drafted"] is False
    assert "起草抛错" in rep["results"][0]["reason"]


def test_learned_rule_maps_cluster(tmp_path):
    """★ 学到即认：RULES 覆盖的键 ⇒ proposals，不再 unmapped（合成键事后 pop）。"""
    from dwc.organs.evolver import Mutator
    key = "E_VALUE:wrong_magnitude:zzz_tmp_fn"
    Mutator.RULES[key] = {"component": "prompt", "dimension": "D7",
                          "target_layer": "assets", "target": "zzz_tmp_fn",
                          "m": "tmp_m", "patch": "p", "rationale": "test"}
    try:
        sigs = [{"c": "E_VALUE", "q": "wrong_magnitude", "m": "",
                 "fn": "zzz_tmp_fn", "task": "t"}]
        d = Evolver().diagnose(sigs)
        assert d["n_unmapped"] == 0
        assert len(d["proposals"]) >= 1
    finally:
        Mutator.RULES.pop(key, None)
