# -*- coding: utf-8 -*-
"""R443 · P1-c 逐例对比（把"一个分数"拆成"哪几例错了"）。

为什么：trial 只回 in_score=1.0/0.0。
"修好 3 例、弄坏 3 例"和"什么都没改"在分数上一样（都是 0.5），
但前者是回归、后者是没动 —— 分数看不出这个差别。
"""
from __future__ import annotations

from dwc.organs import contrast as CT

SKEL = {"f": [[1, None], [2, None], [3, None]]}   # ★ obs_skeleton 故意不带 expected
EXP = {"f": [1, 4, 9]}


def test_all_pass():
    obs = {"f": [[1, 1], [2, 4], [3, 9]]}
    c = CT.from_observed(SKEL, obs, EXP)
    assert c is not None
    assert (c["n_cases"], c["n_failed"], c["n_passed"]) == (3, 0, 3)
    assert c["failed"] == []


def test_partial_failure_lists_exact_cases():
    obs = {"f": [[1, 1], [2, 99], [3, 9]]}
    c = CT.from_observed(SKEL, obs, EXP)
    assert c["n_failed"] == 1
    assert c["failed"][0]["args"] == 2
    assert c["failed"][0]["expected"] == 4
    assert c["failed"][0]["actual"] == 99


def test_numeric_equivalence_int_vs_float():
    """1 与 1.0 是同一个值（模型常返回 1.0）—— 不许判不等。"""
    skel = {"f": [[1, None]]}
    c = CT.from_observed(skel, {"f": [[1, 1.0]]}, {"f": [1]})
    assert c["n_failed"] == 0


def test_missing_function_returns_none():
    assert CT.from_observed(SKEL, {}, EXP) is None


def test_length_mismatch_returns_none():
    """少一例/多一例 ⇒ 不可比，fail-closed（不许拿前面的例子蒙混）。"""
    assert CT.from_observed(SKEL, {"f": [[1, 1]]}, EXP) is None
    assert CT.from_observed(SKEL, {"f": [[1, 1], [2, 4], [3, 9], [4, 16]]}, EXP) is None


def test_none_observed_returns_none():
    assert CT.from_observed(SKEL, None, EXP) is None
    assert CT.from_observed(None, {"f": []}, EXP) is None


def test_regressed_is_none_with_reason():
    """诚实缺席：没有基线逐例结果，就不许编 'regressed'。"""
    c = CT.from_observed(SKEL, {"f": [[1, 1], [2, 4], [3, 9]]}, EXP)
    assert c["regressed"] is None
    assert c["regressed_reason"]


def test_bad_case_shape_returns_none():
    assert CT.from_observed({"f": ["not-a-pair"]}, {"f": [[1, 1]]}, {"f": [1]}) is None


def test_missing_expected_returns_none():
    """★ 没有期望值就**不可判** —— 不许把每一例都判成失败。"""
    assert CT.from_observed(SKEL, {"f": [[1, 1], [2, 4], [3, 9]]}, None) is None
    assert CT.from_observed(SKEL, {"f": [[1, 1], [2, 4], [3, 9]]}, {}) is None


def test_expected_from_checks():
    checks = [{"fn": "f", "args": "1", "expected": "1"},
              {"fn": "f", "args": "2", "expected": "4"}]
    assert CT.expected_from_checks(checks) == {"f": [1, 4]}


def test_expected_from_checks_tolerates_junk():
    assert CT.expected_from_checks(None) == {}
    assert CT.expected_from_checks([{"fn": ""}]) == {}
