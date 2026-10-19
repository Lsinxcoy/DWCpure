# -*- coding: utf-8 -*-
"""dwc_graded_bench · 分级基准跑批（Phase C）

逐个跑 instance → 收集 report → 汇总成 6 级 fitness。

DWC-AUTO 定位声明（工具脚本，非器官）
TRUTH_SOURCE: 每级来自 run_tests 的真实执行结果，本脚本不生成 label。

用法:
  python scripts/dwc_graded_bench.py <inst1.json> [inst2.json ...]
  python scripts/dwc_graded_bench.py --glob "inst_pytest-dev__pytest-*.json"
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import subprocess
import sys

ROOT = os.environ.get("DWC_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
if os.path.join(ROOT, "src") not in sys.path:
    sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.organs.benchmark_fitness import (  # noqa: E402
    fitness_breakdown, record_from_harness,
)

REPORT = os.environ.get(
    "DWC_AGENT_REPORT",
    "C:/Users/41228/AppData/Local/hermes/cache/scratch/dwc_agent_report.json")
OUT = os.path.join(ROOT, "var", "graded_bench.json")


def run_one(inst_path: str, timeout: int = 900, policy: str = ""):
    print("\n" + "=" * 70)
    print("RUN:", os.path.basename(inst_path), ("| policy=" + policy) if policy else "")
    print("=" * 70)
    cmd = [sys.executable, os.path.join(ROOT, "scripts", "dwc_agent_patch.py"), inst_path]
    if policy:
        cmd += ["--policy", policy]
    try:
        r = subprocess.run(
            cmd,
            capture_output=True, timeout=timeout,
            env=dict(os.environ, PYTHONIOENCODING="utf-8"),
        )
        tail = r.stdout.decode("utf-8", "replace").strip().splitlines()[-8:]
        for line in tail:
            print("  " + line)
        if r.returncode not in (0, 1):
            print("  stderr:", r.stderr.decode("utf-8", "replace")[-400:])
    except subprocess.TimeoutExpired:
        print("  TIMEOUT after %ss" % timeout)
        return None
    if not os.path.exists(REPORT):
        print("  no report produced")
        return None
    try:
        return json.load(open(REPORT, encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print("  report unreadable: %s" % e)
        return None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("instances", nargs="*")
    ap.add_argument("--glob", default="")
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--policy", default="", help="k=v,... 透传给 dwc_agent_patch")
    args = ap.parse_args(argv)

    paths = list(args.instances)
    if args.glob:
        paths.extend(sorted(glob.glob(args.glob)))
    if not paths:
        print("no instances given", file=sys.stderr)
        return 2

    reports, records = [], []
    for p in paths:
        rep = run_one(p, args.timeout, args.policy)
        if rep is None:
            continue
        reports.append(rep)
        records.append(record_from_harness(rep))

    fb = fitness_breakdown(records)

    print("\n" + "=" * 70)
    print("GRADED FITNESS")
    print("=" * 70)
    print("n = %d | verdict = %s" % (fb["n"], fb["verdict"]))
    print("%-14s %6s %6s %8s" % ("LEVEL", "OK", "TOTAL", "RATE"))
    for lv, c in fb["counts"].items():
        rate = "-" if c["rate"] is None else "%.2f" % c["rate"]
        print("%-14s %6d %6d %8s" % (lv, c["ok"], c["total"], rate))
    print("-" * 40)
    print("realization = %s" % fb["realization"])
    print("outcome     = %s" % fb["outcome"])
    print("scalar      = %s" % fb["scalar"])

    print("\nPER INSTANCE")
    for r in records:
        print("  %-34s parse=%-5s apply=%-5s syntax=%-5s f2p=%-5s verifier=%-5s"
              % (r["instance_id"], r["parse_ok"], r["apply_ok"], r["syntax_ok"],
                 r["f2p_ok"], r["verifier_ok"]))

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    out_path = OUT
    if args.policy:
        safe = re.sub(r"[^A-Za-z0-9_.=-]", "_", args.policy)
        out_path = OUT.replace(".json", "__" + safe + ".json")
    json.dump({"fitness": fb, "records": records, "policy": args.policy,
               "reports": [{"instance_id": x.get("instance_id"),
                            "success": x.get("success"),
                            "iterations": x.get("iterations"),
                            "last_error": (x.get("last_error") or "")[:300]}
                           for x in reports]},
              open(out_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("\n-> %s" % out_path.replace(os.sep, "/"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
