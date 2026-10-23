# -*- coding: utf-8 -*-
"""R104 · 阶段 2d — 技能卡双字段（PRACTICE）+ τ 近重复合并（PAHF）+ 治理报表。

判据:
  · D6 门槛加严 = SKILL 必含 invalid_conditions/recovery_strategies（写入时判）
  · 合并 = 经验域去重语义（ratio≥MERGE_TAU）; TRACE 不参与; 内容级摘要=留位
  · 报表 = 事实标记（access>0∧effect==0）非阈值; 行为级变更留裁决（显式字段）
"""
from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.organs.memory import (  # noqa: E402
    EXPERIENCE_REQUIREMENTS, MERGE_TAU, MemoryError, MemoryKind,
    MemoryKernel)


def _mem(tmp_path) -> MemoryKernel:
    return MemoryKernel(db_path=str(tmp_path / "m.db"))


def test_skill_requires_dual_fields_d6(tmp_path):
    """D6: SKILL 缺 invalid_conditions / recovery_strategies ⇒ 拒。"""
    mem = _mem(tmp_path)
    base = {"scene": "s", "method": "m", "boundary": "b"}
    for miss in ("invalid_conditions", "recovery_strategies"):
        payload = dict(base)
        payload[miss] = None
        with pytest.raises(MemoryError, match="D6"):
            mem.remember(MemoryKind.SKILL, payload)
    ok = dict(base, invalid_conditions=["no_cast"], recovery_strategies=["retry"])
    nid = mem.remember(MemoryKind.SKILL, ok)
    assert mem.get(nid).payload["invalid_conditions"] == ["no_cast"]
    # requirements 真源含五字段（防回退）
    assert len(EXPERIENCE_REQUIREMENTS[MemoryKind.SKILL]) == 5


def test_near_duplicate_merges_experience(tmp_path):
    """τ 合并: 同 kind 近重复 ⇒ 库里仍 1 条; 明显不同 ⇒ 2 条。"""
    mem = _mem(tmp_path)
    p = {"scene": "edit", "method": "use_diff", "boundary": "small",
         "invalid_conditions": ["conflict"], "recovery_strategies": ["manual"]}
    a = mem.remember(MemoryKind.SKILL, dict(p))
    b = mem.remember(MemoryKind.SKILL, dict(p))          # 完全重复 ⇒ 合并
    assert a == b, "近重复返回现节点（去重语义）"
    n = mem._conn.execute("SELECT COUNT(*) AS n FROM memory_node"
                          " WHERE kind='skill'").fetchone()["n"]
    assert n == 1, "完全重复不新增（PAHF 第三步防膨胀）"
    # 明显不同 payload ⇒ 2 条
    q = dict(p, method="rewrite_everything_from_scratch_completely",
             scene="totally_other_domain_architecture_rebuild")
    c = mem.remember(MemoryKind.SKILL, q)
    n2 = mem._conn.execute("SELECT COUNT(*) AS n FROM memory_node"
                           " WHERE kind='skill'").fetchone()["n"]
    assert c != a and n2 == 2, "非近重复不合并"
    assert 0 < MERGE_TAU < 1


def test_near_duplicate_not_applied_to_trace(tmp_path):
    """TRACE 不参与合并（经验域限定 — 噪声记录不 dedup）。"""
    mem = _mem(tmp_path)
    a = mem.remember(MemoryKind.TRACE, {"action": "step_0"})
    b = mem.remember(MemoryKind.TRACE, {"action": "step_0"})
    assert a != b, "trace 相同也各记各的（合并只限 EXPERIENCE）"


def test_contribution_report_flags_and_leaves_behavior(tmp_path):
    """治理报表: 访问过零效果的事实标记 + 行为级变更显式留裁决。"""
    mem = _mem(tmp_path)
    nid = mem.remember(MemoryKind.TRACE, {"action": "x"})
    mem.recall(nid)                       # access+1, effect 不动
    rep = mem.contribution_report()
    assert rep["n_nodes"] == 1
    assert rep["n_accessed_no_effect"] == 1
    row = next(i for i in rep["items"] if i["node_id"] == nid)
    assert row["access"] == 1 and row["effect"] == 0
    assert row["no_effect_flag"] is True
    # 行为级留位（不默认开退役/封顶）
    assert rep["behavioral_changes"] == "left_for_verdict"
    # 归档节点不 flag
    mem.maintain() if hasattr(mem, "maintain") else None
