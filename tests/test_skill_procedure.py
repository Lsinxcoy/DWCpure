"""DWC-AUTO · M1.2 procedure fields from real actions_log; no invented steps."""
from __future__ import annotations

import json

from dwc.organs.memory import MemoryKernel
from dwc.organs.skill_writer import (
    from_task_result, from_term, procedure_from_actions, result_verified,
)


def _result():
    return {
        "task_id": "T_proc",
        "status": "done",
        "answer": "先读取文件，再运行测试验证",
        "trajectory_ref": "C:/var/trajectories/T_proc.jsonl#TRJ_1",
        "actions_log": [
            {"round": 1, "phase": "obs", "op": "read",
             "target": "a.py", "ok": True, "obs": "SECRET_BODY"},
            {"round": 1, "phase": "obs", "op": "run",
             "target": "pytest -q", "ok": True, "obs": "3 passed"},
            {"round": 2, "phase": "obs", "op": "run",
             "target": "pytest -q", "ok": False, "obs": "1 failed"},
            {"round": 2, "phase": "obs", "op": "final",
             "target": "", "ok": True, "obs": "done"},
        ],
    }


def test_procedure_extracts_only_real_actions():
    p = procedure_from_actions(_result()["actions_log"], "ref-1")
    assert [s["op"] for s in p["steps"]] == ["read", "run", "run"]
    assert p["tools"] == ["read", "run"]
    assert len(p["verification"]) == 1
    assert len(p["failure_modes"]) == 1
    assert p["evidence_ref"] == "ref-1"
    assert p["procedure_status"] == "observed"
    assert p["preconditions"] == []


def test_from_task_result_writes_procedure_and_refs(tmp_path):
    mem = MemoryKernel(str(tmp_path / "m.db"))
    nid = from_task_result(mem, "t1", "实现 f", _result(), passed=True)
    assert nid
    node = mem.get(nid)
    p = node.payload if isinstance(node.payload, dict) else json.loads(node.payload)
    assert p["skill_kind"] == "procedural"
    assert p["procedure_status"] == "observed"
    assert len(p["steps"]) == 3
    assert p["evidence_ref"].endswith("#TRJ_1")
    assert "SECRET_BODY" not in json.dumps(p, ensure_ascii=False)


def test_from_task_result_without_actions_does_not_invent(tmp_path):
    mem = MemoryKernel(str(tmp_path / "m.db"))
    assert from_task_result(mem, "t1", "实现 f",
                            {"task_id": "t", "answer": "答案",
                             "actions_log": []}, passed=True) is None


def test_from_term_without_procedure_is_not_instrumented(tmp_path):
    mem = MemoryKernel(str(tmp_path / "m.db"))
    nid = from_term(mem, "t1", "实现 f", "先乘后加再取整", passed=True)
    node = mem.get(nid)
    p = node.payload if isinstance(node.payload, dict) else json.loads(node.payload)
    assert p["steps"] == []
    assert p["procedure_status"] == "not_instrumented"


def test_result_verified_requires_successful_verification():
    assert result_verified({"status": "done", "actions_log": [
        {"phase": "obs", "op": "read", "ok": True},
    ]}) is False
    assert result_verified({"status": "done", "actions_log": [
        {"phase": "obs", "op": "read", "ok": True},
        {"phase": "obs", "op": "run", "ok": True},
    ]}) is True
    assert result_verified({"status": "incomplete", "actions_log": [
        {"phase": "obs", "op": "run", "ok": True},
    ]}) is False


def test_from_task_result_default_gate_blocks_unverified(tmp_path):
    mem = MemoryKernel(str(tmp_path / "m.db"))
    assert from_task_result(mem, "t1", "实现 f", {
        "task_id": "t1", "status": "done", "answer": "先读取文件",
        "actions_log": [{"phase": "obs", "op": "read", "ok": True}],
    }) is None
    assert from_task_result(mem, "t1", "实现 f", {
        "task_id": "t1", "status": "done", "answer": "先读取文件，再运行测试",
        "actions_log": [
            {"phase": "obs", "op": "read", "ok": True},
            {"phase": "obs", "op": "run", "ok": True},
        ],
    }) is not None
