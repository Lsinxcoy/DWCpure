#!/usr/bin/env python3
"""DWC-AUTO · Shadow round orchestration; never modifies production config.

Input is a frozen JSON bundle of evaluations, rollouts, diagnoses, candidate
edits and compose decisions. Output is a deterministic report. Production
apply is deliberately absent; use RecoveryJournal separately after approval.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, fields as dataclass_fields
import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.evaluation.protocol import Protocol  # noqa: E402
from dwc.harness.intent_candidates import (  # noqa: E402
    CandidateEdit,
    CandidatePlanError,
    build_candidate_plans,
    static_validate_plan,
)
from dwc.harness.pareto_select import select_candidate_pool  # noqa: E402
from dwc.harness.probe_compose import ComposeError, compose_candidates  # noqa: E402
from dwc.harness.rollout_diagnostics import diagnose_rollouts  # noqa: E402


def _load(path: str) -> dict:
    with open(path, encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError("bundle must be a JSON object")
    return value


def _atomic_json(path: str, value) -> None:
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".dwc-shadow-", suffix=".json", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _edit_rows(rows) -> list[tuple[dict, CandidateEdit]]:
    if not isinstance(rows, list):
        raise ValueError("edits must be a list")
    allowed = {field.name for field in dataclass_fields(CandidateEdit)}
    result = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("each edit must be an object")
        unknown = sorted(set(row) - allowed - {"intent", "scope"})
        if unknown:
            raise ValueError("edit has unknown fields: %s" % ", ".join(unknown))
        result.append((row, CandidateEdit(
            **{key: row[key] for key in allowed if key in row})))
    return result


def run_bundle(bundle: dict) -> dict:
    protocol = Protocol(**bundle.get("protocol", {}))
    evaluations = bundle.get("evaluations")
    if not isinstance(evaluations, list) or not evaluations:
        raise ValueError("evaluations must be a non-empty list")
    selection = select_candidate_pool(
        evaluations,
        incumbent_baseline_id=str(bundle["incumbent_baseline_id"]),
        original_base_id=str(bundle["original_base_id"]),
        protocol=protocol,
        mode_weights=bundle.get("mode_weights") or {"balanced": (1.0, 1.0)},
    )
    rollouts = bundle.get("rollouts") or []
    diagnoses = (diagnose_rollouts(rollouts) if rollouts
                 else bundle.get("diagnoses") or [])
    base_rollouts = bundle.get("base_rollouts") or []
    plan_batch = build_candidate_plans(
        str(bundle["parent_id"]), str(bundle["archive_snapshot_id"]),
        diagnoses, base_rollouts,
    )
    edits = _edit_rows(bundle.get("edits") or [])
    by_cell: dict[tuple[str, str], list[CandidateEdit]] = {}
    for source, edit in edits:
        by_cell.setdefault((str(source.get("intent", "")),
                            str(source.get("scope", ""))), []).append(edit)
    plan_rows = []
    validation_errors: dict[str, list[str]] = {}
    for plan in plan_batch.plans:
        row = plan.to_dict()
        selected_edits = by_cell.get((plan.intent, plan.scope), [])
        row["edits"] = [asdict(edit) for edit in selected_edits]
        if selected_edits:
            try:
                static_validate_plan(plan, edits=selected_edits)
                row["static_validation"] = "passed"
            except CandidatePlanError as exc:
                row["static_validation"] = "failed"
                validation_errors["%s/%s" % (plan.intent, plan.scope)] = [
                    item for item in str(exc).split("; ") if item
                ]
        else:
            row["static_validation"] = "not_run_no_edits"
        plan_rows.append(row)
    compose_row = None
    compose_spec = bundle.get("compose")
    if compose_spec:
        try:
            result = compose_candidates(
                compose_spec["base_root"], compose_spec.get("decisions") or [],
                output_root=compose_spec.get("output_root"),
            )
            compose_row = asdict(result)
        except ComposeError as exc:
            compose_row = {"status": "blocked", "error": str(exc)}
    return {
        "status": "shadow_only",
        "production_modified": False,
        "protocol_id": protocol.protocol_id,
        "selection": asdict(selection),
        "diagnoses": [item.to_dict() if hasattr(item, "to_dict")
                      else dict(item) if isinstance(item, dict) else asdict(item)
                      for item in diagnoses],
        "plans": plan_rows,
        "skipped_cells": {("%s/%s" % key): value
                          for key, value in plan_batch.skipped.items()},
        "validation_errors": validation_errors,
        "compose": compose_row,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    try:
        report = run_bundle(_load(args.bundle))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print("shadow round input error: %s" % exc, file=sys.stderr)
        return 2
    _atomic_json(args.out, report)
    print(json.dumps({
        "status": report["status"],
        "selection_status": report["selection"]["status"],
        "plans": len(report["plans"]),
        "compose_status": (report["compose"] or {}).get("status"),
        "out": os.path.abspath(args.out),
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
