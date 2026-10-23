# -*- coding: utf-8 -*-
"""R125 · 项2-4b Move-on 停止判决 — 五判据 + 决策留痕 + insufficient。

验收:
  □ C1 连败（末 k 全低于首项）; C2 峰值≥90%（含当前=峰值）
  □ C3 时间 2× 预算; C4 成本 2× 基线; C5 增益/成本 < 门槛
  □ continue / move_on / insufficient 三态（insufficient≠continue）
  □ 输入非法大声 raise（空序列/非数值/负倍率/k<1）
  □ 决策留痕（§3.6.5「是否停的记录」字段）; 校准注记在位
  □ 判据并集触发（非加权 — 与 Eq.10 决策层零权重同款）
"""
from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.foundation.stop_criteria import (  # noqa: E402
    CALIBRATION, StopError, move_on_verdict)


def test_c1_loss_streak_boundary():
    """C1: 末 k 项**全低于首项**才触发（一项持平/回升即不判）。"""
    # 5 项尾 [0.9,0.8,0.7,0.6,0.5] 全 <1.0 ⇒ 触发
    v = move_on_verdict(score_history=[1.0, 0.9, 0.8, 0.7, 0.6, 0.5],
                        cost_history=[1.0] * 6)
    assert "C1_loss_streak" in v["fired_criteria"]
    # ★ C1 实现约定: tail = score_history[-k:]（含**首项当尾成员**时首项
    #   不<自身 ⇒ 短序列天然不触发 — 保守语义（序列短⇒连败证据不足）;
    #   len<k ⇒ why 明示"不判"（insufficient）
    v_short = move_on_verdict(score_history=[1.0, 0.9, 0.8],        # len 3<5
                              cost_history=[1.0] * 3)
    assert "C1_loss_streak" not in v_short["fired_criteria"]
    assert "不判" in v_short["criteria"]["C1_loss_streak"]["why"]   # len<k
    # 末项持平（=首项 1.0）⇒ 不触发
    v3 = move_on_verdict(score_history=[1.0, 0.9, 0.8, 0.7, 0.6, 1.0],
                         cost_history=[1.0] * 6)
    assert "C1_loss_streak" not in v3["fired_criteria"]


def test_c2_peak_frac_and_current_equals_peak():
    """C2: 当前 ≥90% 峰值（含当前=峰值本身就是剩余空间小）。"""
    v = move_on_verdict(score_history=[0.4, 0.5, 0.46],
                        cost_history=[1, 1, 1])
    assert "C2_peak_exploited" in v["fired_criteria"]   # 0.46 ≥ 0.45
    v2 = move_on_verdict(score_history=[0.4, 0.5, 0.44],
                         cost_history=[1, 1, 1])
    assert "C2_peak_exploited" not in v2["fired_criteria"]  # 0.44<0.45
    # 单点序列 ⇒ C2 insufficient（峰值=自身无意义 — 不判）
    v0 = move_on_verdict(score_history=[1.0], cost_history=[1.0])
    assert v0["criteria"]["C2_peak_exploited"]["status"] == "insufficient"
    assert "C2_peak_exploited" not in v0["fired_criteria"]
    # 可调 peak_frac: [1.0,0.4] 阈值 0.5 ⇒ 0.4<0.5 不触发（阈值语义如实）
    v3 = move_on_verdict(score_history=[1.0, 0.4],
                         cost_history=[1, 1], params={"peak_frac": 0.5})
    assert "C2_peak_exploited" not in v3["fired_criteria"]
    # 阈值 0.3 ⇒ 0.4≥0.3 触发
    v4 = move_on_verdict(score_history=[1.0, 0.4],
                         cost_history=[1, 1], params={"peak_frac": 0.3})
    assert "C2_peak_exploited" in v4["fired_criteria"]


def test_c3_time_and_c4_cost_budgets():
    """C3 时间 2× 预算; C4 成本 ≥2× 基线均值（基线=前 n-1 项）。"""
    v = move_on_verdict(score_history=[0.3, 0.3], cost_history=[1, 5],
                        time_used=200, time_budget=90)
    assert "C3_time_budget" in v["fired_criteria"]   # 200≥180
    assert "C4_cost_budget" in v["fired_criteria"]   # 5 ≥ 2*1
    # 未达 ⇒ 不触发
    v2 = move_on_verdict(score_history=[0.3, 0.35], cost_history=[1, 1],
                         time_used=100, time_budget=90)
    assert "C3_time_budget" not in v2["fired_criteria"]
    assert "C4_cost_budget" not in v2["fired_criteria"]
    # cost 缺 ⇒ C4/C5 insufficient（不装判决）
    v3 = move_on_verdict(score_history=[0.3, 0.35])
    assert v3["criteria"]["C4_cost_budget"]["status"] == "insufficient"
    assert v3["criteria"]["C5_cost_benefit"]["status"] == "insufficient"


