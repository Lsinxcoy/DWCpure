# -*- coding: utf-8 -*-
"""R170 · 可修任务面（broken_dev）→ agent 闭环第一次真动（landed）。

验收（全部实测断言 — 不是复刻）:
  □ broken_dev 6 条初值全 fail（judge 真判 — 不是装的）
  □ rules_known=true 的 2 条: 试跑真验 ⇒ 链 all_applicable_passed ⇒ landed
  □ landed ⇒ impl_store 真写回（agent 的"手"动了 — 文本长度变）
  □ rules_known=false ⇒ diagnose 无提案 ⇒ blocked 弃权（如实 — 不编修法）
  □ 重新评已修 task ⇒ idle（分数真变好）
  □ ② 未注入 registry ⇒ 回落 builtin（终结假阴性 blocked）
"""
from __future__ import annotations

import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.harness.loop import Loop, LoopError            # noqa: E402
from dwc.organs.actor import execute_task               # noqa: E402
from dwc.organs.judge import Judge                      # noqa: E402
from dwc.organs.evolver import Mutator, Evolver         # noqa: E402


def _facts():
    from dwc.harness.candidate_bridge import to_facts
    from dwc.organs.evolver import Proposal
    return to_facts([Proposal(proposal_id="p", failure_signature={},
                              component="control_flow", target="f",
                              patch="return 1", rationale="t")])


@pytest.fixture()
def loop():
    lp = Loop()
    lp.impl_store = dict(lp.impl_store)      # 隔离（不污染跨测共享）
    yield lp


def test_broken_dev_all_fail(loop):
    """★ 10 条初值全 fail（judge 真判 — 闭合性不自欺; R171 起含
    reasoning 4 条 keyword_match 答案文本）。"""
    assert len(loop.impl_store) == 13   # ★ R199: +3 rung3
    for tid, impl in loop.impl_store.items():
        out = execute_task(loop.actor, loop.judge, tid, implementation=impl)
        v = loop.judge.evaluate(tid, "dev", observed=out["observation"])
        assert v.success is False, tid


def test_trial_run_real_evidence(loop):
    """★★★ 试跑 = 真收益证据（RULES 修法合成 ⇒ judge 复判 pass）。"""
    from dwc.organs.actor import Actor
    o = execute_task(loop.actor, loop.judge, "code_fix_001",
                     implementation=loop.impl_store["code_fix_001"])
    v = loop.judge.evaluate("code_fix_001", "dev", observed=o["observation"])
    p0 = loop.evolver.diagnose([dict(v.failure_signature or {})])["proposals"][0]
    tr = loop._trial_run("code_fix_001", p0)
    assert tr is not None and tr["success"] is True
    assert tr["pass_rate"] == 1.0
    # ★ 签名口径实测（首版 *a,**k 让 n 未定义 — 锁回归）
    assert "def sum_first_n(n):" in tr["impl"]


def test_known_task_lands(loop):
    """★★★★ rules_known=true 的 task: 链全过 ⇒ landed ⇒ store 写回。"""
    tid = "code_fix_003"
    before = loop.impl_store[tid]
    out = loop._run_one_task(tid, round_no=1)
    assert out["chain_verdict"] in ("all_applicable_passed",
                                    "applicable_passed_with_na")
    assert out["landed"] is True
    after = loop.impl_store[tid]
    assert after != before            # ★ agent 的手真动了
    # 复评 ⇒ idle（修好了 ⇒ 无失败签名 ⇒ 无提案）
    out2 = loop._run_one_task(tid, round_no=11)
    assert out2["landed"] is False and "已通过" in (loop._last_skip or "")


