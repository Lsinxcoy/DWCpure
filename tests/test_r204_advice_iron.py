# -*- coding: utf-8 -*-
"""R204 · advice 执行消费 + 铁律运行时执行面（用户令"执行你的建议"轮）。

A · advice 消费: governor_advice 的触发真改行为 —— 下一轮任务源剔除
    环节⑥ 默认探索（world_tree_action）; Q6 对照臂按触发态记账
    （触发⇒iwm 臂 / 无触发⇒baseline 臂 / 仅 downweight⇒不可执行标 not_actionable）。
B · 铁律执行面: foundation/iron_runtime.py —— laws_block 从恒 () 变为
    四态真源（block/warn 真判 · na 无对象 · not_instrumented 显式缺席）;
    G11 report_must_quote 的动作侧（certification_limit 摘录）+ 判在位。
"""
from __future__ import annotations

import os
import sys
from types import SimpleNamespace

ROOT = r"E:\Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.core import DWC                                    # noqa: E402
from dwc.organs.actor import Actor, execute_task, Receipt   # noqa: E402
from dwc.foundation import iron_runtime as IR               # noqa: E402


def _dwc() -> DWC:
    d = DWC(depth_limit=3, max_nodes=50)
    actor = Actor()

    def exe(task):
        r = execute_task(actor, d.judge, task["task_id"])
        return Receipt(ok=bool(r["observation"]),
                       detail={"observed": r["observation"]}, verified=True)
    d.executor = exe
    d.runner.executor = exe
    return d


# ══════════════════════════════════════
# A · advice 执行消费
# ══════════════════════════════════════
def test_advice_consumed_demotes_world_tree_tasks():
    """★★★ 首 term 必触发（min_samples=5 ⇒ self_trust degrade）⇒ 消费段
    **降序不丢**（R216 语义校准 — 旧'drop 全丢'是永久降级自锁根因之一:
    台账实证 wta 66/66 全 drop ⇒ 无改进 ⇒ trust 恒 0 ⇒ 永久降级）。
    行为锁: wta 保活且基线在前; consumed_action 标 demote。"""
    d = _dwc()
    rep = d.run_term("code_fix_001", n_steps=1)
    adv = rep.iwm_advice
    assert adv and "error" not in adv, adv
    assert adv["degrade_to_baseline"] is True, "首 term 不触发? %s" % adv
    assert adv["consumed"] is True, "消费未回填"
    assert adv["consumed_action"].startswith("demote_world_tree_action"), adv
    kinds = [t["kind"] for t in rep.next_task_source["tasks"]]
    assert "world_tree_action" in kinds, "降级把探索杀了（R216 禁止）: %s" % kinds
    assert kinds[0] != "world_tree_action", "降级须基线在前（排序降档非杀探索）"


def test_advice_no_trigger_keeps_world_tree_and_baseline_arm():
    """★★ 无触发路径: monkeypatch governor_advice 返回干净建议 ⇒
    任务源保留 world_tree_action + Q6 记 baseline 臂（对照面真存在）。"""
    d = _dwc()
    clean = SimpleNamespace(degrade_to_baseline=False,
                            downweight_pre_enactment=False,
                            forbid_default_dream=False, reason="干净")
    orig = d.iwm.governor_advice
    d.iwm.governor_advice = lambda state, layer="all": clean
    try:
        rep = d.run_term("code_fix_001", n_steps=1)
    finally:
        d.iwm.governor_advice = orig
    kinds = [t["kind"] for t in rep.next_task_source["tasks"]]
    assert "world_tree_action" in kinds, "无触发却剔除了探索任务: %s" % kinds
    assert rep.iwm_advice["consumed"] is True
    assert rep.iwm_advice["consumed_action"] == "none(no_trigger)"
    assert d.iwm._arms["baseline"][0] == 1, "baseline 臂没记账: %s" % d.iwm._arms
    assert d.iwm._arms["iwm"][0] == 0


def test_advice_downweight_only_marked_not_actionable():
    """★ downweight-only: run_term 无 pre-enactment 层 ⇒ 如实标
    not_actionable（不假装消费）+ 记 baseline 臂（未采纳）。"""
    d = _dwc()
    wo = SimpleNamespace(degrade_to_baseline=False,
                         downweight_pre_enactment=True,
                         forbid_default_dream=False, reason="半阈黄区")
    orig = d.iwm.governor_advice
    d.iwm.governor_advice = lambda state, layer="all": wo
    try:
        rep = d.run_term("code_fix_001", n_steps=1)
    finally:
        d.iwm.governor_advice = orig
    adv = rep.iwm_advice
    assert adv["downweight_actionable"] is False
    assert "pre-enactment" in adv["downweight_why"]
    assert adv["consumed_action"] == "not_actionable(downweight)"
    assert d.iwm._arms["baseline"][0] == 1, "downweight-only 不算采纳"
    assert d.iwm._arms["iwm"][0] == 0


