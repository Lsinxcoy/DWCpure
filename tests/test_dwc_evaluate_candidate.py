"""DWC-AUTO · Offline evaluation CLI contract."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def _attempt(aid, task, passed):
    return {
        "attempt_id": aid, "task_id": task, "candidate_id": "cand",
        "rollout_id": "r1", "protocol_id": "validation-v1",
        "pair_id": "pair", "attempt_index": 0, "selected_formal": True,
        "passed": passed, "execution_cost_status": "not_reported",
    }


def _usage(aid, task, model="m"):
    return {
        "event_id": "e-" + aid, "attempt_id": aid, "task_id": task,
        "candidate_id": "cand", "requested_model": model, "actual_model": model,
        "input_tokens": 100, "cached_input_tokens": 0,
        "uncached_input_tokens": 100, "output_tokens": 10,
        "billable_output_tokens": 10, "reasoning_tokens": 0,
        "usage_status": "reported", "usage_coverage": "full",
    }


def _run(tmp_path, attempts, usage, extra=()):
    (tmp_path / "attempts.json").write_text(json.dumps(attempts), encoding="utf-8")
    (tmp_path / "usage.json").write_text(json.dumps(usage), encoding="utf-8")
    (tmp_path / "pricing.json").write_text(json.dumps({
        "m": {"version": "test", "input_per_million": 1.0,
              "output_per_million": 1.0}
    }), encoding="utf-8")
    out = tmp_path / "report.json"
    proc = subprocess.run([
        sys.executable, str(ROOT / "scripts" / "dwc_evaluate_candidate.py"),
        "--attempts", str(tmp_path / "attempts.json"),
        "--usage", str(tmp_path / "usage.json"),
        "--pricing", str(tmp_path / "pricing.json"),
        "--out", str(out), *extra,
    ], cwd=ROOT, capture_output=True, text=True)
    return proc, out


def test_evaluate_candidate_prices_only_complete_formal_units(tmp_path):
    attempts = [_attempt("a1", "t1", True), _attempt("a2", "t2", False)]
    usage = [_usage("a1", "t1"), _usage("a2", "t2")]
    proc, out = _run(tmp_path, attempts, usage, ("--require-measured",))
    assert proc.returncode == 0, proc.stderr
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["measurement_status"] == "measured"
    assert report["completed_formal_units"] == 2
    assert report["mean_cost_per_task"] == 0.00011
    assert report["pricing_complete"] is True


def test_evaluate_candidate_missing_usage_is_not_priced(tmp_path):
    attempts = [_attempt("a1", "t1", True)]
    proc, out = _run(tmp_path, attempts, [], ("--require-measured",))
    assert proc.returncode == 3
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["measurement_status"] == "incomplete"
    assert report["mean_cost_per_task"] is None
    assert report["cost_status"] == "indeterminate"
