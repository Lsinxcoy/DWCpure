from pathlib import Path

import pytest

from dwc.harness.evidence_bundle import EvidenceBundleBuilder, EvidenceError


def test_manifest_records_materialized_and_withheld_without_fake_content(tmp_path):
    (tmp_path / "trace.jsonl").write_text('{"event":"observed"}\n')
    builder = EvidenceBundleBuilder(tmp_path)
    manifest = builder.build([
        {"ref": "trace.jsonl", "role": "propose"},
        {"ref": "private.jsonl", "role": "propose", "withheld": True, "reason": "names_only"},
        {"ref": "missing.jsonl", "role": "propose"},
    ])
    assert [x.status for x in manifest.entries] == ["materialized", "withheld", "failed"]
    assert manifest.entries[0].sha256
    assert manifest.entries[1].path is None
    assert manifest.entries[1].reason == "names_only"
    assert manifest.entries[2].reason == "missing"


def test_full_trajectory_read_failure_fails_closed(tmp_path):
    builder = EvidenceBundleBuilder(tmp_path)
    with pytest.raises(EvidenceError, match="trajectory"):
        builder.build([{"ref": "missing.jsonl", "kind": "trajectory", "role": "compose"}])


def test_names_only_never_materializes_bytes(tmp_path):
    (tmp_path / "answer.patch").write_text("secret bytes")
    manifest = EvidenceBundleBuilder(tmp_path).build([
        {"ref": "answer.patch", "role": "propose", "names_only": True}
    ])
    assert manifest.entries[0].status == "withheld"
    assert not list((tmp_path / "evidence").glob("**/*")) if (tmp_path / "evidence").exists() else True
