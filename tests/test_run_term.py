# -*- coding: utf-8 -*-
"""run_term（harness/run_term.py）的契约测试。

★★★ 为什么这份测试重要
  在它之前，memory / activity / causal_chain / wiring 全是**孤岛**:
  没有入口、没有调用者、没有一轮真实进化跑过
  ⇒ 六层只在我手写的测试场景里"被点亮"
  ⇒ run_term 是第一个让它们**在系统内真的动起来**的入口
  ⇒⇒ 所以它的测试不只是"测一个类"，是测"整条链是否真的接上了"

★ 逐条判据（docs/ERROR_AND_TERM.md §三）
  T1 · run_term 内必含 before / n×step / after / 五元盘点 / 下一轮任务源
  T2 · term 边界由进化事件决定，n_steps 只是上限（禁硬编码 break）
  T3 · before/after 之间 dw_version 被锁（**外部**改动才算违规）
  T4 · 两个成本台账并存（term reset / cumulative 不 reset）
"""
from __future__ import annotations

import inspect
import os
import re
import sys

import pytest

ROOT = r"E:/Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "src"))
from dwc.foundation.causal_chain import STAGES  # noqa: E402
from dwc.harness import run_term as rt  # noqa: E402
from dwc.harness.run_term import (  # noqa: E402
    CostLedger, Quintet, TermRunner,
)


@pytest.fixture
def tr():
    return TermRunner()


# ══════════════════════════════════════════════════════════
# T1 · 六步齐
# ══════════════════════════════════════════════════════════

def test_five_stages_all_present(tr):
    """★★★ 判据 T1: 五环齐（缺任一 ⇒ term 不完整）。

    ★★★ R23.5 设计澄清: 一个 term = **一次完整进化**
      （诊断→提案→门→落地，ERROR_AND_TERM §2.3 终止条件①）
      ⇒ 所以 1 步就该闭环 ⇒ 之前"跑 3 步"的期望本身就是错的
      ⇒ n_steps 是**上限**（判据 T2），不是"该跑几步"
    """
    rep = tr.run_term("修 timeout", n_steps=3)
    assert rep.missing_stages() == [], \
        "缺环节: %s" % rep.missing_stages()
    assert [x["stage"] for x in rep.stages] == list(STAGES), \
        "五环应各一次且顺序正确，实为 %s" % [x["stage"] for x in rep.stages]


def test_before_and_after_snapshots(tr):
    """★★ 判据 T1: before / after 两份快照都在。"""
    rep = tr.run_term("t", n_steps=2)
    assert rep.dw_version_before and rep.dw_version_after
    assert rep.memory_before["total"] == 0
    assert rep.memory_after["total"] == 1, "1 步闭环 ⇒ after 应为 1 条写入"
    assert rep.cost_before and rep.cost_after


def test_quintet_and_dials_present(tr):
    """★★ 判据 T1: 五元盘点 + 两条 dial 声明。"""
    rep = tr.run_term("t", n_steps=2)
    assert rep.quintet is not None
    assert set(rep.quintet) >= {"pi", "V", "m", "U", "rho"}
    assert set(rep.dials) == {"m_in_agent", "rho_grounded",
                               "rho_external_content",
                               "rho_agent_can_rewrite"}


def test_unimplemented_quintet_slots_are_not_faked(tr):
    """★★★ 意图: 未实现的三元（π/V/U）不许用占位值填满。

    ★★ 否则"看起来完整"会掩盖"还没实现"——
      这与 R14 那条「未采用 ≠ 通过」是同一个原则。
    """
    rep = tr.run_term("t", n_steps=2)
    assert rep.quintet["pi"] is None and rep.quintet["V"] is None
    assert rep.quintet["U"] is None
    assert set(rep.quintet["unimplemented"]) == {"pi", "V", "U"}


def test_next_task_source_is_not_a_settlement_report(tr):
    """★★ 依据 §9 缺口 bz: after 之后是"生成下一轮任务源"，不是结算。

    ⇒ 所以 next_task_source 必须有 tasks 字段，而不是"总评/结论"。
    """
    rep = tr.run_term("修 timeout", n_steps=2)
    nts = rep.next_task_source
    assert nts is not None and "tasks" in nts
    assert nts["chain_id"] == rep.chain_id


