# -*- coding: utf-8 -*-
"""R155 · 闭环回写（信用台账 ℒ_t）— 七元组 + a_i 二元 + append-only。

验收:
  □ 七字段顺序（t/edit/layer/hunk/dimension/ΔS/ΔC/a_i）
  □ a_i 二元: winner=1 / admissible_but_lost=0（0.5/None 拒）
  □ append-only: 只增不改（entries() 返副本 — 外部改不动内部）
  □ 契约: t<0/空字段/非数值/原因空 全拒
  □ summary: n_winner/lost/winner_rate + by_dimension/by_layer 聚合
  □ 空台账: 缺席≠0（没记≠没发生）
"""
from __future__ import annotations

import os
import sys

import pytest

ROOT = r"E:/Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.organs.credit import (  # noqa: E402
    CREDIT_MECHANICS, LEDGER_FIELDS, CreditEntry, CreditError, CreditLedger,
    adopted_flag)


def _e(**kw) -> CreditEntry:
    base = dict(t=1, edit="e1", layer="assets", hunk="d1",
                dimension="D1", delta_s=0.1, delta_c=0.2, adopted=1)
    base.update(kw)
    return CreditEntry(**base)


def test_seven_fields_and_entry_contract():
    """★ 七字段顺序 + 逐字段契约（t<0/空串/非数值/a_i 越界全拒）。"""
    assert LEDGER_FIELDS == ("t", "edit", "layer", "hunk", "dimension",
                             "delta_s", "delta_c", "adopted")
    for bad in (dict(t=-1), dict(edit=""), dict(layer=""), dict(hunk=""),
                dict(dimension=""), dict(delta_s="x"), dict(delta_c="y"),
                dict(adopted=2), dict(adopted=0.5), dict(adopted=None)):
        with pytest.raises(CreditError):
            _e(**bad)


def test_a_i_binary_and_causes():
    """★★ a_i 只 0/1; cause 非空（陪跑也要可归因）。"""
    assert adopted_flag(True, "winner") == 1
    assert adopted_flag(False, "admissible_but_lost") == 0    # ★ 原文显式要记
    with pytest.raises(CreditError):
        adopted_flag(None, "x")                               # 待定不许
    with pytest.raises(CreditError):
        adopted_flag(False, "")                               # 无因不许


def test_append_only_and_record_round():
    """★ append-only: 录两轮四笔; entries() 返副本（外部改不动内部）。"""
    led = CreditLedger()
    led.record_round(1, [{"edit": "a", "layer": "assets", "hunk": "h1",
                          "dimension": "D1", "delta_s": 0.2,
                          "delta_c": 0.1, "adopted": 1},
                         {"edit": "b", "layer": "architecture", "hunk": "h2",
                          "dimension": "D3", "delta_s": 0.0,
                          "delta_c": 0.1, "adopted": 0}])   # admissible lost
    led.record_round(2, [{"edit": "c", "layer": "assets", "hunk": "h3",
                          "dimension": "D1", "delta_s": 0.3,
                          "delta_c": 0.2, "adopted": 1}])
    assert len(led.entries()) == 3
    got = led.entries()
    got.append("junk")                        # 改副本不动内部
    assert len(led.entries()) == 3
    # 字段名错 ⇒ 显式拒（不是吞）
    with pytest.raises(CreditError):
        led.record_round(3, [{"typo": 1}])


def test_summary_aggregation():
    """★ 聚合: winner_rate/by_dimension/by_layer 逐维度算（不抽数）。"""
    led = CreditLedger()
    led.record_round(1, [
        {"edit": "a", "layer": "assets", "hunk": "h1", "dimension": "D1",
         "delta_s": 0.2, "delta_c": 0.1, "adopted": 1},
        {"edit": "b", "layer": "assets", "hunk": "h2", "dimension": "D1",
         "delta_s": 0.0, "delta_c": 0.0, "adopted": 0},
        {"edit": "c", "layer": "architecture", "hunk": "h3", "dimension": "D2",
         "delta_s": 0.1, "delta_c": 0.1, "adopted": 1}])
    s = led.summary()
    assert s["n"] == 3 and s["n_winner"] == 2 and s["n_lost"] == 1
    assert abs(s["winner_rate"] - 2 / 3) < 1e-12
    d1 = s["by_dimension"]["D1"]
    assert d1["n"] == 2 and d1["n_winner"] == 1          # D1 一半赢一半陪
    assert abs(d1["sum_ds"] - 0.2) < 1e-12
    assert s["rounds"] == [1]


def test_empty_ledger_absent_not_zero():
    """★★ 空台账: 缺席≠0（没记≠没发生 — 不编 0.0 冒充测过）。"""
    s = CreditLedger().summary()
    assert s["n"] == 0
    assert "缺席≠0" in s["note"]
    assert "winner_rate" not in s                          # 不造率


def test_mechanics_documented():
    """ℒ_t 口径 + admissible-but-lost + append-only 在档。"""
    assert "七元组" in CREDIT_MECHANICS["ledger_fields"]
    assert "admissible but lost" in CREDIT_MECHANICS["a_i_rule"]
    assert "只增不改" in CREDIT_MECHANICS["append_only"]
