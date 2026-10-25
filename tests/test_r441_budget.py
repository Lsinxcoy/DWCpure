# -*- coding: utf-8 -*-
"""R441 · P1-a 三段式工具预算（economy → strict → finalize）。

为什么：DWC 现在只有一道悬崖 —— `NATIVE_TOOLS_MAX_ROUNDS=15` 一到就强制 final。
模型在第 14 轮还在发散探索，第 15 轮突然被掐断，中间没有"收着点"的信号。

三段式（借 HarnessPro §5.3）：
  economy  到点 ⇒ 提醒批量检查、别重复读、别叙述过程
  strict   到点 ⇒ 提醒停止发散，只查与当前失败直接相关的证据
  finalize 到点 ⇒ **硬阻断**新工具调用，要求基于现有证据作答

纪律：提醒只能**追加**到观测，不许重写系统提示（cache 前缀 + 已证伪的"重写"做法）。
"""
from __future__ import annotations

from dwc.llm import budget as B


def test_stage_boundaries():
    b = B.ToolBudget(economy_after=6, strict_after=10,
                     finalize_after=15, reminder_every=3)
    assert [B.stage_of(n, b) for n in (0, 5, 6, 9, 10, 14, 15, 16)] == [
        "normal", "normal", "economy", "economy", "strict",
        "strict", "finalize", "finalize"]


def test_normalized_sorts_inverted_thresholds():
    """坏配置（economy > strict > finalize）不许把阶段顺序倒过来。"""
    b = B.ToolBudget(economy_after=20, strict_after=10,
                     finalize_after=5, reminder_every=3).normalized()
    assert b.economy_after <= b.strict_after <= b.finalize_after
    assert B.stage_of(21, b) == "finalize"


def test_normalized_rejects_nonpositive():
    b = B.ToolBudget(economy_after=0, strict_after=-3,
                     finalize_after=0, reminder_every=0).normalized()
    assert b.economy_after >= 1 and b.strict_after >= 1
    assert b.finalize_after >= 1 and b.reminder_every >= 1


def test_reminder_at_economy_boundary_only_once():
    b = B.ToolBudget(economy_after=6, strict_after=10,
                     finalize_after=15, reminder_every=3)
    assert B.reminder(5, b) == ""
    assert "批量" in B.reminder(6, b) or "batch" in B.reminder(6, b).lower()
    assert B.reminder(7, b) == ""          # 只在该点提醒一次


def test_reminder_at_strict_repeats_every_n():
    b = B.ToolBudget(economy_after=6, strict_after=10,
                     finalize_after=15, reminder_every=3)
    assert B.reminder(10, b) != ""
    assert B.reminder(11, b) == ""
    assert B.reminder(13, b) != ""          # 10 + 3
    assert B.reminder(16, b) == ""          # finalize 之后不再提醒


def test_finalize_has_no_reminder_but_blocks():
    """finalize 由 stage_of 驱动硬阻断，不需要再叠一段提醒。"""
    b = B.ToolBudget(economy_after=6, strict_after=10,
                     finalize_after=15, reminder_every=3)
    assert B.reminder(15, b) == ""
    assert B.stage_of(15, b) == "finalize"


def test_reminder_never_mentions_internal_names():
    """提醒是给模型看的 —— 不许出现内部常量名/文件路径。"""
    b = B.ToolBudget()
    for n in (b.economy_after, b.strict_after,
              b.strict_after + b.reminder_every):
        t = B.reminder(n, b)
        assert "NATIVE_TOOLS" not in t and "task_exec" not in t


# ------------------------------------------------------------ 与 task_exec 接线

def test_tool_budget_reads_policy(monkeypatch):
    from dwc.llm import task_exec as TE

    def fake_policy(component, key, default):
        assert component == "context_mgmt"
        return {"budget_economy_after": 4,
                "budget_strict_after": 8,
                "budget_finalize_after": 12,
                "budget_reminder_every": 2}.get(key, default)

    monkeypatch.setattr(TE, "_policy", fake_policy)
    b = TE.tool_budget()
    assert (b.economy_after, b.strict_after, b.finalize_after,
            b.reminder_every) == (4, 8, 12, 2)


def test_tool_budget_bad_policy_falls_back(monkeypatch):
    from dwc.llm import task_exec as TE

    def boom(*a, **k):
        raise RuntimeError("坏配置")

    monkeypatch.setattr(TE, "_policy", boom)
    b = TE.tool_budget()
    assert b.finalize_after >= b.strict_after >= b.economy_after >= 1