# ══════════════════════════════════════
# B · 铁律运行时执行面
# ══════════════════════════════════════
def test_iron_report_four_states():
    """★★★ 四态齐全: checked 真判（G8/G11 + R217 新增 G3/G10）+ na（G1
    pre_apply 无对象）+ not_instrumented 逐条 why（剩 6 条）+ block/warn 进报告。"""
    d = _dwc()
    rep = d.run_term("code_fix_001", n_steps=1)
    ir = rep.iron_report
    assert ir is not None, "iron_report 没产"
    checked = {c["id"]: c["verdict"] for c in ir["checked"]}
    assert checked.get("G8") == "pass", "G8 五环齐该 pass: %s" % ir["checked"]
    assert checked.get("G11") == "pass", "certification_limit 已摘该 pass"
    assert any(x["id"] == "G1" for x in ir["na"]), "G1 pre_apply 应 na"
    ni = {x["id"] for x in ir["not_instrumented"]}
    # ★ R217 语义升级: G3（frozen 设置方 R208 已落）/G10（sealed sha 审计）
    #   已升级真判 — 从缺席表移除; 剩余 6 条仍必须显式缺席
    assert {"G4", "G5", "G6"} <= ni, "数据面无设置方的律必须显式缺席: %s" % ni
    assert {"G3", "G10"} <= set(checked), "G3/G10 未进真判: %s" % set(checked)
    for x in ir["not_instrumented"]:
        assert x["why"], "not_instrumented 缺 why: %s" % x
    # 11 条全交代（无静默跳过）
    assert ir["n_laws"] == len(ir["checked"]) + len(ir["na"]) \
        + len(ir["not_instrumented"]) + len(ir["block"]) + \
        sum(1 for c in ir["checked"] if c["verdict"] in ("block", "warn")), \
        "律交代不齐: %s" % ir


def test_g11_certification_limit_present_and_quoted():
    """★ G11 report_must_quote 动作侧: rep.certification_limit 从 yaml 摘出
    （非空）; 缺席时 evaluate 必判 block[G11]（可违反状态存在）。"""
    d = _dwc()
    rep = d.run_term("code_fix_001", n_steps=1)
    assert len(rep.certification_limit) > 0, "G11 动作侧没摘录"
    assert "安全证明" in rep.certification_limit or "certif" in rep.certification_limit
    bad = IR.evaluate_for_term(rep, certification_limit_present=False)
    assert "G11" in bad["block"], "摘录缺失却没判 block: %s" % bad["block"]


def test_g8_missing_stage_warns():
    """★ G8 可违反状态: 五环缺 experience ⇒ warn[G8]（真判, 非恒真）。"""
    d = _dwc()
    rep = d.run_term("code_fix_001", n_steps=1)
    rep.stages = [x for x in rep.stages if x.get("stage") != "experience"]
    r = IR.evaluate_for_term(rep, certification_limit_present=True)
    assert "G8" in r["warn"], "缺环没判 warn: %s" % r
    g8 = [c for c in r["checked"] if c["id"] == "G8"][0]
    assert g8["verdict"] == "warn" and "experience" in g8["missing"]


def test_laws_block_true_source_equals_report():
    """★★ laws_block 真源相等锁: _build_state 的 G.laws_block/laws_warn
    必须逐字节等于 iron_report 的 block/warn（真源, 非手填）。"""
    d = _dwc()
    rep = d.run_term("code_fix_001", n_steps=1)
    st = d.runner._build_state(rep, "code_fix_001")
    assert st.G.laws_block == tuple(rep.iron_report["block"])
    assert st.G.laws_warn == tuple(rep.iron_report["warn"])


def test_governor_advice_sees_laws_block():
    """★ 接缝锁: governor_advice 的 state.G.laws_block 现在是执行面真值
    （构造带 block 的 state ⇒ advice.reason 必点名铁律触发）。"""
    d = _dwc()
    rep = d.run_term("code_fix_001", n_steps=1)
    from dwc.foundation.state import (State, AssetVersions,
                                      ArchitectureVersions, GateSnapshot,
                                      ExecutionContext)
    st = d.runner._build_state(rep, "code_fix_001")
    g = st.G
    blocked = GateSnapshot(
        wm_version=g.wm_version, wm_dev_accuracy=g.wm_dev_accuracy,
        wm_dev_n=g.wm_dev_n, theta_dev=g.theta_dev,
        theta_dev_kind=g.theta_dev_kind, gate1_verdict=g.gate1_verdict,
        iwm_verdict=g.iwm_verdict, iwm_reason=g.iwm_reason,
        train_verdict=g.train_verdict, laws_block=("G3",),
        laws_warn=g.laws_warn, cost_used=g.cost_used,
        task_scores_ref=g.task_scores_ref)
    st2 = State(S=st.S, H=st.H, G=blocked, X=st.X)
    adv = d.iwm.governor_advice(st2)
    assert adv.degrade_to_baseline is True, "铁律 block 没进判定"
    assert "G3" in adv.reason and "铁律" in adv.reason, adv.reason
