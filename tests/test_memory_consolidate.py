"""H5 · 离线 consolidation：近重复合并、证据门槛、原节点保留。"""
from __future__ import annotations

import time

from dwc.organs import consolidate as C
from dwc.organs.memory import MemoryKernel, MemoryKind


def _skill(mem, tag, source):
    return mem.remember(MemoryKind.SKILL, {
        "scene": "定位代码符号",
        "method": "先搜索定义，再读取文件，最后核对行号",
        "boundary": "success_pattern:code",
        "invalid_conditions": "非代码定位不适用",
        "recovery_strategies": "失败后重新诊断",
        "src_key": tag,
        "source_ids": [source],
        "observed_at": time.time(),
    })


def test_plan_merges_near_duplicates_with_two_sources(tmp_path):
    mem = MemoryKernel(str(tmp_path / "m.db"))
    a = _skill(mem, "A", "task:A")
    b = _skill(mem, "B", "task:B")
    rep = C.plan(mem)
    assert rep["n_actions"] == 1
    act = rep["actions"][0]
    assert set(act["node_ids"]) == {a, b}
    assert act["proof_count"] == 2
    assert act["action"] == "merge"


def test_apply_keeps_originals_and_links_supersedes(tmp_path):
    mem = MemoryKernel(str(tmp_path / "m.db"))
    a = _skill(mem, "A", "task:A")
    b = _skill(mem, "B", "task:B")
    rep = C.apply(mem)
    assert len(rep["written"]) == 1
    new = rep["written"][0]["new_id"]
    n = mem.get(new)
    assert n.proof_count == 2
    assert set(n.source_ids) == {"task:A", "task:B"}
    assert set(n.supersedes) == {a, b}
    assert mem.get(a).status == "superseded"
    assert mem.get(b).status == "superseded"
    # 原节点仍在库（历史可查）
    assert mem.get(a).payload["scene"] == "定位代码符号"
    # 当前召回只剩新节点
    got = [x.node_id for x in mem.recall_search("定位代码符号", k=10)]
    assert new in got and a not in got and b not in got


def test_apply_is_idempotent(tmp_path):
    mem = MemoryKernel(str(tmp_path / "m.db"))
    _skill(mem, "A", "task:A")
    _skill(mem, "B", "task:B")
    C.apply(mem)
    rep2 = C.apply(mem)
    assert rep2["written"] == []
    assert rep2["plan"]["n_actions"] == 0


def test_single_source_is_not_merged(tmp_path):
    mem = MemoryKernel(str(tmp_path / "m.db"))
    for tag in ("A", "B"):
        mem.remember(MemoryKind.REFERENCE, {
            "claim": "测试命令是 pytest -q",
            "topic": "测试命令",
            "src_key": tag,
            "source_ids": ["task:same"],
        })
    rep = C.plan(mem)
    assert rep["n_actions"] == 1
    assert rep["actions"][0]["action"] == "skip"
    assert rep["actions"][0]["why"] == "insufficient_evidence"
    out = C.apply(mem)
    assert out["written"] == []
