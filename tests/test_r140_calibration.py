# -*- coding: utf-8 -*-
"""R140 · ECE 校准度量 — 深水唯一真欠账的落地（B 方案: 建在 iwm 外侧）。

验收:
  □ Point 契约: conf ∈[0,1] 有限数值; outcome bool（int 混入拒绝）
  □ ECE 公式手算对账（单桶/多桶/混合 conf）
  □ 缺席≠0: 空桶/低样本桶跳过（不计项）, 空序列 raise（不是 0.0）
  □ 单调性自检: ECE ∈[0,1]（结构断言在实现内）
  □ overconfidence_penalty: ECE>threshold ⇒ penalized+trust_scale=1−ECE
  □ iwm 合作性: self_trust() 的 trust 可直接喂入（端到端投影）
  □ from_trust_history: (trust, improved) ⇒ Point 序列
"""
from __future__ import annotations

import math
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.foundation.calibration import (  # noqa: E402
    CALIBRATION_BINS, CalibrationError, CalibrationPoint,
    expected_calibration_error, from_trust_history,
    overconfidence_penalty)


def test_point_contract():
    """★ conf 值域 + outcome bool 强制（X1 同族纪律）。"""
    p = CalibrationPoint(conf=0.5, outcome=True)
    assert p.conf == 0.5 and p.outcome is True
    for bad in (1.5, -0.1, float("nan"), float("inf"), True):
        with pytest.raises(CalibrationError):
            CalibrationPoint(conf=bad, outcome=True)
    # outcome 不许 int 混入（0/1 ≠ False/True 的显式两义）
    with pytest.raises(CalibrationError):
        CalibrationPoint(conf=0.5, outcome=1)


def test_ece_formula_single_bin():
    """★ 公式对账①: 单桶 conf=0.7×3 全成功 ⇒ acc=1 ⇒ ECE=|1−0.7|=0.3。"""
    pts = [CalibrationPoint(conf=0.7, outcome=True) for _ in range(3)]
    r = expected_calibration_error(pts, n_bins=1)
    assert r["ece"] == pytest.approx(0.3)
    assert r["n_total"] == 3 and r["n_bins_used"] == 1


def test_ece_formula_multi_bin():
    """★ 公式对账②: 混 conf=0.2(全败) + 0.8(全成功) ⇒ 两桶等权。"""
    pts = ([CalibrationPoint(conf=0.2, outcome=False)] * 2 +
           [CalibrationPoint(conf=0.8, outcome=True)] * 2)
    r = expected_calibration_error(pts, n_bins=10)
    # 桶1: conf=0.2, acc=0 ⇒ gap=0.2; 桶8: conf=0.8, acc=1 ⇒ gap=0.2
    assert r["ece"] == pytest.approx(0.2)
    assert r["n_bins_used"] == 2


def test_ece_perfect_and_worst():
    """边界: conf=0.5 五成败 ⇒ acc=0.5 ⇒ ECE=0（完美校准）。"""
    pts = ([CalibrationPoint(conf=0.5, outcome=True)] * 5 +
           [CalibrationPoint(conf=0.5, outcome=False)] * 5)
    r = expected_calibration_error(pts, n_bins=10)
    assert r["ece"] == pytest.approx(0.0)
    # 最差: conf=1.0 全败 ⇒ acc=0 ⇒ ECE=1.0
    r2 = expected_calibration_error(
        [CalibrationPoint(conf=1.0, outcome=False)] * 4, n_bins=10)
    assert r2["ece"] == pytest.approx(1.0)


def test_absent_not_zero():
    """★ 缺席≠0: 空序列 raise（没数据≠校准好）; 空桶跳过不计项。"""
    with pytest.raises(CalibrationError):
        expected_calibration_error([], n_bins=10)
    # min_bin_count=100 ⇒ 全桶跳过 ⇒ 0 桶参与但 n_total 仍真（ECE=0 但可判）
    pts = [CalibrationPoint(conf=0.5, outcome=True)]
    r = expected_calibration_error(pts, n_bins=10, min_bin_count=100)
    assert r["n_bins_used"] == 0 and r["n_total"] == 1


def test_bins_validation():
    """分桶参数值域（1..MAX_BINS; bool 不算 int）。"""
    pts = [CalibrationPoint(conf=0.5, outcome=True)]
    for bad_n in (0, -1, True, 10 ** 6):
        with pytest.raises(CalibrationError):
            expected_calibration_error(pts, n_bins=bad_n)
    with pytest.raises(CalibrationError):
        expected_calibration_error(pts, n_bins=10, min_bin_count=0)


