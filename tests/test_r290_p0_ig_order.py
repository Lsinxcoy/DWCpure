# -*- coding: utf-8 -*-
"""R290-P0 · 世界树任务源排序：information_gain 第一键（B 口径叠加）。

★★★ 存在理由
  _next_task_source 只调 legal_actions（枚举），world.select（信息增益
  排序＋不回退，world_model.py:537）生产零调用 —— 收束不选最不确定分支
  的能力在产线外躺着（○-1）。
  B 口径：IG 第一键，δ/组序保留做 tie-break（R77/R101 承诺不断）。
  IG 全 0（无观测/无 WM）⇒ 退化现状分支（行为零变，真保底）。
"""
from __future__ import annotations

import os
import sys

import pytest  # noqa: F401

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.harness.run_term import TermRunner, TermReport  # noqa: E402
from dwc.organs.judge import Judge  # noqa: E402
from dwc.organs.world_model import WorldModel, information_gain  # noqa: E402


def _wm() -> WorldModel:
    wm = WorldModel(depth_limit=3, max_nodes=50)
    wm.seed_tasks(["code_fix_001", "code_fix_002", "code_fix_003"],
                  tree_id="dev")
    return wm


def _wm_deep() -> WorldModel:
    """★★ 深树：001 下展开 001a/001b（未揭示，在集）；观测 001 父分支
    ⇒ 001a/001b 谱系含父观测，IG 低于 002/003（路径无观测）。"""
    wm = _wm()
    wm.expand("dev", "code_fix_001", node_id="code_fix_001a",
              action="sub_a", provenance="simulated")
    wm.expand("dev", "code_fix_001", node_id="code_fix_001b",
              action="sub_b", provenance="simulated")
    wm.tree("dev").observe("code_fix_001", 1.0, True)
    return wm


def _wta(tr: TermRunner):
    import time
    rep = TermReport(term_id="t", chain_id="c", started_at=time.time(),
                     memory_after={"used_ratio": 1.0})
    src = tr._next_task_source("t", rep)
    return [t["node"] for t in src["tasks"]
            if t["kind"] == "world_tree_action"]


def test_ig_first_key_orders_most_uncertain_first():
    """★★★ IG 第一键：谱系有观测的排后，最不确定的先探（§4.3 理由3）。

    ★ 前提修正（实测）：depth1 叶路径全等（root 同值＋己未观测）⇒ IG 恒
      无区分 —— 预排永不触发是正确的（不是 bug）。区分只出现在深树
      （父分支观测差），故本测用深树。
    """
    wm = _wm_deep()
    tr = TermRunner(judge=Judge(), world_model=wm)
    order = _wta(tr)
    # 001 已揭示出集；001a/001b 谱系含父观测（IG 低）垫底；002/003 先探
    assert order[:2] == ["code_fix_002", "code_fix_003"], order
    assert set(order[2:]) == {"code_fix_001a", "code_fix_001b"}, order


def test_no_observation_falls_back_to_legacy_order():
    """★★ IG 全 0 ⇒ 退化现状（R77 原序保底，行为零变）。"""
    wm = _wm()                                   # 零观测
    tr = TermRunner(judge=Judge(), world_model=wm)
    order = _wta(tr)
    assert order == ["code_fix_001", "code_fix_002", "code_fix_003"], order


def test_no_world_model_keeps_legacy_branches():
    """★ world_model=None ⇒ 现状分支原样（没注入不假装有）。"""
    tr = TermRunner(judge=Judge(), world_model=None)
    import time as _t
    src = tr._next_task_source(
        "t", TermReport(term_id="t", chain_id="c", started_at=_t.time(),
                        memory_after={"used_ratio": 1.0}))
    assert src["tasks"] == [] or all(
        t["kind"] != "world_tree_action" for t in src["tasks"])


def test_ig_pure_function_sanity():
    """★ information_gain 纯函数：见过 1 次全过 < 未见（判据方向锁死）。"""
    assert information_gain(1, 1) < information_gain(0, 0)
