"""Read legacy JSONL facts into an EvidenceStore without modifying the source."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from dwc.observability.evidence_store import EvidenceStore


def migrate_jsonl(
    source: str | Path, store: EvidenceStore, kind: str | None = None
) -> dict[str, int]:
    """Migrate JSON objects or {kind, payload, idempotency_key} envelopes.

    The source is opened read-only. Existing legacy ids are retained; otherwise
    the exact non-empty line provides a deterministic idempotency key.
    """
    counts = {"read": 0, "inserted": 0, "duplicates": 0}
    source_path = Path(source)
    with source_path.open("r", encoding="utf-8") as lines:
        for line_number, line in enumerate(lines, 1):
            if not line.strip():
                continue
            counts["read"] += 1
            try:
                value = json.loads(line)
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                raise ValueError(f"{source_path}: invalid JSON at line {line_number}") from exc
            if not isinstance(value, dict):
                raise ValueError(f"{source_path}: line {line_number} must be a JSON object")

            row_kind = value.get("kind", kind)
            if not isinstance(row_kind, str) or not row_kind.strip():
                raise ValueError(f"{source_path}: missing kind at line {line_number}")
            if "payload" in value:
                payload = value["payload"]
            elif "idempotency_key" in value:
                raise ValueError(f"{source_path}: missing payload at line {line_number}")
            else:
                payload = {key: child for key, child in value.items() if key != "kind"}
            if not isinstance(payload, dict):
                raise ValueError(f"{source_path}: invalid payload at line {line_number}")

            key = value.get("idempotency_key")
            if key is None:
                digest = hashlib.sha256(line.rstrip("\r\n").encode("utf-8")).hexdigest()
                key = f"jsonl:{row_kind}:{digest}"
            elif not isinstance(key, str) or not key.strip():
                raise ValueError(
                    f"{source_path}: invalid idempotency_key at line {line_number}"
                )

            before = len(store.query(idempotency_key=key))
            store.append(row_kind, payload, idempotency_key=key)
            counts["duplicates" if before else "inserted"] += 1
    return counts


def main(argv: list[str] | None = None) -> int:
    arguments = sys.argv[1:] if argv is None else argv
    if len(arguments) not in {2, 3}:
        print("usage: dwc_metrics_migrate.py SOURCE.jsonl DEST.sqlite [KIND]", file=sys.stderr)
        return 2
    source, destination = arguments[:2]
    kind = arguments[2] if len(arguments) == 3 else None
    with EvidenceStore(destination) as store:
        print(json.dumps(migrate_jsonl(source, store, kind), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
