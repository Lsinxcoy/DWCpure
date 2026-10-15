# -*- coding: utf-8 -*-
"""R277 · term verdict 落盘可观测（daemon 每轮判了什么不再盲飞）。

★ 冻结: _backfill_failures 口径不动（success is False 才记）;
  本轮只加观测行（var/eval/term_verdicts.jsonl append-only）。
★ 测试隔离: 写 tmp 库旁 eval 目录，禁碰生产 sqlite。
"""
from __future__ import annotations

import json
import os
import sys

import pytest

ROOT = r"E:\Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "src"))
from dwc.harness import run_term as RT                      # noqa: E402


def _fake_verdict(n_fail=1):
    ds = [{"task_id": "t_ok", "success": True,
           "failure_signature": None, "sigs": []}]
    for i in range(n_fail):
        ds.append({"task_id": "t_bad%d" % i, "success": False,
                   "failure_signature": {"c": "c%d" % i, "q": "q",
                                         "m": "m"},
                   "sigs": [{"c": "c%d" % i, "q": "q", "m": "m"}]})
    return {"pass_rate": 0.5, "fail": n_fail, "details": ds}


def test_append_verdict_log_roundtrip(tmp_path):
    db = str(tmp_path / "p.sqlite")
    n = RT._append_verdict_log(db, "code_fix_001", _fake_verdict(2))
    assert n == 2
    lp = os.path.join(str(tmp_path), "eval", "term_verdicts.jsonl")
    rows = [json.loads(l) for l in open(lp, encoding="utf-8")]
    assert len(rows) == 1 and rows[0]["task"] == "code_fix_001"
    assert rows[0]["false_tasks"] == ["t_bad0", "t_bad1"]


def test_append_verdict_log_bad_input_never_raises(tmp_path):
    db = str(tmp_path / "p.sqlite")
    with pytest.raises((TypeError, ValueError, AttributeError)):
        RT._append_verdict_log(db, "t", None)
    with pytest.raises((TypeError, ValueError, AttributeError)):
        RT._append_verdict_log(db, "t", {"details": [{"success": False}]})
