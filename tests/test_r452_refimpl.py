# -*- coding: utf-8 -*-
"""R452 · 参考实现登记表：新任务的期望值只能来自**已验证**的实现。

为什么需要：anchor 里只有 (fn, args, expected)，**没有原始实现**。
想扰动参数就必须能重算 expected —— 但重算的凭据不能是"我觉得对"。

所以：每条参考实现必须先复现**现有全部 anchor 检查**才有资格被用。
这条测试就是那道门：只要有一条复现不了，登记表就不能用于生成。
"""
from __future__ import annotations

import json
import os

import pytest

from dwc.organs import refimpl as R

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ANCHORS = [os.path.join(ROOT, "config", "anchors", f)
           for f in ("dev.json", "fresh.json")]


def _checks():
    for p in ANCHORS:
        with open(p, encoding="utf-8") as f:
            d = json.load(f)
        for tid, a in d.items():
            if not isinstance(a, dict) or tid.startswith("_"):
                continue
            for c in (a.get("checks") or []):
                if isinstance(c, dict) and c.get("fn"):
                    yield tid, c


def test_every_anchor_fn_has_a_reference():
    missing = {c["fn"] for _, c in _checks()} - set(R.REFS)
    assert missing == set(), "缺参考实现: %r" % (sorted(missing),)


def test_every_existing_check_reproduces():
    """★ 这是登记表的准入证 —— 一条不符就不许拿去生成新题。"""
    bad = []
    for tid, c in _checks():
        got = R.compute(c["fn"], c["args"])
        if got != c["expected"]:
            bad.append((tid, c["fn"], c["args"], c["expected"], got))
    assert bad == [], "复现失败: %r" % (bad,)


def test_unknown_fn_returns_none():
    assert R.compute("no_such_fn", "1") is None


def test_bad_literal_returns_none():
    assert R.compute("sum_first_n", "not-a-number") is None


def test_verified_fns_reports_only_good_ones():
    """verify() 对每个 fn 单独判：坏的必须被点名，不许整体放行。"""
    checks = [{"fn": "sum_first_n", "args": "3", "expected": "6"},
              {"fn": "fibonacci", "args": "10", "expected": "999"}]
    ok, bad = R.verify(checks)
    assert "sum_first_n" in ok
    assert "fibonacci" in bad
