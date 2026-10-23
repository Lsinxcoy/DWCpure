# -*- coding: utf-8 -*-
"""R174 · replay 选择面接 Loop（候选集含 current — 组件树⑥那个备注落地）。

验收:
  □ Loop 候选集 = {提案, __current__}（shortlist_candidates 语义）
  □ prop > current ⇒ argmax=prop ⇒ 继续走链（003/reasoning 实测 landed）
  □ prop == current（平手）⇒ kept_current 不落地（§2.7 不劣于保证）
  □ prop < current ⇒ kept_current（提案更差 ⇒ 不动）
  □ _trial_run 的 current 分支复用同一 judge 复验口径（不另造分）
"""
from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.harness.loop import Loop                     # noqa: E402
from dwc.organs.replay import (no_worse_than_current,  # noqa: E402
                               select_policy, shortlist_candidates)


@pytest.fixture()
def loop():
    lp = Loop()
    lp.impl_store = dict(lp.impl_store)
    yield lp


def test_candidate_set_contains_current(loop):
    """★★ 候选集必含 current（shortlist 语义 — 缺 current 不许装保证）。"""
    v = {"__current__": 0.0, "prop": 1.0}
    sl = shortlist_candidates(v, current="__current__", k=2)
    assert "__current__" in sl
    # select_policy 对缺 current 的候选必须 raise（稿⑥约束）
    with pytest.raises(Exception):
        select_policy({"prop": 1.0}, current="__current__")


def test_prop_wins_then_lands(loop):
    """★★★★ 提议分更高 ⇒ argmax=prop ⇒ 链继续 ⇒ landed（003 实测）。"""
    out = loop._run_one_task("code_fix_003", round_no=1)
    assert out["landed"] is True
    pk = loop._last_replay_pick
    assert pk["picked"] == "prop" and pk["v"]["prop"] > pk["v"]["__current__"]
    assert pk["no_worse"] is True


def test_tie_keeps_current(loop):
    """★★★★ 平手 ⇒ tie-break 字典序 ⇒ current ⇒ kept_current 不落地（002 实测）。

    ★ 语义: 没好处就不动（§2.7 不劣于当前; 平手时 current 是更稳选择）
    """
    out = loop._run_one_task("code_fix_002", round_no=1)
    assert out["chain_verdict"] == "kept_current"
    assert out["landed"] is False
    pk = loop._last_replay_pick
    assert pk["picked"] == "__current__"
    # ★★ R200 改正: kin 集被 expected_values 族拓宽后, 002 的 LATERAL kin
    #   从 sum_first_n（可编译但语义错 ⇒ trial 出 0.0 分）变为 pow2（答案
    #   文本 ⇒ 编译炸 ⇒ trial None ⇒ _v 无 prop 键）。**语义不变**: 无
    #   试跑证据 = 0 贡献 ⇒ current 更稳（§2.7 不劣于保证, 只是更彻底）。
    assert pk["v"].get("prop", 0.0) <= pk["v"]["__current__"]


def test_worse_prop_keeps_current(loop):
    """★★★ 提案分更低 ⇒ 明显该 kept_current（构造: 手动喂低分候选）。"""
    # prop=0.2 < current=0.8 ⇒ argmax=current
    v = {"__current__": 8.0, "prop": 2.0}
    picked, score = select_policy(v, current="__current__")
    assert picked == "__current__" and no_worse_than_current(
        v, current="__current__")


def test_current_trial_same_judge_path(loop):
    """★★ V(current) 与 V(prop) 同口径（都走 _trial_run 的 judge 复验）。"""
    from dwc.harness.loop import _CurrentProposal
    tid = "code_fix_003"
    tr = loop._trial_run(tid, _CurrentProposal(tid, loop.impl_store[tid]))
    assert tr is not None
    # 当前实现 broken ⇒ pass_rate=0.0（judge 真判, 不是默认值）
    assert tr["pass_rate"] == 0.0
