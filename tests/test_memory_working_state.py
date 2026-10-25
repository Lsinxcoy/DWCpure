"""DWC-AUTO · M1.7 working state: done requires environment evidence."""
from __future__ import annotations

from dwc.organs.memory import MemoryKernel, MemoryKind
from dwc.organs.working_state import check_update, propose_update


def test_done_without_evidence_is_bounced():
    v = check_update("g1", "done", evidence=[])
    assert v["passed"] is False
    assert v["code"] == "truth_bounce_no_env_evidence"


def test_done_with_evidence_passes():
    v = check_update("g1", "done", evidence=["pytest: 3 passed"])
    assert v["passed"] is True and v["code"] == "ok"


def test_blocked_without_blocker_is_bounced():
    v = check_update("g1", "blocked", evidence=[])
    assert v["passed"] is False
    assert v["code"] == "blocked_without_blocker"


def test_claim_without_evidence_is_bounced():
    v = check_update("g1", "active", evidence=[], claimed=True)
    assert v["passed"] is False
    assert v["code"] == "claim_without_evidence"


def test_propose_writes_working_state(tmp_path):
    mem = MemoryKernel(str(tmp_path / "m.db"))
    v = propose_update(mem, "g1", "done", evidence=["read: a.py"],
                       claimed=True)
    assert v["passed"] is True and v["written"]
    node = mem.get(v["written"])
    assert node.kind is MemoryKind.WORKING_STATE
    assert node.payload["goal_id"] == "g1"
    assert node.payload["evidence"] == ["read: a.py"]


def test_propose_failed_does_not_write(tmp_path):
    mem = MemoryKernel(str(tmp_path / "m.db"))
    v = propose_update(mem, "g1", "done", evidence=[])
    assert v["written"] is None
    assert mem.usage_stats()["total"] == 0
