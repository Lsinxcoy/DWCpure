# -*- coding: utf-8 -*-
"""R447 · 按档位归因（多记一列，不改任何决策）。

为什么：P2 上了五档，但没有任何数据能回答"哪档更省"。
先把 profile 记进用量行，跑几天就有真实分布 —— 不需要 A/B 预算。
"""
from __future__ import annotations

import json
import os

from dwc.llm import cost as C
from dwc.organs import cost_attribution as A


def _rows(p):
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]


def test_record_writes_current_profile(tmp_path, monkeypatch):
    p = str(tmp_path / "u.jsonl")
    monkeypatch.setenv("DWC_USAGE_PATH", p)
    C.set_profile("deep")
    try:
        C.record("m", C.Usage(10, 5, 0), None, tag="t1")
    finally:
        C.clear_profile()
    assert _rows(p)[0]["profile"] == "deep"


def test_explicit_profile_wins_over_thread(tmp_path, monkeypatch):
    p = str(tmp_path / "u.jsonl")
    monkeypatch.setenv("DWC_USAGE_PATH", p)
    C.set_profile("deep")
    try:
        C.record("m", C.Usage(1, 1, 0), None, tag="t", profile="lite")
    finally:
        C.clear_profile()
    assert _rows(p)[0]["profile"] == "lite"


def test_no_profile_means_no_field(tmp_path, monkeypatch):
    """★ 没有档位就不写这个键（空串不是档位名）。"""
    p = str(tmp_path / "u.jsonl")
    monkeypatch.setenv("DWC_USAGE_PATH", p)
    C.record("m", C.Usage(1, 1, 0), None, tag="t")
    assert "profile" not in _rows(p)[0]


def test_by_profile_groups_calls_and_tokens(tmp_path, monkeypatch):
    p = str(tmp_path / "u.jsonl")
    monkeypatch.setenv("DWC_USAGE_PATH", p)
    C.record("m", C.Usage(10, 5, 0), None, tag="t1", profile="deep")
    C.record("m", C.Usage(20, 5, 0), None, tag="t2", profile="deep")
    C.record("m", C.Usage(4, 1, 0), None, tag="t3", profile="lite")
    got = A.by_profile(p)
    assert got["deep"]["calls"] == 2
    assert got["deep"]["total_tokens"] == 40
    assert got["lite"]["total_tokens"] == 5


def test_by_profile_skips_unlabeled(tmp_path):
    p = str(tmp_path / "u.jsonl")
    with open(p, "w", encoding="utf-8") as f:
        f.write(json.dumps({"prompt_tokens": 9, "completion_tokens": 1}) + "\n")
    assert A.by_profile(p) == {}
