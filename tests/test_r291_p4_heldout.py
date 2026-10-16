# -*- coding: utf-8 -*-
"""R291-P4 Task 1 · held_out 分数口（Judge 读 sealed，不读 dev）。

★★★ 存在理由
  accept 门要 Δ_ho，但 held_out 无分数口 ⇒ 门永 blocked（R289 条件②）。
  sealed（R28，11 条 locked）是真值源；evaluate(split="test") 已存在。
  本步只包一层转 1.0/0.0/None，不造新语义。
"""
from __future__ import annotations

import os
import sys

import pytest  # noqa: F401

ROOT = r"E:/Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.organs.judge import Judge, SPLIT_TEST  # noqa: E402


def _obs_math001(right=True):
    # ★ 真形态（executor.obs_skeleton/parse_llm_observed）：{fn: [[args, v]]}
    # ★ R30 纪律：actual 须 JSON 本色（int 7，不是 "7" —— 字符串冒充判 False）
    # ★ sealed test_math_001 有 2 checks（[3,7,2]→7；[]→None）—— 两条都得喂
    return {"observed": {"max_of": [[[3, 7, 2], 7 if right else 8], [[], None]]},
            "★_executed": True}


def test_held_out_score_reads_sealed_not_dev():
    """★★ sealed 真题判分：对⇒1.0，错⇒0.0（与 in-sample 同口径）。"""
    j = Judge()
    assert j.held_out_score("test_math_001", _obs_math001(True)) == 1.0
    assert j.held_out_score("test_math_001", _obs_math001(False)) == 0.0


def test_held_out_unknown_task_returns_none_loud():
    """★ 不在 sealed⇒None（未判，不编分；accept 管 blocked）。"""
    j = Judge()
    assert j.held_out_score("no_such_task", {}) is None
    assert j.held_out_score("code_fix_007", {}) is None  # dev 任务无 held_out


def test_held_out_none_observed_returns_none():
    """★ observed None⇒None（没跑=未评价，Verdict 纪律）。"""
    assert Judge().held_out_score("test_math_001", None) is None


def test_held_out_locked_out_of_metric_paths():
    """★★★ locked 语义：除 accept 门外，任何 metric/排序路径不得读 held_out。

    2607.12790 §2.2 "no part of metric evolution reads it" —— 静态 pin：
    metric_loop/candidates/direction/world_model 若引用 held_out_score
    即破 locked，本测即红。
    """
    import io
    bad = []
    for rel in ("src/dwc/organs/metric_loop.py",
                "src/dwc/organs/candidates.py",
                "src/dwc/organs/direction.py",
                "src/dwc/organs/world_model.py",
                "scripts/dwc_agent.py"):
        p = os.path.join(ROOT, rel)
        if not os.path.exists(p):
            continue
        if "held_out_score" in io.open(p, encoding="utf-8").read():
            bad.append(rel)
    assert bad == [], "locked 破口：%r 读了 held_out" % (bad,)


def test_held_out_score_raises_quota():
    """★ raises 配额：sealed 缺席启动（sealed_path 指向空）判分即炸不装有。"""
    import tempfile
    with pytest.raises(Exception):
        Judge(sealed_path=os.path.join(tempfile.mkdtemp(), "no_sealed.json"))


# ══════════════════════════════════════════════════════════
# R291-P4 Task 2 · _real_trial 回 held_out＋adopt 门传真值
# ══════════════════════════════════════════════════════════
def _fake_llm_007():
    import json as _json

    class _FakeLLM:
        def complete(self, prompt, max_tokens=1500):
            obs = {"code_fix_007": {"average": [[[0.1, 0.2], "0.15"]]}}
            return type("R", (), {"ok": True,
                                  "text": _json.dumps({"observed": obs})})()
    return _FakeLLM()


def test_real_trial_returns_held_out_key():
    """★★ _real_trial 回 dict 含 held_out 键（dev 任务 sealed 无同名⇒None）。"""
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    import dwc_evo_round as EVO
    r = EVO._real_trial(Judge(), _fake_llm_007(), "code_fix_007", "patch")
    assert isinstance(r, dict), type(r)
    assert "held_out" in r, r
    assert r["held_out"] is None  # dev 任务本来就不该有 held_out（诚实 None）


