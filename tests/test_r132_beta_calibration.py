# -*- coding: utf-8 -*-
"""R132 · β 校准探针 — 恒等的第二根因（系数退化）坐实。

验收:
  □ β=0 全组合全退化（v_distinct<=1）— 系数根因坐实
  □ β₂ 非零也仍退化 ⇒ N/k 在注入树里对所有 spec 相同（第二根因）
  □ 探针不改 config/replay.yaml（校准纪律 — 注释明示非零须协议后才写）
  □ 临时 yaml 走 dc.REPLAY_PATH 换 + finally 恢复（不留垃圾文件）
  □ verdict 如实: 有分化⇒列边界; 无分化⇒说明"还受树形约束"
"""
from __future__ import annotations

import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from probe_beta_calibration import (  # noqa: E402
    _anchors, build_tree, run_variants)


def test_beta0_all_degenerate():
    """★ β=0（当前配置）⇒ 所有树族全退化（v 全恒等）。"""
    ids = list((_anchors().get("_split") or {}).get("search", []))
    n = len(ids)
    for plan in ([1.0] * n, [0.0] + [1.0] * (n - 1), [0.0] * n):
        d = build_tree(plan, ids)
        v_by = run_variants(d, (0.0, 0.0))
        assert len(set(round(v, 6) for v in v_by.values())) <= 1


def test_beta2_nonzero_still_degenerate():
    """β₂≠0 仍退化 ⇒ N/k 对所有 spec 相同（起底耗尽揭示面）。"""
    ids = list((_anchors().get("_split") or {}).get("search", []))
    n = len(ids)
    d = build_tree([0.0] + [1.0] * (n - 1), ids)
    v_by = run_variants(d, (0.0, 0.05))
    assert len(set(round(v, 6) for v in v_by.values())) <= 1


def test_config_not_modified_by_probe():
    """★ 纪律: 探针跑完 config/replay.yaml 原样（非零不许擅写）。"""
    p = os.path.join(ROOT, "config", "replay.yaml")
    before = open(p, encoding="utf-8").read()
    ids = list((_anchors().get("_split") or {}).get("search", []))
    n = len(ids)
    d = build_tree([1.0] * min(3, n), ids)
    run_variants(d, (0.05, 0.1))
    after = open(p, encoding="utf-8").read()
    assert before == after
    # 临时 yaml 也被 finally 清掉（不留垃圾）
    assert not os.path.exists(os.path.join(ROOT, "config",
                                           "_tmp_replay_probe.yaml"))


def test_probe_doc_structure():
    """文档须含 36 组合 + verdict 双根因解读。"""
    p = os.path.join(ROOT, "docs", "beta_calibration.json")
    assert os.path.exists(p), "先跑 scripts/probe_beta_calibration.py"
    d = json.load(open(p, encoding="utf-8"))
    assert d["n_results"] == 36            # 3 树 × 12 β 组合
    assert d["current_config"] == {"beta1": 0.0, "beta2": 0.0}
    v = d["verdict"]
    assert v["beta0_always_degenerate"] is True
    assert v["n_separating_combos"] == 0
    assert "系数根因" in v["reading"]
    # 校准纪律写进 caveats
    assert any("不改 config/replay.yaml" in c for c in d["caveats"])


def test_no_tmp_yaml_left_behind_on_failure():
    """★ 即使 dream 抛异常, tmp yaml 也必须清（finally 纪律）。"""
    ids = list((_anchors().get("_split") or {}).get("search", []))
    d = build_tree([], ids)             # 空注入也应不炸 finally
    run_variants(d, (0.1, 0.0))
    assert not os.path.exists(os.path.join(ROOT, "config",
                                           "_tmp_replay_probe.yaml"))
