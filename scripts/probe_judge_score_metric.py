# -*- coding: utf-8 -*-
"""judge 逐任务分度量探针 —— R129 · R128 整改路径②的实证。

R128 定案: 论文式 V = max s_v − β₁N + β₂(N/k) 有 **max 饱和** ⇒ 观测面
有一个满分节点就顶格 ⇒ 恒等与 executor 无关。整改路径② = 换**搜索目标
度量**: 用 judge 逐任务分（TS3 口①）的均值而不是世界树节点的 max。

本探针做 A/B（同起底同任务, 只换度量）:
  A = 论文式 V（max 聚合, dream 产出）—— 已知恒等
  B = judge 逐任务分均值 / 组均值（TS3 口径, 但同样跑完任务集）
若 B 在 golden 替身下仍恒等而在 LLM 臂下有区分 ⇒ 证明"度量换掉后,
  区分度来自执行体"（这正是 R127 想要而拿错度量的东西）;
若 B 也恒等 ⇒ 说明任务集太易（都答对）, 记录"任务集难度不足"。

用法: python scripts/probe_judge_score_metric.py [--executor llm]
写出: docs/judge_score_metric.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, List, Optional

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from dwc.core import DWC                              # noqa: E402
from dwc.organs.judge import TaskScoreStore           # noqa: E402
from ga_duel import (PolicySpec, make_executor,       # noqa: E402
                     seed_population, _coerce)


def _anchors() -> Dict[str, Any]:
    return json.load(open(os.path.join(ROOT, "config", "anchors",
                                       "dev.json"), encoding="utf-8"))


def run(spec: PolicySpec, shared: DWC, search_ids: List[str]) -> float:
    """论文式 V（R128 已知性质 — A 口径）。"""
    rep = shared.dream(k2_max=4, policy_variants=[spec])
    return float(rep.v_by_version.get(spec.pid, 0.0))


def judge_metric(shared: DWC, spec: PolicySpec,
                 search_ids: List[str]) -> Optional[float]:
    """★ B 口径: 起底后直接取 judge 逐任务分的组均值（TS3）。

    注意: 这不是 dream — 是**同一执行体**判出的逐任务分, 均值聚合。
    spec 变体对判分无因果（判分由任务×执行体定）⇒ 此处 spec 参数只
    为对齐 A/B 调用形态; 真区分若存在, 应体现在执行体 arm 之间而非
    策略之间 —— 探针如实分两轴记录。
    """
    pts = shared.judge.task_scores(split="dev")
    if not pts:
        return None
    vals = [p.score for p in pts]
    return sum(vals) / len(vals)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--executor", choices=["golden", "llm"], default="golden")
    ap.add_argument("--out", default=os.path.join(ROOT, "docs",
                                                  "judge_score_metric.json"))
    args = ap.parse_args()
    anch = _anchors()
    sp = anch.get("_split") or {}
    search_ids = list(sp.get("search", []))
    if not search_ids:
        print("★ 无 _split ⇒ not_applicable")
        return 2

    shared = DWC(3, 50, executor=None, db_path=":memory:")
    shared.judge.store = TaskScoreStore(dw_version="probe_r129")
    shared.executor = make_executor(anch, mode=args.executor,
                                    memory=shared.memory)
    # 起底: 每 search 任务跑一次（与 ga_duel 起底同构）
    n_calls_before = len(shared.judge.task_scores(split="dev"))
    for tid in search_ids:
        out = shared.step({"task_id": tid, "kind": "dev"})
    pts = shared.judge.task_scores(split="dev")
    per_task = {p.task_id: p.score for p in pts}
    groups = shared.judge.group_scores(split="dev")

    # A 口径: 论文 V (同起底, 只取 π0)
    v_pi0 = run(PolicySpec(), shared, search_ids)
    # B 口径: judge 逐任务分均值 + 组均值
    mean_score = (sum(per_task.values()) / len(per_task)
                 if per_task else None)
    n_full = sum(1 for v in per_task.values() if v == 1.0)
    n_zero = sum(1 for v in per_task.values() if v == 0.0)

    identical_metric = (mean_score == 1.0)
    out = {
        "probe": ("R129 整改路径②实证: 同起底下 A=论文式V(max聚合) vs "
                  "B=judge逐任务分均值(TS3) — 若 A 恒等而 B 有区分 "
                  "⇒ 区分度来自度量选择; 都恒等 ⇒ 任务集对当前执行体"
                  "过易（难度不足, 非度量问题）"),
        "executor": args.executor,
        "n_search": len(search_ids),
        "judged_points_before": n_calls_before,
        "judged_points_after": len(pts),
        "per_task_score": per_task,
        "group_scores": groups,
        "metrics": {
            "A_dream_v_pi0": v_pi0,
            "B_judge_mean": mean_score,
            "n_full_marks": n_full,
            "n_zero_marks": n_zero,
            "n_mixed": n_full > 0 and n_zero > 0,
        },
        "verdict": {
            "A_saturated": v_pi0 == 1.0 and n_full > 0,
            "B_separates": (mean_score is not None and mean_score != 1.0),
            "reading": ("B 有区分（均值 %.4f) — max 饱和被均值解除; "
                        "但注意: judge 均值在**策略轴**上不变（判分由"
                        "任务×执行体定, 与 spec 无因果）⇒ 真区分须在"
                        "**执行体轴**上比（换 executor 才有区分）"
                        % mean_score)
            if (mean_score is not None and mean_score != 1.0)
            else ("A/B 都顶格 ⇒ 该执行体对这些任务全对 ⇒ 区分度受限于"
                  "任务集难度, 不换度量也不换执行体都测不出"),
        },
        "caveats": [
            "judge 均值对策略变体无因果 — 探针如实分两轴: 策略轴(恒等)/"
            "执行体轴(才可能有区分)",
            "本脚本一次跑无方差; 端点波动须 repeat 才有方向结论(R124 同)",
            "golden 替身下 expected 全灌 ⇒ B 必 1.0（结构必然, 预期内）",
        ],
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("executor=%s | A(V,π0)=%s | B(judge均值)=%s | 逐任务=%s"
          % (args.executor, v_pi0, mean_score, per_task))
    print("写出:", args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
