"""H1/H3/H4 · DWC pure 记忆数据契约：类型、时间、证据、失效。"""
from __future__ import annotations

import json
import time

import pytest

from dwc.llm.executor import memory_text
from dwc.organs.memory import (
    MemoryError, MemoryKernel, MemoryKind, Zone,
)


def _skill(mem, scene="定位代码符号", method="先搜索定义，再读取文件"):
    return mem.remember(MemoryKind.SKILL, {
        "scene": scene, "method": method,
        "boundary": "success_pattern:code",
        "invalid_conditions": "非代码定位不适用",
        "recovery_strategies": "失败后重新诊断",
        "src_key": "test:%s" % method,
    })


def test_defaults_are_backward_compatible(tmp_path):
    mem = MemoryKernel(str(tmp_path / "m.db"))
    nid = _skill(mem)
    n = mem.get(nid)
    assert n.derived_kind == "procedure"
    assert n.status == "active"
    assert n.proof_count == 1
    assert n.source_ids == ()
    assert n.valid_from is not None
    assert n.valid_to is None


def test_reference_requires_claim_and_evidence(tmp_path):
    mem = MemoryKernel(str(tmp_path / "m.db"))
    with pytest.raises(MemoryError, match="claim"):
        mem.remember(MemoryKind.REFERENCE, {"source_ids": ["task:1"]})
    with pytest.raises(MemoryError, match="source_ids"):
        mem.remember(MemoryKind.REFERENCE, {"claim": "pytest -q"})
    nid = mem.remember(MemoryKind.REFERENCE, {
        "claim": "测试命令是 pytest -q",
        "source_ids": ["task:1"],
        "observed_at": time.time(),
    })
    n = mem.get(nid)
    assert n.kind is MemoryKind.REFERENCE
    assert n.zone is Zone.REFERENCE
    assert n.derived_kind == "fact"
    assert n.proof_count == 1


def test_supersede_hides_old_from_recall_but_keeps_history(tmp_path):
    mem = MemoryKernel(str(tmp_path / "m.db"))
    old = _skill(mem, "定位代码符号", "先搜索定义，再读取文件")
    new = _skill(mem, "定位代码符号", "先搜索定义，再读取文件，最后核对行号")
    mem.supersede(old, new, at=time.time())
    assert mem.get(old).status == "superseded"
    assert mem.get(old).valid_to is not None
    assert old in mem.get(new).supersedes
    got = [n.node_id for n in mem.recall_search("定位代码符号", k=10)]
    assert new in got
    assert old not in got
    # 历史时刻仍可查旧节点（as_of 落在旧节点有效期内）
    _old = mem.get(old)
    assert _old.valid_from is not None and _old.valid_to is not None
    _mid = (float(_old.valid_from) + float(_old.valid_to)) / 2.0
    hist = [n.node_id for n in mem.recall_search(
        "定位代码符号", k=10, as_of=_mid)]
    assert old in hist


def test_valid_to_filters_prompt(tmp_path):
    mem = MemoryKernel(str(tmp_path / "m.db"))
    nid = _skill(mem, "定位代码符号")
    assert "先搜索定义" in memory_text(mem, "定位代码符号")
    mem._conn.execute(
        "UPDATE memory_node SET valid_to=? WHERE node_id=?",
        (time.time() - 1, nid))
    mem._conn.commit()
    assert memory_text(mem, "定位代码符号") == ""


def test_candidate_status_is_not_injected(tmp_path):
    mem = MemoryKernel(str(tmp_path / "m.db"))
    nid = _skill(mem, "定位代码符号")
    mem._conn.execute(
        "UPDATE memory_node SET status='candidate' WHERE node_id=?", (nid,))
    mem._conn.commit()
    assert memory_text(mem, "定位代码符号") == ""


def test_memory_stats_reports_contract(tmp_path):
    mem = MemoryKernel(str(tmp_path / "m.db"))
    _skill(mem)
    mem.remember(MemoryKind.REFERENCE, {
        "claim": "pytest -q", "source_ids": ["task:1"]})
    st = mem.memory_stats()
    assert st["n_nodes"] == 2
    assert st["by_kind"]["skill"] == 1
    assert st["by_kind"]["reference"] == 1
    assert st["by_derived_kind"]["procedure"] == 1
    assert st["by_derived_kind"]["fact"] == 1
    assert st["n_valid"] == 2
    assert st["n_stale"] == 0
    assert st["n_reference"] == 1


def test_proof_count_is_derived_from_source_ids(tmp_path):
    mem = MemoryKernel(str(tmp_path / "m.db"))
    nid = mem.remember(MemoryKind.REFERENCE, {
        "claim": "pytest -q",
        "source_ids": ["task:1", "task:2", "task:1"],
        "proof_count": 99,
    })
    assert mem.get(nid).proof_count == 2
    assert json.loads(mem._conn.execute(
        "SELECT source_ids FROM memory_node WHERE node_id=?",
        (nid,)).fetchone()[0]) == ["task:1", "task:2"]
