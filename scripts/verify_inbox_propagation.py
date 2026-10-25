# -*- coding: utf-8 -*-
"""★ R337 · 组织级 RSI 传播验证。

survey §3.3：failure 成为组织改进，仅当被诊断、蒸馏、独立验证、选择性传播。
本脚本检查 inbox_done 中的任务：对应 task 的 failure_sig 是否已停产
（count=0 或未增长），作为传播验证的最小证据。

用法:
    python scripts/verify_inbox_propagation.py [--db PATH]
"""
from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))


def verify(db_path: str, prod: str) -> dict:
    os.path.join(prod, "var", "dwc_inbox.jsonl")
    done_path = os.path.join(prod, "var", "dwc_inbox_done.json")
    try:
        with open(done_path, encoding="utf-8") as f:
            done = json.load(f)
    except (OSError, ValueError):
        done = {}
    # distinct tasks in db
    try:
        import sqlite3
        con = sqlite3.connect(db_path)
        counts = dict(con.execute(
            "SELECT task, COUNT(*) FROM failure_sig GROUP BY task").fetchall())
        con.close()
    except Exception:
        counts = {}
    results = []
    for tid, info in (done or {}).items():
        task = (info or {}).get("task") if isinstance(info, dict) else None
        # tid like evo_auto_<task>
        if task is None and isinstance(tid, str) and tid.startswith("evo_auto_"):
            task = tid[len("evo_auto_"):]
        c = counts.get(task, 0) if task else None
        results.append({"id": tid, "task": task,
                        "remaining_sigs": c,
                        "verified": (c == 0) if c is not None else False})
    return {"checked": len(results), "verified": sum(1 for r in results if r["verified"]),
            "results": results}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=os.path.join(
        os.path.expanduser("~"), ".dwc", "var", "dwc_prod.sqlite"))
    ap.add_argument("--prod", default=os.path.join(
        os.path.expanduser("~"), ".dwc"))
    a = ap.parse_args()
    r = verify(a.db, a.prod)
    print(json.dumps(r, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
