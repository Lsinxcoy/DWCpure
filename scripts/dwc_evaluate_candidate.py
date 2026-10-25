#!/usr/bin/env python3
"""DWC-AUTO · Offline fixed-protocol candidate evaluation.

Reads frozen attempt/usage facts and a price book. It never calls an LLM and
never writes production config; missing usage or pricing stays indeterminate.
"""
from __future__ import annotations

import argparse
from dataclasses import fields
import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.observability.task_metrics import AttemptRecord  # noqa: E402
from dwc.observability.usage_pricing import (  # noqa: E402
    UsageEvent,
    summarize_candidate,
)


def _load(path: str):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _rows(value, name: str) -> list[dict]:
    if not isinstance(value, list) or any(not isinstance(row, dict) for row in value):
        raise ValueError("%s must be a list of objects" % name)
    return value


def _build(cls, row: dict, name: str):
    allowed = {field.name for field in fields(cls)}
    unknown = sorted(set(row) - allowed)
    if unknown:
        raise ValueError("%s has unknown fields: %s" % (name, ", ".join(unknown)))
    return cls(**row)


def _atomic_json(path: str, value) -> None:
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".dwc-eval-", suffix=".json", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempts", required=True)
    parser.add_argument("--usage", required=True)
    parser.add_argument("--pricing", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--requested-formal-units", type=int, default=None)
    parser.add_argument("--protocol-allows-mixture", action="store_true")
    parser.add_argument("--require-measured", action="store_true")
    args = parser.parse_args(argv)
    try:
        attempts = [_build(AttemptRecord, row, "attempt")
                    for row in _rows(_load(args.attempts), "attempts")]
        usage = [_build(UsageEvent, row, "usage")
                 for row in _rows(_load(args.usage), "usage")]
        pricing = _load(args.pricing)
        if not isinstance(pricing, dict):
            raise ValueError("pricing must be an object keyed by model")
        report = summarize_candidate(
            attempts, usage, pricing,
            requested_formal_units=args.requested_formal_units,
            protocol_allows_mixture=args.protocol_allows_mixture,
        ).to_dict()
    except (OSError, ValueError, TypeError) as exc:
        print("evaluation input error: %s" % exc, file=sys.stderr)
        return 2
    _atomic_json(args.out, report)
    print(json.dumps({
        "candidate_id": report.get("candidate_id"),
        "measurement_status": report.get("measurement_status"),
        "cost_status": report.get("cost_status"),
        "mean_cost_per_task": report.get("mean_cost_per_task"),
        "out": os.path.abspath(args.out),
    }, ensure_ascii=False, sort_keys=True))
    if args.require_measured and report.get("measurement_status") != "measured":
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
