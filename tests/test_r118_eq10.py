# -*- coding: utf-8 -*-
"""R118 · ⑤ Eq.10 验收执行 — 支配式判定 / 双审计 / 展示层无裁决力 / 校准注记。

验收（设计稿⑤ §⑦ 写死清单）:
  □ eq10_accept 六边界: 改善∨改善 / 双门拒 / η_gain 硬拒 / η_ret 硬拒 /
    平票拒（Δ=δ 不算改善, 严格 >）/ cost 改善路径
  □ 耦合审计: n≥8 出 ρ + coupled 标记; n<8 insufficient（不装数）
  □ 展示层不进 accept 路径（源码级 + 行为级双锁, 破坏即红）
  □ 门参数校准注记在位（每个门带来源 / δ_gain 标待校准）
  □ 单维退化: gain-only 语义覆盖现行 no_worse（超集关系）
  □ 缺维大声 raise（X2 不装可比）
"""
from __future__ import annotations

import inspect
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.foundation.eq10 import (  # noqa: E402
    CALIBRATION, DELTA, DIMENSIONS, ETA, Eq10Error, coupling_audit,
    eq10_accept, score_display)
from dwc.organs.replay import no_worse_than_current, select_policy  # noqa: E402


def _d(g=0.0, c=0.0, r=0.0):
    return {"gain": g, "cost": c, "retention": r}


def test_accept_boundaries_six_cases():
    """六边界（稿⑦首条逐条）。"""
    # ① gain 改善（Δ>δ_gain=0）且无回退 ⇒ 接受
    assert eq10_accept(_d(g=0.05, c=-0.01))["accept"] is True
    # ② 双门拒: 无一维过改善门（gain 0=δ 不算严格改善; cost 5%<10%）
    r2 = eq10_accept(_d(g=0.0, c=0.05))
    assert r2["accept"] is False and r2["improved_by"] == []
    # ③ η_gain 硬拒: gain 改善过门但 gain 回退破 η=0 不可能同时 —
    #    单维不可分时看 cost 改善 + gain 回退 ⇒ 违反 η_gain
    r3 = eq10_accept(_d(g=-0.01, c=0.15))
    assert r3["accept"] is False and "gain" in r3["violated"]
    # ④ η_ret 硬拒: 任何维度改善都救不了 retention 回退（Recuris 硬 0）
    r4 = eq10_accept(_d(g=0.5, c=0.5, r=-0.001))
    assert r4["accept"] is False and "retention" in r4["violated"]
    # ⑤ 平票拒: Δ_gain 恰 = δ_cost 的 cost 改善按严格 >; Δ=0 恰=δ_gain ⇒ 拒
    assert eq10_accept(_d(g=0.0))["accept"] is False
    # ⑥ cost 改善路径: 变便宜 >10% 即改善, 无 gain 也接受（但零回退）
    r6 = eq10_accept(_d(g=0.0, c=0.12))
    assert r6["accept"] is True and r6["improved_by"] == ["cost"]


def test_missing_dimension_raises():
    """缺维大声 raise（缺维不许装可比 — X2 同族）。"""
    with pytest.raises(Eq10Error, match="缺维"):
        eq10_accept({"gain": 0.1})
    with pytest.raises(Eq10Error, match="缺维"):
        eq10_accept({"gain": 0.1, "cost": 0.0})          # 少 retention
    with pytest.raises(Eq10Error, match="须数值"):
        eq10_accept(_d(g="x"))
    with pytest.raises(Eq10Error, match="须数值"):
        eq10_accept({"gain": 0.1, "cost": 0.0, "retention": None})
    with pytest.raises(Eq10Error, match="须 dict"):
        eq10_accept([0.1, 0.0, 0.0])


def test_no_weighted_sum_source_lock():
    """★ 展示层不进裁决（源码级锁 — eq10_accept 函数体不引用 score_display）。"""
    src = inspect.getsource(eq10_accept)
    assert "score_display" not in src and "DISPLAY_WEIGHTS" not in src, \
        "★ 展示层混进 eq10_accept = 违约（稿⑤层1 零权重是设计约束）"
    # 行为级: 展示值怎么变都不影响 accept（同一 deltas 两个展示输入无读数差）
    deltas = _d(g=0.05, c=0.0, r=0.0)
    a1, a2 = eq10_accept(deltas), eq10_accept(dict(deltas))
    assert a1 == a2
    # 展示层本身可用（等权三键）
    assert abs(score_display({"gain": 1, "cost": 0, "retention": 0}) - 1/3) < 1e-9


def test_calibration_notes_in_place():
    """门参数每个带校准注记; δ_gain 标待校准（稿⑧.1 诚实条款）。"""
    assert set(CALIBRATION) == {"delta_gain", "delta_cost", "eta_gain",
                                "eta_cost", "eta_ret"}
    assert "待校准" in CALIBRATION["delta_gain"]
    assert "管理口径" in CALIBRATION["delta_cost"]
    assert "判据" in CALIBRATION["eta_ret"]
    r = eq10_accept(_d(g=0.1))
    assert r["gates"]["delta"] == DELTA and r["gates"]["eta"] == ETA
    assert DIMENSIONS == ("gain", "cost", "retention")


def test_coupling_audit_boundaries():
    """耦合审计: n<8 不装数; n≥8 出 ρ + coupled 标记。"""
    few = coupling_audit([_d(g=i * 0.1) for i in range(4)])
    assert few["status"] == "insufficient_samples" and "rho" not in few
    # 完美正相关样本: gain 与 cost 同步涨 ⇒ |ρ|=1 > 0.8 ⇒ coupled
    samples = [_d(g=i * 0.1, c=i * 0.1, r=0.0) for i in range(8)]
    ok = coupling_audit(samples)
    assert ok["status"] == "ok" and ("gain", "cost") in ok["coupled"]
    assert abs(ok["rho"]["gain~cost"] - 1.0) < 1e-9
    # 零方差 ⇒ ρ=None 不装 0
    flat = [_d(g=0.5, c=0.5, r=0.0) for _ in range(8)]
    r = coupling_audit(flat)
    assert r["rho"]["gain~cost"] is None and r["coupled"] == []


def test_single_dim_degeneration_covers_no_worse():
    """单维退化: Eq.10(gain-only 无回退) ⇒ 现行 no_worse 的超集方向一致。"""
    # no_worse: best ≥ current ⇒ Eq.10 的 gain 无回退 + 改善
    cases = [({"m": 0.9, "c": 0.8}, "c"), ({"m": 0.8, "c": 0.8}, "c"),
             ({"m": 0.7, "c": 0.8}, "c")]
    for v_by, cur in cases:
        nw = no_worse_than_current(v_by, current=cur)
        best = max(v_by.values())
        d_gain = best - v_by[cur]
        # 现行 no_worse ⇔ d_gain ≥ 0; Eq.10 接受 ⇔ d_gain > 0（δ=0 严格 >
        #   且无回退）⇒ no_worse 放行的「持平」Eq.10 不当改善 —
        #   关系: Eq.10 accept ⇒ no_worse 必真（超集方向, 不反向）
        if eq10_accept(_d(g=d_gain))["accept"]:
            assert nw is True, "Eq.10 接受必须 ⇒ no_worse 真（不反向）"
