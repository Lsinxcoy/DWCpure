"""DWC-AUTO · Append-only SQLite evidence storage."""

from __future__ import annotations

import json
import re
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_SECRET_KEY = re.compile(
    r"(?:^api[_-]?key$|(?:^|[_-])token$|(?:^|[_-])password$|(?:^|[_-])secret$)",
    re.IGNORECASE,
)
_BEARER = re.compile(r"^\s*Bearer\s+", re.IGNORECASE)
_RAW_FIELD = re.compile(r"(?:^|_)(?:raw|response|trajectory|deliverable)(?:_|$)")
_SHA256 = re.compile(r"^[0-9a-fA-F]{64}$")
_RAW_COUNT_KEYS = {"raw_tool_calls"}


def _raw_pair_error(path: str) -> ValueError:
    return ValueError(
        "raw content requires ref and hash, not inline data: %s" % path
    )


def _validate_raw_pair(mapping: dict[str, Any], key: str, path: str) -> None:
    """raw 内容只允许 ref+hash 成对引用，禁止任何内联值。"""
    if key.endswith("_ref"):
        base = key[:-4]
        ref = mapping.get(key)
        hashes = [mapping.get(base + "_sha256"), mapping.get(base + "_hash")]
        if not (isinstance(ref, str) and ref.strip()) or not any(
            isinstance(value, str) and _SHA256.match(value) for value in hashes
        ):
            raise _raw_pair_error(f"{path}.{key}")
        return
    if key.endswith("_sha256") or key.endswith("_hash"):
        base = key[:-7] if key.endswith("_sha256") else key[:-5]
        ref = mapping.get(base + "_ref")
        value = mapping.get(key)
        if not (isinstance(ref, str) and ref.strip()) or not (
            isinstance(value, str) and _SHA256.match(value)
        ):
            raise _raw_pair_error(f"{path}.{key}")
        return
    if key in _RAW_COUNT_KEYS and isinstance(mapping.get(key), int):
        return
    raise _raw_pair_error(f"{path}.{key}")


def _validate_large_objects(value: Any, path: str = "payload") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if isinstance(key, str) and _RAW_FIELD.search(key):
                _validate_raw_pair(value, key, path)
            _validate_large_objects(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _validate_large_objects(child, f"{path}[{index}]")


def _is_secret_key(key: str) -> bool:
    normalized = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", key).lower()
    return bool(_SECRET_KEY.search(normalized)) or normalized == "authorization"


def _reject_secrets(value: Any, path: str = "payload") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if isinstance(key, str) and _is_secret_key(key):
                raise ValueError(f"secret field is not allowed: {child_path}")
            _reject_secrets(child, child_path)
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _reject_secrets(child, f"{path}[{index}]")
    elif isinstance(value, str) and _BEARER.match(value):
        raise ValueError(f"secret bearer credential is not allowed: {path}")


class EvidenceStore:
    """A small, injectable-path, append-only fact ledger."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(
            self.path, timeout=30.0, isolation_level=None, check_same_thread=False
        )
        self._connection.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        self._closed = False
        self._connection.execute("PRAGMA busy_timeout=30000")
        # 多进程冷启动可能同时切换 WAL；busy_timeout 不覆盖所有 PRAGMA 路径。
        for _attempt in range(20):
            try:
                self._connection.execute("PRAGMA journal_mode=WAL")
                break
            except sqlite3.OperationalError as exc:
                if "locked" not in str(exc).lower() or _attempt == 19:
                    raise
                import time
                time.sleep(0.05 * (_attempt + 1))
        self._connection.execute("PRAGMA synchronous=NORMAL")
        self._connection.execute("PRAGMA foreign_keys=ON")
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS evidence (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                record_id TEXT NOT NULL UNIQUE,
                kind TEXT NOT NULL,
                payload TEXT NOT NULL,
                idempotency_key TEXT UNIQUE,
                created_at TEXT NOT NULL
            )
            """
        )

    def append(
        self,
        kind: str,
        payload: dict[str, Any],
        idempotency_key: str | None = None,
    ) -> str:
        if not isinstance(kind, str) or not kind.strip():
            raise ValueError("kind must be a non-empty string")
        if not isinstance(payload, dict):
            raise TypeError("payload must be a dictionary")
        if idempotency_key is not None and (
            not isinstance(idempotency_key, str) or not idempotency_key.strip()
        ):
            raise ValueError("idempotency_key must be a non-empty string or None")
        _reject_secrets(payload)
        _validate_large_objects(payload)
        encoded = json.dumps(
            payload, ensure_ascii=False, allow_nan=False, separators=(",", ":")
        )

        with self._lock:
            self._ensure_open()
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                if idempotency_key is not None:
                    row = self._connection.execute(
                        "SELECT record_id, kind, payload FROM evidence "
                        "WHERE idempotency_key = ?",
                        (idempotency_key,),
                    ).fetchone()
                    if row is not None:
                        self._connection.execute("ROLLBACK")
                        if row["kind"] != kind or row["payload"] != encoded:
                            raise ValueError(
                                "idempotency key is already bound to a different fact"
                            )
                        return row["record_id"]
                record_id = uuid.uuid4().hex
                self._connection.execute(
                    "INSERT INTO evidence "
                    "(record_id, kind, payload, idempotency_key, created_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (
                        record_id,
                        kind,
                        encoded,
                        idempotency_key,
                        datetime.now(timezone.utc).isoformat(),
                    ),
                )
                self._connection.execute("COMMIT")
            except Exception:
                if self._connection.in_transaction:
                    self._connection.execute("ROLLBACK")
                raise
        return record_id

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("EvidenceStore is closed")

    def query(self, kind: str | None = None, **filters: Any) -> list[dict[str, Any]]:
        sql = "SELECT record_id, kind, payload, idempotency_key, created_at FROM evidence"
        parameters: list[Any] = []
        clauses = []
        if kind is not None:
            clauses.append("kind = ?")
            parameters.append(kind)
        for key, value in filters.items():
            if key in {"record_id", "idempotency_key", "created_at"}:
                clauses.append(f"{key} = ?")
                parameters.append(value)
            else:
                clauses.append("json_extract(payload, ?) = json_extract(?, '$')")
                parameters.extend((f"$.{key}", json.dumps(value, ensure_ascii=False)))
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY sequence"
        with self._lock:
            rows = self._connection.execute(sql, parameters).fetchall()
        return [
            {
                "record_id": row["record_id"],
                "kind": row["kind"],
                "payload": json.loads(row["payload"]),
                "idempotency_key": row["idempotency_key"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def close(self) -> None:
        with self._lock:
            if not self._closed:
                self._connection.close()
                self._closed = True

    def __enter__(self) -> "EvidenceStore":
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.close()
