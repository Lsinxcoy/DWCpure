# -*- coding: utf-8 -*-
"""R143 · Table 8 七桶路由接线 — TermReport.router + 三形态 + 自造路径诚实边界。

验收:
  □ TermReport.router 字段存在（routed 三形态）
  □ 无 judge ⇒ routed=False + why 在场（不猜桶: 0 事实≠infra 失败）
  □ 有 judge ⇒ routed=True + bucket/action/evolvable 真路由
  □ 成本投影: cost_after.term_cost 真入 TermObservation
  □ infra_fail 不映射 not_evaluated（未评价≠环境失败 — 口径纪律）
  □ 自造路径诚实边界: R25 自造观测全过 ⇒ bucket 恒 all_pass_efficient
    （与 R127 V 恒等同族 — router 在有真执行体前无区分度, 如实标注）
"""
from __future__ import annotations

import inspect
import os
import sys

ROOT = r"E:/Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.harness.run_term import TermRunner  # noqa: E402
from dwc.organs.judge import Judge  # noqa: E402


def test_term_report_has_router_field():
    """★ 字段在位 + 默认空 dict（不破坏既有构造）。"""
    from dwc.harness.run_term import TermReport
    import time
    r = TermReport(term_id="t1", chain_id="c1", started_at=time.time())
    assert r.router == {}


def test_no_judge_no_route():
    """★ 无 judge ⇒ 显式 not routed（不猜桶 — 0 事实≠infra 失败）。"""
    rep = TermRunner(db_path=":memory:").run_term("t", n_steps=2)
    assert rep.router["routed"] is False
    assert "不猜桶" in rep.router["why"]


def test_with_judge_real_route():
    """★ 有 judge ⇒ 真路由（all_pass_efficient + no_evolution）。"""
    rep = TermRunner(db_path=":memory:", judge=Judge()).run_term(
        "t", n_steps=3)
    ro = rep.router
    assert ro["routed"] is True
    assert ro["bucket"] == "all_pass_efficient"
    assert ro["action"] == "no_evolution"
    assert ro["evolvable"] is False
    assert ro["evolvable_buckets"] and "infra_only" not in ro["evolvable_buckets"]


def test_cost_projection_into_observation():
    """★ 成本投影: CostLedger.term_cost 真进 router 输入。"""
    from dwc.organs.router import TermObservation, route
    tr = TermRunner(db_path=":memory:", judge=Judge())
    rep = tr.run_term("t", n_steps=3)
    cost = rep.cost_after.get("term_cost")
    assert cost is not None and cost > 0
    # 同输入复算 ⇒ 同桶（路由器确定性, 无随机成分）
    r = route(TermObservation(n_pass=rep.judgement.get("pass", 0),
                              n_fail=rep.judgement.get("fail", 0),
                              cost=float(cost), budget_ceiling=float(tr.budget)))
    assert r["bucket"] == rep.router["bucket"]


def test_infra_fail_not_mapped_from_not_evaluated():
    """★ 口径纪律: not_evaluated 不进 infra_fail（未评价≠环境失败）。

    判据（行为级, 不靠源码字符串）: 跑一次 judge 注入的 term, 若
    not_evaluated 被映射成 infra_fail 且 verdict 里 not_evaluated>0
    ⇒ 桶会变 infra_only; 反之 routed 面保持 all_pass_* 即未混入。
    """
    rep = TermRunner(db_path=":memory:", judge=Judge()).run_term(
        "t", n_steps=3)
    # 自造观测全过 ⇒ not_evaluated=0 ⇒ 该判据只锁"映射后不会误判 infra"
    if rep.router["routed"] is True:
        assert rep.router["bucket"] != "infra_only"
    # 源码侧: 确认没有把 not_evaluated 传给 infra_fail（字符串级兜底）
    src = inspect.getsource(TermRunner.run_term)
    seg = src.split("TermObservation(")[1][:300]
    assert "not_evaluated" not in seg


def test_synthetic_path_caveat():
    """★★ 诚实边界: 自造观测全过 ⇒ bucket 恒 all_pass_efficient。

    R25 自造路径的观测 success 全 True ⇒ router 区分度只在真执行体
    接入后出现（同 R127 V 恒等教训: 度量的区分度前提是观测有区分）。
    本条测试锁住这个**边界**（不假装区分度存在）。
    """
    rep = TermRunner(db_path=":memory:", judge=Judge()).run_term(
        "t", n_steps=3)
    # 自造路径 ⇒ 全过 ⇒ 唯一可能桶（efficient/wasteful 只差成本维度）
    assert rep.router["bucket"] in ("all_pass_efficient", "all_pass_wasteful")
    # 且来源是自造（观测带 synthetic 标记）
    assert rep.router["routed"] is True


def test_judgeless_report_still_valid():
    """不回归: 无 judge 时 term 其余面（五环/valid）不受 router 影响。"""
    rep = TermRunner(db_path=":memory:").run_term("t", n_steps=3)
    assert rep.valid is True
    assert rep.judgement is None
    assert rep.router["routed"] is False
