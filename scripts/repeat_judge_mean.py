# -*- coding: utf-8 -*-
"""judge_mean 口径 repeat 序列 —— R131 · R130 读数的方向稳定性证据。

R130 同参数两跑 B(LLM)=0.9 / 0.875 ⇒ 端点波动存在 ⇒ **单跑无方向
结论**（R124 repeat 纪律同款）。本脚本把 ga_duel --metric judge_mean
跑 N 次（seed 递增 42+i，其余参数不动），产出序列统计:

  · 每次的 best_v_single / best_v_ga / winner / basis
  · median / min / max（不报 mean-without-方差 — 端点右尾未核）
  · B 序列的 direction_stable: 是否全 <1.0（区分方向一致）
  · A 序列的 saturation: 是否恒 1.0（结构必然恒定）

不改 ga_duel.py 本身（R121-R130 协议已冻结; repeat 是**外部包装**
⇒ 单跑零破坏）。

用法: python scripts/repeat_judge_mean.py [--n 3] [--executor golden]
写出: docs/repeat_judge_mean.json
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from typing import Any, Dict, List

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable
GA = os.path.join(ROOT, "scripts", "ga_duel.py")


def _stats(xs: List[float]) -> Dict[str, Any]:
    """median/min/max（手写, 不引 statistics — 保持仓库零依赖纪律）。"""
    if not xs:
        return {"n": 0, "median": None, "min": None, "max": None}
    s = sorted(xs)
    n = len(s)
    med = (s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0)
    return {"n": n, "median": med, "min": s[0], "max": s[-1],
            "all_equal_1.0": all(v == 1.0 for v in s),
            "all_below_1.0": all(v < 1.0 for v in s)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=3)
    ap.add_argument("--executor", choices=["golden", "llm"], default="golden")
    ap.add_argument("--seed0", type=int, default=42)
    ap.add_argument("--out", default=os.path.join(ROOT, "docs",
                                                  "repeat_judge_mean.json"))
    args = ap.parse_args()
    if args.n < 3:
        print("★ n<3 不出方向结论（R130 两跑已证单跑无方向）⇒ not_applicable")
        return 2

    runs: List[Dict[str, Any]] = []
    for i in range(args.n):
        outp = os.path.join(ROOT, "docs", "ga_duel_repeat_%d.json" % i)
        r = subprocess.run([PY, GA, "--metric", "judge_mean",
                            "--executor", args.executor,
                            "--seed", str(args.seed0 + i), "--out", outp],
                           capture_output=True, timeout=1800, cwd=ROOT,
                           env=dict(os.environ, PYTHONIOENCODING="utf-8"))
        rc = r.returncode
        entry: Dict[str, Any] = {"seed": args.seed0 + i, "rc": rc}
        if rc == 0 and os.path.exists(outp):
            d = json.load(open(outp, encoding="utf-8"))
            entry.update({
                "best_v_single": d["verdict"]["best_v_single"],
                "best_v_ga": d["verdict"]["best_v_ga"],
                "winner": d["verdict"]["winner"],
                "basis": d["verdict"]["basis"],
                "accept_single": d["verdict"]["accept_single"],
                "accept_ga": d["verdict"]["accept_ga"],
            })
        else:
            entry["error"] = (r.stderr or r.stdout).decode("utf-8",
                                                           "replace")[-300:]
        runs.append(entry)
        print("跑%d seed=%d rc=%s single=%s ga=%s winner=%s" % (
            i, entry["seed"], rc,
            entry.get("best_v_single"), entry.get("best_v_ga"),
            entry.get("winner")))

    a_vals = [e["best_v_single"] for e in runs if "best_v_single" in e]
    b_vals = [e["best_v_ga"] for e in runs if "best_v_ga" in e]
    n_fail = sum(1 for e in runs if e["rc"] != 0)
    out = {
        "protocol": ("R131: ga_duel --metric judge_mean 跑 N 次(seed 递增, "
                     "其余不动) ⇒ 序列 median/min/max + 方向稳定性; "
                     "单跑无方向结论(R124/R130 纪律)"),
        "n": args.n, "executor": args.executor, "seed0": args.seed0,
        "runs": runs,
        "stats": {"A_golden": _stats(a_vals), "B_llm": _stats(b_vals),
                  "n_failed_runs": n_fail},
        "verdict": {
            "A_saturated_always": (bool(a_vals) and
                                   all(v == 1.0 for v in a_vals)),
            "B_below_1_always": (bool(b_vals) and
                                 all(v < 1.0 for v in b_vals)),
            "direction": ("A>B 稳定（golden 结构必然 1.0 vs LLM 真判分 "
                          "恒定 <1）— 但注意这是**执行体轴**的方向, 不是"
                          "策略优劣方向（度量假象同 R130）")
            if (a_vals and b_vals and all(v == 1.0 for v in a_vals)
                and all(v < 1.0 for v in b_vals))
            else "序列未收敛到单向 — 记录实际分布, 不套方向结论",
        },
        "caveats": [
            "winner=A 是度量假象（golden expected 全灌=1.0）— R130 同款, 不解读为策略优劣",
            "median/min/max 不做显著性检验（n=%d 端点右尾未核）" % args.n,
            "seed 只变 GA 搜索起点 —执行体差异不因 seed 变; 端点波动是真随机源",
            "重复跑是外部包装 ⇒ 不改 ga_duel 协议（R121-R130 冻结不动）",
        ],
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("A(median/min/max): %s / %s / %s" % (
        out["stats"]["A_golden"]["median"],
        out["stats"]["A_golden"]["min"], out["stats"]["A_golden"]["max"]))
    print("B(median/min/max): %s / %s / %s" % (
        out["stats"]["B_llm"]["median"],
        out["stats"]["B_llm"]["min"], out["stats"]["B_llm"]["max"]))
    print("方向:", out["verdict"]["direction"][:80])
    print("写出:", args.out)
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
