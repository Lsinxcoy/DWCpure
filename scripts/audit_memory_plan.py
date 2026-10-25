#!/usr/bin/env python3
"""audit_memory_plan · 机制矩阵 vs 代码/测试落点审计（可复跑）。

定位声明 · **DWC-AUTO**（自我强化）
  ★ 只做文件/符号/测试存在性检查；不判断语义正确性、不跑测试。
  ★ 缺文件/缺符号/缺测试 ⇒ exit 1；否则 exit 0。
"""
from __future__ import annotations

import csv
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def audit(matrix_path: str) -> dict:
    rows = list(csv.DictReader(open(matrix_path, encoding="utf-8")))
    issues = []
    for row in rows:
        files = []
        for part in re.split(r"\s*\+\s*", row.get("target") or ""):
            path = part.split(":", 1)[0].strip()
            if path.endswith(".py"):
                files.append(path)
        for path in files:
            if not os.path.exists(os.path.join(ROOT, path)):
                issues.append({"id": row["id"], "kind": "missing_file",
                               "target": path})
        test = (row.get("test") or "").split()[0]
        if test and not os.path.exists(os.path.join(ROOT, "tests", test)):
            issues.append({"id": row["id"], "kind": "missing_test",
                           "target": test})
        for part in re.split(r"\s*\+\s*", row.get("target") or ""):
            if ":" not in part:
                continue
            path, symbols = part.split(":", 1)
            path = path.strip()
            fp = os.path.join(ROOT, path)
            text = open(fp, encoding="utf-8").read() \
                if os.path.exists(fp) else ""
            for sym in symbols.split("/"):
                sym = sym.strip()
                if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", sym or ""):
                    continue
                if sym not in text:
                    issues.append({"id": row["id"], "kind": "missing_symbol",
                                   "target": "%s:%s" % (path, sym)})
    return {
        "matrix": matrix_path,
        "rows": len(rows),
        "adopt": sum(1 for r in rows if r.get("status") == "adopt"),
        "conditional": sum(1 for r in rows
                           if r.get("status") == "conditional"),
        "issues": issues,
        "ok": not issues,
    }


def main(argv: list[str]) -> int:
    path = argv[1] if len(argv) > 1 else os.path.join(
        ROOT, "docs", "research", "memory_mechanism_matrix.csv")
    out = audit(path)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
