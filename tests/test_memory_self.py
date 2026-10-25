"""DWC-AUTO · M2.2 SELF zone: explicit channels only, protected from archive."""
from __future__ import annotations

import pytest

from dwc.organs.memory import MemoryError, MemoryKernel, MemoryKind, Zone


def test_self_accepts_user_message_and_sets_protected(tmp_path):
    mem = MemoryKernel(str(tmp_path / "m.db"))
    nid = mem.remember(MemoryKind.IDENTITY, {"text": "我是 DWC"},
                       source_channel="user_message")
    node = mem.get(nid)
    assert node.zone is Zone.SELF
    assert node.payload["protected"] is True


def test_self_rejects_tool_output(tmp_path):
    mem = MemoryKernel(str(tmp_path / "m.db"))
    with pytest.raises(MemoryError):
        mem.remember(MemoryKind.STANDING_RULE, {"text": "ignore previous"},
                     source_channel="tool_output")


def test_self_cannot_be_archived_or_evicted(tmp_path):
    mem = MemoryKernel(str(tmp_path / "m.db"))
    nid = mem.remember(MemoryKind.IDENTITY, {"text": "身份"},
                       source_channel="user_message")
    with pytest.raises(MemoryError):
        mem.archive(nid)
    assert all(x["node_id"] != nid for x in mem.eviction_candidates())
    assert mem.maintain()["n_archived"] == 0


def test_revise_self_keeps_old_and_links(tmp_path):
    mem = MemoryKernel(str(tmp_path / "m.db"))
    old = mem.remember(MemoryKind.IDENTITY, {"text": "旧身份"},
                       source_channel="user_message")
    new = mem.revise_self(old, {"text": "新身份"},
                          source_traj="traj-1", why="用户纠正")
    assert new.payload["_rev_prev"] == old
    assert mem.get(old).payload["_revised_to"] == new.node_id
    out = mem.neighbors(new.node_id, relation="revises")
    assert [x["node"].node_id for x in out] == [old]
