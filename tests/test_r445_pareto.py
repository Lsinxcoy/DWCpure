# -*- coding: utf-8 -*-
"""R445 · P3 三档 Pareto（性能 × 成本的非支配选择）。

诚实前提（必须记住）：
  trial 期能测到的成本是 **peer held-out 的评测开销**，两臂都要付，
  与候选规则的线上成本无关 ⇒ 它是噪声，不是信号。
  所以本模块**只在成本真有差异时**才改变结果；成本全等时退化为"最高分"，
  与现状完全一致（有测试锁定）。
"""
from __future__ import annotations

from dwc.organs import pareto as PA

# a 与 b 是干净的权衡对：b 分高一点、贵一点
A = {"name": "a", "score": 0.90, "cost": 100}
B = {"name": "b", "score": 0.95, "cost": 110}
C = {"name": "c", "score": 0.70, "cost": 50}    # 便宜但差 —— 非支配
D = {"name": "d", "score": 0.80, "cost": 120}   # 被 a 支配（分低且贵）
PTS = [A, B, C, D]


def test_non_dominated_drops_dominated():
    """d 被 a 支配（分更低、成本更高）；a/b/c 都在前沿上。"""
    assert sorted(PA.non_dominated(PTS)) == ["a", "b", "c"]


def test_non_dominated_keeps_all_when_tradeoff():
    assert sorted(PA.non_dominated([A, B])) == ["a", "b"]


def test_equal_points_are_all_kept():
    pts = [{"name": "x", "score": 1.0, "cost": 10},
           {"name": "y", "score": 1.0, "cost": 10}]
    assert sorted(PA.non_dominated(pts)) == ["x", "y"]


def test_empty_returns_empty():
    assert PA.non_dominated([]) == []


def test_heavy_prefers_score():
    """heavy 更看性能：b（0.95 / 110）赢 a（0.90 / 100）。"""
    assert PA.select([A, B], "heavy")["name"] == "b"


def test_lite_prefers_cost():
    """lite 更看成本：a（0.90 / 100）赢 b（0.95 / 110）。"""
    assert PA.select([A, B], "lite")["name"] == "a"


def test_equal_cost_degrades_to_best_score():
    """★ 成本全等 ⇒ 必须等于"最高分"，不许因为算法把好候选选掉。"""
    pts = [{"name": "lo", "score": 0.6, "cost": 100},
           {"name": "hi", "score": 0.9, "cost": 100}]
    for m in ("lite", "medium", "heavy"):
        assert PA.select(pts, m)["name"] == "hi"


def test_unknown_mode_falls_back_to_medium():
    assert PA.select(PTS, "nonsense")["name"] == PA.select(PTS, "medium")["name"]


def test_single_point():
    one = [{"name": "only", "score": 0.5, "cost": 7}]
    assert PA.select(one, "heavy")["name"] == "only"


def test_missing_cost_is_ignored_not_zero():
    """★ 没有成本 ⇒ 不许当 0（0 会被选成"最便宜"）。缺成本的候选不参与。"""
    pts = [{"name": "measured", "score": 0.8, "cost": 100},
           {"name": "unknown", "score": 0.99, "cost": None}]
    assert PA.select(pts, "lite")["name"] == "measured"
    assert PA.non_dominated(pts) == ["measured"]


def test_no_measured_points_returns_none():
    assert PA.select([{"name": "u", "score": 1.0, "cost": None}], "lite") is None


def test_selection_reports_why():
    r = PA.select([A, B], "lite")
    assert r["name"] and "mode" in r and "n_points" in r