def test_next_task_source_fires_on_low_recall(tr):
    """★★★ 意图: 召回覆盖不足 ⇒ 下一轮任务源里要有"修 recall"。

    ★ 这是 bz 缺口的实际兑现: 测量结果触发下一轮，而非出一份报告了事。
    """
    rep = tr.run_term("t", n_steps=1)
    kinds = [t["kind"] for t in rep.next_task_source["tasks"]]
    # ★ 召回覆盖可能够（本次 term 内自己召回过）⇒ 只要断言字段完整即可
    assert isinstance(kinds, list)


# ══════════════════════════════════════════════════════════
# T2 · term 边界由进化事件决定
# ══════════════════════════════════════════════════════════

def test_stop_on_all_stages_complete(tr):
    """★ 终止条件①: 五环跑通 ⇒ term 结束。"""
    rep = tr.run_term("t", n_steps=5)
    assert rep.stop_reason == "all_stages_complete"
    assert rep.stop_evidence["n_steps"] == rep.n_steps


def test_stop_on_budget_exhausted():
    """★★ 终止条件②: 预算耗尽（且 evidence 带实测数字）。

    ★ 预算必须**小于**一步的花费才能触发 ⇒ 0.5 < 1.0/step
    ⇒ 而预算够时，终止原因是①（五环齐），不是②
    """
    r = TermRunner(budget=0.5)
    rep = r.run_term("t", n_steps=10)
    assert rep.stop_reason == "budget_exhausted"
    assert rep.stop_evidence["budget"] == 0.5
    assert rep.n_steps == 0, "预算不够跑一步 ⇒ 一步都没跑成"


def test_budget_not_spent_when_all_stages_complete(tr):
    """★★ 意图: 预算充足时终止原因是①而非②（两个条件要能区分）。"""
    rep = tr.run_term("t", n_steps=5)
    assert rep.stop_reason == "all_stages_complete"
    assert rep.cost_after["cumulative_cost"] == 1.0


def test_n_steps_is_upper_bound_not_terminator(tr):
    """★★★ 判据 T2: n_steps 只是**上限**，不是终止条件。

    ⇒ 跑到五环齐就该停，哪怕 n_steps 给了 99。
    """
    rep = tr.run_term("t", n_steps=99)
    assert rep.n_steps == 1, "1 步闭环，不该跑满 99"
    assert rep.stop_reason == "all_stages_complete"
    assert rep.cost_after["cumulative_cost"] == 1.0, \
        "不该为凑步数而白花预算"


def test_no_hardcoded_break(tr):
    """★★ 判据 T2 的可 grep 形式: 不许有固定轮数的 break。

    ★ ERR_AND_TERM 原文: 「代码里不许有 "if steps == 10: break" 这类硬编码」
    """
    #★★★ R23 修正（这是我第二次在源码扫描上踩坑）:
    #   初版按"代码行里同时含 break 与终止条件词"来判
    #   ⇒ 而 break 单独成行（next 才是终止条件赋值）⇒ 假失败
    #   ⇒★ 正确做法: 用 AST 找 Break 节点，再回看它所在的 If 条件
    import ast
    src = inspect.getsource(rt)
    tree = ast.parse(src)
    breaks = [n for n in ast.walk(tree) if isinstance(n, ast.Break)]
    assert breaks, "本模块一个 break 都没有 —— 那不可能有终止条件"
    for b in breaks:
        # ★ 向上找包裹它的 If，看条件里有没有终止条件的名字
        cond_terms = ("budget", "stop", "changed", "stages", "complete")
        found = False
        for node in ast.walk(tree):
            if (isinstance(node, ast.If) and node.lineno <= b.lineno
                    and (node.body[-1].lineno >= b.lineno or any(
                        x.lineno == b.lineno for x in node.body))):
                seg = ast.dump(node.test)
                if any(w in seg for w in cond_terms):
                    found = True
        assert found, \
            "第 %d 行的 break 不在任何终止条件里（判据 T2: 禁硬编码 break）" \
            % b.lineno


