# -*- coding: utf-8 -*-
"""多组件 recovery journal/outbox 测试；只使用 tmp_path。"""
from __future__ import annotations

import hashlib
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.organs import evo_targets as ET  # noqa: E402
from dwc.harness.recovery_journal import RecoveryJournal  # noqa: E402


@pytest.fixture()
def sandbox(tmp_path, monkeypatch):
    monkeypatch.setattr(ET, "ROOT", str(tmp_path))
    return tmp_path


def _sha(value):
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def test_commit_sorts_targets_hashes_and_publishes_canary(sandbox):
    journal_path = sandbox / "var" / "recovery.jsonl"
    journal = RecoveryJournal(str(journal_path))

    out = journal.apply({
        "output_plumbing": {"max_answer_chars": 7000},
        "context_mgmt": {"read_default_lines": 300},
    })

    assert out["state"] == "committed"
    assert [t["component"] for t in out["targets"]] == [
        "context_mgmt", "output_plumbing"]
    for target in out["targets"]:
        assert target["before_hash"] == _sha(target["before"])
        assert target["after_hash"] == _sha(target["after"])
        assert target["state"] == "committed"
    assert journal.canary(out["transaction_id"]) == {
        "context_mgmt": ET.read("context_mgmt"),
        "output_plumbing": ET.read("output_plumbing"),
    }
    persisted = json.loads(journal_path.read_text(encoding="utf-8").splitlines()[-1])
    assert persisted["state"] == "committed"


def test_failed_component_rolls_back_entire_transaction(sandbox):
    existing = sandbox / "config" / "context_policy.json"
    existing.parent.mkdir()
    existing.write_text(json.dumps({"read_default_lines": 200}), encoding="utf-8")
    journal = RecoveryJournal(str(sandbox / "var" / "recovery.json"))
    txid = None
    try:
        journal.apply({
            "context_mgmt": {"read_default_lines": 300},
            "output_plumbing": {"max_answer_chars": 1},
        })
    except ET.TargetError:
        pass
    else:
        pytest.fail("无效组件必须失败")

    record = json.loads((sandbox / "var" / "recovery.json").read_text(
        encoding="utf-8"))
    txid = record["transaction_id"]
    assert record["state"] == "rolled_back"
    assert json.loads(existing.read_text(encoding="utf-8"))[
        "read_default_lines"] == 200
    assert not (sandbox / "config" / "output_policy.json").exists()
    with pytest.raises(Exception, match="committed"):
        journal.canary(txid)


def test_recover_applying_transaction_restores_all_targets(sandbox):
    paths = {
        "context_mgmt": sandbox / "config" / "context_policy.json",
        "output_plumbing": sandbox / "config" / "output_policy.json",
    }
    paths["context_mgmt"].parent.mkdir()
    paths["context_mgmt"].write_text(json.dumps({
        "read_default_lines": 200, "search_limit": 60}), encoding="utf-8")
    paths["output_plumbing"].write_text(json.dumps({
        "max_answer_chars": 6000}), encoding="utf-8")
    original_bytes = {key: path.read_bytes() for key, path in paths.items()}
    journal = RecoveryJournal(str(sandbox / "var" / "recovery.json"))

    real_save = journal._save
    def crash_before_commit(record):
        real_save(record)
        if len(record["targets"]) == 2 and record["state"] == "applying":
            raise RuntimeError("simulated crash")
    journal._save = crash_before_commit
    # 模拟硬崩溃：本进程不再执行异常清理，只留下 applying outbox。
    journal.rollback = lambda record: record
    with pytest.raises(RuntimeError, match="simulated crash"):
        journal.apply({
            "context_mgmt": {"read_default_lines": 300},
            "output_plumbing": {"max_answer_chars": 7000},
        })

    recovered = RecoveryJournal(str(sandbox / "var" / "recovery.json")).recover()
    assert recovered["state"] == "rolled_back"
    for key, path in paths.items():
        assert path.read_bytes() == original_bytes[key]
    with pytest.raises(Exception, match="committed"):
        journal.canary(recovered["transaction_id"])


def test_crash_before_any_target_write_needs_no_undo(sandbox):
    journal_path = sandbox / "var" / "recovery.json"
    journal_path.parent.mkdir()
    record = {"transaction_id": "tx-empty", "state": "applying", "targets": []}
    journal_path.write_text(json.dumps(record), encoding="utf-8")

    recovered = RecoveryJournal(str(journal_path)).recover()
    assert recovered["state"] == "rolled_back"


def test_undo_is_persisted_before_first_target_write(sandbox, monkeypatch):
    journal_path = sandbox / "var" / "recovery.json"
    journal_path.parent.mkdir()
    journal_path.write_text(json.dumps({
        "transaction_id": "tx-empty", "state": "applying", "targets": []
    }), encoding="utf-8")
    journal = RecoveryJournal(str(journal_path))

    def fail_if_no_undo(component, patch, backup_dir=""):
        record = json.loads(journal_path.read_text(encoding="utf-8"))
        assert len(record["targets"]) == 2
        assert all(t["state"] == "applying" for t in record["targets"])
        assert all("backup" in t and "created" in t for t in record["targets"])
        raise RuntimeError("stop before first write")
    monkeypatch.setattr(ET, "apply", fail_if_no_undo)

    with pytest.raises(RuntimeError, match="stop before first write"):
        journal.apply({
            "context_mgmt": {"read_default_lines": 300},
            "output_plumbing": {"max_answer_chars": 7000},
        })
    assert not (sandbox / "config" / "context_policy.json").exists()
    assert not (sandbox / "config" / "output_policy.json").exists()
