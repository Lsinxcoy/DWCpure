"""DWC-AUTO · End-to-end shadow round contract (temporary dirs only)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def _evaluation(candidate_id, performance, cost):
    return {
        "candidate_id": candidate_id, "protocol_id": "validation-v1",
        "pair_id": "pair-1", "performance": performance,
        "performance_kind": "binary_pass", "mean_cost_per_task": cost,
        "cost_status": "priced", "usage_complete": True,
        "pricing_complete": True, "result_set_complete": True,
        "measurement_status": "measured", "completed_formal_units": 1,
        "successful_formal_units": 1 if performance >= 0.5 else 0,
    }


def _tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def test_shadow_round_selects_diagnoses_plans_and_composes_without_touching_base(tmp_path):
    base = tmp_path / "base"
    candidate = tmp_path / "candidate"
    (base / "prompts").mkdir(parents=True)
    (candidate / "prompts").mkdir(parents=True)
    (base / "prompts" / "system.md").write_text("base prompt\n", encoding="utf-8")
    (candidate / "prompts" / "system.md").write_text("candidate prompt\n", encoding="utf-8")
    before = _tree_hash(base)
    bundle = {
        "parent_id": "current",
        "archive_snapshot_id": "archive:1",
        "protocol": {"protocol_id": "validation-v1", "outcome_kind": "binary_pass",
                     "min_formal_units": 1, "baseline_noise_band": 0.0},
        "evaluations": [
            _evaluation("current", 0.8, 0.002),
            _evaluation("original", 0.7, 0.003),
            _evaluation("cand", 0.9, 0.0015),
        ],
        "incumbent_baseline_id": "current",
        "original_base_id": "original",
        "mode_weights": {"balanced": [1.0, 1.0]},
        "diagnoses": [
            {"diagnosis_ref": "diag:waste", "problem_type": "waste",
             "scope": "domain", "evidence_status": "observed"},
            {"diagnosis_ref": "diag:correct", "problem_type": "correctness",
             "scope": "invariant", "evidence_status": "observed"},
        ],
        "base_rollouts": [{"task_id": "t1", "rollout_id": "r1", "passed": False}],
        "edits": [{
            "intent": "performance-first", "scope": "invariant",
            "edit_id": "edit:1", "component": "tool guidance",
            "operation": "replace", "path": "tool_guidance/check.md",
            "content_ref": "evidence:check", "evidence_refs": ["diag:correct"],
        }],
        "compose": {
            "base_root": str(base), "output_root": str(tmp_path / "composed"),
            "decisions": [{"label": "cand", "root": str(candidate),
                           "claimed_decision": "adopt"}],
        },
    }
    bundle_path = tmp_path / "bundle.json"
    bundle_path.write_text(json.dumps(bundle), encoding="utf-8")
    out = tmp_path / "report.json"
    proc = subprocess.run([
        sys.executable, str(ROOT / "scripts" / "dwc_shadow_round.py"),
        "--bundle", str(bundle_path), "--out", str(out),
    ], cwd=ROOT, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["status"] == "shadow_only"
    assert report["production_modified"] is False
    assert report["selection"]["status"] == "selected"
    assert "cand" in report["selection"]["mode_selections"]["balanced"]
    assert len(report["plans"]) == 2
    validated = [row for row in report["plans"] if row["static_validation"] == "passed"]
    assert len(validated) == 1
    assert report["compose"]["status"] == "needs_reprobe"
    assert report["compose"]["decision"] == "COMPOSED"
    assert _tree_hash(base) == before
    assert (tmp_path / "composed" / "prompts" / "system.md").read_text(
        encoding="utf-8") == "candidate prompt\n"
