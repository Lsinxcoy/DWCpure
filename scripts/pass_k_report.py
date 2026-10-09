# -*- coding: utf-8 -*-
"""pass^k + 重复采样方差报告 —— τ-bench(2406.12045) + Phi-4(2504.21318) 纪律（R99·1b）。

★★ τ-bench: pass^k 无偏估计 = C(c,k)/C(n,k)（k 次独立试验全对的概率）。
★★ Phi-4 纪律: 同条件重复跑报 std、批判单次单分数（两次 5-run 可差 5–10pp）。
★★ DWC 的口径诚实（不编造）:
   · 数据 = trial 报告的同任务跨 term 布尔序列（judged = [[task, bool], ...]）
   · ★ 该序列**非严格 iid**（跨 term 上下文不同、judge 确定性）⇒ approx_iid=false,
     报告只作「任务通过的稳定性读数」, 不冒充严格 pass^k 实验
   · judge 判分本身零随机（R50 实测 5 次 std=0.0）⇒ 方差来自任务池/上下文, 非判分器

读:  docs/trial_report_*.json
写:  docs/pass_k_report.json
用法: python scripts/pass_k_report.py
"""
from __future__ import annotations

import glob
import json
import math
import os
import sys
from collections import defaultdict
from typing import Dict, List

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

KS = (2, 3, 4)   # τ-bench 报 k=1..8; DWC trial 序列短, 只报有数据支撑的 k≤4


def pass_k(c: int, n: int, k: int) -> float:
    """pass^k 无偏估计 C(c,k)/C(n,k)（τ-bench Eq; n<k ⇒ 调用方不报）。"""
    if k > n or c < 0 or n <= 0:
        raise ValueError("pass_k 参数越界: c=%d n=%d k=%d" % (c, n, k))
    if c < k:
        return 0.0
    return math.comb(c, k) / math.comb(n, k)


def _pairs(seq) -> List[list]:
    return [x for x in (seq or [])
            if isinstance(x, (list, tuple)) and len(x) == 2]


def analyze(path: str) -> Dict:
    rep = json.load(open(path, encoding="utf-8"))
    per: Dict[str, List[bool]] = defaultdict(list)
    for r in rep.get("records") or []:
        for pair in _pairs(r.get("judged")):
            v = pair[1]
            if isinstance(v, bool):
                per[str(pair[0])].append(v)
    tasks = {}
    all_k: Dict[str, List[float]] = {k: [] for k in KS}
    for t, seq in sorted(per.items()):
        n, c = len(seq), sum(seq)
        rate = c / n if n else None
        row = {"n": n, "c": c, "rate": rate}
        for k in KS:
            if n >= k:
                v = pass_k(c, n, k)
                row["pass^%d" % k] = v
                all_k[k].append(v)
        tasks[t] = row
    # 跨任务通过率的 std（Phi-4 方差纪律: 同报告内任务间离散度）
    rates = [r["rate"] for r in tasks.values() if r["rate"] is not None]
    std = None
    if len(rates) >= 2:
        m = sum(rates) / len(rates)
        std = math.sqrt(sum((x - m) ** 2 for x in rates) / (len(rates) - 1))
    return {
        "source": os.path.basename(path),
        "approx_iid": False,
        "iid_note": ("同任务跨 term 序列非严格独立同分布（上下文不同 + judge "
                     "确定性）⇒ 读作稳定性, 不冒充严格 pass^k 实验"),
        "per_task": tasks,
        "mean_pass_k": {("pass^%d" % k): (
            sum(v) / len(v) if v else None) for k, v in all_k.items()},
        "rate_std_across_tasks": std,
        "n_tasks": len(tasks),
    }


def main() -> int:
    paths = sorted(glob.glob(os.path.join(ROOT, "docs",
                                           "trial_report_*.json")))
    if not paths:
        print("无 trial 报告", file=sys.stderr)
        return 2
    out = {"reports": [analyze(p) for p in paths],
           "formula": "pass^k = C(c,k)/C(n,k)（无偏, τ-bench）",
           "k_list": list(KS)}
    p = os.path.join(ROOT, "docs", "pass_k_report.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    for r in out["reports"]:
        print("%-46s 任务=%d std=%s" % (
            r["source"], r["n_tasks"],
            ("%.4f" % r["rate_std_across_tasks"])
            if r["rate_std_across_tasks"] is not None else "None"))
        print("    mean:", {k: (round(v, 4) if v is not None else None)
                            for k, v in r["mean_pass_k"].items()})
    print("写出:", p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
