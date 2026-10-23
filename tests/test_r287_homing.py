# -*- coding: utf-8 -*-
"""R287-E · 新锚归位（load_groups_with_homing）契约测试。

★★★ 存在理由
  anchors（守门人）的新锚带自带 category，但 sealed 组表滞后 ⇒ 直挂 root
  artifact 组 ⇒ dream 组结构假分化（R133/R134 意图被打破）。
  归位函数是生产播种/脚本分组的共用真相源 —— 无测试即裸奔。
"""
from __future__ import annotations

import os
import sys

import pytest  # noqa: F401

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.core import load_groups_with_homing  # noqa: E402


def test_homing_puts_new_anchors_in_category_group():
    """★★ 归位：007-009（category=code_repair）进 code_repair 组。"""
    g = load_groups_with_homing()
    assert {"code_fix_007", "code_fix_008", "code_fix_009"} <= set(
        g["code_repair"]), g["code_repair"]
    assert len(g["code_repair"]) == 9


def test_homing_does_not_touch_yaml_source():
    """★★ 归位只返回副本 —— yaml 文件本身不动（G1 真相源 intact）。"""
    import yaml
    import io
    p = os.path.join(ROOT, "config", "capability_groups.yaml")
    obj = yaml.safe_load(io.open(p, encoding="utf-8").read())
    code_repair = [g for g in obj["groups"]
                   if g["group_id"] == "code_repair"][0]
    assert code_repair["sealed_task_ids"] == [
        "code_fix_001", "code_fix_002", "code_fix_003",
        "code_fix_004", "code_fix_005", "code_fix_006"]


def test_homing_unknown_category_left_alone(tmp_path):
    """★★ category 无对应组 ⇒ 不归位（seed 直挂降级语义不变）。"""
    import json
    dev = {"code_fix_001": {"category": "code_repair"},
           "zzz_odd": {"category": "no_such_group"},
           "_split": {}}
    ap = str(tmp_path / "dev.json")
    open(ap, "w", encoding="utf-8").write(json.dumps(dev))
    g = load_groups_with_homing(
        anchors_path=ap)
    assert "zzz_odd" not in {t for m in g.values() for t in m}
    assert "code_fix_001" in g["code_repair"]


def test_homing_unreadable_anchors_falls_back_to_pure_groups(tmp_path):
    """★★ anchors 不可读 ⇒ 纯组表（不炸，降级可观测）。"""
    g = load_groups_with_homing(
        anchors_path=str(tmp_path / "nope.json"))
    assert g["code_repair"] == [
        "code_fix_001", "code_fix_002", "code_fix_003",
        "code_fix_004", "code_fix_005", "code_fix_006"]


def test_homing_rejects_bad_path_loudly():
    """★★★ 坏组表路径必须大声 raise（raises 配额 — 不许静默降级）。"""
    with pytest.raises(Exception):
        load_groups_with_homing(path=r"Z:\no\such\groups.yaml")
