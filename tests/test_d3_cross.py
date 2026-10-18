# -*- coding: utf-8 -*-
"""★ D3 · crossed evaluation 单版本内 cross（companion §6.3.3：换 anchor/
换模型时 H_k×D_A、H_{k+1}×D_B 双向 cross —— 本方法是单版本内 cross，
版本间靠 git 历史＋ledger diff，见 cross docstring）。

锁（真 Judge＋真 anchors）：
1. reasoning_001 全关键词 obs ⇒ dev True；sealed_task 配对有值；
   agree 与 (dev==sealed) 一致。
2. observed=None ⇒ dev None ⇒ agree None（未评价不当 False）。
3. 无配对 task（code_fix_008）⇒ sealed_task None＋sealed None（不顶替）。
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.organs.judge import Judge

_FULL = "快排最坏 O(n^2)：pivot 选到极值，递归深度达 n"


def test_d3_cross_structure():
    j = Judge()
    r = j.cross("reasoning_001", observed={"answer": _FULL})
    assert r["task"] == "reasoning_001"
    assert r["sealed_task"] == "test_reasoning_001"
    assert r["dev"] is True
    assert r["sealed"] in (True, False, None)
    if r["sealed"] is not None:
        assert r["agree"] == (r["dev"] == r["sealed"])
    else:
        assert r["agree"] is None


def test_d3_cross_unevaluated():
    j = Judge()
    r = j.cross("code_fix_001", observed=None)
    assert r["dev"] is None
    assert r["agree"] is None
    assert r["sealed_task"] == "test_list_001"


def test_d3_cross_unpaired():
    j = Judge()
    r = j.cross("code_fix_008", observed=None)
    assert r["sealed_task"] is None
    assert r["sealed"] is None
    assert r["agree"] is None
