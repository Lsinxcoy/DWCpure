# -*- coding: utf-8 -*-
"""R445 · P3 · 三档 Pareto（性能 × 成本的非支配选择）。

★★★ 定位（G1）: **DWC-AUTO** —— 自我强化的选择层：一轮多个候选时，
按"要分"还是"要省"挑一个，而不是永远只挑最高分。

★★★ 诚实前提（这个模块最容易被写成假机制，必须写清）
  trial 期能测到的成本是 **peer held-out 的评测开销** —— 两臂都要付，
  与候选规则的线上成本无关 ⇒ 它是噪声，不是信号。
  所以：
    · 成本全等 ⇒ 退化为"最高分"，与现状完全一致（有测试锁定）。
    · 成本缺失 ⇒ 该候选**不参与**（不许当 0，0 会被选成"最便宜"）。
    · 没有任何成本数据 ⇒ `select` 返回 None，调用方保持原行为。
  本模块只在**成本真有差异**时才改变结果。

三档权重（借 HarnessPro 的 lite/medium/heavy）
  J = a·d_perf² + b·d_cost²
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

MODES: Dict[str, tuple] = {
    "lite": (1.0, 2.0),      # 更看成本
    "medium": (1.0, 1.0),
    "heavy": (2.0, 1.0),     # 更看性能
}
DEFAULT_MODE = "medium"


def _measured(points: Any) -> List[Dict[str, Any]]:
    """只保留 **分数与成本都测到** 的点。坏条目跳过，不猜。"""
    out: List[Dict[str, Any]] = []
    for p in (points or []):
        if not isinstance(p, dict):
            continue
        try:
            s = float(p.get("score"))
        except (TypeError, ValueError):
            continue
        c = p.get("cost")
        if c is None:
            continue                  # ★ 缺失 ≠ 0
        try:
            c = float(c)
        except (TypeError, ValueError):
            continue
        out.append({"name": str(p.get("name") or ""), "score": s, "cost": c})
    return out


def non_dominated(points: Any) -> List[str]:
    """非支配集的名字（分越高越好、成本越低越好）。"""
    m = _measured(points)
    out: List[str] = []
    for p in m:
        dominated = False
        for q in m:
            if q is p:
                continue
            if (q["score"] >= p["score"] and q["cost"] <= p["cost"]
                    and (q["score"] > p["score"] or q["cost"] < p["cost"])):
                dominated = True
                break
        if not dominated:
            out.append(p["name"])
    return out


def _norm(v: float, lo: float, hi: float) -> float:
    if hi <= lo:
        return 0.0                    # 无差异 ⇒ 该维不参与
    return (v - lo) / (hi - lo)


def select(points: Any, mode: str = DEFAULT_MODE) -> Optional[Dict[str, Any]]:
    """按档位选一个点。没有可测点 ⇒ None（调用方保持原行为）。"""
    m = _measured(points)
    if not m:
        return None
    use = mode if mode in MODES else DEFAULT_MODE
    a, b = MODES[use]
    smin = min(p["score"] for p in m)
    smax = max(p["score"] for p in m)
    cmin = min(p["cost"] for p in m)
    cmax = max(p["cost"] for p in m)
    best: Optional[Dict[str, Any]] = None
    best_key = None
    for p in m:
        d_perf = 1.0 - _norm(p["score"], smin, smax)   # 分越高越小
        d_cost = _norm(p["cost"], cmin, cmax)
        j = a * d_perf * d_perf + b * d_cost * d_cost
        # 平手：先看分高，再看便宜，最后按名字（保证确定性）
        key = (j, -p["score"], p["cost"], p["name"])
        if best_key is None or key < best_key:
            best_key, best = key, p
    return {"name": best["name"], "mode": use, "n_points": len(m),
            "score": best["score"], "cost": best["cost"], "j": best_key[0]}
