# -*- coding: utf-8 -*-
"""R291-P4 Task 1 · held_out 分数口（Judge 读 sealed，不读 dev）。

★★★ 存在理由
  accept 门要 Δ_ho，但 held_out 无分数口 ⇒ 门永 blocked（R289 条件②）。
  sealed（R28，11 条 locked）是真值源；evaluate(split="test") 已存在。
  本步只包一层转 1.0/0.0/None，不造新语义。
"""
from __future__ import annotations

import os
import sys

import pytest  # noqa: F401

ROOT = r"E:/Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.organs.judge import Judge, SPLIT_TEST  # noqa: E402


def _obs_math001(right=True):
    # ★ 真形态（executor.obs_skeleton/parse_llm_observed）：{fn: [[args, v]]}
    # ★ R30 纪律：actual 须 JSON 本色（int 7，不是 "7" —— 字符串冒充判 False）
    # ★ sealed test_math_001 有 2 checks（[3,7,2]→7；[]→None）—— 两条都得喂
    return {"observed": {"max_of": [[[3, 7, 2], 7 if right else 8], [[], None]]},
            "★_executed": True}


def test_held_out_score_reads_sealed_not_dev():
    """★★ sealed 真题判分：对⇒1.0，错⇒0.0（与 in-sample 同口径）。"""
    j = Judge()
    assert j.held_out_score("test_math_001", _obs_math001(True)) == 1.0
    assert j.held_out_score("test_math_001", _obs_math001(False)) == 0.0


def test_held_out_unknown_task_returns_none_loud():
    """★ 不在 sealed⇒None（未判，不编分；accept 管 blocked）。"""
    j = Judge()
    assert j.held_out_score("no_such_task", {}) is None
    assert j.held_out_score("code_fix_007", {}) is None  # dev 任务无 held_out


def test_held_out_none_observed_returns_none():
    """★ observed None⇒None（没跑=未评价，Verdict 纪律）。"""
    assert Judge().held_out_score("test_math_001", None) is None


def test_held_out_locked_out_of_metric_paths():
    """★★★ locked 语义：除 accept 门外，任何 metric/排序路径不得读 held_out。

    2607.12790 §2.2 "no part of metric evolution reads it" —— 静态 pin：
    metric_loop/candidates/direction/world_model 若引用 held_out_score
    即破 locked，本测即红。
    """
    import io
    bad = []
    for rel in ("src/dwc/organs/metric_loop.py",
                "src/dwc/organs/candidates.py",
                "src/dwc/organs/direction.py",
                "src/dwc/organs/world_model.py",
                "scripts/dwc_agent.py"):
        p = os.path.join(ROOT, rel)
        if not os.path.exists(p):
            continue
        if "held_out_score" in io.open(p, encoding="utf-8").read():
            bad.append(rel)
    assert bad == [], "locked 破口：%r 读了 held_out" % (bad,)


def test_held_out_score_raises_quota():
    """★ raises 配额：sealed 缺席启动（sealed_path 指向空）判分即炸不装有。"""
    import tempfile
    with pytest.raises(Exception):
        Judge(sealed_path=os.path.join(tempfile.mkdtemp(), "no_sealed.json"))
