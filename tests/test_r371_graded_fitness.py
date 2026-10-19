# -*- coding: utf-8 -*-
"""R371 · 分级 fitness 的行为锁（Phase C）。

守四件事:
  1. 六级全过 ⇒ realization=outcome=scalar=1
  2. 落地失败 ⇒ scalar=0（即使结果层看起来还行 —— 落地是前提）
  3. 未测的级（None）不进分母 —— 未填 ≠ 测得零
  4. harness 报告到分级记录的字段搬运正确
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if os.path.join(_ROOT, "src") not in sys.path:
    sys.path.insert(0, os.path.join(_ROOT, "src"))

from dwc.organs.benchmark_fitness import (  # noqa: E402
    GRADED_LEVELS, fitness_breakdown, record_from_harness,
)


def _rec(**kw):
    base = {"instance_id": "x"}
    base.update(kw)
    return base


def test_all_levels_pass():
    fb = fitness_breakdown([_rec(parse_ok=True, apply_ok=True, syntax_ok=True,
                                 f2p_ok=True, p2p_ok=True, verifier_ok=True)])
    assert fb["realization"] == 1.0
    assert fb["outcome"] == 1.0
    assert fb["scalar"] == 1.0
    assert fb["verdict"] == "measured"
    assert set(fb["counts"]) == set(GRADED_LEVELS)


def test_realization_failure_zeroes_scalar():
    """落地层全败时，即使结果层全过，scalar 也必须为 0。"""
    fb = fitness_breakdown([_rec(parse_ok=False, apply_ok=False, syntax_ok=False,
                                 f2p_ok=True, p2p_ok=True, verifier_ok=True)])
    assert fb["realization"] == 0.0
    assert fb["outcome"] == 1.0
    assert fb["scalar"] == 0.0


def test_unmeasured_level_excluded_not_zero():
    """p2p 未测（None）时不计入分母；测到的那条 False 才拉低。"""
    fb = fitness_breakdown([
        _rec(parse_ok=True, apply_ok=True, syntax_ok=True,
             f2p_ok=True, p2p_ok=None, verifier_ok=True),
        _rec(parse_ok=True, apply_ok=True, syntax_ok=True,
             f2p_ok=True, p2p_ok=False, verifier_ok=True),
    ])
    assert fb["counts"]["p2p_ok"]["total"] == 1     # 只有一条被测
    assert fb["counts"]["p2p_ok"]["ok"] == 0
    assert fb["counts"]["p2p_ok"]["rate"] == 0.0
    # 其余级两条都测到
    assert fb["counts"]["f2p_ok"]["total"] == 2


def test_insufficient_data():
    fb = fitness_breakdown([])
    assert fb["scalar"] is None
    assert fb["verdict"] == "insufficient_data"
    assert fb["realization"] is None


def test_record_from_harness_maps_fields():
    report = {
        "instance_id": "pytest-dev__pytest-11143",
        "success": True,
        "last_tool_result": {
            "applied": True,
            "syntax_ok": True,
            "f2p": {"all_passed": True, "passed": 1, "total": 1},
            "verdict": "PASS",
        },
    }
    rec = record_from_harness(report)
    assert rec["instance_id"] == "pytest-dev__pytest-11143"
    assert rec["parse_ok"] is True
    assert rec["apply_ok"] is True
    assert rec["syntax_ok"] is True
    assert rec["f2p_ok"] is True
    assert rec["p2p_ok"] is None            # harness 没跑 P2P，不补值
    assert rec["verifier_ok"] is True
    assert rec["resolved"] is True

    fb = fitness_breakdown([rec])
    assert fb["scalar"] == 1.0


def test_record_from_harness_without_tool_result():
    """解析失败 ⇒ 没有 tool_result ⇒ parse_ok 必须是 None 而不是 False。"""
    rec = record_from_harness({"instance_id": "x", "success": False,
                               "last_tool_result": None})
    assert rec["parse_ok"] is None
    assert rec["apply_ok"] is None
    fb = fitness_breakdown([rec])
    assert fb["verdict"] == "insufficient_data"
