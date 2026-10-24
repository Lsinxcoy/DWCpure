# -*- coding: utf-8 -*-
"""R449 · 规则版本成本轴：按"规则激活前后"分段统计每任务 token。

这是缺口2 的最小可判形态。
★★ 诚实边界：这是**分段相关**，不是因果 —— 激活前后任务构成会变。
   所以每份结果都必须带 confound 说明，报告里不许把它当"规则省了多少钱"。
"""
from __future__ import annotations

import json

from dwc.organs import cost_attribution as A


def _usage(tmp_path, rows):
    p = str(tmp_path / "u.jsonl")
    with open(p, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    return p


def test_segments_before_and_after(tmp_path):
    p = _usage(tmp_path, [
        {"ts": 100, "prompt_tokens": 10, "completion_tokens": 10, "tag": "t1"},
        {"ts": 110, "prompt_tokens": 20, "completion_tokens": 0, "tag": "t1"},
        {"ts": 200, "prompt_tokens": 30, "completion_tokens": 30, "tag": "t2"},
    ])
    r = A.by_rule_epoch(activated_at=150, path=p)
    assert r["before"]["n_tasks"] == 1
    assert r["before"]["mean_total"] == 40      # t1 两次调用：(10+10)+(20+0)
    assert r["after"]["n_tasks"] == 1
    assert r["after"]["mean_total"] == 60
    assert r["delta"] == 20                     # 60 - 40


def test_missing_activation_time_is_not_guessed(tmp_path):
    p = _usage(tmp_path, [{"ts": 1, "prompt_tokens": 1, "completion_tokens": 1}])
    r = A.by_rule_epoch(activated_at=None, path=p)
    assert r["status"] == "no_activation_time"
    assert "mean_total" not in r


def test_empty_side_is_none_not_zero(tmp_path):
    p = _usage(tmp_path, [{"ts": 100, "prompt_tokens": 5, "completion_tokens": 5, "tag": "t"}])
    r = A.by_rule_epoch(activated_at=999, path=p)
    assert r["after"]["n_tasks"] == 0
    assert r["after"]["mean_total"] is None
    assert r["delta"] is None


def test_confound_note_always_present(tmp_path):
    p = _usage(tmp_path, [{"ts": 1, "prompt_tokens": 1, "completion_tokens": 0, "tag": "a"},
                          {"ts": 9, "prompt_tokens": 1, "completion_tokens": 0, "tag": "b"}])
    r = A.by_rule_epoch(activated_at=5, path=p)
    assert "confound" in r and r["confound"]


def test_untagged_rows_are_excluded(tmp_path):
    """★ 与 per_task 同口径：无标签不归因，不许给它们编号充数。"""
    p = _usage(tmp_path, [
        {"ts": 100, "prompt_tokens": 100, "completion_tokens": 100},
        {"ts": 200, "prompt_tokens": 5, "completion_tokens": 5, "tag": "t"},
    ])
    r = A.by_rule_epoch(activated_at=150, path=p)
    assert r["before"]["n_tasks"] == 0
    assert r["before"]["mean_total"] is None
    assert r["after"]["mean_total"] == 10
