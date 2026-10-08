# -*- coding: utf-8 -*-
"""el_sched（organs/el_sched.py）的契约 + 行为测试。

★★★ 为什么这份测试重要
  EL 调度器是**取任务行为**的未来开关（ARCHITECTURE 三段式①），而它的
  论文语义与设计文档的口语口径有两处出入（=τ 停滞 / 两级推进）——
  测试锁的是**论文逐字**，防实现顺着手感把边界放宽。
★ 判据族: 锁值 B=8 τ=6/8（NOISE_DELTA 同款防漂移）· insufficient 不装数 ·
  =τ 停滞 · 同代推进 · 换代清窗 · 1-based k/g
"""
from __future__ import annotations

import os
import sys

import pytest

ROOT = r"E:/Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.organs.el_sched import (  # noqa: E402
    B_WINDOW, STATUS_INSUFFICIENT, STATUS_NEXT_ENV, STATUS_NEXT_GEN,
    STATUS_STALLED, TAU, ELDecision, ELScheduler, ElSchedError,
)


def _fill(sched: ELScheduler, n_pass: int, n_fail: int) -> None:
    """按顺序灌 n_pass 个 True / n_fail 个 False（窗口滑到最近 B 条）。"""
    for _ in range(n_pass):
        sched.record(True)
    for _ in range(n_fail):
        sched.record(False)


# ══════════════════════════════════════════════════════════
# 锁值（论文常量防漂移 —— NOISE_DELTA=0.15 同款纪律）
# ══════════════════════════════════════════════════════════

def test_paper_constants_locked():
    """★ B=8, τ=6/8（2609.04128 式 2 后原文 "We use B=8 and τ=6/8"）。"""
    assert B_WINDOW == 8
    assert TAU == 6.0 / 8.0 == 0.75
    s = ELScheduler()
    assert s.B == 8 and s.tau == 0.75


# ══════════════════════════════════════════════════════════
# 窗口与 insufficient（"没观测过"不许默认）
# ══════════════════════════════════════════════════════════

def test_insufficient_until_full_window():
    """★ 窗口未满 B ⇒ pass_rate=None / status=insufficient（不装 0.0）。"""
    s = ELScheduler()
    d = s.decide(n_envs=3)
    assert d.status == STATUS_INSUFFICIENT and d.pass_rate is None
    _fill(s, 7, 0)                     # 7/8 还差 1
    d2 = s.decide(n_envs=3)
    assert d2.status == STATUS_INSUFFICIENT and d2.pass_rate is None
    assert s.n_obs == 7 and s.pass_rate is None
    # 状态没被动过
    assert (d2.generation, d2.index) == (1, 1)


def test_sliding_window_drops_oldest():
    """滑动窗口: 灌满 B 后新观测挤掉最旧（p̂ 只看最近 B 条）。"""
    s = ELScheduler()
    _fill(s, 8, 0)                     # 全过
    assert s.pass_rate == 1.0
    for _ in range(7):                 # 连灌 7 个 fail
        s.record(False)
    # 窗口 = 最后 8 条 = 1 个 True + 7 个 False = 0.125
    assert s.pass_rate == pytest.approx(1.0 / 8.0)


def test_non_bool_observation_rejected():
    """布尔观测必须是 bool —— 零模型依赖的输入面收紧。"""
    s = ELScheduler()
    with pytest.raises(ElSchedError, match="bool"):
        s.record("yes")


# ══════════════════════════════════════════════════════════
# 式 2 三段（★ 两处语义边界按论文逐字）
# ══════════════════════════════════════════════════════════

def test_exactly_tau_stalls():
    """★★ 边界①: p̂ = τ（恰 6/8）走 **≤τ 分支 = 停滞** —— 论文 ≤τ/>, 不是口语 6/8 放行。"""
    s = ELScheduler()
    _fill(s, 6, 2)                     # p̂ = 6/8 = τ
    assert s.pass_rate == pytest.approx(0.75)
    d = s.decide(n_envs=4)
    assert d.status == STATUS_STALLED
    assert (d.generation, d.index) == (1, 1)   # 状态完全不动
    assert s.n_obs == 8                         # 停滞不清窗（还在观察当前环境）


