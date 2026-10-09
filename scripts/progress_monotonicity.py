# -*- coding: utf-8 -*-
"""progress 单调性验证 —— H-JEPA(2610.06805) 方案 A（R92 稿固化 · R99 执行）。

★★ 论文判据（Fig 8, 逐字核自 2610.06805）:
   沿**专家轨迹**的 cost 做 Spearman(cost, time) —— 好 cost 单调 0.89–1.00,
   坏 cost 0.48–0.75（subgoal tracking vs flat 全程 cost 的对照）。
★★ DWC 的差异（R92 稿已声明, 不在本脚本发明新阈值）:
   论文是 latent cost 沿连续时间; DWC 是进度指标沿 **trial 执行步**离散序列
   ⇒ 报 ρ + 参照区间, **不贴过强标签**（0.48≤|ρ|<0.89 记「弱/存疑」档）。

读:  docs/trial_report_*.json（records: term/pool_rate/delta_top3/judged）
写:  docs/progress_monotonicity_r92.json（R92 稿定名）
判读分支（R92 稿 · 阶段 2 排序依据）:
   ρ 强单调 ⇒ C 的组 cost 改造降级、先做 B（死锁是硬伤）
   ρ 弱/振荡 ⇒ C 的分级 cost 升优先

用法: python scripts/progress_monotonicity.py [report.json ...]
"""
from __future__ import annotations

import glob
import json
import os
import sys
from typing import Dict, List, Optional, Sequence

#: 论文区间（2610.06805 Fig 8 —— 参照, 不是 DWC 阈值）
PAPER_STRONG = 0.89   # 好 cost 下界（0.89–1.00）
PAPER_WEAK = 0.48     # 坏 cost 下界（0.48–0.75）

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _ranks(xs: Sequence[float]) -> List[float]:
    """平均秩（并列取平均 —— Spearman 标准处理）。"""
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    ranks = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0            # 1-based 平均秩
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def spearman(xs: Sequence[float], ys: Sequence[float]) -> Optional[float]:
    """Spearman ρ（手写 —— 不引 scipy; n≈20 秩相关, 并列平均秩）。"""
    if len(xs) != len(ys) or len(xs) < 3:
        return None                          # n<3 不算（显式 None, 不装 0）
    rx, ry = _ranks(xs), _ranks(ys)
    n = len(xs)
    mx = sum(rx) / n
    my = sum(ry) / n
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    dx = sum((a - mx) ** 2 for a in rx) ** 0.5
    dy = sum((b - my) ** 2 for b in ry) ** 0.5
    if dx == 0.0 or dy == 0.0:
        return None                          # 常数序列无秩相关（显式）
    return num / (dx * dy)


def _pair_values(seq) -> Optional[List[float]]:
    """delta_top3/judged 的真实形态是 **[key, value] 对列表**（R82 实测）:
      · delta_top3 = [[task_id, δ], ...]
      · judged     = [[task_id, bool], ...]
    兼容裸数值列表（未来形态）; 认不出 ⇒ None（显式跳过, 不猜）。"""
    if not isinstance(seq, list) or not seq:
        return None
    out: List[float] = []
    for x in seq:
        if isinstance(x, bool):
            out.append(1.0 if x else 0.0)
        elif isinstance(x, (int, float)):
            out.append(float(x))
        elif isinstance(x, (list, tuple)) and len(x) == 2:
            v = x[1]
            if isinstance(v, bool):
                out.append(1.0 if v else 0.0)
            elif isinstance(v, (int, float)):
                out.append(float(v))
            else:
                return None                  # 对值不可数 ⇒ 整条不取（显式）
        else:
            return None                      # 混形态 ⇒ 整条不取（显式）
    return out


def judge_rate(record: Dict) -> Optional[float]:
    """record['judged'] 的通过率（取不到 ⇒ None, 不冒充）。"""
    vals = _pair_values(record.get("judged"))
    return sum(vals) / len(vals) if vals else None


def series(records: List[Dict]) -> Dict[str, List[float]]:
    """三指标沿 term 序（全部取「越大越好」口径 —— cost 类取负）。"""
    s_pool, s_negtop, s_jr = [], [], []
    for r in records:
        p = r.get("pool_rate")
        if isinstance(p, (int, float)):
            s_pool.append(float(p))
        dts = _pair_values(r.get("delta_top3"))
        if dts:
            s_negtop.append(-max(dts))       # cost 口径取负
        jr = judge_rate(r)
        if jr is not None:
            s_jr.append(jr)
    return {"pool_rate": s_pool, "neg_delta_top3_max": s_negtop,
            "judge_rate": s_jr}


def verdict_of(rho: Optional[float]) -> str:
    """参照论文区间的三档判读（★ 不发明新阈值）。"""
    if rho is None:
        return "not_computable"
    a = abs(rho)
    if a >= PAPER_STRONG:
        return "strong_monotone"       # 参照论文好 cost 档（0.89–1.00）
    if a >= PAPER_WEAK:
        return "weak_or_uncertain"     # 参照论文坏 cost 档（0.48–0.75）
    return "no_monotone"


def analyze(path: str) -> Dict:
    with open(path, encoding="utf-8") as f:
        rep = json.load(f)
    records = rep.get("records") or []
    s = series(records)
    n_terms = len(records)
    out = {
        "source": os.path.basename(path),
        "n_terms": n_terms,
        "series_len": {k: len(v) for k, v in s.items()},
        "spearman": {}, "verdict": {},
        "paper_reference": {
            "strong": "0.89–1.00 (好 cost, Fig 8)",
            "weak": "0.48–0.75 (坏 cost, Fig 8)",
            "note": ("DWC 指标沿 trial 执行步离散序列, 论文沿专家轨迹连续时间 "
                     "—— 参照区间只作档位, 不贴绝对标签（R92 稿声明）"),
        },
    }
    # x = 步序（1..n）, y = 指标 —— 「指标随步进是否单调」
    for name, ys in s.items():
        rho = spearman(list(range(1, len(ys) + 1)), ys)
        out["spearman"][name] = rho
        out["verdict"][name] = verdict_of(rho)
    out["branch_r92"] = ("C_cost_downgrade_first_B"    # 全强 ⇒ C 降级先 B
        if out["verdict"].get("pool_rate") == "strong_monotone"
           or out["verdict"].get("neg_delta_top3_max") == "strong_monotone"
        else "C_cost_upgrade"                          # 弱/无 ⇒ C 升优先
        if n_terms >= 3 else "insufficient_terms")
    return out


def main(argv: List[str]) -> int:
    paths = argv or sorted(
        glob.glob(os.path.join(ROOT, "docs", "trial_report_*.json")))
    if not paths:
        print("无 trial 报告可分析", file=sys.stderr)
        return 2
    results = [analyze(p) for p in paths]
    out_path = os.path.join(ROOT, "docs",
                            "progress_monotonicity_r92.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"reports": results}, f, ensure_ascii=False, indent=1)
    for r in results:
        print("%-52s n=%d" % (r["source"], r["n_terms"]))
        for k, rho in r["spearman"].items():
            print("    %-20s rho=%s  %s"
                  % (k, ("%.3f" % rho) if rho is not None else "None",
                     r["verdict"][k]))
        print("    branch(R92): %s" % r["branch_r92"])
    print("写出:", out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
