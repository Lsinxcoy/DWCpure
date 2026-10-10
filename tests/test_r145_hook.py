# -*- coding: utf-8 -*-
"""R145 · 八 hook + 互斥类（2606.14249 Table 1; 违规即抛不用日志）。

验收:
  □ HOOKS 八点名逐字 + READ_ONLY 原文明列
  □ 互斥类: 同组第二个注册即抛（治抢位冲突）
  □ 只读 hook（step_end/task_end）带 writes ⇒ 抛 paper_error
  □ ProcessorSpec 契约: 未知 hook/order 越界/空组/after 自指全拒
  □ fire: order 三段（PRE→NORMAL→POST）按名稳定 + 无逻辑占位可审计
  □ unregister: 不存在即 KeyError（不猜注没注册过）
"""
from __future__ import annotations

import os
import sys

import pytest

ROOT = r"E:/Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.organs.hook import (  # noqa: E402
    HOOKS, HOOK_MECHANICS, ORDERS, HookRegistry, HookViolation,
    ProcessorSpec)


def _spec(name: str, hook: str = "step_start", order: str = "NORMAL",
          group=None, after=(), call=None) -> ProcessorSpec:
    # ★ group=None ⇒ 默认唯一组; group="" 是**显式空串**要透传给契约层
    #   （助手不许用 or 兜底把测试要判的违规吃掉 — R145 教训同族）
    grp = ("g_" + name) if group is None else group
    return ProcessorSpec(name=name, hook=hook, order=order,
                         singleton_group=grp,
                         after=tuple(after), call=call)


def test_hooks_match_paper():
    """★ 八 hook 与 Table 1 原文逐字一致。"""
    assert HOOKS == ("task_start", "step_start", "before_model",
                     "after_model", "before_tool", "after_tool",
                     "step_end", "task_end")
    # READ_ONLY 原文明列两个（语义等价的扩展在实现内注释, 不改原文事实）
    assert "step_end" in HOOKS and "task_end" in HOOKS
    assert ORDERS == ("PRE", "NORMAL", "POST")


def test_singleton_group_conflict():
    """★ 互斥类: 同组第二个注册即抛（论文"每组至多一个"）。"""
    reg = HookRegistry()
    reg.register(_spec("p1", group="memory"))
    with pytest.raises(HookViolation):
        reg.register(_spec("p2", group="memory"))   # 抢位 ⇒ 抛
    # 不同组可共存
    reg.register(_spec("p3", group="judge"))
    assert reg.groups() == {"memory": "p1", "judge": "p3"}


def test_duplicate_name_rejected():
    """重名不静默覆盖（先 unregister 才可再注册）。"""
    reg = HookRegistry()
    reg.register(_spec("p1"))
    with pytest.raises(HookViolation):
        reg.register(_spec("p1"))
    reg.unregister("p1")
    reg.register(_spec("p1"))           # 注销后可重注册
    assert reg.groups()["g_p1"] == "p1"


def test_read_only_hook_write_violation():
    """★★ 只读 hook 带 writes ⇒ 立即抛 paper_error（不是日志后继续）。"""
    reg = HookRegistry()
    for hook in ("step_end", "task_end"):
        reg.register(_spec("ro_" + hook, hook=hook, group="g_ro_" + hook))
        with pytest.raises(HookViolation) as ei:
            reg.fire(hook, {}, writes=["state"])   # 违规写 ⇒ 抛
        assert "立即抛" in str(ei.value)
        # 无 writes 的正常触发不受影响
        assert reg.fire(hook, {}) == [None]


def test_spec_contract():
    """ProcessorSpec 契约: 未知 hook/order 越界/空组/after 自指全拒。"""
    with pytest.raises(HookViolation):
        _spec("x", hook="task_done")              # 未知 hook（拼错不宽容）
    with pytest.raises(HookViolation):
        _spec("x", order="LATE")                  # order 越界
    with pytest.raises(HookViolation):
        _spec("x", group="")                      # 空组（无法判同组）
    with pytest.raises(HookViolation):
        _spec("x", group="g", after=["g"])        # after 自指 ⇒ 环


def test_fire_order_segments():
    """★ order 三段 PRE→NORMAL→POST; 同段按名稳定（可复现触发序列）。"""
    reg = HookRegistry()
    trace: list = []
    reg.register(_spec("b", hook="step_start", order="POST",
                       group="g1", call=lambda s: trace.append("b")))
    reg.register(_spec("a", hook="step_start", order="PRE",
                       group="g2", call=lambda s: trace.append("a")))
    reg.register(_spec("c", hook="step_start", order="NORMAL",
                       group="g3", call=lambda s: trace.append("c")))
    reg.register(_spec("a2", hook="step_start", order="PRE",
                       group="g4", call=lambda s: trace.append("a2")))
    reg.fire("step_start", {})
    assert trace == ["a", "a2", "c", "b"]     # PRE(按名)→NORMAL→POST


def test_unregister_missing_is_explicit():
    """unregister 不存在 ⇒ KeyError（不猜注没注册过 — 显式失败）。"""
    reg = HookRegistry()
    with pytest.raises(KeyError):
        reg.unregister("nope")


def test_summary_and_registry_shape():
    """汇总面: per_hook 计数 + read_only 原文明列 + n_groups。"""
    reg = HookRegistry()
    reg.register(_spec("p1", hook="before_tool"))
    reg.register(_spec("p2", hook="after_tool"))
    s = reg.summary()
    assert s["n_registered"] == 2 and s["n_groups"] == 2
    assert s["per_hook"]["before_tool"] == 1 and s["per_hook"]["task_end"] == 0
    assert sorted(s["read_only"]) == ["step_end", "task_end"]
