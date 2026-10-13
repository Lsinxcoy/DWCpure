# -*- coding: utf-8 -*-
"""nightbench_weekly · 成功率周报（R260 — 短板 2 的收敛证据汇总）。

读 var/eval/success_curve.jsonl → 最近 7 天成功率曲线 + 分类型 + 修订回路
活动（dwc_pairs.jsonl 修订对数 / dwc_skills 固化数）。
输出: stdout（cron deliver=local 落盘）。
"""
from __future__ import annotations

import io
import json
import os
import sys
import time
from collections import Counter

def _find_root() -> str:
    """★ cron 拷贝跑时 __file__ 在 hermes/scripts — 向上找 .dwc_repo 标记。"""
    d = os.path.dirname(os.path.abspath(__file__))
    for _ in range(6):
        if os.path.exists(os.path.join(d, ".dwc_repo")):
            return d
        d = os.path.dirname(d)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_ROOT = _find_root()
CURVE = os.path.join(_ROOT, "var", "eval", "success_curve.jsonl")
PAIRS = os.path.join(_ROOT, "var", "dwc_pairs.jsonl")
SKILLS = os.path.join(_ROOT, "var", "dwc_skills")


def main() -> int:
    if not os.path.exists(CURVE):
        print("（暂无跑批曲线 — nightbench 未跑）")
        return 0
    rows = [json.loads(l) for l in io.open(CURVE, encoding="utf-8")
            if l.strip()]
    cutoff = time.strftime("%Y-%m-%d", time.localtime(time.time() - 7 * 86400))
    week = [r for r in rows if r.get("at", "") >= cutoff]
    if not week:
        print("（最近 7 天无跑批记录）")
        return 0
    n_ok = sum(1 for r in week if r.get("ok"))
    print("==== DWC 无人值守周报（%s 起, %d 单）====" % (cutoff, len(week)))
    print("成功率: %d/%d = %.1f%%" % (n_ok, len(week),
                                     100 * n_ok / max(1, len(week))))
    by_day = {}
    for r in week:
        d = r.get("at", "")[:10]
        by_day.setdefault(d, []).append(1 if r.get("ok") else 0)
    for d in sorted(by_day):
        v = by_day[d]
        print("  %s: %d/%d" % (d, sum(v), len(v)))
    kinds = Counter(r.get("kind", "?") for r in week)
    print("分类型:", json.dumps(
        {k: "%d单" % v for k, v in kinds.items()}, ensure_ascii=False))
    n_pairs = 0
    if os.path.exists(PAIRS):
        n_pairs = sum(1 for _ in io.open(PAIRS, encoding="utf-8"))
    n_skills = len([f for f in os.listdir(SKILLS)
                    if f.endswith(".md") and not f.startswith("_")]) \
        if os.path.isdir(SKILLS) else 0
    print("修订回路: 任务修订对 %d · 固化规矩 %d 个" % (n_pairs, n_skills))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
