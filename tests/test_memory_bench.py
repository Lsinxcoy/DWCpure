"""DWC-AUTO · MEM-18 lexical benchmark baseline; no vector dependency."""
from __future__ import annotations

from dwc.organs.memory import MemoryKernel, MemoryKind
from dwc.organs.memory_bench import bench


def test_bench_hits_labeled_trace(tmp_path):
    mem = MemoryKernel(str(tmp_path / "m.db"))
    nid = mem.remember(MemoryKind.TRACE,
                       {"task": "alpha symbol", "action": "read"})
    out = bench(mem, {"alpha symbol": [nid]}, k=3)
    assert out["n_queries"] == 1
    assert out["hit_rate"] == 1.0
    assert out["mrr"] == 1.0
    assert out["ndcg"] == 1.0
    assert "no embedding" in out["note"]


def test_bench_without_labels_is_none(tmp_path):
    mem = MemoryKernel(str(tmp_path / "m.db"))
    out = bench(mem, {}, k=3)
    assert out["n_queries"] == 0
    assert out["hit_rate"] is None and out["mrr"] is None
