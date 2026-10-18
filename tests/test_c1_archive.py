# -*- coding: utf-8 -*-
"""★ C1 · archive→adopt 两步走（18813 §3.2：archive≠adopt —— 进 archive
只保留候选供后搜）。

锁：
1. archive_candidate：同 key 多候选并存（list），版本递增，不进 RULES。
2. archive≠adopt 实证：archive 后 propose 仍 None（RULES 未动）。
3. withdraw 覆盖 archive（RULES 无 key 时撤整 key archive）。
4. parent 选择器另轮（诚实口径，见 ARCHIVE 注释）。
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.organs.evolver import Mutator


def _clean(key):
    Mutator.RULES.pop(key, None)
    Mutator.ARCHIVE.pop(key, None)


def test_c1_archive_multi_versions():
    key = "E:q:c1_tmp_fn"
    _clean(key)
    try:
        r1 = Mutator.archive_candidate(key, {"patch": "p1"})
        r2 = Mutator.archive_candidate(key, {"patch": "p2"})
        assert (r1["version"], r2["version"]) == (1, 2)
        assert len(Mutator.ARCHIVE[key]) == 2
        assert key not in Mutator.RULES  # 只保留，不 adopt
    finally:
        _clean(key)


def test_c1_archive_not_adopted():
    key = "E:q:c1_tmp_fn2"
    _clean(key)
    try:
        Mutator.archive_candidate(key, {"patch": "p"})
        mu = Mutator()
        assert mu.propose({"c": "E", "q": "q",
                           "fn": "c1_tmp_fn2"}) is None
    finally:
        _clean(key)


def test_c1_withdraw_archive():
    key = "E:q:c1_tmp_fn3"
    _clean(key)
    try:
        Mutator.archive_candidate(key, {"patch": "p1"})
        Mutator.archive_candidate(key, {"patch": "p2"})
        r = Mutator.withdraw(key, reason="毒候选清理")
        assert r["withdrawn"] is True
        assert r["from"] == "archive"
        assert len(r["entry"]) == 2
        assert key not in Mutator.ARCHIVE
        assert Mutator.withdraw(key)["withdrawn"] is False
    finally:
        _clean(key)
