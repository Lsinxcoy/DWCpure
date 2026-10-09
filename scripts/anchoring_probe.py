# -*- coding: utf-8 -*-
"""锚定探针 —— Verma(2607.26117) inter-attempt 相似度的 DWC 版（R99 · 阶段1b）。

★★ Verma: 相似度 >0.95 = near-identical（锚定: 反复产出同款的在线度量）。
★★ DWC 的口径诚实（不编造可比性）:
   · 原料 = config/anchors/liquidity.jsonl 的 d_i（每次 edit 的 diff 文本）
   · Verma 比的是**同一任务的多次尝试**; DWC 比的是**历次 edit diff** ——
     对象不同 ⇒ 阈值 0.95 只作参照报警, 不作结论（近同款 edit ⇒ 疑似锚定/重复）
   · 数据缺/空 ⇒ no_data 显式（不装 0.0）

读:  config/anchors/liquidity.jsonl（evolver.record_edit 的落盘）
写:  docs/anchoring_probe.json
用法: python scripts/anchoring_probe.py
"""
from __future__ import annotations

import difflib
import glob
import json
import os
import sys
from typing import Any, Dict, List

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIQ = os.path.join(ROOT, "config", "anchors", "liquidity.jsonl")
THRESH = 0.95          # Verma 参照阈值（口径差见模块头 —— 只报警不结论）


def ratio(a: str, b: str) -> float:
    """两段 diff 文本的相似度（difflib 归一到 [0,1]）。"""
    return difflib.SequenceMatcher(None, a, b).ratio()


def probe(recs: List[Dict[str, Any]]) -> Dict[str, Any]:
    diffs = [(i, str(r.get("d_i") or "")) for i, r in enumerate(recs)
             if str(r.get("d_i") or "").strip()]
    pairs: List[Dict[str, Any]] = []
    mx = 0.0
    near = 0
    for x in range(len(diffs)):
        for y in range(x + 1, len(diffs)):
            s = ratio(diffs[x][1], diffs[y][1])
            mx = max(mx, s)
            if s >= THRESH:
                near += 1
                pairs.append({"i": diffs[x][0], "j": diffs[y][0],
                              "ratio": round(s, 4)})
    return {
        "n_records": len(recs),
        "n_with_diff": len(diffs),
        "n_pairs": len(diffs) * (len(diffs) - 1) // 2,
        "max_ratio": round(mx, 4) if diffs else None,
        "near_identical_pairs": near,      # ≥0.95 的对数（Verma 参照报警）
        "near_identical_list": pairs[:20],
        "threshold": THRESH,
        "caveat": ("对象口径差: Verma 比同任务多次尝试, 本探针比历次 edit "
                   "diff ⇒ ≥0.95 报警『疑似重复编辑』, 不直接等于锚定结论"),
    }


def main() -> int:
    if not os.path.exists(LIQ):
        out = {"status": "no_data", "why": "liquidity.jsonl 不存在",
               "path": os.path.relpath(LIQ, ROOT).replace("\\", "/")}
    else:
        recs = []
        for line in open(LIQ, encoding="utf-8"):
            line = line.strip()
            if line:
                recs.append(json.loads(line))
        if not recs:
            out = {"status": "no_data", "why": "liquidity.jsonl 为空",
                   "path": os.path.relpath(LIQ, ROOT).replace("\\", "/")}
        else:
            out = {"status": "ok", "probe": probe(recs)}
    p = os.path.join(ROOT, "docs", "anchoring_probe.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False, indent=1))
    print("写出:", p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
