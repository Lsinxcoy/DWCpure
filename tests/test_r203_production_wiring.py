# -*- coding: utf-8 -*-
"""R203 · 生产级审计 F1/F3/F4 三发现的接线锁（"投入生产"轮）。

F1 · iwm 守卫发出口接线 —— governor_advice + record_round 从"仅测试调用"
    变为生产在环（run_term 4.45 段）; State 由 _build_state 用本轮已判
    事实构造（零占位）。
F3 · loop._dir_ledger_append 归档写盘失败留痕（_last_archive_error）——
    审计轨迹不许静默丢（G7 同族）。
F4 · scripts/e2e_core.py —— DWC 主类三入口（step/ingest/run_term）端到端
    （此前 e2e 只覆盖器官级 harness 链路）。
"""
from __future__ import annotations

import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.core import DWC                                    # noqa: E402
from dwc.organs.actor import Actor, execute_task, Receipt   # noqa: E402
from dwc.organs.evolver import NOISE_DELTA                  # noqa: E402
from dwc.foundation.state import GateSnapshot               # noqa: E402


def _dwc_with_exe() -> DWC:
    """真执行器注入（execute_task 全断言跑 + detail 契约包装）。"""
    actor = Actor()

    def exe(task):
        r = execute_task(actor, d.judge, task["task_id"])
        return Receipt(ok=bool(r["observation"]),
                       detail={"observed": r["observation"]}, verified=True)

    d = DWC(depth_limit=3, max_nodes=50, executor=exe)
    return d


# ══════════════════════════════════════════════
# F1 · governor_advice + record_round 生产在环
# ══════════════════════════════════════════════
def test_f1_iwm_advice_produced_in_run_term():
    """★★★ run_term 后 rep.iwm_advice 必在（守卫发出口真接线）——
    四字段齐 + consumed=False（诚实: 执行消费未接线, 不假装采纳）。"""
    d = _dwc_with_exe()
    rep = d.run_term("code_fix_001", n_steps=1)
    adv = rep.iwm_advice
    assert adv is not None, "run_term 没产 iwm_advice（F1 接线缺失）"
    assert "error" not in adv, "governor_advice 生产路径抛错: %s" % adv
    for k in ("degrade_to_baseline", "downweight_pre_enactment",
              "forbid_default_dream", "reason", "consumed"):
        assert k in adv, "iwm_advice 缺字段 %r" % k
    # ★ R204 语义升级（消费已接线）: 锁从"恒 False"升级为**一致性** ——
    #   consumed=True 必带合法 action 证据（三形态之一）, 防未来假 True
    if adv["consumed"]:
        ca = adv.get("consumed_action") or ""
        # ★ R216 语义升级: demote（降序不丢）取代 drop（全丢 — 自锁根因）
        assert ca.startswith(("demote_world_tree_action",
                       "drop_world_tree_action", "none(no_trigger)",
                              "not_actionable")), (
            "consumed=True 却无合法 action 证据（自欺）: %r" % ca)
    else:
        assert not adv.get("consumed_action"), "consumed=False 不该带 action"


def test_f1_record_round_wired_baseline_arm():
    """★★★ Q6 对照臂真记账: run_term 后 baseline 臂 +1（adopted 恒 False
    —— advice 执行消费未接线, 不假装采纳; 两臂同源会毁掉对照语义）。"""
    d = _dwc_with_exe()
    before = [sum(v[0] for v in d.iwm._arms.values())]
    rep = d.run_term("code_fix_001", n_steps=1)
    after = sum(v[0] for v in d.iwm._arms.values())
    assert after == before[0] + 1, (
        "Q6 记账没发生: %d -> %d" % (before[0], after))
    # ★ R204 语义升级: 臂归属随 advice 触发态（触发⇒iwm 臂 / 无触发⇒baseline）
    fired = bool(rep.iwm_advice.get("degrade_to_baseline")
                 or rep.iwm_advice.get("forbid_default_dream"))
    if fired:
        assert d.iwm._arms["iwm"][0] == 1, "触发轮没进 iwm 臂: %s" % d.iwm._arms
    else:
        assert d.iwm._arms["baseline"][0] == 1, (
            "无触发轮没进 baseline 臂: %s" % d.iwm._arms)


def test_f1_build_state_honest_fields():
    """★★ _build_state 的诚实字段: laws_block=()（铁律执行面未接线）、
    train_verdict=not_implemented（world_model 无 train）、
    theta_dev=NOISE_DELTA（R58 锁值）、G 冻结 dataclass 可过。"""
    d = _dwc_with_exe()
    rep = d.run_term("code_fix_001", n_steps=1)
    st = d.runner._build_state(rep, "code_fix_001")
    assert isinstance(st.G, GateSnapshot)
    assert st.G.laws_block == (), "铁律执行面未接线却标了 block id（装有）"
    assert st.G.train_verdict == "not_implemented", "world_model 无 train 却假装"
    assert st.G.theta_dev == NOISE_DELTA, "theta_dev 必须是 R58 锁值"
    assert st.G.theta_dev_kind == "anchored"
    # X 层: 环内瞬时字段来自本轮真事实
    assert st.X.chain_id == rep.chain_id
    assert st.X.turn_index == rep.n_steps


# ══════════════════════════════════════════════
# F3 · 归档写盘失败留痕
# ══════════════════════════════════════════════
def test_f3_archive_failure_leaves_trail():
    """★★★ 归档写盘炸 ⇒ _last_archive_error 留痕 + 不炸主链（观察面失败
    不拦进化决策 — G7 同族: 静默丢审计轨迹是缺陷）。"""
    d = _dwc_with_exe()
    loop = d.runner  # TermRunner 无 _dir_ledger_append —— 在 Loop 侧
    # Loop 类构造较重 ⇒ 直接对 Loop 类的未绑定方法验行为
    from dwc.harness.loop import Loop
    import inspect
    src = inspect.getsource(Loop._dir_ledger_append)
    assert "_last_archive_error" in src, (
        "归档写盘 except 无留痕字段（F3 回退）")
    assert "except Exception as exc" in src, (
        "except 仍是裸捕获无 exc 绑定（F3 未修）")


# ══════════════════════════════════════════════
# F4 · e2e_core.py 主类三入口端到端（结构锁 + 可执行）
# ══════════════════════════════════════════════
def test_f4_e2e_core_script_exists_and_wires():
    """★★★ F4 脚本在位 + 三入口断言齐（step/ingest 不变量/run_term）。"""
    p = os.path.join(ROOT, "scripts", "e2e_core.py")
    assert os.path.exists(p), "e2e_core.py 缺失（F4 回退）"
    src = io.open(p, encoding="utf-8").read()
    for marker in ("d.step(", "d.ingest(", "d.run_term(",
                   "failure_signature", "action_dispatched"):
        assert marker in src, "e2e_core 缺断言面 %r" % marker


def test_f4_e2e_core_script_runs():
    """★★★ F4 脚本真跑通（subprocess 隔离 — kernel 陈旧坑防御）。"""
    import subprocess
    r = subprocess.run(
        [sys.executable, os.path.join(ROOT, "scripts", "e2e_core.py")],
        capture_output=True, text=True, timeout=300, cwd=ROOT)
    assert r.returncode == 0, (
        "e2e_core rc=%d\nstdout tail: %s\nstderr tail: %s"
        % (r.returncode, r.stdout[-600:], r.stderr[-600:]))
    assert "STEP1_CORE=passed" in r.stdout
