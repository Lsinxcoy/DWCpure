# -*- coding: utf-8 -*-
"""R124 · 项2-4a Transfer LLM 臂 — 解析/契约/协议断言。

验收:
  □ _parse_llm_observed: 好 JSON 抽对; 空/坏 ⇒ None（不猜）
  □ _obs_skeleton: fn→[[args,None]]（None=待填, 不预填当 0）;
    keyword_match 不进 skeleton（本臂只做 behavior）
  □ llm_executor: 端点不可用占位 ⇒ 全 None（不为 False）
  □ 协议: 三维解耦（author≠user）+ 三臂 + 盲安慰剂 + repeat 序列均值
  □ 端点不可用 ⇒ not_computable exit=3（不装数）
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from transfer_llm_arm import (  # noqa: E402
    _null_exec, _obs_skeleton, _parse_llm_observed)

ANCHORS = json.load(open(os.path.join(ROOT, "config", "anchors",
                                      "dev.json"), encoding="utf-8"))
BEH = sorted(t for t in ANCHORS if not t.startswith("_")
             and ANCHORS[t].get("verifier_kind") == "behavior")[:1]


def test_obs_skeleton_none_placeholder():
    """骨架 fn→[[args,None]]: None=待 LLM 填, 不预填 0（未评价不当假零）。"""
    skel = _obs_skeleton(ANCHORS, BEH[0])
    assert skel, "behavior 任务应有 fn checks"
    for fn, pairs in skel.items():
        assert isinstance(pairs, list) and pairs
        for args, obs in pairs:
            assert obs is None
    # keyword 任务 ⇒ 无 skeleton（本臂只跑 behavior）
    kw = [t for t in ANCHORS if ANCHORS[t].get("verifier_kind")
          == "keyword_match"][0]
    assert _obs_skeleton(ANCHORS, kw) == {}


def test_parse_llm_observed_good_and_bad():
    """好 JSON 抽成形态; 空/坏/非对 ⇒ None（不猜不编）。"""
    skel = _obs_skeleton(ANCHORS, BEH[0])
    fn0 = sorted(skel)[0]
    good = json.dumps({fn0: skel[fn0]})           # 回填 None — 合法形态
    parsed = _parse_llm_observed(good, skel)
    assert parsed is not None and fn0 in parsed
    assert _parse_llm_observed("", skel) is None
    assert _parse_llm_observed("garbage text", skel) is None
    assert _parse_llm_observed('{"a": 1}', skel) is None   # 不完全成对
    # 围栏宽容（```json）
    fenced = "```json\n%s\n```" % good
    assert _parse_llm_observed(fenced, skel) is not None


def test_null_executor_returns_unjudged():
    """端点不可用占位: detail 空 ⇒ judge 判 None（未评价, 不当 False）。"""
    from dwc.organs.actor import Receipt
    r = _null_exec()({"task_id": "x"})
    assert isinstance(r, Receipt) and r.verified is True
    assert r.detail == {}


def test_memory_text_channel_shared():
    """memory 文本通道对三臂同构（真实/盲造工件均走同一渲染路径）。"""
    from transfer_llm_arm import _memory_text
    from dwc.core import DWC
    b = DWC(3, 50, executor=None, db_path=":memory:")
    assert _memory_text(b) == ""                   # 空库 ⇒ 空串（不造）
    from dwc.organs.memory import MemoryKind
    b.memory.remember(MemoryKind.SKILL,
                      {"scene": "s", "method": "m", "boundary": "b",
                       "invalid_conditions": ["x"],
                       "recovery_strategies": ["y"]})
    txt = _memory_text(b)
    assert "scene" in txt and "invalid_conditions" in txt


def test_script_runs_or_not_computable():
    """脚本真跑: 已跑（后台产物）⇒ 结构全; 未跑/端点不可用 ⇒
    not_computable 或 exit=3（不装数不造假）。"""
    outp = os.path.join(ROOT, "docs", "transfer_llm_arm.json")
    if not os.path.exists(outp):
        pytest.skip("后台跑未落盘 —等 notify 后重跑")
    d = json.load(open(outp, encoding="utf-8"))
    if d.get("status") == "not_computable":
        assert "llm unconfigured" == d.get("why") or d.get("why")
        return
    assert d["attribution"]["content_effect_verdict"] in (
        "content_gain", "placebo_equal", "negative", "not_computable")
    for arm in ("transplant", "blind_placebo", "baseline"):
        s = d["arms_summary"][arm]
        assert "rates" in s and "n_parsed" in s and "n_calls" in s
    assert d["author_tasks"] and d["n_user_tasks"] >= 2   # author≠user
    assert "端点质量决定绝对分数" in "\n".join(d["caveats"])
