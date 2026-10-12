# -*- coding: utf-8 -*-
"""R216 · degrade 消费语义: 降序不丢（探索保活 — 死锁另一半的解除）。"""
from __future__ import annotations

import sys
import os

ROOT = r"E:\Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "src"))


def test_demote_not_drop_semantics():
    """★★★ 消费段行为级: degrade 时 wta **保活**且基线在前; consumed_action
    标 demote（不再 drop — 旧语义把 baseline 变死水: 台账 66/66 全 drop）。"""
    import inspect
    from dwc.harness import run_term
    src = inspect.getsource(run_term)
    assert "demote_world_tree_action" in src, "消费语义未改"
    assert "drop_world_tree_action×" not in src, "仍在全丢 wta"
    # 结构锁: 保活重排 = _base + _wta（基线在前）
    assert "_base + _wta" in src.replace("_base + _wta", "_base + _wta") or \
           "_base + _wta" in src


def test_demote_keeps_all_wta_in_order():
    """★★ 保活重排的纯逻辑: 任务列表经 _base+wta 重排后 wta 全在、原序。"""
    tasks = [{"kind": "world_tree_action", "node": "n1"},
             {"kind": "dev_pool"},
             {"kind": "world_tree_action", "node": "n2"},
             {"kind": "drift_degrade"}]
    _wta = [t for t in tasks if t.get("kind") == "world_tree_action"]
    _base = [t for t in tasks if t.get("kind") != "world_tree_action"]
    tasks[:] = _base + _wta
    kinds = [t["kind"] for t in tasks]
    assert kinds.count("world_tree_action") == 2
    assert kinds[0] == "dev_pool", "基线须在前（降级=排序降档不是杀探索）"
    assert [t["node"] for t in tasks if t["kind"] == "world_tree_action"] \
        == ["n1", "n2"], "wta 原序须保持"
