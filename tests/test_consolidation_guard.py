"""DWC-AUTO · M1.8 consolidation guard: originals survive revise/dream/learn."""
from __future__ import annotations

import copy
import json

from dwc.organs.memory import MemoryKernel, MemoryKind


def _skill(mem):
    return mem.remember(MemoryKind.SKILL, {
        "scene": "定位代码符号", "method": "先搜索定义，再读取文件",
        "boundary": "success_pattern:code",
        "invalid_conditions": "非代码定位不适用",
        "recovery_strategies": "失败后重新诊断",
    })


def test_revise_keeps_original_content_and_adds_pointer(tmp_path):
    mem = MemoryKernel(str(tmp_path / "m.db"))
    old_id = _skill(mem)
    before = copy.deepcopy(mem.get(old_id).payload)
    new = mem.revise(old_id, {
        "scene": "定位代码符号", "method": "先搜索定义，再读取文件，再核对行号",
        "boundary": "success_pattern:code",
        "invalid_conditions": "非代码定位不适用",
        "recovery_strategies": "失败后重新诊断",
    }, source_traj="traj-1", why="补充行号")
    old_after = mem.get(old_id)
    assert old_after.payload["_revised_to"] == new.node_id
    # 除新增指针外，原内容字段逐字不变
    for key, value in before.items():
        assert old_after.payload[key] == value
    assert new.payload["_rev_prev"] == old_id


def test_dream_does_not_write_or_change_access(tmp_path):
    mem = MemoryKernel(str(tmp_path / "m.db"))
    nid = mem.remember(MemoryKind.FAILURE_SIGNATURE,
                       {"c": "E_VALUE", "q": "wrong", "m": "off_by_one",
                        "detail": "边界少一"})
    before = mem.usage_stats()
    out = mem.dream("E_VALUE", "wrong", "off_by_one")
    assert out["n_members"] == 1
    assert mem.usage_stats() == before
    assert mem.get(nid).access_count == 0


def test_learn_changes_importance_not_payload(tmp_path):
    mem = MemoryKernel(str(tmp_path / "m.db"))
    nid = mem.remember(MemoryKind.TRACE, {"task": "t", "action": "a"})
    before = json.dumps(mem.get(nid).payload, ensure_ascii=False, sort_keys=True)
    mem._conn.execute(
        "UPDATE memory_node SET access_count=2, effect_count=1 WHERE node_id=?",
        (nid,))
    mem._conn.commit()
    mem.learn([nid])
    after = json.dumps(mem.get(nid).payload, ensure_ascii=False, sort_keys=True)
    assert after == before
