from dwc.observability.evidence_store import EvidenceStore

import json
import os
import sqlite3
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

import pytest


def test_append_and_query_round_trip(tmp_path):
    store = EvidenceStore(tmp_path / "evidence.sqlite")
    try:
        record_id = store.append(
            "usage", {"task_id": "t-1", "input_tokens": 7}, idempotency_key="call-1"
        )

        assert isinstance(record_id, str) and record_id
        assert store.query() == [
            {
                "record_id": record_id,
                "kind": "usage",
                "payload": {"task_id": "t-1", "input_tokens": 7},
                "idempotency_key": "call-1",
                "created_at": store.query()[0]["created_at"],
            }
        ]
        assert store.query(kind="usage", task_id="t-1")[0]["record_id"] == record_id
        assert store.query(kind="other") == []
        assert store.query(task_id="missing") == []
        assert store.query(record_id=record_id)[0]["kind"] == "usage"
        assert store.query(idempotency_key="call-1")[0]["record_id"] == record_id
    finally:
        store.close()


@pytest.mark.parametrize(
    "bad_key,payload",
    [
        ("api_key", {"api_key": "do-not-store"}),
        ("authorization", {"nested": [{"authorization": "Bearer abc"}]}),
        ("headers", {"headers": {"Authorization": "bearer abc"}}),
        ("client_secret", {"client_secret": "do-not-store"}),
        ("access_token", {"access_token": "do-not-store"}),
        ("password", {"password": "do-not-store"}),
        ("apiKey", {"apiKey": "do-not-store"}),
        ("accessToken", {"accessToken": "do-not-store"}),
        ("clientSecret", {"clientSecret": "do-not-store"}),
    ],
)
def test_secrets_are_rejected_recursively(tmp_path, bad_key, payload):
    with EvidenceStore(tmp_path / "evidence.sqlite") as store:
        with pytest.raises(ValueError, match="secret"):
            store.append("attempt", payload)
        assert store.query() == []
        assert "do-not-store" not in (tmp_path / "evidence.sqlite").read_bytes().decode(
            "latin-1"
        )


@pytest.mark.parametrize(
    "kind,payload,key",
    [
        ("", {}, None),
        (None, {}, None),
        ("usage", [], None),
        ("usage", {"value": float("nan")}, None),
        ("usage", {"value": object()}, None),
        ("usage", {}, ""),
        ("usage", {}, 12),
    ],
)
def test_bad_input_raises_explicit_error(tmp_path, kind, payload, key):
    with EvidenceStore(tmp_path / "evidence.sqlite") as store:
        with pytest.raises((TypeError, ValueError)):
            store.append(kind, payload, idempotency_key=key)
        assert store.query() == []


def test_raw_large_objects_must_be_referenced_by_hash(tmp_path):
    with EvidenceStore(tmp_path / "evidence.sqlite") as store:
        with pytest.raises(ValueError, match="ref.*hash|hash.*ref"):
            store.append("llm_call", {"raw_response": "x" * 8193})
        with pytest.raises(ValueError, match="ref.*hash|hash.*ref"):
            store.append("llm_call", {"raw_response": {"choices": ["x" * 8193]}})

        record_id = store.append(
            "llm_call",
            {"usage_raw_ref": "evidence/abc.json", "usage_raw_sha256": "a" * 64},
        )
        assert store.query(kind="llm_call")[0]["record_id"] == record_id


def test_short_raw_text_is_not_inlined(tmp_path):
    with EvidenceStore(tmp_path / "evidence.sqlite") as store:
        with pytest.raises(ValueError, match="ref.*hash|hash.*ref"):
            store.append("llm_call", {"raw_response": "PRIVATE-short-text"})
        assert store.query() == []


def test_raw_ref_requires_valid_hash_and_hash_requires_ref(tmp_path):
    with EvidenceStore(tmp_path / "evidence.sqlite") as store:
        with pytest.raises(ValueError, match="ref.*hash|hash.*ref"):
            store.append("llm_call", {"raw_response_ref": "evidence/a.json"})
        with pytest.raises(ValueError, match="ref.*hash|hash.*ref"):
            store.append("llm_call", {"raw_response_sha256": "a" * 64})
        with pytest.raises(ValueError, match="ref.*hash|hash.*ref"):
            store.append("llm_call", {"raw_response_ref": "evidence/a.json",
                                      "raw_response_sha256": "short"})
        assert store.query() == []


def test_idempotency_conflict_is_not_silently_rebound(tmp_path):
    with EvidenceStore(tmp_path / "evidence.sqlite") as store:
        original = store.append("usage", {"call_id": "c1"}, "unique-key")
        assert store.append("usage", {"call_id": "c1"}, "unique-key") == original
        with pytest.raises(ValueError, match="idempotency"):
            store.append("usage", {"call_id": "different"}, "unique-key")
        assert len(store.query()) == 1


def test_wal_survives_reopen_and_bad_database_is_loud(tmp_path):
    path = tmp_path / "evidence.sqlite"
    with EvidenceStore(path) as store:
        store.append("usage", {"input_tokens": 3})
    with EvidenceStore(path) as store:
        assert store.query()[0]["payload"]["input_tokens"] == 3
    connection = sqlite3.connect(path)
    try:
        assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        connection.close()

    (tmp_path / "bad.sqlite").write_text("not sqlite")
    with pytest.raises(sqlite3.DatabaseError):
        EvidenceStore(tmp_path / "bad.sqlite")


def test_threads_share_store_without_lost_appends(tmp_path):
    path = tmp_path / "evidence.sqlite"
    with EvidenceStore(path) as store:
        def append_one(index):
            return store.append("usage", {"index": index}, f"key-{index}")

        with ThreadPoolExecutor(max_workers=8) as pool:
            ids = list(pool.map(append_one, range(40)))
        assert len(set(ids)) == 40
        assert len(store.query()) == 40


def test_processes_share_unique_idempotency_key(tmp_path):
    path = tmp_path / "evidence.sqlite"
    code = """
import sys
from dwc.observability.evidence_store import EvidenceStore
with EvidenceStore(sys.argv[1]) as store:
    for _ in range(5):
        print(store.append('usage', {'input_tokens': 1}, 'shared-key'))
"""
    outputs = []
    for _ in range(4):
        result = subprocess.run(
            [sys.executable, "-B", "-c", code, os.fspath(path)],
            cwd=os.fspath(tmp_path),
            env={**os.environ, "PYTHONPATH": os.fspath(tmp_path.parent)},
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        outputs.extend(result.stdout.splitlines())
    assert len(set(outputs)) == 1
    with EvidenceStore(path) as store:
        assert len(store.query()) == 1


def test_concurrent_processes_append_distinct_facts(tmp_path):
    path = tmp_path / "evidence.sqlite"
    code = """
import sys
from dwc.observability.evidence_store import EvidenceStore
with EvidenceStore(sys.argv[1]) as store:
    for index in range(20):
        store.append('usage', {'worker': sys.argv[2], 'index': index},
                     f'{sys.argv[2]}-{index}')
"""
    processes = [
        subprocess.Popen(
            [sys.executable, "-B", "-c", code, os.fspath(path), str(worker)],
            cwd=os.fspath(tmp_path),
            env={**os.environ, "PYTHONPATH": os.fspath(tmp_path.parent)},
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for worker in range(4)
    ]
    for process in processes:
        stdout, stderr = process.communicate(timeout=60)
        assert process.returncode == 0, stdout + stderr
    with EvidenceStore(path) as store:
        assert len(store.query()) == 80
        connection = sqlite3.connect(path)
        try:
            assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        finally:
            connection.close()
