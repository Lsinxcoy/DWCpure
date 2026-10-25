"""DWC-AUTO · M2.3 preference/belief: support/contradiction, no overwrite."""
from __future__ import annotations

from dwc.organs.memory import MemoryKernel, MemoryKind
from dwc.organs.preference import (
    latest_preference, observe_preference, revise_belief,
)


def test_preference_same_stance_supports(tmp_path):
    mem = MemoryKernel(str(tmp_path / "m.db"))
    a = observe_preference(mem, "报告风格", "简洁", "u1")
    b = observe_preference(mem, "报告风格", "简洁", "u2")
    assert a["support_count"] == 1
    assert b["support_count"] == 2
    assert latest_preference(mem, "报告风格")["payload"]["support_count"] == 2
    assert b["supersedes"] == a["node_id"]


def test_preference_different_stance_counts_contradiction(tmp_path):
    mem = MemoryKernel(str(tmp_path / "m.db"))
    a = observe_preference(mem, "报告风格", "简洁", "u1")
    b = observe_preference(mem, "报告风格", "详细", "u2")
    assert b["contradict_count"] == 1
    assert mem.get(a["node_id"]).payload["stance"] == "简洁"
    assert mem.neighbors(b["node_id"], relation="supersedes")


def test_revise_belief_keeps_old_and_links(tmp_path):
    mem = MemoryKernel(str(tmp_path / "m.db"))
    old = mem.remember(MemoryKind.BELIEF, {
        "topic": "部署窗口", "stance": "周末", "confidence": 0.6,
        "evidence_refs": ["u1"], "support_count": 1, "contradict_count": 0,
    }, source_channel="user_message")
    out = revise_belief(mem, old, "工作日", "u2", confidence=0.8)
    assert out["contradict_count"] == 1
    assert mem.get(old).payload["_revised_to"] == out["node_id"]
    new = mem.get(out["node_id"])
    assert new.payload["_rev_prev"] == old
    assert new.payload["confidence"] == 0.8
    assert mem.neighbors(out["node_id"], relation="revises")
