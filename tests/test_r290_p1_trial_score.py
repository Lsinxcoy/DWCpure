# -*- coding: utf-8 -*-
"""R290-P1 · trial 分数化（legacy 退役条件①）。

★★★ 存在理由
  _real_trial 只回布尔 —— accept 要两份判分（baseline/current），
  trial 无分数 ⇒ accept 缺输入 ⇒ legacy 永删不掉（R289 复核条件①）。
  本步：_real_trial 回判分 dict；run_round 原样存 trial（旧测零改），
  归一走 trial_score；adopt 门传真 baseline/current（held_out 仍缺 ⇒
  仍判 blocked，但 blocked 带真 Δ_in —— 门开始吃真输入）。
"""
from __future__ import annotations

import io
import json as _json
import os
import sys

import pytest  # noqa: F401

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import dwc_evo_round as EVO  # noqa: E402
from dwc.organs.evolver import Evolver, LLMMutator  # noqa: E402

_GOOD = {"component": "prompt", "dimension": "D7",
         "target_layer": "assets", "target": "average",
         "m": "float_repr", "patch": "p", "rationale": "r"}


def _tmpdb(p):
    import sqlite3
    c = sqlite3.connect(p)
    c.execute("CREATE TABLE failure_sig(c,q,m,node_id)")
    c.execute("INSERT INTO failure_sig VALUES (?,?,?,?)",
              ("E_VALUE", "wrong_magnitude", "M-wrong", "n1"))
    c.execute("INSERT INTO failure_sig VALUES (?,?,?,?)",
              ("E_VALUE", "wrong_magnitude", "M-wrong", "n2"))
    c.commit()
    c.close()
    return p


def test_real_trial_returns_scored_dict():
    """★★ _real_trial 回判分 dict（success＋in_score＋baseline_in）。"""
    from dwc.organs.judge import Judge

    class _FakeLLM:
        def complete(self, prompt, max_tokens=1500):
            obs = {"code_fix_007": {"average": [[0.1, 0.2], "0.15"]}}
            return type("R", (), {"ok": True,
                                  "text": _json.dumps({"observed": obs})})()

    r = EVO._real_trial(Judge(), _FakeLLM(), "code_fix_007", "patch")
    assert isinstance(r, dict), type(r)
    assert set(("success", "in_score", "baseline_in")) <= set(r), r
    assert r["success"] in (True, False, None)
    if r["success"] is True:
        assert r["in_score"] == 1.0
    elif r["success"] is False:
        assert r["in_score"] == 0.0
    else:
        assert r["in_score"] is None


def test_real_trial_llm_down_returns_none_scored():
    """★ LLM 挂 ⇒ success/in_score 双 None（不编分数，None 透传）。"""
    from dwc.organs.judge import Judge

    class _DeadLLM:
        def complete(self, prompt, max_tokens=1500):
            return type("R", (), {"ok": False, "error": "down"})()

    r = EVO._real_trial(Judge(), _DeadLLM(), "code_fix_007", "patch")
    # ★ 核心判据: LLM 挂 ⇒ 不编分数（None 透传）
    assert r["success"] is None
    assert r["in_score"] is None
    assert r["baseline_in"] is None
    assert r["held_out"] is None
    assert r["mode"] == "report"
    # ★ R346 / R343 新增键：未激活、机制未跑、partial 未评 —— 诚实缺席
    #   （旧锁是精确 dict 相等，加键即红 ⇒ 改成「逐键锁语义」更强）
    assert r["activated"] is False
    assert r["mechanism_ran"] is False
    assert r["partial"] is None


def test_round_scores_dict_trial_into_adopt(tmp_path):
    """★★★ dict trial 进 adopt 门：blocked 带真 delta_in（门吃真输入）。

    fake trial 给 success=True＋in_score=1.0＋baseline_in=0.5 ⇒
    accept 判 blocked（held_out 缺，未落地纪律不变），但 delta_in=0.5 真数。
    """
    db = _tmpdb(str(tmp_path / "p.sqlite"))
    mu = LLMMutator(llm=lambda p: _json.dumps(_GOOD))
    rep = EVO.run_round(
        db, Evolver(), mu, context="",
        trial_fn=lambda task, patch, code=None: {"success": True, "in_score": 1.0,
                                      "baseline_in": 0.5},
        apply=True, rules_path=str(tmp_path / "rules.json"),
        backup_dir=str(tmp_path),
        fn_of=lambda r: "zzz_norule_fn", task_of=lambda r: "zzz_norule_task")
    item = rep["results"][0]
    assert item["trial"] == {"success": True, "in_score": 1.0,
                             "baseline_in": 0.5}
    assert item["adopt"] == "blocked", item.get("adopt")
    assert item.get("delta_in") == 0.5, item


def test_bool_trial_no_longer_lands_not_evaluated(tmp_path):
    """★★ 旧 bool trial 新语义：True 照存 trial，但门未判⇒不落地（R291-P4 Task 3）。"""
    db = _tmpdb(str(tmp_path / "p.sqlite"))
    rp = str(tmp_path / "rules.json")
    mu = LLMMutator(llm=lambda p: _json.dumps(_GOOD))
    rep = EVO.run_round(db, Evolver(), mu, context="",
                        trial_fn=lambda task, patch, code=None: True, apply=True,
                        rules_path=rp, backup_dir=str(tmp_path),
                        fn_of=lambda r: "zzz_norule_fn",
                        task_of=lambda r: "zzz_norule_task")
    assert rep["results"][0]["trial"] is True
    assert rep["results"][0]["landed"] is False  # ★ R291-P4 Task 3：无分数不落地
    assert rep["results"][0]["adopt"] == "not_evaluated"  # 无分数⇒门未判
