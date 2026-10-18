# -*- coding: utf-8 -*-
"""★ A6 · peak-picking 禁令（companion HarnessX 反例：报 peak 73.8% 而
终态 49.5%）：evo 呈现面只报当轮终态＋ledger，不回溯历史 peak。

锁：run_round 与 triage_report 的 docstring 纪律在位（删纪律即红）。
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import dwc_evo_round as E


def test_a6_discipline_present():
    assert "peak-picking" in (E.run_round.__doc__ or "")
    assert "peak-picking" in (E.triage_report.__doc__ or "")
    assert "73.8%" in (E.run_round.__doc__ or "")
