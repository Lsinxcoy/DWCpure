from pathlib import Path
import sys

import pytest

from dwc.observability.evidence_store import EvidenceStore

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from dwc_metrics_migrate import migrate_jsonl


def test_jsonl_migration_is_read_only_and_idempotent(tmp_path):
    source = tmp_path / "old.jsonl"
    original = (
        b'{"kind":"usage","payload":{"event_id":"e1","input_tokens":4},'
        b'"idempotency_key":"old-e1"}\n'
        b'{"kind":"attempt","payload":{"task_id":"t1","passed":true}}\n'
    )
    source.write_bytes(original)
    destination = tmp_path / "new.sqlite"
    with EvidenceStore(destination) as store:
        first = migrate_jsonl(source, store)
        second = migrate_jsonl(source, store)

        assert first == {"read": 2, "inserted": 2, "duplicates": 0}
        assert second == {"read": 2, "inserted": 0, "duplicates": 2}
        assert len(store.query()) == 2
        assert store.query(kind="usage")[0]["payload"]["input_tokens"] == 4
        assert store.query(kind="attempt")[0]["payload"]["task_id"] == "t1"
    assert source.read_bytes() == original


def test_migration_preserves_missing_usage_as_missing(tmp_path):
    source = tmp_path / "old.jsonl"
    source.write_text('{"kind":"usage","payload":{"event_id":"e1"}}\n')
    with EvidenceStore(tmp_path / "new.sqlite") as store:
        migrate_jsonl(source, store)
        payload = store.query()[0]["payload"]
        assert "input_tokens" not in payload
        assert "output_tokens" not in payload


@pytest.mark.parametrize(
    "contents,match",
    [
        ('{"kind":"usage"}\nnot-json\n', "line 2"),
        ('[]\n', "line 1"),
        ('{"payload":{}}\n', "kind"),
        ('{"kind":"usage","idempotency_key":"x"}\n', "payload"),
        ('{"kind":"usage","payload":{},"idempotency_key":""}\n', "idempotency"),
        ('{"kind":"usage","idempotency_key":"x"}\n', "payload"),
    ],
)
def test_bad_migration_row_fails_loudly(tmp_path, contents, match):
    source = tmp_path / "old.jsonl"
    source.write_text(contents)
    with EvidenceStore(tmp_path / "new.sqlite") as store:
        with pytest.raises(ValueError, match=match):
            migrate_jsonl(source, store)


def test_migration_cli_uses_injected_source_and_destination(tmp_path):
    source = tmp_path / "legacy.jsonl"
    source.write_text('{"kind":"usage","payload":{"event_id":"e1"}}\n')
    destination = tmp_path / "nested" / "facts.sqlite"
    script = Path(__file__).resolve().parents[1] / "scripts" / "dwc_metrics_migrate.py"
    result = __import__("subprocess").run(
        [sys.executable, "-B", str(script), str(source), str(destination)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert '"inserted": 1' in result.stdout
    with EvidenceStore(destination) as store:
        assert store.query()[0]["payload"] == {"event_id": "e1"}
