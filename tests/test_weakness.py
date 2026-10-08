# -*- coding: utf-8 -*-
"""weakness（organs/weakness.py）的契约 + 数值测试。

★★★ 为什么这份测试重要
  δ_θ 是器官⑥ 的第一件（EVOLUTION_CORE_V2 点名 weakness.py），且它的
  **语义被裁决改窄过**（p_𝒯→组内基线）—— 测试锁的不是"论文原式"，
  是**裁决后的路线丙公式 + X1/X2/X3 判据**。
  ⇒⇒ 数值例直接锚 ARCHITECTURE 的实测 −log(12/55)，防实现与设计漂移。

★ 判据族: X1 semantics 必填无默认 · X2 n_obs=0⇒NaN · X3 路线甲不假装
  · [·]₊ 截断 · Δ_θ 轨迹和 · 排序偏置（无阈值接口）
"""
from __future__ import annotations

import math
import os
import sys

import pytest

ROOT = r"E:/Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.foundation.dial_config import DialError  # noqa: E402
from dwc.organs.weakness import (  # noqa: E402
    Difficulty, DifficultyEstimator, WeaknessError,
)


def _hist():
    """组 g: z_a 出现 11 次、z_b 43 次 ⇒ n=54（对齐 ARCHITECTURE 实测例）。"""
    return {"g": ["z_a"] * 11 + ["z_b"] * 43}


# ══════════════════════════════════════════════════════════
# 路线丙公式（Laplace k=1 · [·]₊ · NaN）
# ══════════════════════════════════════════════════════════

def test_delta_group_matches_architecture_numeric_example():
    """★ 数值锚: r=(11+1)/(54+1)=12/55 ⇒ −log(12/55)=1.5224（设计实测同构）。"""
    est = DifficultyEstimator(_hist())
    d = est.delta_group("z_a", "g")
    assert d.n_obs == 54 and d.semantics == "group_baseline"
    assert d.delta == pytest.approx(-math.log(12.0 / 55.0), abs=1e-12)
    # 更稀有的 z ⇒ δ 更大（排序语义: 罕见优先探索）
    d_b = est.delta_group("z_b", "g")
    assert d.delta > d_b.delta


def test_delta_zero_when_maximally_common():
    """Laplace 下 n_z=n ⇒ r=1 ⇒ −log 1 = 0（[·]₊ 截断口径的边界值）。"""
    est = DifficultyEstimator({"g": ["z"] * 5})
    d = est.delta_group("z", "g")
    assert d.delta == 0.0 and d.n_obs == 5


def test_delta_nan_when_group_unobserved():
    """★★ X2: 组内无观测（n=0）⇒ delta=NaN, 不许是 0（『没观测过』≠『频率0』）。"""
    est = DifficultyEstimator({})
    d = est.delta_group("z_x", "missing_group")
    assert math.isnan(d.delta), d.delta
    assert d.n_obs == 0


def test_delta_trajectory_sums_and_propagates_nan():
    """Δ_θ(ξ) = Σ δ; 含**未观测组**的 z ⇒ 整条 NaN（不吞不跳）。

    ★ 区分两种 0（X2 原文语义）:
      · 组无观测（n=0）⇒ NaN —— "没观测过"
      · 组有观测但某 z 从没出现（n_z=0, n>0）⇒ r=1/(n+1) 有限 δ ——
        "观测过、频率极低"= 合法的高稀有度, 不是 NaN
    """
    est = DifficultyEstimator(_hist())
    seq = ["z_a", "z_b"]
    expect = (-math.log(12.0 / 55.0)) + (-math.log(44.0 / 55.0))
    assert est.delta_trajectory(seq, "g") == pytest.approx(expect, abs=1e-12)
    # 组有数据、z 没出现过 ⇒ 高 δ 但不是 NaN
    d_nope = est.delta_group("nope", "g")
    assert not math.isnan(d_nope.delta)
    assert d_nope.delta == pytest.approx(-math.log(1.0 / 55.0), abs=1e-12)
    # 组本身没观测过 ⇒ NaN 传播
    assert math.isnan(est.delta_trajectory(["z_a"], "missing_group"))


def test_weak_ranking_is_order_only_no_threshold():
    """★ 排序偏置口: 只给顺序（罕见在前）—— 模块无阈值判定接口（L1105）。"""
    est = DifficultyEstimator(_hist())
    rank = est.weak_ranking("g")
    assert [r["z_id"] for r in rank] == ["z_a", "z_b"]   # 罕见(δ大)在前
    # 接口面没有 threshold 类参数（防"绝对阈值混用"）
    import inspect
    src = inspect.getsource(type(est))
    assert "threshold" not in src


# ══════════════════════════════════════════════════════════
# X1 / X3（语义纪律 + 路线甲不假装）
# ══════════════════════════════════════════════════════════

def test_difficulty_requires_valid_semantics_and_nobs():
    """X1 双保险: dataclass 层对非法 semantics/n_obs 直接 raise。"""
    with pytest.raises(WeaknessError, match="X1"):
        Difficulty(delta=1.0, semantics="residual", z_id="z",
                   group_id="g", n_obs=3, estimated_at="t")
    with pytest.raises(WeaknessError, match="n_obs"):
        Difficulty(delta=1.0, semantics="group_baseline", z_id="z",
                   group_id="g", n_obs=-1, estimated_at="t")


def test_world_knowledge_semantics_refused(tmp_path):
    """★★ X3 诚实面: semantics=world_knowledge ⇒ delta_group raise（不假装）。"""
    bad = tmp_path / "d.yaml"
    bad.write_text(
        "version: 1\n"
        "difficulty:\n"
        "  semantics: world_knowledge\n"
        "  deep_research:\n    enabled: true\n"
        "    require_outside_write_mask: true\n"
        "  n_obs:\n    zero_means: NaN\n"
        "  report_field: delta_semantics\n",
        encoding="utf-8")
    est = DifficultyEstimator({}, config_path=str(bad))
    assert est.semantics == "world_knowledge"
    with pytest.raises(WeaknessError, match="不假装能算"):
        est.delta_group("z", "g")


def test_bad_semantics_rejected_by_loader(tmp_path):
    """X1 加载器面: semantics=residual（字段名误用）⇒ DialError。"""
    bad = tmp_path / "d2.yaml"
    bad.write_text(
        "version: 1\n"
        "difficulty:\n"
        "  semantics: residual\n"
        "  deep_research:\n    enabled: false\n"
        "    require_outside_write_mask: true\n"
        "  n_obs:\n    zero_means: NaN\n"
        "  report_field: delta_semantics\n",
        encoding="utf-8")
    with pytest.raises(DialError, match="X1"):
        DifficultyEstimator({}, config_path=str(bad))


def test_zero_means_must_be_nan_string(tmp_path):
    """X2 加载器面: zero_means=0（数字）⇒ DialError（类型先查, 防短路放行）。"""
    bad = tmp_path / "d3.yaml"
    bad.write_text(
        "version: 1\n"
        "difficulty:\n"
        "  semantics: group_baseline\n"
        "  deep_research:\n    enabled: false\n"
        "    require_outside_write_mask: true\n"
        "  n_obs:\n    zero_means: 0\n"
        "  report_field: delta_semantics\n",
        encoding="utf-8")
    with pytest.raises(DialError, match="X2"):
        DifficultyEstimator({}, config_path=str(bad))


def test_report_field_exposed_for_x4():
    """X4 报告字段来源: report_field 从 config 透出（delta_semantics）。"""
    est = DifficultyEstimator(_hist())
    assert est.report_field == "delta_semantics"
    assert est.semantics == "group_baseline"
