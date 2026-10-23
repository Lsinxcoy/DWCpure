# -*- coding: utf-8 -*-
"""R151 · 退火编辑预算（门⑥ · 式 4）— state.b_t 空挂字段的议程落地。

验收:
  □ 式 4 逐字（ceil + cos 议程）+ 端点（t=0 最宽, t=T=b_min）
  □ 契约: b_min≥1 / b_max≥b_min / T≥1 / t∈[0,T]（越界即拒）
  □ 单调不增（结构断言在实现内 — 议程错了要炸不等测试）
  □ check: 精确同键去重（component,hunk）+ within_budget 判定
  □ EditItem: 空 component/hunk 拒
  □ state.b_t 空挂实况入档（议程落此, 填值归调用方）
"""
from __future__ import annotations

import math
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.organs.budget import (  # noqa: E402
    BUDGET_MECHANICS, DEFAULT_B_MAX, DEFAULT_B_MIN, DEFAULT_HORIZON,
    BudgetError, EditItem, anneal_report, check, schedule)


def test_formula_and_endpoints():
    """★ 式 4 逐字 + 端点（t=0 ⇒ b_max, t=T ⇒ b_min）。"""
    assert schedule(0, 20) == DEFAULT_B_MAX          # cos0=1 ⇒ 最宽
    assert schedule(20, 20) == DEFAULT_B_MIN         # cosπ=−1 ⇒ 最紧=1
    # 中点手算: b_min=1,b_max=8,T=20,t=10 ⇒ 1+7×0.5×(1+cos(π/2))=1+3.5=4.5⇒ceil=5
    assert schedule(10, 20, b_min=1, b_max=8) == 5


def test_schedule_contract():
    """契约: b_min≥1 / b_max≥b_min / T≥1 / t∈[0,T]（bool 不算 int）。"""
    for bad in (0, -1, True, "5"):
        with pytest.raises(BudgetError):
            schedule(5, T=bad)
    with pytest.raises(BudgetError):
        schedule(5, 20, b_min=0)                     # b_min<1
    with pytest.raises(BudgetError):
        schedule(5, 20, b_min=8, b_max=2)            # b_max<b_min
    for bad_t in (-1, 21, 1.5, True):
        with pytest.raises(BudgetError):
            schedule(bad_t, 20)


def test_anneal_monotone_and_report():
    """★ 全议程单调不增（结构断言）+ 末轮=b_min ✓。"""
    rep = anneal_report(20)
    assert rep["monotone_nonincreasing"] is True
    assert rep["endpoints"]["t0"] == DEFAULT_B_MAX
    assert rep["endpoints"]["tT"] == DEFAULT_B_MIN
    assert "✓" in rep["note"]
    assert len(rep["rows"]) == 21                    # t = 0..T 含端点


def test_check_dedup_and_verdict():
    """★ 精确同键去重（component,hunk）+ within_budget 判定。"""
    items = [EditItem("prompt", "f1"), EditItem("prompt", "f1"),
             EditItem("config", "f2")]
    out = check(items, 20)                            # 末轮 b_t=1
    assert out["b_t"] == 1
    assert out["n_edits"] == 2                        # 3 条去重成 2 键
    assert out["verdict"] == "over_budget" and out["within_budget"] is False
    # 早期宽预算 ⇒ 同批过
    out2 = check(items, 0)
    assert out2["b_t"] == DEFAULT_B_MAX
    assert out2["verdict"] == "ok"
    # 编辑范围可审计
    assert sorted(out["components"]) == ["config", "prompt"]


def test_edit_item_contract():
    """EditItem: 空 component/hunk ⇒ 拒（计数单位不可缺边）。"""
    with pytest.raises(BudgetError):
        EditItem("", "h")
    with pytest.raises(BudgetError):
        EditItem("prompt", "")


def test_check_input_type_guard():
    """items 非序列 ⇒ 显式拒（不猜 iterable）。"""
    with pytest.raises(BudgetError):
        check("not-a-list", 5)


def test_mechanics_and_state_gap():
    """★ state.b_t 空挂实况入档（议程落此, 填值归调用方）。"""
    assert "式 4" in BUDGET_MECHANICS["formula"]
    assert "无写入方" in BUDGET_MECHANICS["state_b_t"]


def test_midpoint_exact_math():
    """中点数学对账（半値点 cos(π/2)=0 防浮点误差误判 ceil）。"""
    # b_min=2,b_max=10,T=10,t=5 ⇒ 2+8×0.5×1=6.0 ⇒ ceil(6−1e-12)=6
    assert schedule(5, 10, b_min=2, b_max=10) == 6
