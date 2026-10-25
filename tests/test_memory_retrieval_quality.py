"""DWC-AUTO · M2.5 retrieval quality: MRR/NDCG only with labels."""
from __future__ import annotations

from dwc.organs.memory import MemoryKernel


def test_retrieval_quality_without_labels_is_none(tmp_path):
    mem = MemoryKernel(str(tmp_path / "m.db"))
    out = mem.retrieval_quality()
    assert out["n_labeled"] == 0
    assert out["mrr"] is None and out["ndcg"] is None


def test_retrieval_quality_mrr_and_ndcg(tmp_path):
    mem = MemoryKernel(str(tmp_path / "m.db"))
    mem.record_retrieval("q", "skill_prompt", ["a", "b"], touch=False)
    out = mem.retrieval_quality({"q": ["b"]})
    assert out["n_labeled"] == 1
    assert out["mrr"] == 0.5
    assert 0.0 < out["ndcg"] < 1.0
    out2 = mem.retrieval_quality({"q": ["a"]})
    assert out2["mrr"] == 1.0
    assert out2["ndcg"] == 1.0


def test_unmatched_labels_do_not_invent_score(tmp_path):
    mem = MemoryKernel(str(tmp_path / "m.db"))
    out = mem.retrieval_quality({"other": ["x"]})
    assert out["n_labeled"] == 0
    assert out["mrr"] is None
