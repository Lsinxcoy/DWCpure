# -*- coding: utf-8 -*-
"""R134 · dream 终止条件与 K₂ 分区探针 — 恒等问题的终极解剖。

验收:
  □ 五档 k2_max: n 随 k2 增长（活区 1/2）后饱和（4/8/16 恒 12）
  □ 饱和区成因 = C=∅ 抢先（树全节点 12 个）
  □ 活区混合树实测: n 随 k2 增长但 v_by 全同 ⇒ 活区也无策略区分
  □ 三层根因汇总（R128/R132/R133+R134）如实入档
  □ 配置不动/临时 yaml 无残留（R132 同款）
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from probe_dream_termination import (_anchors, probe_growing_zone,  # noqa: E402
                                      probe_k2)


def test_k2_growing_then_saturated():
    """★ 两区坐实: 活区 n 增长, 饱和区 = 全树。

    ★ R199 修订: 旧态"k2=4 起饱和恒 12"是 10 任务树的边界; 13 任务树
    （17 节点）下饱和点右移到 k2=8（16=excl-root 全量）— 边界规模相关。
    ★ R287-E 修订: 16 任务树（20 节点）下饱和点再右移（k2=8 揭 19 =
    revealable 全量）— 边界规模相关，"存在饱和区"仍坐实。"""
    rows = probe_k2([1, 2, 4, 8])
    n_by = {r["k2_max"]: r["per_world"][0][3] for r in rows}
    assert n_by[1] < n_by[2] < n_by[4]        # 活区增长
    # ★★★ R287-E 实测: dev 16 任务后饱和点再右移（k2=8 揭 19 = 全树
    #   excl root 可揭示全量）— "存在饱和区"仍坐实，边界随树规模移动。
    assert n_by[4] == 15 and n_by[8] == 19, n_by
    assert n_by[8] == 19          # 19 = 20 节点树的 excl-root 可揭示全量


def test_growing_zone_mixed_tree_no_separation():
    """★ 决定性: 活区 k2=1/2/3 混合树（有0有1）下 n 增长但 v_by 全同。"""
    anch = _anchors()
    ids = list((anch.get("_split") or {}).get("search", []))
    plan = [0.0] + [1.0] * (len(ids) - 1)
    gz = probe_growing_zone(ids, plan)
    assert [g["n_revealed"] for g in gz] and all(g["n_revealed"] for g in gz)
    # n 确实随 k2 变化（活区证据）
    assert len({tuple(g["n_revealed"]) for g in gz}) >= 2
    # 但无一档出策略区分（全区无区分）
    assert all(g["separates"] is False for g in gz)
    assert all(g["n_distinct_v"] == 1 for g in gz)


def test_probe_doc_records_two_zone_verdict():
    """文档须含两区判定 + 三层根因汇总 + 活区诊断明细。"""
    p = os.path.join(ROOT, "docs", "dream_termination_probe.json")
    assert os.path.exists(p), "先跑 scripts/probe_dream_termination.py"
    d = json.load(open(p, encoding="utf-8"))
    v = d["verdict"]
    assert v["k2_growing_zone"] == [1, 2]
    assert v["k2_saturated_zone"] == [4, 8, 16]
    assert "活区也无区分" in v["reading"]
    assert "C=∅" in v["reading"]
    # 三层根因汇总
    for key in ("R128", "R132", "R133+R134"):
        assert key in d["三层根因汇总"]
    assert "扩树/扩任务池" in d["三层根因汇总"]["判定"]
    # 活区诊断明细落档
    assert len(d["growing_zone_diag"]) == 3
    assert all(g["separates"] is False for g in d["growing_zone_diag"])


def test_config_untouched_no_tmp_left():
    """配置不动 + 临时 yaml 无残留（R132 同款纪律）。"""
    p = os.path.join(ROOT, "config", "replay.yaml")
    before = open(p, encoding="utf-8").read()
    probe_k2([4], betas=(0.05, 0.05))
    assert open(p, encoding="utf-8").read() == before
    assert not os.path.exists(os.path.join(ROOT, "config",
                                           "_tmp_replay_probe.yaml"))
