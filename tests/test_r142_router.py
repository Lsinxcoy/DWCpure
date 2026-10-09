# -*- coding: utf-8 -*-
"""R142 · 七桶路由（Table 8 原文语义 — infra_only 不进化 + 弃权一等输出）。

验收:
  □ 七桶值枚举（BUCKETS 与设计稿一字不差）
  □ 路由表 ROUTE/EVOLVABLE 语义（infra_only 不在可进化集）
  □ 判定链顺序: infra > all_pass > unreachable > stuck > fixable > mixed
  □ 成本维度: wasteful（过限）vs efficient（限内）— None 口径不猜
  □ TermObservation 契约: 空观测 raise / 负值 raise / cost 负 raise
  □ 批量 batch 保序
"""
from __future__ import annotations

import os
import sys

import pytest

ROOT = r"E:/Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.organs.router import (  # noqa: E402
    BUCKETS, EVOLVABLE, ROUTE, RouterError, TermObservation, batch, route)


def test_buckets_match_paper():
    """★ 七桶与 Table 8 原文一字不差（设计稿 L106-108 逐字）。"""
    assert BUCKETS == ("all_pass_efficient", "all_pass_wasteful", "mixed",
                       "fixable_fail", "stuck_fail", "unreachable_fail",
                       "infra_only")
    # infra_only 永不可进化（论文禁令: 不修环境 bug）
    assert "infra_only" not in EVOLVABLE
    assert ROUTE["infra_only"] == "no_diagnosis"
    # 弃权是一等输出（Listing 2 is_culprit=false）
    assert ROUTE["unreachable_fail"] == "abstain"
    # stuck ⇒ recovery hint（不是 propose!）
    assert ROUTE["stuck_fail"] == "recovery_hint"


def test_infra_only_exclusive():
    """★ infra_only: 只观测 infra 失败 ⇒ 不诊断（pass=fail=0 ∧ infra>0）。"""
    r = route(TermObservation(infra_fail=2))
    assert r["bucket"] == "infra_only"
    assert r["evolvable"] is False
    assert "不进诊断" in r["note"] or "不诊断" in r["note"]
    # pass + infra 混合: Table 8 未定义该组合 ⇒ **显式 raise 不猜**
    # （infra_only 的排他性: 一旦有被测对象的 pass, infra 混入就出口径）
    with pytest.raises(RouterError):
        route(TermObservation(n_pass=1, infra_fail=1))
    # fail + infra 混合: infra 不计入 n_fail ⇒ 全败侧正常分 fixable
    # （口径: infra_fail 只用于 infra_only 的排他判据 — 不含混入语义）
    r2 = route(TermObservation(n_fail=1, infra_fail=1))
    assert r2["bucket"] == "fixable_fail"


def test_all_pass_efficient_vs_wasteful():
    """成本维度: 过限 wasteful / 限内 efficient / 无口径 efficient（不猜）。"""
    r_eff = route(TermObservation(n_pass=5, cost=2.0, budget_ceiling=10.0))
    assert r_eff["bucket"] == "all_pass_efficient"
    assert r_eff["evolvable"] is False            # 无改进面
    r_waste = route(TermObservation(n_pass=5, cost=20.0, budget_ceiling=10.0))
    assert r_waste["bucket"] == "all_pass_wasteful"
    assert r_waste["evolvable"] is True          # 省成本是改进面
    # None 口径: cost/ceiling 任一缺 ⇒ 不判 wasteful（口径外不猜）
    r_none = route(TermObservation(n_pass=5))
    assert r_none["bucket"] == "all_pass_efficient"
    r_none2 = route(TermObservation(n_pass=5, cost=99.0))  # ceiling None
    assert r_none2["bucket"] == "all_pass_efficient"


def test_unreachable_abstain():
    """★ unreachable ⇒ abstain 且不可进化（弃权是一等输出）。"""
    r = route(TermObservation(n_fail=3, reachable=False))
    assert r["bucket"] == "unreachable_fail"
    assert r["action"] == "abstain"
    assert r["evolvable"] is False


def test_stuck_before_fixable():
    """★ 顺序: stuck（重复≥N）优先于 fixable ⇒ recovery_hint 不是 propose。"""
    r = route(TermObservation(n_fail=4, repeat_signature_count=3,
                             stuck_threshold=3))
    assert r["bucket"] == "stuck_fail"
    assert r["action"] == "recovery_hint"
    # 未达阈值 ⇒ fixable（提改动）
    r2 = route(TermObservation(n_fail=4, repeat_signature_count=2,
                              stuck_threshold=3))
    assert r2["bucket"] == "fixable_fail"
    assert r2["action"] == "propose"


def test_mixed_and_fixable_defaults():
    """mixed（有 pass 有 fail）与 fixable（全败有签名）默认路径。"""
    r_mixed = route(TermObservation(n_pass=2, n_fail=3))
    assert r_mixed["bucket"] == "mixed"
    assert r_mixed["action"] == "propose"
    r_fix = route(TermObservation(n_fail=3, signature_present=True))
    assert r_fix["bucket"] == "fixable_fail"


def test_observation_contract():
    """★ 契约: 空观测/负值/cost 负 ⇒ 显式 raise（不是默认桶）。"""
    with pytest.raises(RouterError):
        route(TermObservation())                    # 全 0
    with pytest.raises(RouterError):
        TermObservation(n_pass=-1)                  # 负计数
    with pytest.raises(RouterError):
        TermObservation(n_fail=True)                # bool 不算 int
    with pytest.raises(RouterError):
        TermObservation(n_pass=1, cost=-5.0)        # cost 负


def test_batch_preserves_order():
    """批量保序（term 序列喂入不改次序）。"""
    seq = [TermObservation(n_pass=1),
           TermObservation(n_fail=2),
           TermObservation(infra_fail=1)]
    out = batch(seq)
    assert [o["bucket"] for o in out] == [
        "all_pass_efficient", "fixable_fail", "infra_only"]


def test_route_returns_full_table():
    """返回带全表 + 可进化集（调用方免查表 — 可审计）。"""
    r = route(TermObservation(n_pass=1))
    assert set(r["route"]) == set(BUCKETS)
    assert "infra_only" not in r["evolvable_buckets"]