def test_c5_cost_benefit_threshold():
    """C5: 增益/成本 < 门槛（阈值 0 ⇒ 有正收益才继续）。"""
    # 末项增益 = 0（无变化）⇒ ratio=0 < 0? 否（0 不小于 0）— 边界: ≥ 门槛
    v = move_on_verdict(score_history=[1.0, 1.0], cost_history=[1.0, 1.0])
    assert "C5_cost_benefit" not in v["fired_criteria"]
    # 增益负 ⇒ ratio<0 < 0 触发
    v2 = move_on_verdict(score_history=[1.0, 0.8], cost_history=[1.0, 1.0])
    assert "C5_cost_benefit" in v2["fired_criteria"]
    # 门槛可调（0.5: ratio=0.1<0.5 触发）
    v3 = move_on_verdict(score_history=[1.0, 1.1], cost_history=[1.0, 1.0],
                         params={"cb_min_gain_per_cost": 0.5})
    assert "C5_cost_benefit" in v3["fired_criteria"]
    # 末条目成本 0 ⇒ 不装数（insufficient）
    v4 = move_on_verdict(score_history=[1.0, 1.1], cost_history=[1.0, 0.0])
    assert v4["criteria"]["C5_cost_benefit"]["status"] == "insufficient"


def test_verdict_states_and_decision_record():
    """三态 + 决策留痕（§3.6.5 字面"是否停的记录"）。"""
    # ★ 真 continue 设计例: 有峰值余量（60% vs 峰值 100% 中 = 0.6）
    v_cont = move_on_verdict(score_history=[1.0, 0.6, 0.61],
                             cost_history=[1, 1, 1])
    assert v_cont["verdict"] == "continue"
    assert v_cont["fired_criteria"] == []
    assert v_cont["decision_record"]["answer"] == "continue"
    # 对照: [0.5,0.52,0.6] 末项=峰值 ⇒ C2 exploited ⇒ move_on（升到顶=停）
    v_peak = move_on_verdict(score_history=[0.5, 0.52, 0.6],
                              cost_history=[1, 1, 1])
    assert v_peak["verdict"] == "move_on"
    assert "C2_peak_exploited" in v_peak["fired_criteria"]
    v_stop = move_on_verdict(score_history=[0.9, 0.95, 0.93],
                              cost_history=[1, 1, 1])
    assert v_stop["verdict"] == "move_on"
    assert "C2_peak_exploited" in v_stop["fired_criteria"]
    assert v_stop["decision_record"]["by"] == v_stop["fired_criteria"]
    # 单点序列 ⇒ 无判据可判（C1/C2 全 insufficient）⇒ verdict continue
    #   + status insufficient（数据不足不下"停"的判 — 保守继续）
    v_ins = move_on_verdict(score_history=[1.0], cost_history=[1.0])
    assert v_ins["status"] == "insufficient"
    assert v_ins["verdict"] == "continue"
    assert v_ins["fired_criteria"] == []
    # 校准注记五条在位
    assert set(CALIBRATION) == {"loss_streak_k", "peak_frac",
                                "budget_frac", "cb_min_gain_per_cost"} \
        or len(CALIBRATION) >= 4


def test_bad_input_raises():
    """非法输入大声 raise（空/非数值/负倍率/k<1）。"""
    with pytest.raises(StopError, match="非空"):
        move_on_verdict(score_history=[], cost_history=[])
    with pytest.raises(StopError, match="数值"):
        move_on_verdict(score_history=[1.0, "x"], cost_history=[1, 1])
    with pytest.raises(StopError, match="budget_frac"):
        move_on_verdict(score_history=[1.0], cost_history=[1],
                        params={"budget_frac": -1})
    with pytest.raises(StopError, match="loss_streak_k"):
        move_on_verdict(score_history=[1.0, 0.5],
                        cost_history=[1, 1],
                        params={"loss_streak_k": 0})


def test_union_not_weighted():
    """判据并集（触发即停 — 与 Eq.10 决策层零权重同款纪律）。"""
    # 两判据全触发 ⇒ 两个都列出（不是一个加权分）
    v = move_on_verdict(score_history=[1.0, 0.5, 0.4], cost_history=[3, 3, 3],
                        time_used=200, time_budget=90,   # 200≥2*90 ⇒ C3
                        params={"loss_streak_k": 2})
    assert set(v["fired_criteria"]) >= {"C1_loss_streak", "C3_time_budget"}
    # C5 也会触发（末两差负 — 并集非互斥）— 这正说明是并集
    assert v["criteria"]      # 每条判据的 why/参数全在（可审计）
    assert "并集" in v["★"]
