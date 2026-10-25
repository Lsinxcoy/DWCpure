from pathlib import Path

import pytest

from dwc.harness.component_manifest import (
    COMPONENT_MANIFEST,
    ManifestError,
    materialize_sparse_patch,
)


def test_all_eight_components_have_real_consumers():
    assert set(COMPONENT_MANIFEST) == {
        "system prompt", "guardrails", "memory", "tool guidance",
        "subagents", "skills", "scripts", "plugin/hooks",
    }
    assert all(spec.consumer and spec.allowed_roots for spec in COMPONENT_MANIFEST.values())
    assert COMPONENT_MANIFEST["system prompt"].consumer == "prompt_ota"
    assert COMPONENT_MANIFEST["plugin/hooks"].consumer == "agent_harness"


def test_sparse_patch_inherits_untouched_files_and_only_deletes_explicitly(tmp_path):
    base = tmp_path / "base"
    (base / "prompts").mkdir(parents=True)
    (base / "memory").mkdir()
    (base / "prompts/system.txt").write_text("old")
    (base / "prompts/other.txt").write_text("inherit")
    (base / "memory/old.md").write_text("remove")
    out = tmp_path / "candidate"
    result = materialize_sparse_patch(base, [
        {"path": "prompts/system.txt", "content": "new"},
        {"path": "memory/old.md", "operation": "delete"},
    ], out)
    assert (out / "prompts/other.txt").read_text() == "inherit"
    assert (out / "prompts/system.txt").read_text() == "new"
    assert not (out / "memory/old.md").exists()
    actions = {entry.path: entry.action for entry in result.entries}
    assert actions["prompts/other.txt"] == "inherited"
    assert actions["memory/old.md"] == "deleted"
    assert result.content_hash


@pytest.mark.parametrize("path", ["../secret", "/absolute", "C:/secret", "unknown/file"])
def test_manifest_rejects_unsafe_or_unowned_paths(tmp_path, path):
    base = tmp_path / "base"
    base.mkdir()
    with pytest.raises(ManifestError):
        materialize_sparse_patch(base, [{"path": path, "content": "x"}], tmp_path / "out")


def test_manifest_rejects_symlink_escape_and_hash_tampering(tmp_path):
    base = tmp_path / "base"
    (base / "prompts").mkdir(parents=True)
    (base / "prompts/good.txt").write_text("ok")
    (base / "prompts/link").symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(ManifestError, match="symlink"):
        materialize_sparse_patch(base, [], tmp_path / "out")
