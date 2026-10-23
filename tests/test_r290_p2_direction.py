# -*- coding: utf-8 -*-
"""R290-P2 · direction 轮内 fallback（○-3 摘牌）。

★★★ 存在理由
  direction.next_action（R1/R2 fallback＋R3 记账）生产零调用 ——
  起草全废时无方向切换，同一方向死磕到底（plan 原接线点 run_term._step
  是错的：_step 无失败语义，硬接=造语义。真接线点=LLMMutator 起草环）。
  本步：起草前选方向＋记账（成功 n=1/全废 n=0）；三方向耗尽 ⇒
  DirectionError 上抛（run_round 已隔离：单簇留痕不掀轮，R279 纪律）。
  方向不进 prompt（prompt 方向化是 P4+，零语义发明）。
"""
from __future__ import annotations

import json as _json
import os
import sys

import pytest  # noqa: F401

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.organs.direction import DirectionError  # noqa: E402
from dwc.organs.evolver import LLMMutator  # noqa: E402

_SIG = {"c": "E_VALUE", "q": "wrong_magnitude", "fn": "average",
        "task": "code_fix_007"}


def test_first_draft_chooses_a_direction_and_records():
    """★★ 首起草选方向＋记账（成功 n_candidates=1）。"""
    mu = LLMMutator(llm=lambda p: _json.dumps(
        {"component": "prompt", "dimension": "D7", "target_layer": "assets",
         "target": "average", "m": "x", "patch": "p", "rationale": "r"}))
    p = mu.propose_from_cluster([_SIG], "")
    assert p is not None
    assert len(mu._direction_history) == 1
    assert mu._direction_history[0].n_candidates == 1


def test_wasted_draft_records_zero_and_moves_on():
    """★★ 全废记 n=0＋换方向（下一簇不死磕同一方向）。"""
    mu = LLMMutator(llm=lambda p: "not json at all {{{")
    assert mu.propose_from_cluster([_SIG], "") is None
    assert mu.propose_from_cluster([_SIG], "") is None
    dirs = [a.direction for a in mu._direction_history]
    assert len(dirs) == 2 and dirs[0] != dirs[1], dirs
    assert all(a.n_candidates == 0 for a in mu._direction_history)
    assert "方向" in (mu.last_reason or ""), mu.last_reason


def test_three_directions_exhausted_raises_loud():
    """★★★ 三方向耗尽大声抛（raises 配额 —— run_round 隔离，不掀轮）。"""
    mu = LLMMutator(llm=lambda p: "not json {{{")
    for _ in range(3):
        assert mu.propose_from_cluster([_SIG], "") is None
    with pytest.raises(DirectionError):
        mu.propose_from_cluster([_SIG], "")