def test_from_trust_history():
    """★ iwm 投影入口: (trust, improved) ⇒ Point（bool 强制）。"""
    pts = from_trust_history([(0.8, True), (0.6, False), (1.0, True)])
    assert [p.conf for p in pts] == [0.8, 0.6, 1.0]
    assert [p.outcome for p in pts] == [True, False, True]
    # improved 非 bool ⇒ 显式拒绝（iwm 语义是 bool）
    with pytest.raises(CalibrationError):
        from_trust_history([(0.5, 1)])


def test_overconfidence_penalty():
    """★ 过置信惩罚: ECE>阈值 ⇒ penalized + trust_scale=1−ECE。"""
    # 构造 ECE=0.4: conf=0.3 全成功 (gap=0.7)? 用对账过的简单例:
    pts = [CalibrationPoint(conf=0.2, outcome=False)] * 2  # acc=0,gap=0.2
    r = expected_calibration_error(pts, n_bins=10)
    assert r["ece"] == pytest.approx(0.2)
    pen = overconfidence_penalty(r, threshold=0.1)
    assert pen["penalized"] is True
    assert pen["trust_scale"] == pytest.approx(0.8)
    assert "过置信" in pen["note"]
    # 校准良好: conf=1.0 全成功 ⇒ acc=1 ⇒ ECE=0 ≤ 阈值 ⇒ 不动 trust
    r0 = expected_calibration_error(
        [CalibrationPoint(conf=1.0, outcome=True)] * 2, n_bins=10)
    assert r0["ece"] == pytest.approx(0.0)
    pen0 = overconfidence_penalty(r0, threshold=0.1)
    assert pen0["penalized"] is False and pen0["trust_scale"] == 1.0
    with pytest.raises(CalibrationError):
        overconfidence_penalty(r, threshold=1.5)


def test_iwm_end_to_end_projection():
    """★ 端到端: iwm.record_round/self_trust 真值 ⇒ ECE 可算。"""
    from dwc.organs.iwm import IwmOrgan
    g = IwmOrgan(baseline=None)   # min_samples=5/degrade_below=0.35 (config/drift.yaml)
    # 基线臂 3 轮 + iwm 臂 5 轮（2 改进 / 3 未 ⇒ trust=2/5=0.4）
    for _ in range(3):
        g.record_round(adopted=False, improved=True)   # baseline 臂
    g.record_round(adopted=True, improved=True)
    g.record_round(adopted=True, improved=True)
    for _ in range(3):
        g.record_round(adopted=True, improved=False)   # iwm 臂未改进
    st = g.self_trust()
    assert st["n_iwm"] == 5, st                       # ★ min_samples=5 达限
    assert st["n_baseline"] == 3
    trust = st["trust"]                               # 2/5 = 0.4
    assert trust == pytest.approx(2 / 5)
    assert st["degrade"] is False                     # 0.4 ≥ 0.35 不降级
    # 投影: trust 序列 vs improved 序列（iwm 臂 5 轮: 2T/3F）
    hist = [(trust, True), (trust, True)] + [(trust, False)] * 3
    r = expected_calibration_error(from_trust_history(hist), n_bins=10)
    # conf=acc=0.4 ⇒ ECE=0（trust 是自洽的预测器）
    assert r["ece"] == pytest.approx(0.0)
    # 换成"高 trust 低达成" ⇒ 非零 ECE（过置信被抓到）
    hist2 = [(0.9, False), (0.9, False), (0.9, False)]
    r2 = expected_calibration_error(from_trust_history(hist2), n_bins=10)
    assert r2["ece"] == pytest.approx(0.9)


def test_iwm_self_trust_carries_ece_field():
    """★ 轻接线落档: self_trust() 带 ece 字段（available/近似标注）。"""
    from dwc.organs.iwm import IwmOrgan
    g = IwmOrgan(baseline=None)
    for _ in range(3):
        g.record_round(adopted=False, improved=True)
    for _ in range(5):
        g.record_round(adopted=True, improved=False)   # iwm 5 轮全败 ⇒ trust=0
    st = g.self_trust()
    assert "ece" in st                                  # ★ R140 增量字段
    assert st["ece"]["available"] is True
    # 末态回填 ⇒ 全 conf 同 ⇒ ECE=0（结构必然, approx 标注诚实）
    assert st["ece"]["ece"] == pytest.approx(0.0)
    assert "回填" in st["ece"]["approx"]
