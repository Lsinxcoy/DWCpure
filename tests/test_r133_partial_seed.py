# -*- coding: utf-8 -*-
"""R133 · 部分起底探针 — 假设被证伪, 根因B 真机制坐实（dream 自身穷举）。

验收:
  □ m=0/4/8 三档全退化（v_distinct<=1）
  □ 决定性证据: n_revealed 恒 12（K₂=4 × 段数 3）⇒ 起底量不影响观测面
  □ 假设证伪如实写进 reading/caveats（不掩盖"原假设错"）
  □ 配置不动/finally 清临时 yaml（R132 同款纪律）
  □ not_applicable: D_search <4 ⇒ rc=2
"""
from __future__ import annotations

import json
import os
import sys

import pytest

ROOT = r"E:/Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from probe_partial_seed import (_anchors, build_partial,  # noqa: E402
                                 run_variants, specs_default)
from dwc.core import DWC                              # noqa: E402
from dwc.organs.judge import TaskScoreStore           # noqa: E402


def test_n_revealed_constant_across_m():
    """★ 决定性: m=0/4/8 的 per_world n_revealed 恒 12（K₂×段）。"""
    anch = _anchors()
    ids = list((anch.get("_split") or {}).get("search", []))
    plan = [0.0] + [1.0] * (len(ids) - 1)
    for m in (0, 4, len(ids)):
        d = DWC(3, 50, executor=None, db_path=":memory:")
        d.judge.store = TaskScoreStore(dw_version="probe_r133_test")
        for i, tid in enumerate(ids):
            if i >= m:
                break
            d.world_model.record_observation("dev", tid, float(plan[i]),
                                             bool(plan[i] >= 0.5))
        rep = d.dream(k2_max=4, policy_variants=specs_default())
        # per_world: (world, V, k, n_revealed) tuple; n 恒 12 ⇒ list 单值
        ns = [w[3] for w in rep.per_world]
        assert ns == [12], ns
        assert len(set(rep.v_by_version.values())) <= 1


def test_all_m_all_beta_degenerate():
    """全 m × 全 β 组合无分化（v_distinct<=1）。"""
    anch = _anchors()
    ids = list((anch.get("_split") or {}).get("search", []))
    plan = [0.0] + [1.0] * (len(ids) - 1)
    for m in (0, len(ids) // 2, len(ids)):
        d = build_partial(plan, ids, m)
        for b1 in (0.0, 0.02, 0.05):
            for b2 in (0.0, 0.05):
                v_by = run_variants(d, (b1, b2))
                assert len(set(round(v, 6) for v in v_by.values())) <= 1


def test_hypothesis_falsified_honestly():
    """★ 假设证伪如实: reading 说『原假设错』, caveats 记证伪条目。"""
    p = os.path.join(ROOT, "docs", "partial_seed_probe.json")
    assert os.path.exists(p), "先跑 scripts/probe_partial_seed.py"
    d = json.load(open(p, encoding="utf-8"))
    v = d["verdict"]
    assert v["n_separating_total"] == 0
    assert "n_revealed 恒 12" in v["reading"]
    assert "如实更正当初假设" in v["reading"]
    assert "部分起底假设被证伪" in v["★ 恒等证据"]
    assert any("证伪" in c for c in d["caveats"])


def test_config_untouched_no_tmp_left():
    """配置不动 + 临时 yaml 无残留（R132 同款）。"""
    p = os.path.join(ROOT, "config", "replay.yaml")
    before = open(p, encoding="utf-8").read()
    anch = _anchors()
    ids = list((anch.get("_split") or {}).get("search", []))
    d = build_partial([1.0] * 2, ids, 2)
    run_variants(d, (0.05, 0.05))
    assert open(p, encoding="utf-8").read() == before
    assert not os.path.exists(os.path.join(ROOT, "config",
                                           "_tmp_replay_probe.yaml"))
