# -*- coding: utf-8 -*-
"""R172 · task 选择升级 — δ_θ 排序 + EL 状态机（同源接线, 非发明）。

验收:
  □ Loop._pick_task 在（weakness.task_delta_map + el_sched）上工作
  □ 无判分历史 ⇒ insufficient ⇒ 保底行为（旧机械序 compat）
  □ p̂ = **当前被选 task** 的最近判分（不喂全体 mean — R172 实测纠偏:
    混 mean ⇒ 002/004/005/006 恒 0 ⇒ 永久 stalled ⇒ 卡死 001 idle 19 轮）
  □ stalled（p̂≤τ）时 index 不动（论文式 2 原文语义 — 不发明跳卡）
  □ R70/R73 诚实边界仍在: direction"何时选哪个"仍无设计 ⇒ 保持不造
"""
from __future__ import annotations

import os
import sys

import pytest

ROOT = r"E:/Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.harness.loop import Loop          # noqa: E402
from dwc.organs.el_sched import (         # noqa: E402
    ELScheduler, STATUS_STALLED, STATUS_INSUFFICIENT, TAU)


@pytest.fixture()
def loop():
    lp = Loop()
    lp.impl_store = dict(lp.impl_store)
    yield lp


def test_pick_task_baseline_compat(loop):
    """★ 无判分历史 ⇒ insufficient ⇒ 不炸, 保底返回在候选内。"""
    tasks = sorted(k for k in loop.judge.anchors if not k.startswith("_"))
    t = loop._pick_task(tasks)
    assert t in tasks


def test_el_wired_state(loop):
    """★★ EL 调度器状态在 Loop 上真建（不是 None 假装接了）。"""
    tasks = sorted(k for k in loop.judge.anchors if not k.startswith("_"))
    loop._pick_task(tasks)
    assert loop.el is not None
    assert loop._el_last_task in tasks


def test_p_hat_is_current_env_not_mean(loop):
    """★★★ p̂ 口径 = 当前 task 最近判分（不是全体 mean — 卡死回归锁）。

    ★ 构造: 002（broken, score=0）+ reasoning_001（修好后 score=1）
      ⇒ 全体 mean>τ 但 002 自己 p̂=0 ⇒ must stall（不该被别的 task
      的好分推着走）⇒ index 不变 ⇒ 002 被再选
    """
    tasks = ["code_fix_002", "reasoning_001"]
    # 灌判分: 002=0.0, reasoning_001=1.0（走 judge 真落盘口径）
    from dwc.organs.actor import Actor, execute_task
    for tid, score_impl in (
            ("code_fix_002", loop.impl_store["code_fix_002"]),
            ("reasoning_001",
             "快速排序最坏 O(n^2) 与 pivot 和递归深度有关。")):
        o = execute_task(loop.actor, loop.judge, tid, implementation=score_impl)
        loop.judge.evaluate(tid, "dev", observed=o["observation"])
    picked = loop._pick_task(tasks)
    # ★ 第一次 pick: 无 _el_last_task ⇒ insufficient ⇒ tasks[0]
    assert picked == "code_fix_002"
    # ★ 第二轮: _el_last_task=002, p̂=0.0 ≤ τ ⇒ stalled ⇒ index 不动
    loop._el_token = -1                     # 强制重判（同观测已重灌）
    picked2 = loop._pick_task(tasks)
    assert loop._el_last.status == STATUS_STALLED
    assert picked2 == "code_fix_002"        # 停滞不推进（论文式 2 语义）


def test_stall_does_not_invent_skip(loop):
    """★★ stalled = index 不动（R70 原文: p̂≤τ ⇒ 状态完全不动）。"""
    el = ELScheduler()
    d = el.decide_from_rate(TAU, 5)         # 恰 τ 也停滞（原文字）
    assert d.status == STATUS_STALLED and d.index == 1


def test_direction_boundary_unchanged():
    """★★ R73 纪律仍在: direction 只枚举, "何时选哪个"仍无设计 ⇒ 不造。

    ★ 接 EL 是**任务采样**（把 core._el_pick 同源机制接到 dev 池）, 不是
      evolution-direction 选择器 — 两者不同层, 别混说"direction 已做"
    """
    from dwc.organs.direction import EvolutionDirection, ensure_direction
    assert len(list(EvolutionDirection)) == 3          # 锁 3
    with pytest.raises(Exception):
        ensure_direction(None)                          # None 不是第四方向
