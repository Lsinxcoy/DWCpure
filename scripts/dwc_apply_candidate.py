#!/usr/bin/env python3
"""DWC-AUTO · Controlled multi-component apply with recovery journal.

Safety contract:
- an explicit --root is mandatory;
- production repository root is refused unless --allow-production is also given;
- --confirm APPLY is mandatory for writes;
- every undo record is persisted before the first target write;
- canary only publishes committed transactions whose hashes still match.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.harness.recovery_journal import RecoveryError, RecoveryJournal  # noqa: E402
from dwc.organs import evo_targets as ET  # noqa: E402


def _load(path: str):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    parser.add_argument("--journal", required=True)
    parser.add_argument("--patches")
    parser.add_argument("--confirm", default="")
    parser.add_argument("--allow-production", action="store_true")
    parser.add_argument("--recover", action="store_true")
    parser.add_argument("--canary", metavar="TRANSACTION_ID")
    args = parser.parse_args(argv)

    target_root = os.path.abspath(args.root)
    if not os.path.isdir(target_root):
        print("root does not exist: %s" % target_root, file=sys.stderr)
        return 2
    if target_root == os.path.abspath(ROOT) and not args.allow_production:
        print("refusing production root without --allow-production", file=sys.stderr)
        return 2
    ET.ROOT = target_root
    journal = RecoveryJournal(args.journal)
    try:
        if args.recover:
            result = journal.recover()
        elif args.canary:
            result = {"canary": journal.canary(args.canary)}
        else:
            if args.confirm != "APPLY":
                print("write requires --confirm APPLY", file=sys.stderr)
                return 2
            if not args.patches:
                print("--patches is required for apply", file=sys.stderr)
                return 2
            patches = _load(args.patches)
            if not isinstance(patches, dict) or not patches:
                print("patches must be a non-empty object", file=sys.stderr)
                return 2
            result = journal.apply(patches)
    except (OSError, ValueError, RecoveryError, ET.TargetError) as exc:
        print("apply error: %s" % exc, file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    if not args.recover and not args.canary and result.get("state") != "committed":
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
