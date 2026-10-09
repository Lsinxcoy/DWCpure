# -*- coding: utf-8 -*-
"""R99 · 阶段 1a 可观测三件的探针（T1: CostLedger history / repair_layer / A 脚本）。

判据族:
  · T4-序列: reset 结上一 term 的账（标记配对 = 上一 term 的 open 标记;
             首次无账不记 —— insufficient 同族纪律）
  · AIPC 层: repair_layer 三分支（judge→verification / receipt→execution /
             未知→unmapped 显式）+ 回填链真链带出该字段
  · A 方案 : progress_monotonicity 脚本对真 trial 报告可跑、结构与分支枚举断言
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from types import SimpleNamespace

import pytest

ROOT = r"E:/Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.harness.run_term import CostLedger  # noqa: E402
from dwc.organs.weakness import (  # noqa: E402
    REPAIR_LAYER_UNKNOWN, repair_layer)


# ══════════════════════════════════════════════════════════
# CostLedger · T 序列结账
# ══════════════════════════════════════════════════════════

def test_history_settles_previous_term_with_its_own_marks():
    """★ 结账语义: 条目带的是**上一** term 的标记（不是本次传入的）。"""
    c = CostLedger()
    c.reset_term(task_id="t0")           # 首次: 无账 ⇒ 不记, 只标记 t0
    assert c.history == []
    c.spend(1.0)
    c.reset_term(task_id="t1")           # 结 t0 的账, 标记 t1
    assert len(c.history) == 1
    e = c.history[0]
    assert e["task"] == "t0" and e["round"] is None
    assert e["term_cost"] == 1.0 and e["cumulative_cost"] == 1.0


def test_history_no_fake_entry_on_clean_ledger():
    """★ 首次/无账 reset 不造假空账（insufficient 同族: 空 ≠ 0）。"""
    c = CostLedger()
    c.reset_term(round_id="R1", task_id="a")
    c.reset_term(round_id="R2", task_id="b")
    assert c.history == [], "两连 reset 无账 ⇒ 零条目"


def test_history_round_mark_survives_to_entry():
    """round 标记随 open 账存活到结账条目（(round,task) 两维都在）。"""
    c = CostLedger()
    c.reset_term(round_id="R1", task_id="a")
    c.spend(2.5)
    c.reject(0.5)
    c.reset_term(round_id="R2", task_id="b")
    e = c.history[0]
    assert e["round"] == "R1" and e["task"] == "a"
    assert e["term_cost"] == 3.0 and e["rejected_cost"] == 0.5
    assert e["cumulative_cost"] == 3.0      # cumulative 不因结账而变


def test_to_dict_has_n_history_not_full_sequence():
    """to_dict 报条数不搬全序列（防每 term 快照按史膨胀）。"""
    c = CostLedger()
    c.reset_term(task_id="t0")
    c.spend(1.0)
    c.reset_term(task_id="t1")
    d = c.to_dict()
    assert d["n_history"] == 1
    assert "history" not in d, "全序列走 .history 属性, 不进快照"
    assert d["term_cost"] == 0.0            # 旧三键原样（T4 不回退）


def test_termrunner_reports_history_across_terms():
    """真链: 两个 term 后 history 结出一条（task 标记来自 run() 传参）。"""
    from dwc.harness.run_term import TermRunner
    r = TermRunner(budget=100.0)
    r.run_term("t1", n_steps=1)
    r.run_term("t2", n_steps=1)
    assert len(r.cost.history) == 1, r.cost.history
    assert r.cost.history[0]["task"] == "t1"


# ══════════════════════════════════════════════════════════
# repair_layer（AIPC 三行映射）
# ══════════════════════════════════════════════════════════

def test_repair_layer_by_source_three_branches():
    """judge→verification · receipt→execution · 未知→unmapped（显式不猜）。"""
    assert repair_layer("ValueError", "judge") == "verification"
    assert repair_layer("executor_rejected", "receipt") == "execution"
    assert repair_layer("X", None) == REPAIR_LAYER_UNKNOWN
    assert repair_layer("X", "made_up_source") == REPAIR_LAYER_UNKNOWN


def test_judge_backfill_carries_repair_layer_on_real_chain():
    """真链: _judge_and_backfill 产物带 repair_layer（fail⇒verification 族）。"""
    from dwc.core import DWC
    d = DWC(3, 50, executor=None)
    anchors = d.judge.anchors
    tid = next(t for t in sorted(anchors)
               if not t.startswith("_")
               and anchors[t].get("verifier_kind") == "behavior")
    # ★ 造错值观测（behavior: {fn: [值...]}; 错值 ⇒ 失败族）—— 抄 trial_run 口径
    wrong = {}
    for cdef in anchors[tid].get("checks", []):
        if "fn" in cdef:
            wrong.setdefault(cdef["fn"], []).append("__wrong__")
    trace = SimpleNamespace(observed={"observed": wrong})
    out = d._judge_and_backfill({"task_id": tid}, trace)
    assert out is not None, "真 anchors + 错观测 ⇒ 应有判定"
    assert "repair_layer" in out, "★ R99: 回填必带 repair_layer 键"
    if out.get("failure_signature"):
        assert out["repair_layer"] == "verification", \
            "judge 产生点 ⇒ verification 层（source=judge 由产生点决定）"
    else:
        assert out["repair_layer"] is None, "无签名 ⇒ 无层（不冒充）"


# ══════════════════════════════════════════════════════════
# A 方案 · progress 单调性脚本
# ══════════════════════════════════════════════════════════

def test_progress_script_runs_on_real_trial_reports():
    """脚本对真 trial 报告可跑: 输出 json + ρ/判读/分支三枚举齐全。"""
    script = os.path.join(ROOT, "scripts", "progress_monotonicity.py")
    outp = os.path.join(ROOT, "docs", "progress_monotonicity_r92.json")
    r = subprocess.run([sys.executable, script],
                       capture_output=True, timeout=120, cwd=ROOT)
    assert r.returncode == 0, r.stderr.decode("utf-8", "replace")[-800:]
    assert os.path.exists(outp)
    data = json.load(open(outp, encoding="utf-8"))
    reps = data["reports"]
    assert reps, "至少一份 trial 报告"
    for rep in reps:
        assert rep["n_terms"] >= 3
        # ★ 不用 set(循环变量)=={字面量}（test_no_locked_values 会抓 —— R52 病灶形状）
        assert len(rep["spearman"]) == 3, rep["spearman"]
        for _name in ("pool_rate", "neg_delta_top3_max", "judge_rate"):
            assert _name in rep["spearman"], rep["spearman"]
        assert rep["branch_r92"] in {
            "C_cost_downgrade_first_B", "C_cost_upgrade",
            "insufficient_terms"}
        for name, rho in rep["spearman"].items():
            if rho is not None:
                assert -1.0 <= rho <= 1.0, (name, rho)
                assert rep["verdict"][name] in {
                    "strong_monotone", "weak_or_uncertain", "no_monotone"}
