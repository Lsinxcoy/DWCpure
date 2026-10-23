# -*- coding: utf-8 -*-
"""R442 · P1-b 成本归因（按任务聚合 + 每轮快照 + 趋势）。

为什么：P0-a 记了每次调用，但**不知道属于哪个任务**。
进化轮要回答"这条规则落地后，任务变贵了还是便宜了"，必须先能按任务聚合。

诚实边界（重要）
----------------
候选规则的成本**无法在 trial 期测量**：trial 是纯 Python 沙箱，不调 LLM。
规则的真实成本只有在 agent 真正跑任务时才产生。所以本模块做的是
**回溯归因**（按 task_id 聚合生产用量），不是"候选成本预判"。
"""
from __future__ import annotations

import io
import json
import os

from dwc.llm import cost as C
from dwc.organs import cost_attribution as A


def _row(**kw):
    base = {"ts": 1.0, "model": "m1", "prompt_tokens": 100,
            "completion_tokens": 10, "cached_tokens": 0, "cost_usd": None}
    base.update(kw)
    return json.dumps(base, ensure_ascii=False)


# ---------------------------------------------------------------- tag 传递

def test_record_uses_current_tag(tmp_path, monkeypatch):
    monkeypatch.setenv("DWC_USAGE_PATH", str(tmp_path / "u.jsonl"))
    C.set_tag("T1")
    try:
        C.record("m1", C.Usage(10, 2), None)
    finally:
        C.clear_tag()
    row = json.loads(io.open(tmp_path / "u.jsonl", encoding="utf-8").readline())
    assert row["tag"] == "T1"


def test_explicit_tag_wins_over_current(tmp_path, monkeypatch):
    monkeypatch.setenv("DWC_USAGE_PATH", str(tmp_path / "u.jsonl"))
    C.set_tag("T1")
    try:
        C.record("m1", C.Usage(10, 2), None, tag="EXPLICIT")
    finally:
        C.clear_tag()
    row = json.loads(io.open(tmp_path / "u.jsonl", encoding="utf-8").readline())
    assert row["tag"] == "EXPLICIT"


def test_clear_tag_removes_it(tmp_path, monkeypatch):
    monkeypatch.setenv("DWC_USAGE_PATH", str(tmp_path / "u.jsonl"))
    C.set_tag("T1")
    C.clear_tag()
    C.record("m1", C.Usage(10, 2), None)
    row = json.loads(io.open(tmp_path / "u.jsonl", encoding="utf-8").readline())
    assert "tag" not in row


# ---------------------------------------------------------------- 聚合

def test_per_task_groups_by_tag(tmp_path):
    p = tmp_path / "u.jsonl"
    p.write_text("\n".join([
        _row(tag="T1", prompt_tokens=100, completion_tokens=10),
        _row(tag="T1", prompt_tokens=200, completion_tokens=20),
        _row(tag="T2", prompt_tokens=50, completion_tokens=5),
    ]) + "\n", encoding="utf-8")
    got = A.per_task(str(p))
    assert got["T1"]["calls"] == 2
    assert got["T1"]["prompt_tokens"] == 300
    assert got["T1"]["total_tokens"] == 330
    assert got["T2"]["total_tokens"] == 55


def test_per_task_ignores_untagged(tmp_path):
    p = tmp_path / "u.jsonl"
    p.write_text("\n".join([_row(tag="T1"), _row()]) + "\n", encoding="utf-8")
    got = A.per_task(str(p))
    assert list(got) == ["T1"]


def test_per_task_tolerates_bad_lines(tmp_path):
    p = tmp_path / "u.jsonl"
    p.write_text('{"tag":"T1","prompt_tokens":1,"completion_tokens":1}\n'
                 'not json\n'
                 '{"tag":"T1"}\n', encoding="utf-8")
    got = A.per_task(str(p))
    assert got["T1"]["calls"] == 2      # 缺 token 字段按 0 计，不炸


def test_mean_tokens_per_task(tmp_path):
    p = tmp_path / "u.jsonl"
    p.write_text("\n".join([
        _row(tag="T1", prompt_tokens=100, completion_tokens=0),
        _row(tag="T2", prompt_tokens=300, completion_tokens=0),
    ]) + "\n", encoding="utf-8")
    m = A.mean_tokens_per_task(str(p))
    assert m["n_tasks"] == 2
    assert m["mean_total"] == 200.0


def test_mean_tokens_empty_returns_none(tmp_path):
    p = tmp_path / "missing.jsonl"
    m = A.mean_tokens_per_task(str(p))
    assert m["n_tasks"] == 0 and m["mean_total"] is None


# ---------------------------------------------------------------- 快照/趋势

def test_snapshot_is_incremental(tmp_path):
    """快照只统计**上次快照之后**的任务 —— 否则历史会把趋势抹平。"""
    p = tmp_path / "u.jsonl"
    p.write_text(_row(ts=1.0, tag="T1", prompt_tokens=100,
                      completion_tokens=0) + "\n", encoding="utf-8")
    led = tmp_path / "cost_ledger.jsonl"
    s1 = A.snapshot(usage_path=str(p), ledger_path=str(led), note="r1")
    assert s1["n_tasks"] == 1 and s1["mean_total"] == 100.0

    with io.open(p, "a", encoding="utf-8") as f:
        f.write(_row(ts=2.0, tag="T2", prompt_tokens=200,
                     completion_tokens=0) + "\n")
    s2 = A.snapshot(usage_path=str(p), ledger_path=str(led), note="r2")
    assert s2["n_tasks"] == 1 and s2["mean_total"] == 200.0

    tr = A.trend(ledger_path=str(led))
    assert tr["direction"] == "up" and tr["delta"] == 100.0


def test_snapshot_without_new_tasks_records_none(tmp_path):
    p = tmp_path / "u.jsonl"
    p.write_text(_row(ts=1.0, tag="T1") + "\n", encoding="utf-8")
    led = tmp_path / "cost_ledger.jsonl"
    A.snapshot(usage_path=str(p), ledger_path=str(led))
    s2 = A.snapshot(usage_path=str(p), ledger_path=str(led))
    assert s2["n_tasks"] == 0 and s2["mean_total"] is None


def test_trend_up_when_tokens_grow(tmp_path):
    led = tmp_path / "cost_ledger.jsonl"
    led.write_text("\n".join([
        json.dumps({"ts": 1.0, "n_tasks": 1, "mean_total": 100.0}),
        json.dumps({"ts": 2.0, "n_tasks": 1, "mean_total": 150.0}),
    ]) + "\n", encoding="utf-8")
    tr = A.trend(ledger_path=str(led))
    assert tr["direction"] == "up" and tr["delta"] == 50.0


def test_trend_insufficient_data(tmp_path):
    led = tmp_path / "cost_ledger.jsonl"
    A.trend(ledger_path=str(led))
    tr = A.trend(ledger_path=str(led))
    assert tr["direction"] == "unknown"
