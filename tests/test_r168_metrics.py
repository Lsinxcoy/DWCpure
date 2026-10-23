# -*- coding: utf-8 -*-
"""R168 · 四量采集器 — measure.py 的喂数方（②③④ 从 not_instrumented 到真采）。

验收:
  □ ② activation = 候选过门率（n_gated/n_proposals — 母巢 98.8% 同构量）
  □ ③ faithful = 落地执行率（n_landed/n_gated）
  □ ④ downstream = ℒ_t ΔS 组间差（adopted vs 非）
  □ 缺源显式 na（缺席≠0 — 不拿 0 顶替）
  □ 分母 0 ⇒ None（不造 0% — measure raise 同义前置）
  □ RoundLog ⇒ metrics_from_round（Loop 每轮出口采集位）
  □ 类型错配 ⇒ MeasureError（位置即口径 — measure 按位校验）
"""
from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.organs.metrics import (  # noqa: E402
    METRICS_MECHANICS, collect_activation, collect_downstream,
    collect_faithful, four_metrics, metrics_from_round, summarize)
from dwc.organs.credit import CreditEntry  # noqa: E402
from dwc.organs.measure import (  # noqa: E402
    NOT_INSTRUMENTED, Activation, FaithfulUse, MeasureError)


def _entry(t, adopted, ds, edit=None):
    # ★ 默认参数在**定义时**求值 — 首版写 % t 直接 NameError（我自己的错）
    if edit is None:
        edit = "e%d" % t
    return CreditEntry(t=t, edit=edit, layer="assets", hunk="h",
                       dimension="D1", delta_s=ds, delta_c=0.01,
                       adopted=adopted)


class _RL:
    def __init__(self, n_candidates=4, landed=True, score=0.7):
        self.n_candidates = n_candidates
        self.landed = landed
        self.score = score
        self.chain_verdict = "all_applicable_passed"


def test_activation_from_gate_all():
    """★ ② = n_gated/n_proposals（生成面→过门面的检索命中同构量）。"""
    a = collect_activation(4, 3)
    assert isinstance(a, Activation)
    assert a.n_retrieved == 3 and a.as_dict()["activation"] == 0.75
    # 缺源
    assert collect_activation(None, 3) is None
    assert collect_activation(4, None) is None
    # 分母 0 ⇒ None（不是 0%）
    assert collect_activation(0, 0) is None


def test_faithful_from_landing():
    """★ ③ = n_landed/n_gated（过门⇒照做 — R163 adopted 数）。"""
    f = collect_faithful(5, 2)
    assert isinstance(f, FaithfulUse)
    assert f.n_faithful == 2 and f.as_dict()["faithful"] == 0.4
    assert collect_faithful(0, 0) is None           # 分母 0
    assert collect_faithful(None, 1) is None


def test_downstream_from_ledger_delta_s():
    """★★ ④ = ℒ_t ΔS 组间差（adopted 组均值 − 未 adopted 组均值）。"""
    entries = [_entry(1, 1, 0.10), _entry(2, 1, 0.20),
               _entry(3, 0, 0.02), _entry(4, 0, 0.04)]
    d = collect_downstream(entries)
    assert d.as_dict()["instrumented"] is True
    assert abs(d.as_dict()["benefit"] - (0.15 - 0.03)) < 1e-9   # used−unused
    # 单侧空 ⇒ None（不拿 0 顶替 — 『照做没用』≠『没测』）
    assert collect_downstream([_entry(1, 1, 0.1)]) is None
    assert collect_downstream([]) is None


def test_four_metrics_absent_not_zero():
    """★★★ 全缺源 ⇒ 四量全 not_instrumented（缺席≠0 — 母巢病根纪律）。"""
    fm = four_metrics()
    assert fm["instrumented_count"] == 0
    for k, v in fm["quantities"].items():
        assert v["instrumented"] is False
        assert v["status"] == NOT_INSTRUMENTED
    s = summarize(fm)
    assert s.count("=na") == 4


def test_four_metrics_full_pipeline():
    """★★ 四源齐 ⇒ 4/4 埋点（数字说话 — 与母巢 1/4 对照）。"""
    fm = four_metrics(n_proposals=4, n_gated=3, n_landed=2,
                      ledger_entries=[_entry(1, 1, 0.1), _entry(2, 1, 0.2),
                                      _entry(3, 0, 0.05)])
    # ★ 3/4: 采集器职责就是②③④（update ① 由 judge 面单喂 — UpdateQuality
    #   构造要 judge 口径; 不越界造采集器内的"自评"）
    assert fm["instrumented_count"] == 3
    q = fm["quantities"]
    assert q["activation"]["activation"] == 0.75
    assert q["faithful_use"]["faithful"] == 2 / 3
    assert q["downstream_benefit"]["instrumented"] is True
    assert q["update_quality"]["status"] == NOT_INSTRUMENTED   # ①缺 ⇒ na


def test_metrics_from_round_log():
    """★★ RoundLog ⇒ 四量（Loop 每轮出口的采集位 — R164 台账直喂）。"""
    fm = metrics_from_round(_RL(n_candidates=4, landed=True),
                            ledger_entries=[_entry(1, 1, 0.1),
                                            _entry(2, 0, 0.0)])
    assert fm["quantities"]["activation"]["n_items"] == 4    # proposals=N
    assert fm["quantities"]["faithful_use"]["n_retrieved_used"] == 4
    assert fm["quantities"]["faithful_use"]["n_faithful"] == 1
    # 无台账 ⇒ ①②③ na（分母 0/无 ledger）— 不造数
    fm2 = metrics_from_round(_RL(n_candidates=0, landed=False))
    assert fm2["instrumented_count"] == 0


def test_type_mismatch_rejected_by_measure():
    """★ 位置即口径（喂错位 ⇒ MeasureError — measure 按位校验在）。"""
    from dwc.organs.measure import measure
    with pytest.raises(MeasureError):
        measure(update=Activation(1, 1))            # Activation 喂 update 位


def test_mechanics_documented():
    """三源/缺席≠0/非第二实现在档。"""
    assert "98.8%" in METRICS_MECHANICS["activation_source"]
    assert "measure.py" in METRICS_MECHANICS["collector_not_second_impl"]
    assert "没测" in METRICS_MECHANICS["absent_not_zero"]