def test_unknown_task_abstains(loop):
    """★★ rules_known=false ⇒ 无提案 ⇒ blocked 弃权（如实, 不编修法）。

    ★★★ R188 改正: 现由 DirectionController 沿 fallback 序试完三方向
      才 blocked ⇒ _last_skip 文案从「无提案命中（同族泛化也无）」变为
      「三方向全败（terminal — R3）」。**被测行为语义不变**（landed
      False + store 未动）, 变的是描述 — 如实更新断言而非改产品迁就
      旧字面（用户纪律: 实现对齐设计, 不反向）。
    """
    tid = "code_fix_004"     # fibonacci — RULES 无本 fn 键
    out = loop._run_one_task(tid, round_no=1)
    assert out["landed"] is False
    # ★★ R200 改正（同 R188 纪律: 行为语义不变, 描述如实更新）:
    #   R200 给 (E_OFF_BY_ONE, off_by_one_in_range) 族加了 expected_values
    #   kin（mean/median 键）⇒ LATERAL 现在**有**同 (c,q) 近亲（借的是
    #   answer-text patch — R173 设计: 候选生成不问有效性, 试跑拦）⇒
    #   链在 LATERAL 停（一方向一跳, 出候选即止）⇒ 泛化 patch 试跑必炸
    #   （文本不是函数体）⇒ replay 选 current ⇒ kept_current。
    #   ★ landed False + store 未动**不变**（弃权语义完好）。
    assert "不落地" in (loop._last_skip or "")
    assert loop.impl_store[tid] == Loop().impl_store[tid]     # store 未动

    # ★ 链被走满到**出候选为止**: 本 (round,tid) 的 fallback 序是
    #   FORWARD(空) → REVERSE(无更简单 target, 空) → LATERAL(泛化候选)
    #   ⇒ 三方向**都真试过**（序由 sha256(round|tid) 派生 — 确定性）
    dirs = [a.direction.value for a in
            loop._dir_attempts.get(tid, [])]
    assert set(dirs) == {"FORWARD", "LATERAL", "REVERSE"}, dirs


def test_registry_none_falls_back_to_builtin(loop):
    """★★★ ② 未注入 ⇒ builtin 回落（R170: 终结链恒 blocked 假阴性）。"""
    from dwc.harness.gates import run_gates
    from dwc.harness.gates import install_registry
    install_registry(None)
    r = run_gates(_facts())
    g2 = [g for g in r["gates"] if g["gate"] == "contract"][0]
    assert g2["status"] == "passed" and g2["detail"]["n_registered"] == 1


def test_broken_dev_file_required():
    """★ floor=broken 但文件缺 ⇒ LoopError（不静默回落 golden）。"""
    with pytest.raises(LoopError):
        Loop(impl_source=os.path.join(ROOT, "config", "anchors",
                                      "nope_broken.json"))


def test_rules_known_from_file():
    """★ rules_known 自报标（001/003=true, 002/004/005/006=false）。"""
    lp = Loop()
    # ★★ R171 起含 reasoning 4 条（全 true — RULES E_MISMATCH 族已补）
    # ★ R200: +3 条 rung3 自报 true（RULES 已落 expected_values 族 —
    #   自报标随规则库演化更新, 不留过期 false; R199 期曾为 false）
    assert lp.rules_known == {"code_fix_001": True, "code_fix_002": False,
                              "code_fix_003": True, "code_fix_004": False,
                              "code_fix_005": False, "code_fix_006": False,
                              "reasoning_001": True, "reasoning_002": True,
                              "reasoning_003": True, "reasoning_004": True,
                              "reproduce_001": True, "reproduce_002": True,
                              "reproduce_003": True}


def test_known_first_ordering():
    """★ rules_known 优先排（机械默认 — 非 direction 选择器发明）。"""
    lp = Loop()
    tasks = sorted(k for k in lp.judge.anchors if not k.startswith("_"))
    rk = lp.rules_known
    head = [t for t in tasks if rk.get(t)]
    tail = [t for t in tasks if not rk.get(t)]
    # round 1 ⇒ round_no=1 ⇒ index 1 ⇒ head+tail[1]
    ordered = head + tail
    assert ordered[1] in ("code_fix_001", "code_fix_003")
