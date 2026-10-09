# -*- coding: utf-8 -*-
"""R130 · M2 对打 judge_mean 口径 — 执行体轴真对打（A=golden/B=llm）。

验收:
  □ --metric judge_mean 走执行体轴: A 臂 golden 起底 / B 臂 llm 起底
  □ --metric 默认 dream_v = 零破坏（协议回归不变）
  □ metric=judge_mean 的 eval_v 取 judge 逐任务分均值（R129 口径）
  □ caveats 在 judge_mean 下显式标"度量假象"（不解读为策略优劣）
  □ out.protocol/axis/metric 三字段如实记录度量与轴
  □ 真区分: A=1.0(golden 必然) vs B<1.0(LLM 真判分) — winner=basis=best_v
"""
from __future__ import annotations

import json
import os
import sys

import pytest

ROOT = r"E:/Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import ga_duel  # noqa: E402


def test_cli_has_metric_switch():
    """CLI 暴露 --metric {dream_v, judge_mean}（默认 dream_v 零破坏）。"""
    import inspect
    src = inspect.getsource(ga_duel.main)
    assert '"--metric"' in src
    assert 'default="dream_v"' in src
    # judge_mean 分支必须改执行体轴（不是 shared core 假对打）
    assert "axis" in src and "judge_mean" in src


def test_protocol_and_axis_fields_in_doc():
    """留档文档须带 metric/axis/protocol 三字段（度量+轴可审计）。"""
    p = os.path.join(ROOT, "docs", "ga_duel_r130.json")
    assert os.path.exists(p), "先跑 --metric judge_mean"
    d = json.load(open(p, encoding="utf-8"))
    assert d["metric"] == "judge_mean"
    assert d["axis"] == "executor"
    assert "R130" in d["protocol"] and "执行体轴" in d["protocol"]
    # caveats 首条须显式"度量假象"（不可解读为策略优劣）
    assert "度量假象" in d["caveats"][0]
    assert "单点胜 GA" not in d["verdict"].get("basis", "")


def test_judge_mean_separates_executors():
    """★ 核心: judge_mean 下 A(golden)=1.0 vs B(llm)<1.0 ⇒ 真区分。"""
    p = os.path.join(ROOT, "docs", "ga_duel_r130.json")
    assert os.path.exists(p)
    d = json.load(open(p, encoding="utf-8"))
    v = d["verdict"]
    assert v["best_v_single"] == 1.0        # golden expected 全灌=结构必然
    assert v["best_v_ga"] < 1.0             # LLM 真判分 ⇒ 均值 <1
    assert v["winner"] == "single"          # 度量假象下的裁决（如实记）
    assert v["basis"] == "best_v"           # 非平局 ⇒ 真有区分


def test_dream_v_default_doc_unchanged():
    """★ 零破坏: 默认 dream_v 的 docs/ga_duel.json 仍 strategy 轴判 A。"""
    p = os.path.join(ROOT, "docs", "ga_duel.json")
    assert os.path.exists(p)
    d = json.load(open(p, encoding="utf-8"))
    assert d.get("axis") == "strategy"
    assert d.get("metric") == "dream_v"
    assert d["verdict"]["winner"] == "single"
    assert d["budget"]["k_ratio_ga_over_single"] == 2.0