def test_round_passes_held_out_to_accept(tmp_path):
    """★★★ dict trial 带 held_out/baseline_ho ⇒ adopt 门收到真 held_out。

    Δ_in=0.5≥0 ∧ Δ_ho=0.1≥0 ∧ max>0 ⇒ decision "adopted_not_implemented"
    （第五态 —— 门吃真输入；落还是 legacy 直落——删分支是 Task 3 的事，
    本测只 pin 门判真值）。
    ★ 隔离（R287-C 纪律）：LEARNED_PATH 指 tmp（_land_adopted 写盘），
      RULES 类属性键 teardown 清 —— 双防（内存＋磁盘）污染。
    """
    import json as _json
    import sqlite3
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    import dwc_evo_round as EVO
    from dwc.organs.evolver import Evolver, LLMMutator
    db = str(tmp_path / "p.sqlite")
    c = sqlite3.connect(db)
    c.execute("CREATE TABLE failure_sig(c,q,m,node_id)")
    c.execute("INSERT INTO failure_sig VALUES (?,?,?,?)",
              ("E_VALUE", "wrong_magnitude", "llm_asserted:0.15", "n1"))
    c.execute("INSERT INTO failure_sig VALUES (?,?,?,?)",
              ("E_VALUE", "wrong_magnitude", "llm_asserted:0.15", "n2"))
    c.commit()
    c.close()
    mu = LLMMutator(llm=lambda p: _json.dumps(
        {"component": "prompt", "dimension": "D7", "target_layer": "assets",
         "target": "average", "m": "x", "patch": "p", "rationale": "r"}))
    from dwc.organs.evolver import Mutator
    _before = set(Mutator.RULES)
    _old_learned = Mutator.LEARNED_PATH
    Mutator.LEARNED_PATH = str(tmp_path / "learned.json")  # ★ 写盘隔离
    try:
        rep = EVO.run_round(
            db, Evolver(), mu, context="",
            trial_fn=lambda task, patch: {"success": True, "in_score": 1.0,
                                          "baseline_in": 0.5, "held_out": 0.6,
                                          "baseline_ho": 0.5},
            apply=True, rules_path=str(tmp_path / "rules.json"),
            backup_dir=str(tmp_path),
            fn_of=lambda r: "zzz_norule_fn",
            task_of=lambda r: "zzz_norule_task")
    finally:
        # ★ RULES 是 Mutator 类属性（全实例共享）——落地键必须清，
        #   否则同进程后跑的测试 collect 为空（已实锤污染 R279）。
        for _k in set(Mutator.RULES) - _before:
            del Mutator.RULES[_k]
        Mutator.LEARNED_PATH = _old_learned
    item = rep["results"][0]
    assert item["adopt"] == "adopted_not_implemented", item.get("adopt")
    assert item.get("delta_ho") == pytest.approx(0.1), item


# ══════════════════════════════════════════════════════════
# R291-P4 Task 3 · legacy 直落删除（条件①②齐之日）
# ══════════════════════════════════════════════════════════
def test_bool_trial_no_longer_lands_legacy(tmp_path):
    """★★★ 旧 bool trial 不再落地：门没判≠门过了（直落分支已删）。

    trial_fn 回 True（无分数）⇒ adopt not_evaluated＋landed False＋留痕。
    """
    import json as _json
    import sqlite3
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    import dwc_evo_round as EVO
    from dwc.organs.evolver import Evolver, LLMMutator
    db = str(tmp_path / "p.sqlite")
    c = sqlite3.connect(db)
    c.execute("CREATE TABLE failure_sig(c,q,m,node_id)")
    c.execute("INSERT INTO failure_sig VALUES (?,?,?,?)",
              ("E_VALUE", "wrong_magnitude", "llm_asserted:0.15", "n1"))
    c.execute("INSERT INTO failure_sig VALUES (?,?,?,?)",
              ("E_VALUE", "wrong_magnitude", "llm_asserted:0.15", "n2"))
    c.commit()
    c.close()
    mu = LLMMutator(llm=lambda p: _json.dumps(
        {"component": "prompt", "dimension": "D7", "target_layer": "assets",
         "target": "average", "m": "x", "patch": "p", "rationale": "r"}))
    rep = EVO.run_round(db, Evolver(), mu, context="",
                        trial_fn=lambda task, patch: True, apply=True,
                        rules_path=str(tmp_path / "rules.json"),
                        backup_dir=str(tmp_path),
                        fn_of=lambda r: "zzz_norule_fn",
                        task_of=lambda r: "zzz_norule_task")
    item = rep["results"][0]
    assert item["trial"] is True
    assert item["landed"] is False  # ★ 直落已删：无分数不落地
    assert item["adopt"] == "not_evaluated"
    assert "reason" in item, item
