"""DWC-AUTO · M2.1 memory edges: adjacency, 2-hop, idempotence, no self-loop."""
from __future__ import annotations

import pytest

from dwc.organs.memory import MemoryError, MemoryKernel, MemoryKind


def _trace(mem, task):
    return mem.remember(MemoryKind.TRACE, {"task": task, "action": "a"})


def test_link_and_neighbors(tmp_path):
    mem = MemoryKernel(str(tmp_path / "m.db"))
    a, b = _trace(mem, "a"), _trace(mem, "b")
    eid = mem.link(a, b, "task_to_failure", weight=0.8, evidence_ref="ev1")
    assert eid.startswith("E_")
    out = mem.neighbors(a)
    assert [x["node"].node_id for x in out] == [b]
    assert out[0]["edge"]["relation"] == "task_to_failure"
    assert out[0]["edge"]["evidence_ref"] == "ev1"


def test_two_hop_and_relation_filter(tmp_path):
    mem = MemoryKernel(str(tmp_path / "m.db"))
    a, b, c = _trace(mem, "a"), _trace(mem, "b"), _trace(mem, "c")
    mem.link(a, b, "r1")
    mem.link(b, c, "r2")
    hops = mem.multi_hop(a, max_depth=2)
    assert [x["node"].node_id for x in hops] == [b, c]
    assert [x["node"].node_id for x in mem.neighbors(a, relation="r1")] == [b]
    assert mem.neighbors(a, relation="r2") == []


def test_link_is_idempotent_and_rejects_self_loop(tmp_path):
    mem = MemoryKernel(str(tmp_path / "m.db"))
    a, b = _trace(mem, "a"), _trace(mem, "b")
    e1 = mem.link(a, b, "r")
    e2 = mem.link(a, b, "r", weight=0.5)
    assert e1 == e2
    n = mem._conn.execute("SELECT COUNT(*) FROM memory_edge").fetchone()[0]
    assert n == 1
    with pytest.raises(MemoryError):
        mem.link(a, a, "r")


def test_link_requires_existing_nodes(tmp_path):
    mem = MemoryKernel(str(tmp_path / "m.db"))
    a = _trace(mem, "a")
    with pytest.raises(MemoryError):
        mem.link(a, "missing", "r")


def test_revise_creates_revises_edge(tmp_path):
    mem = MemoryKernel(str(tmp_path / "m.db"))
    old = mem.remember(MemoryKind.SKILL, {
        "scene": "s", "method": "先读取", "boundary": "success_pattern:x",
        "invalid_conditions": "n/a", "recovery_strategies": "重新诊断",
    })
    new = mem.revise(old, {
        "scene": "s", "method": "先读取再验证", "boundary": "success_pattern:x",
        "invalid_conditions": "n/a", "recovery_strategies": "重新诊断",
    }, source_traj="traj", why="补充验证")
    out = mem.neighbors(new.node_id, relation="revises")
    assert [x["node"].node_id for x in out] == [old]
