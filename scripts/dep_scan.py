# -*- coding: utf-8 -*-
"""dep(z) 定向失效扫描 —— R113 · E1（设计稿④ §⑥, 与裁决① HCE 合流的那份记录）。

语义（RQGM selective erasure + Metis invalidate 同型 — RUMINATE 探针③:
文献已知做法）: 换评估器 ⇒ **只标记依赖旧评估器的档**, 其余历史不动;
**不物理删**（Humanlaya 版本化 — 历史可审计）只改有效性状态。

分栏（设计稿④ §⑦ 弃置三态的 E1 面）:
  active                     — 六段档且 judge_fingerprint == 当前 judge.py 指纹
  deprecated_by_evaluator    — 六段档且指纹 ≠ 当前（换代触发, 待 E2 首次换代
                               产生此类; 现扫现报, 无则计数 0 — 不装数）
  pre_depz_legacy            — 无 inheritance 字段的旧档（依赖记录建立前,
                               不可判定 — 显式栏, 不冒充 active）
★ 本脚本**只读不改档** — deprecated 的真正置位动作在换代轮（E2）按本报告执行。

读:  archive/knowledge3_*.json · src/dwc/organs/judge.py（当前指纹）
写:  docs/dep_scan.json
用法: python scripts/dep_scan.py
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, List

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.foundation.inheritance import judge_fingerprint  # noqa: E402

JUDGE_PATH = os.path.join(ROOT, "src", "dwc", "organs", "judge.py")


def scan(archive_dir: str, current_fp: str) -> Dict[str, Any]:
    rows: List[Dict[str, Any]] = []
    bucket = {"active": [], "deprecated_by_evaluator": [], "pre_depz_legacy": []}
    for fn in sorted(os.listdir(archive_dir)):
        if not (fn.startswith("knowledge3_") and fn.endswith(".json")):
            continue
        with open(os.path.join(archive_dir, fn), encoding="utf-8") as f:
            rec = json.load(f)
        if not isinstance(rec, dict):
            continue                       # 历史 list 形态档（inheritance 同款）
        inh = rec.get("inheritance")
        if not isinstance(inh, dict):
            bucket["pre_depz_legacy"].append(fn)
            rows.append({"file": fn, "status": "pre_depz_legacy",
                         "judge_fingerprint": None,
                         "why": "无六段/无依赖字段（dep(z) 建立前）"})
            continue
        fp = (inh.get("evaluation_config") or {}).get("judge_fingerprint")
        status = ("active" if fp == current_fp else
                  "deprecated_by_evaluator" if fp else "pre_depz_legacy")
        bucket[status].append(fn)
        rows.append({"file": fn, "status": status,
                     "judge_fingerprint": fp,
                     "why": ("指纹与当前 judge 一致" if status == "active"
                             else "★ 指纹 ≠ 当前 judge ⇒ 换代时须置 "
                                  "deprecated" if status ==
                             "deprecated_by_evaluator" else "字段缺失")})
    return {
        "protocol": ("dep(z): 只标记依赖旧评估器的档, 不物理删; 本报告只读, "
                     "置位动作在换代轮(E2)按此执行"),
        "current_judge_fingerprint": current_fp,
        "counts": {k: len(v) for k, v in bucket.items()},
        "rows": rows,
        "note": ("deprecated_by_evaluator=0 属正常（E2 首次换代前无换代）"
                 " — 不装数不造档"),
        "split_change": ("deprecated_by_split_change 栏随裁决① HCE 拍定后"
                         "启用（dep(z) 同一份记录, 第二触发源）"),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--archive", default=os.path.join(ROOT, "archive"))
    ap.add_argument("--out", default=os.path.join(ROOT, "docs",
                                                  "dep_scan.json"))
    args = ap.parse_args()
    fp = judge_fingerprint(JUDGE_PATH)
    rep = scan(args.archive, fp)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=1)
    print("judge fp:", fp, "| 分栏:", rep["counts"])
    print("写出:", args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
