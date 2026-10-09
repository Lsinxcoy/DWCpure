# -*- coding: utf-8 -*-
"""R129 · judge 逐任务分度量探针 — 整改路径②实证（max 饱和的解除）。

验收:
  □ golden 替身: A/B 双 1.0（expected 全灌 = 结构必然, 非失败）
  □ LLM 臂: A=max 聚合恒等 1.0, B=judge 均值 <1.0（真区分）
  □ 探针如实分两轴: 策略轴(spec 无因果) / 执行体轴(才有区分)
  □ B_separates 与 A_saturated 可在同一文档里对照（可审计）
  □ per_task_score 逐任务明细落盘（002=0.5 的取样证据）
"""
from __future__ import annotations

import json
import os
import sys

import pytest

ROOT = r"E:/Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from probe_judge_score_metric import _anchors, judge_metric, run  # noqa: E402


def test_golden_gives_identical_metrics_by_construction():
    """★ golden 替身: expected 全灌 ⇒ A/B 必双 1.0（结构必然预期内）。"""
    from dwc.core import DWC
    from dwc.organs.judge import TaskScoreStore
    from ga_duel import PolicySpec, make_executor
    anch = _anchors()
    ids = list((anch.get("_split") or {}).get("search", []))
    d = DWC(3, 50, executor=None, db_path=":memory:")
    d.judge.store = TaskScoreStore(dw_version="probe_r129_test")
    d.executor = make_executor(anch, mode="golden", memory=d.memory)
    for tid in ids:
        d.step({"task_id": tid, "kind": "dev"})
    a = run(PolicySpec(), d, ids)
    b = judge_metric(d, PolicySpec(), ids)
    assert a == 1.0 and b == 1.0


def test_probe_doc_records_separation_when_llm_run():
    """LLM 跑过 ⇒ 文档载明 A 饱和/B 有区分（真区分的可审计证据）。"""
    p = os.path.join(ROOT, "docs", "judge_score_metric.json")
    assert os.path.exists(p), "先跑 scripts/probe_judge_score_metric.py"
    d = json.load(open(p, encoding="utf-8"))
    if d["executor"] != "llm":
        pytest.skip("当前留档是 golden 跑（结构必然双 1.0 也合法）")
    m = d["metrics"]
    assert m["A_dream_v_pi0"] == 1.0          # max 饱和
    assert m["B_judge_mean"] < 1.0            # 均值解除饱和
    assert d["verdict"]["A_saturated"] is True
    assert d["verdict"]["B_separates"] is True
    assert d["verdict"]["reading"].startswith("B 有区分")
    # 逐任务明细里有非 1.0 的任务（均值 <1 的算术来源）
    assert any(v < 1.0 for v in d["per_task_score"].values())


def test_metric_separates_axes_honestly():
    """探针如实: B 均值对策略轴无因果 — 真区分在执行体轴。"""
    p = os.path.join(ROOT, "docs", "judge_score_metric.json")
    assert os.path.exists(p)
    d = json.load(open(p, encoding="utf-8"))
    assert "策略轴" in json.dumps(d, ensure_ascii=False)
    assert "执行体" in json.dumps(d, ensure_ascii=False)
    # 留档 caveats 须如实标"策略/执行体/任务集"边界（中文键）
    _cav = json.dumps(d["caveats"], ensure_ascii=False)
    assert "策略" in _cav and "执行体" in _cav


def test_golden_doc_marks_construction_determinism():
    """golden 留档: A/B 双 1.0 且 caveat 明说'结构必然预期内'。"""
    p = os.path.join(ROOT, "docs", "judge_score_metric.json")
    d = json.load(open(p, encoding="utf-8"))
    if d["executor"] == "golden":
        assert d["metrics"]["A_dream_v_pi0"] == 1.0
        assert d["metrics"]["B_judge_mean"] == 1.0
        assert any("结构必然" in c for c in d["caveats"])
