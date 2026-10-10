# -*- coding: utf-8 -*-
"""R144 · 四量度量 — 写了≠用了（2609.11873 §3.3; 缺埋点显式 not_instrumented）。

验收:
  □ update_quality: 三数口径 (not_evaluated 不进分母) + 空判 raise
  □ activation/faithful_use: 契约（越界 raise, n=0 raise — 不是 0%）
  □ downstream: 双侧 None ⇒ not_instrumented（不拿 0 顶替"照做没用"）
  □ measure 汇总: instrumented_count + health（1/4 = 母巢那个病）
  □ 缺量 != 0: 全缺 ⇒ quantities 全显式 not_instrumented
"""
from __future__ import annotations

import os
import sys

import pytest

ROOT = r"E:/Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.organs.measure import (  # noqa: E402
    MEASURE, NOT_INSTRUMENTED, QUANTITIES, Activation, DownstreamBenefit,
    FaithfulUse, MeasureError, UpdateQuality, measure)


def test_update_quality_excludes_not_evaluated():
    """★ ① 三数口径: 未评价不进分母（R14 同族）。"""
    q = UpdateQuality(n_pass=3, n_fail=1, not_evaluated=7)
    d = q.as_dict()
    assert d["quality"] == pytest.approx(0.75)     # 3/4 不是 3/11
    assert d["not_evaluated"] == 7                  # 旁列可审计
    with pytest.raises(MeasureError):
        UpdateQuality(n_pass=0, n_fail=0, not_evaluated=5)  # 空判≠0 分
    with pytest.raises(MeasureError):
        UpdateQuality(n_pass=-1, n_fail=1)


def test_activation_contract():
    """② 契约: 空库 raise / 越界 raise（0% 命中≠空库）。"""
    a = Activation(n_items=10, n_retrieved=2)
    assert a.as_dict()["activation"] == pytest.approx(0.2)
    with pytest.raises(MeasureError):
        Activation(n_items=0, n_retrieved=0)        # 空库不是 0%
    with pytest.raises(MeasureError):
        Activation(n_items=5, n_retrieved=9)        # 检索>总数越界
    with pytest.raises(MeasureError):
        Activation(n_items=True, n_retrieved=1)     # bool 不算 int


def test_faithful_use_contract():
    """③ 契约: 分母 0 raise / 分子越界 raise。"""
    f = FaithfulUse(n_retrieved_used=4, n_faithful=3)
    assert f.as_dict()["faithful"] == pytest.approx(0.75)
    with pytest.raises(MeasureError):
        FaithfulUse(n_retrieved_used=0, n_faithful=0)
    with pytest.raises(MeasureError):
        FaithfulUse(n_retrieved_used=4, n_faithful=5)


def test_downstream_partial_not_instrumented():
    """★★ ④ 缺单侧 ⇒ not_instrumented（缺席≠0: 不拿 0 顶替照做没用）。"""
    d_none = DownstreamBenefit()
    r = d_none.as_dict()
    assert r["instrumented"] is False
    assert r["status"] == NOT_INSTRUMENTED
    # 双侧齐则可算差
    d = DownstreamBenefit(quality_used=0.8, quality_unused=0.6)
    assert d.as_dict()["benefit"] == pytest.approx(0.2)
    # 值域
    with pytest.raises(MeasureError):
        DownstreamBenefit(quality_used=1.5, quality_unused=0.1)


def test_measure_summary_health():
    """★ 汇总: instrumented_count + health 话术（1/4=母巢病）。"""
    r = measure(update=UpdateQuality(n_pass=2, n_fail=1))
    assert r["instrumented_count"] == 1
    assert "母巢那个病" in r["health"]
    # 全缺 ⇒ 全 not_instrumented + count=0
    r0 = measure()
    assert r0["instrumented_count"] == 0
    for name in QUANTITIES:
        assert r0["quantities"][name]["status"] == NOT_INSTRUMENTED
    # 四个全喂 ⇒ health=4/4
    r4 = measure(update=UpdateQuality(n_pass=1, n_fail=1),
                 activation=Activation(n_items=4, n_retrieved=2),
                 faithful=FaithfulUse(2, 1),
                 downstream=DownstreamBenefit(0.5, 0.4))
    assert r4["instrumented_count"] == 4
    assert "多维度在测" in r4["health"]


def test_type_confusion_rejected():
    """口径混用显式拒绝（把 Activation 喂给 update 位 ⇒ raise）。"""
    with pytest.raises(MeasureError):
        measure(update=Activation(n_items=1, n_retrieved=1))


def test_quantities_enum_matches_paper():
    """★ 四量 id 与 2609.11873 §3.3 原文顺序一致。"""
    assert QUANTITIES == ("update_quality", "activation", "faithful_use",
                          "downstream_benefit")
    assert MEASURE["disease"].startswith("只测①")
