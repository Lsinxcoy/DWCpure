"""DWC-AUTO · Controlled apply CLI uses journal and canary."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def _run(tmp_path, patches, *extra):
    patch_path = tmp_path / "patches.json"
    patch_path.write_text(json.dumps(patches), encoding="utf-8")
    return subprocess.run([
        sys.executable, str(ROOT / "scripts" / "dwc_apply_candidate.py"),
        "--root", str(tmp_path / "root"),
        "--journal", str(tmp_path / "var" / "recovery.json"),
        "--patches", str(patch_path), *extra,
    ], cwd=ROOT, capture_output=True, text=True)


def _root(tmp_path):
    root = tmp_path / "root"
    (root / "config").mkdir(parents=True)
    (root / "config" / "context_policy.json").write_text(json.dumps({
        "read_default_lines": 200, "search_limit": 60}), encoding="utf-8")
    return root


def test_apply_requires_confirmation_and_leaves_target_untouched(tmp_path):
    root = _root(tmp_path)
    before = (root / "config" / "context_policy.json").read_bytes()
    proc = _run(tmp_path, {"context_mgmt": {"read_default_lines": 300}})
    assert proc.returncode == 2
    assert "confirm" in proc.stderr
    assert (root / "config" / "context_policy.json").read_bytes() == before
    assert not (tmp_path / "var" / "recovery.json").exists()


def test_apply_commits_then_canary_verifies_hashes(tmp_path):
    root = _root(tmp_path)
    proc = _run(tmp_path, {"context_mgmt": {"read_default_lines": 300}},
                "--confirm", "APPLY")
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["state"] == "committed"
    assert json.loads((root / "config" / "context_policy.json").read_text(
        encoding="utf-8"))["read_default_lines"] == 300
    journal = json.loads((tmp_path / "var" / "recovery.json").read_text(
        encoding="utf-8"))
    assert journal["targets"][0]["backup"]

    canary = subprocess.run([
        sys.executable, str(ROOT / "scripts" / "dwc_apply_candidate.py"),
        "--root", str(root), "--journal", str(tmp_path / "var" / "recovery.json"),
        "--canary", result["transaction_id"],
    ], cwd=ROOT, capture_output=True, text=True)
    assert canary.returncode == 0, canary.stderr
    assert json.loads(canary.stdout)["canary"]["context_mgmt"][
        "read_default_lines"] == 300