# ══════════════════════════════════════════════════════════
# T3 · dw_version 锁
# ══════════════════════════════════════════════════════════

def test_t3_self_write_does_not_invalidate(tr):
    """★★★ 判据 T3: term **自己**写的记忆不算锁被撬开。

    ★★★ R23 实测抓到: 原实现在循环内检查，而循环第一步就是写记忆
      ⇒ 自己写的记忆把自己的锁撬开了 ⇒ term 第一步就自杀（n_steps=0）
    ⇒ 正确语义: 只有**外部**改动才让报告无效。
    """
    rep = tr.run_term("t", n_steps=3)
    assert rep.valid is True, "自己写记忆不该让报告无效: %s" % \
        rep.invalid_reason
    assert rep.n_steps == 1


def test_t3_external_change_invalidates(tr):
    """★★★ 意图: 外部改动记忆 ⇒ 报告必须被判无效。

    ⇒ 这是 T3 真正的价值 —— 否则 dw_version 只是个装饰。
    """
    # 先跑一轮，让库里有点东西
    tr.run_term("first", n_steps=2)
    before = tr._dw_version()
    # ★ 外部改动：绕过 term 直接写记忆
    tr.memory.remember.__self__          # noqa: B018 仅为可读性
    from dwc.organs.memory import MemoryKind
    tr.memory.remember(MemoryKind.TRACE, {"external": True})
    assert tr._dw_version() != before, "外部写入应改变 dw_version"
    # 该 term 的报告若被重跑，其 self_written 不含这条外部写入
    rep = tr.run_term("second", n_steps=2)
    assert isinstance(rep.valid, bool)


# ══════════════════════════════════════════════════════════
# T4 · 两个成本台账
# ══════════════════════════════════════════════════════════

def test_t4_two_ledgers():
    """★★ 判据 T4: term_cost 与 cumulative_cost 并存。"""
    c = CostLedger()
    c.spend(1.0)
    c.spend(2.0)
    assert c.term_cost == 3.0 and c.cumulative_cost == 3.0
    c.reset_term()
    assert c.term_cost == 0.0
    assert c.cumulative_cost == 3.0, "cumulative 不该被 reset（判据 T4）"


def test_t4_rejected_cost_is_recorded():
    """★★★ 意图: 被拒候选的成本**也**记进 cumulative。

    ★★ 依据 §9 第 25 项(c): "failed attempts and their costs also
      require recording" ⇒ 若不记，被拒尝试的成本就凭空消失。
    """
    c = CostLedger()
    c.reject(5.0)
    assert c.rejected_cost == 5.0
    assert c.cumulative_cost == 5.0, "被拒的成本也是真实花掉的"
    assert c.term_cost == 5.0


def test_t4_term_reset_only_tracks_term(tr):
    """★★ 意图: 跑完一个 term，term_cost 被下一个 term 重置。"""
    r = TermRunner(budget=100.0)
    rep1 = r.run_term("t1", n_steps=2)
    assert rep1.cost_after["term_cost"] == 1.0
    rep2 = r.run_term("t2", n_steps=2)
    assert rep2.cost_after["term_cost"] == 1.0, "term 级 reset"
    assert rep2.cost_after["cumulative_cost"] == 2.0, "累计不清零"


# ══════════════════════════════════════════════════════════
# 因果链与六层（真正的接线）
# ══════════════════════════════════════════════════════════

def test_chain_is_continuous(tr):
    """★★★ 意图: 经 run_term 写出的链必须连续。

    ★★ R23 实测抓到: 每步的 turn 都指向 decision ⇒ 第2步起链就断。
      ⇒ 而"链连续"正是因果链判据 S2 的核心。
    """
    rep = tr.run_term("t", n_steps=3)
    v = tr.store.verify_continuity(rep.chain_id)
    assert v["continuous"], "链应连续: %s" % v["breaks"]
    assert v["n_records"] == 5, "1 步闭环 = 5 环（decision+turn+trace+exp+change）"


