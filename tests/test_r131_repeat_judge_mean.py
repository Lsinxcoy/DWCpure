# -*- coding: utf-8 -*-
"""R131 · judge_mean repeat 序列 — R130 读数的方向稳定性证据。

验收:
  □ n<3 拒绝（not_applicable rc=2 — 单跑无方向, R130 纪律的硬编码）
  □ _stats 手写 median/min/max + all_equal_1.0 / all_below_1.0 双旗
  □ 文档: runs 逐跑 + stats 双臂 + verdict 方向 + caveats 度量假象
  □ 方向结论仅在 A 全 1.0 ∧ B 全 <1 时才给（否则"记录实际分布"）
  □ 包装不改 ga_duel 协议（caveats 明示冻结）
"""
from __future__ import annotations

import json
import os
import sys

import pytest

ROOT = r"E:/Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from repeat_judge_mean import _stats, main  # noqa: E402


def test_stats_median_and_flags():
    """median 奇偶都对 + 双旗（1.0 恒 / <1 恒）只给真全集。"""
    s = _stats([1.0, 0.875, 0.9])
    assert s["n"] == 3 and s["median"] == 0.9
    assert s["min"] == 0.875 and s["max"] == 1.0
    assert s["all_equal_1.0"] is False and s["all_below_1.0"] is False
    assert _stats([1.0, 1.0])["all_equal_1.0"] is True
    assert _stats([0.9, 0.875])["all_below_1.0"] is True
    assert _stats([])["median"] is None          # 空 ⇒ None 不装 0


def test_n_below_3_refused(monkeypatch, capsys):
    """★ n<3 硬拒绝（单跑无方向 — R130 两跑纪律的执行点）。"""
    rc = main.__wrapped__ if hasattr(main, "__wrapped__") else None
    # 直接调 main 需伪造 argv
    monkeypatch.setattr(sys, "argv",
                        ["repeat_judge_mean.py", "--n", "2"])
    assert main() == 2
    assert "not_applicable" in capsys.readouterr().out


def test_doc_structure_when_run():
    """跑过 ⇒ 文档含 runs/stats/verdict/caveats 全套（可审计）。"""
    p = os.path.join(ROOT, "docs", "repeat_judge_mean.json")
    if not os.path.exists(p):
        pytest.skip("repeat 跑未完成 — 后台跑完再验")
    d = json.load(open(p, encoding="utf-8"))
    assert d["n"] >= 3 and len(d["runs"]) == d["n"]
    for arm in ("A_golden", "B_llm"):
        assert d["stats"][arm]["n"] >= 3
        assert d["stats"][arm]["median"] is not None
    # 方向结论的纪律: A 恒 1.0 才可称"A 饱和恒定"
    v = d["verdict"]
    assert isinstance(v["A_saturated_always"], bool)
    assert isinstance(v["B_below_1_always"], bool)
    assert "执行体轴" in v["direction"] or "未收敛" in v["direction"]
    # 度量假象须在 caveats 首位区
    assert any("度量假象" in c for c in d["caveats"])
    # 协议冻结声明在位
    assert any("不改" in c or "冻结" in c for c in d["caveats"])


def test_direction_only_when_separated():
    """方向结论仅当 A 全 1.0 ∧ B 全 <1（否则不套结论 — 纪律）。"""
    p = os.path.join(ROOT, "docs", "repeat_judge_mean.json")
    if not os.path.exists(p):
        pytest.skip("未跑")
    d = json.load(open(p, encoding="utf-8"))
    a_ok = d["verdict"]["A_saturated_always"]
    b_ok = d["verdict"]["B_below_1_always"]
    if a_ok and b_ok:
        assert "稳定" in d["verdict"]["direction"]
    else:
        assert "未收敛" in d["verdict"]["direction"]
