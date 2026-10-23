# -*- coding: utf-8 -*-
"""R446 · P4 改进库（Harness² 四条硬规则）。

为什么：`rules.json` 里已有 key + rationale + provenance，但**没有任何东西强制它们非空**。
半条记录进库比不进库更糟 —— 下轮按 cue 取用时拿到一条没有依据的"经验"。
"""
from __future__ import annotations

import json
import os

from dwc.organs import library as LB

CUE = "E_VALUE:wrong_magnitude:average"


def _entry(**kw):
    base = {"cue": CUE, "lesson": "平均值的分子分母要同时乘",
            "evidence": {"in_score": 1.0, "held_out": 1.0}}
    base.update(kw)
    return base


def test_valid_entry_passes():
    assert LB.validate(_entry()) is None


def test_missing_any_field_is_invalid():
    for f in ("cue", "lesson", "evidence"):
        e = _entry()
        e.pop(f)
        assert LB.validate(e), f


def test_empty_lesson_is_invalid():
    assert LB.validate(_entry(lesson="   "))


def test_empty_evidence_is_invalid():
    assert LB.validate(_entry(evidence={}))


def test_add_refuses_partial(tmp_path):
    p = os.path.join(str(tmp_path), "lib.jsonl")
    assert LB.add(p, _entry(lesson="")) is None
    assert not os.path.exists(p) or os.path.getsize(p) == 0


def test_add_appends_valid(tmp_path):
    p = os.path.join(str(tmp_path), "lib.jsonl")
    assert LB.add(p, _entry()) is not None
    assert LB.add(p, _entry(cue="E_VALUE:x:y")) is not None
    rows = LB.load(p)
    assert len(rows) == 2
    assert rows[0]["cue"] == CUE


def test_load_skips_bad_lines(tmp_path):
    p = os.path.join(str(tmp_path), "lib.jsonl")
    with open(p, "w", encoding="utf-8") as f:
        f.write(json.dumps(_entry()) + "\n")
        f.write("{半截\n")
        f.write("\n")
    assert len(LB.load(p)) == 1


def test_load_missing_file_is_empty(tmp_path):
    assert LB.load(os.path.join(str(tmp_path), "nope.jsonl")) == []


def test_family_matches_prefix():
    assert LB.family(CUE) == "E_VALUE:wrong_magnitude"
    assert LB.family("no-colon") == "no-colon"


def test_select_family_returns_same_family_only():
    rows = [_entry(), _entry(cue="E_VALUE:wrong_magnitude:fibonacci"),
            _entry(cue="E_VALUE:off_by_one:average")]
    got = LB.select_family(rows, CUE)
    assert len(got) == 2
    assert all(r["cue"].startswith("E_VALUE:wrong_magnitude") for r in got)


def test_before_filters_future_entries():
    """★ 防未来泄漏：只留当前任务之前入库的条目。"""
    rows = [{"cue": CUE, "lesson": "old", "evidence": {}, "ts": 100},
            {"cue": CUE, "lesson": "new", "evidence": {}, "ts": 300}]
    assert [r["lesson"] for r in LB.before(rows, 200)] == ["old"]


def test_from_rule_builds_entry():
    rule = {"rationale": "分子分母同时乘 100",
            "provenance": {"proposal_id": "P_1"}}
    trial = {"in_score": 1.0, "held_out": 1.0}
    e = LB.from_rule(CUE, rule, trial)
    assert e and e["cue"] == CUE and e["lesson"]
    assert e["evidence"]["in_score"] == 1.0


def test_from_rule_returns_none_without_lesson():
    assert LB.from_rule(CUE, {"provenance": {}}, {"in_score": 1.0}) is None
