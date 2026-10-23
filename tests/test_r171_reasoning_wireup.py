# -*- coding: utf-8 -*-
"""R171 · reasoning 任务面（keyword_match 接通 — 文本执行器 + RULES 修法）。

验收:
  □ execute_task(keyword_match) 不再 ActorError（文本执行器路由）
  □ implementation 缺 ⇒ 显式 ActorError（文本任务无 REFERENCE — 不冒充）
  □ reasoning broken 初值 0/n fail（judge 口径 — expected_keywords 逐条）
  □ RULES E_MISMATCH 族 4 条 ⇒ 提案命中 ⇒ 试跑 pass ⇒ landed
  □ landed ⇒ store 写回答案文本 ⇒ 复评 idle（分数真涨）
  □ reasoning task 的签名 fn = 首失败 kw（judge L788 口径 — 不是 task_id）
"""
from __future__ import annotations

import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.harness.loop import Loop                      # noqa: E402
from dwc.organs.actor import Actor, ActorError, execute_task  # noqa: E402
from dwc.organs.judge import Judge                     # noqa: E402


@pytest.fixture()
def loop():
    lp = Loop()
    lp.impl_store = dict(lp.impl_store)
    yield lp


def test_keyword_task_routes():
    """★★ execute_task 路由 keyword_match（此前硬卡 behavior ⇒ ActorError）。"""
    j = Judge()
    out = execute_task(Actor(), j, "reasoning_001",
                       implementation="最坏情况 O(n^2) 与 pivot 和递归深度有关。")
    v = j.evaluate("reasoning_001", "dev", observed=out["observation"])
    assert v.success is True and v.k_passed == 3


def test_keyword_task_requires_impl():
    """★★ 缺 implementation ⇒ ActorError（文本任务无 REFERENCE — 不冒充）。"""
    j = Judge()
    with pytest.raises(ActorError):
        execute_task(Actor(), j, "reasoning_001")


def test_broken_answers_all_fail(loop):
    """★ R171 broken 4 条答非所问 ⇒ 全 fail（judge kw 口径）。"""
    for tid in ("reasoning_001", "reasoning_002",
                "reasoning_003", "reasoning_004"):
        out = execute_task(loop.actor, loop.judge, tid,
                           implementation=loop.impl_store[tid])
        v = loop.judge.evaluate(tid, "dev", observed=out["observation"])
        assert v.success is False and v.k_passed == 0, tid


def test_reasoning_lands(loop):
    """★★★★ reasoning 四周环: 提案⇒试跑⇒六门⇒landed⇒复评 idle。"""
    tid = "reasoning_002"
    out = loop._run_one_task(tid, round_no=1)
    assert out["landed"] is True
    assert out["chain_verdict"] in ("all_applicable_passed",
                                    "applicable_passed_with_na")
    # ★ store 写回的是完整答案文本（含全部 kw）
    stored = loop.impl_store[tid]
    assert "一致性" in stored and "可用性" in stored and "分区容错" in stored
    out2 = loop._run_one_task(tid, round_no=11)
    assert out2["landed"] is False and out2["score"] == 1.0


def test_signature_fn_is_first_failed_kw():
    """★★★ 签名 fn = 首失败 kw（judge L788: first.get("kw") — 不是 task_id）。"""
    j = Judge()
    bd = json.load(open(os.path.join(ROOT, "config", "anchors",
                                     "broken_dev.json"), encoding="utf-8"))
    tid = "reasoning_003"
    out = execute_task(Actor(), j, tid,
                       implementation=bd[tid]["broken_impl"])
    v = j.evaluate(tid, "dev", observed=out["observation"])
    sig = v.failure_signature or {}
    assert sig.get("fn") == "SYN"          # 首 kw（checks 顺序）
    assert sig.get("c") == "E_MISMATCH"
    # ⇒ RULES 键口径: c:q:fn = E_MISMATCH:extra_content:SYN
    from dwc.organs.evolver import Mutator
    assert "E_MISMATCH:extra_content:SYN" in Mutator.RULES


def test_broken_dev_has_10_tasks():
    """★ broken_dev 13 条（6 behavior + 4 keyword_match + 3 expected_values）。

    ★ R199: +3 rung3（reproduce×3 — rules_known 全 false ⇒ true 计数仍 6）。"""
    lp = Loop()
    assert len(lp.impl_store) == 13
    # ★ R200: true 计数 6→9（+3 rung3 — RULES expected_values 族已落）
    assert sum(1 for v in lp.rules_known.values() if v) == 9