def test_above_tau_advances_within_generation():
    """★★ 两级①: p̂ > τ 且 k < N ⇒ **同代移动**（不是直接换代 —— 口语压缩的出入）。"""
    s = ELScheduler()
    _fill(s, 7, 1)                     # p̂ = 7/8 > τ
    d = s.decide(n_envs=4)
    assert d.status == STATUS_NEXT_ENV
    assert (d.generation, d.index) == (1, 2)   # 同代: g 不动, k+1
    assert s.n_obs == 0                         # 新环境新窗口


def test_generation_advances_only_when_envs_exhausted():
    """★★ 两级②: p̂ > τ 且 k = N ⇒ **换代**（g+1, k=1）+ 清窗。"""
    s = ELScheduler(generation=2, index=3)
    _fill(s, 7, 1)
    d = s.decide(n_envs=3)             # k=3=N
    assert d.status == STATUS_NEXT_GEN
    assert (d.generation, d.index) == (3, 1)
    assert s.n_obs == 0


def test_walk_through_generation_to_next():
    """集成: 环境 1(卡 1 次停滞) → 过 → 2 过 → 3 过 ⇒ 换代; k 永不越 N。"""
    s = ELScheduler()
    _fill(s, 4, 4)                     # p̂=0.5 ≤ τ ⇒ 停滞
    assert s.decide(n_envs=3).status == STATUS_STALLED
    _fill(s, 8, 0)                     # 再灌全过（窗口滑成 1.0）
    assert s.decide(n_envs=3).status == STATUS_NEXT_ENV      # → k=2
    _fill(s, 8, 0)
    assert s.decide(n_envs=3).status == STATUS_NEXT_ENV      # → k=3
    _fill(s, 8, 0)
    d = s.decide(n_envs=3)                                  # k=3=N ⇒ 换代
    assert d.status == STATUS_NEXT_GEN and d.generation == 2
    # k > N ⇒ 大声报错（状态不一致不静默 —— 显式构造 index=2 > N=1）
    s2 = ELScheduler(index=2)
    _fill(s2, 7, 1)
    with pytest.raises(ElSchedError, match="超过当代环境数"):
        s2.decide(n_envs=1)


# ══════════════════════════════════════════════════════════
# 构造与读数
# ══════════════════════════════════════════════════════════

def test_constructor_validation():
    """B/tau/generation/index 全校验（大声报错, 不静默容错）。"""
    with pytest.raises(ElSchedError, match="B"):
        ELScheduler(B=0)
    with pytest.raises(ElSchedError, match="tau"):
        ELScheduler(tau=1.5)
    with pytest.raises(ElSchedError, match="generation"):
        ELScheduler(generation=0)
    s = ELScheduler()
    with pytest.raises(ElSchedError, match="n_envs"):
        s.decide(n_envs=0)


def test_snapshot_is_readonly_audit():
    """snapshot 只读审计（g/k/B/τ/n_obs/p̂ 齐）—— 不改状态。"""
    s = ELScheduler()
    _fill(s, 7, 1)
    snap = s.snapshot()
    assert snap == {"generation": 1, "index": 1, "B": 8, "tau": 0.75,
                    "n_obs": 8, "pass_rate": pytest.approx(0.875)}
    assert s.snapshot() == snap                    # 两次一致 = 没改状态


def test_decision_is_frozen_record():
    """ELDecision frozen（判完的结果不可事后篡改 —— 审计可追溯）。"""
    s = ELScheduler()
    _fill(s, 7, 1)
    d = s.decide(n_envs=2)
    assert isinstance(d, ELDecision)
    with pytest.raises(Exception):
        d.status = "hacked"                        # frozen dataclass 拒写