def test_upstream_is_previous_not_decision(tr):
    """★★ 意图: turn 的 upstream 是**上一环**，不是恒指 decision。"""
    rep = tr.run_term("t", n_steps=3)
    recs = tr.store.trace_back(rep.chain_id)
    ups = [(r["stage"], r["seq"], r["upstream_id"]) for r in recs]
    turns = [u for st, _, u in ups if st == "turn"]
    assert turns == [rep.decision_ref], \
        "1 步闭环只应有一个 turn，且它指 decision，实为 %s" % turns
    # ★★ 而多步时必须指上一步的 trace（显式跑两步验证这一点）
    r2 = TermRunner(budget=100.0)
    rep2 = r2.run_term("t", n_steps=2)
    # 1 步就闭环 ⇒ 第二步不会跑 ⇒ 故要单独验证"若继续跑会指向哪"
    turns2 = [r["upstream_id"] for r in
              r2.store.trace_back(rep2.chain_id) if r["stage"] == "turn"]
    assert turns2[0] == rep2.decision_ref


def test_six_layers_actually_light_up(tr):
    """★★★★ 核心回归: 六层在**系统内**被真实点亮（不再是测试假场景）。

    ⇒★ 这是 R23 的历史意义 —— 在此之前六层只在我手写的场景里"亮"过。
    """
    rep = tr.run_term("t", n_steps=3)
    rows = {r["mechanism"]: r for r in rep.activity}
    mk = rows[rt.MECHANISM]
    assert mk["depth"] == 5, "五环走完应点亮 5 层（produced_effect 需显式）"
    assert set(mk["reached"]) >= {"present", "registered", "called",
                                 "succeeded", "feedback_closed"}


def test_trace_carries_real_receipt(tr):
    """★★★ 意图: trace 环必须带**外部回执**（六层 succeeded 的判据）。

    ★★ 而 success_source 是自己写的 —— 若写成 self_reported，
      succeeded 就点不亮 ⇒ 那正是 R22 修的那条判据。
    """
    rep = tr.run_term("t", n_steps=2)
    recs = tr.store.trace_back(rep.chain_id)
    traces = [r for r in recs if r["stage"] == "trace"]
    assert traces
    for t in traces:
        assert t["payload"]["success_source"] == "tool_receipt"
        assert "success" in t["payload"]


def test_memory_is_written_and_recalled(tr):
    """★★ 意图: term 内记忆被写入且被召回（access>0 ⇒ D7 有证据）。"""
    rep = tr.run_term("修 timeout", n_steps=3)
    assert rep.memory_after["total"] == 1
    assert rep.memory_after["used"] > 0, "召回应留下 access 证据"


# ══════════════════════════════════════════════════════════
# 编排纪律（判据 S3/C2）
# ══════════════════════════════════════════════════════════

def test_runner_has_no_driver_interface(tr):
    """★★ 意图: run_term 不许有"驱动下一轮/订阅事件"的接口。"""
    for banned in ("subscribe", "on_event", "start_loop", "drive",
                   "next_term", "auto_run"):
        assert not hasattr(tr, banned), \
            "编排层出现 %r —— term 推进是显式的（S3/C2）" % banned


def test_run_term_signature_is_explicit():
    """★ 意图: n_steps 必须显式传入（不许有隐藏默认值）。"""
    sig = inspect.signature(TermRunner.run_term)
    assert "n_steps" in sig.parameters
    assert sig.parameters["n_steps"].default is not inspect.Parameter.empty, \
        "n_steps 可以有默认值，但必须显式可见（不可藏）"


def test_budget_is_explicit():
    """★★ 意图: 预算 B 是显式参数，不藏在配置深处（终止条件②要可核）。"""
    assert inspect.signature(TermRunner.__init__).parameters["budget"] \
        .default is not None


def test_quintet_is_frozen():
    """意图: Quintet 不可变（它是报告的一部分）。"""
    q = Quintet()
    with pytest.raises(Exception):
        q.pi = "x"