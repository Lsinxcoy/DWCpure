from pathlib import Path

import pytest

from dwc.harness.candidate_workspace import CandidateWorkspace, WorkspaceError


def test_workspace_sparse_patch_inherits_parent_and_never_mutates_production(tmp_path):
    production = tmp_path / "production"
    production.mkdir()
    (production / "keep.txt").write_text("keep")
    (production / "edit.txt").write_text("old")
    (production / "delete.txt").write_text("delete")
    workspace = CandidateWorkspace(production, tmp_path / "shadows")
    shadow = workspace.create("c1", {"edit.txt": "new", "delete.txt": None, "new.txt": "new"})
    assert (shadow / "keep.txt").read_text() == "keep"
    assert (shadow / "edit.txt").read_text() == "new"
    assert not (shadow / "delete.txt").exists()
    assert (production / "edit.txt").read_text() == "old"
    assert (production / "delete.txt").exists()


def test_workspace_manifest_hashes_actual_files_and_rejects_escape(tmp_path):
    production = tmp_path / "production"
    production.mkdir()
    workspace = CandidateWorkspace(production, tmp_path / "shadows")
    shadow = workspace.create("c1", {"answer.txt": "answer"})
    manifest = workspace.artifact_manifest("c1")
    assert manifest["candidate_id"] == "c1"
    assert manifest["files"][0]["path"] == "answer.txt"
    assert len(manifest["files"][0]["sha256"]) == 64
    with pytest.raises(WorkspaceError):
        workspace.create("c2", {"../production.txt": "escape"})


def test_workspace_is_shadow_only_and_rollback_does_not_apply(tmp_path):
    production = tmp_path / "production"
    production.mkdir()
    (production / "config.txt").write_text("stable")
    workspace = CandidateWorkspace(production, tmp_path / "shadows")
    shadow = workspace.create("c1", {"config.txt": "candidate"})
    assert workspace.rollback("c1") == "shadow_removed"
    assert not shadow.exists()
    assert (production / "config.txt").read_text() == "stable"
    with pytest.raises(PermissionError, match="production"):
        workspace.commit("c1")
