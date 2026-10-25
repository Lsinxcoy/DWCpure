"""DWC-AUTO · M0 retrieval accounting: access + event + zero-hit."""
from __future__ import annotations

import json

from dwc.llm.executor import memory_text
from dwc.organs.memory import MemoryKernel, MemoryKind


def _skill(mem: MemoryKernel, scene: str = "查某个符号在哪个文件") -> str:
    return mem.remember(MemoryKind.SKILL, {
        "scene": scene,
        "method": "先搜索定义，再读取文件，最后核对路径",
        "boundary": "success_pattern:code-locate",
        "invalid_conditions": "任务不是代码定位时不适用",
        "recovery_strategies": "失败后按失败签名重新诊断",
    })


def test_memory_text_records_access_and_event(tmp_path):
    mem = MemoryKernel(str(tmp_path / "m.db"))
    nid = _skill(mem)
    text = memory_text(mem, "查某个符号在哪个文件")
    assert text
    node = mem.get(nid)
    assert node.access_count == 1
    st = mem.retrieval_stats()
    assert st["n_retrievals"] == 1
    assert st["n_with_hits"] == 1
    assert st["n_zero"] == 0
    assert st["n_selected"] == 1
    assert st["hit_rate"] == 1.0
    row = mem._conn.execute(
        "SELECT selected_ids FROM memory_retrieval").fetchone()
    assert json.loads(row["selected_ids"]) == [nid]


def test_memory_text_zero_hit_is_recorded(tmp_path):
    mem = MemoryKernel(str(tmp_path / "m.db"))
    nid = _skill(mem)
    assert memory_text(mem, "完全无关的另一个领域的问题") == ""
    assert mem.get(nid).access_count == 0
    st = mem.retrieval_stats()
    assert st["n_retrievals"] == 1
    assert st["n_zero"] == 1
    assert st["hit_rate"] == 0.0
    assert st["n_selected"] == 0


def test_recall_many_records_event_without_double_access(tmp_path):
    mem = MemoryKernel(str(tmp_path / "m.db"))
    nid = mem.remember(MemoryKind.TRACE, {
        "action": "step_0", "task": "查某个符号在哪个文件", "step": 0,
    })
    hits = mem.recall_many("查某个符号在哪个文件", ["step_0"], k=3)
    assert any(h.node_id == nid for h in hits)
    assert mem.get(nid).access_count == 1, "access 只能 +1，事件不得重复计数"
    st = mem.retrieval_stats("recall_many")
    assert st["n_retrievals"] == 1
    assert st["n_with_hits"] == 1


def test_record_retrieval_dedupes_ids(tmp_path):
    mem = MemoryKernel(str(tmp_path / "m.db"))
    nid = _skill(mem)
    mem.record_retrieval("q", "manual", [nid, nid], [0.5, 0.5], touch=True)
    assert mem.get(nid).access_count == 1
    st = mem.retrieval_stats("manual")
    assert st["n_selected"] == 1


def test_retrieval_stats_empty_is_none_not_zero(tmp_path):
    mem = MemoryKernel(str(tmp_path / "m.db"))
    st = mem.retrieval_stats()
    assert st["n_retrievals"] == 0
    assert st["hit_rate"] is None
    assert st["n_bad_rows"] == 0
