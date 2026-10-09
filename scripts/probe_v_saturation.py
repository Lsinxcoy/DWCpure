# -*- coding: utf-8 -*-
"""V_max_saturation 探针 —— R128 · 论文 V 的 max s_v 聚合饱和效应实测。

R127 留下的定位问题: LLM executor 起底后树内确有 0.0 判分节点, 但
dream 的 V 仍 = 1.0。本探针给出**根因的量化证据**:
  V = max s_v − β₁·N + β₂·(N / max{1,k})   （论文式逐字, replay.py L146）
  ⇒ s_v 在**观测面**上取 max ⇒ 观测面内只要有一个满分节点, max s_v=1.0
  ⇒ 其余节点的 0.0 对 V 无影响（被 max 吃掉）

这不是 bug（论文式如此, 不改论文迁就实现）; 是要如实记住的
**V 的结构性质**: 它对"最低分"不敏感, 只对"最高分"敏感。

用法: python scripts/probe_v_saturation.py
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, List

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.core import DWC                      # noqa: E402
from dwc.organs.judge import TaskScoreStore   # noqa: E402


def _anchors() -> Dict[str, Any]:
    return json.load(open(os.path.join(ROOT, "config", "anchors",
                                       "dev.json"), encoding="utf-8"))


def probe(score_plan: List[float], search_ids: List[str],
          verbose: bool = False) -> Dict[str, Any]:
    """★ 注入制造好的树观测（不调 LLM, 纯论文式算术验证）:
    score_plan[i] 写到第 i 个 search 节点上; 其余节点不写（未揭示）。
    ⇒ 回 V_by 与树内 score 分布, 用来量化 max 饱和。
    """
    d = DWC(3, 50, executor=None, db_path=":memory:")
    d.judge.store = TaskScoreStore(dw_version="probe_v_saturation")
    tree = d.world_model.trees.get("dev")
    written: Dict[str, float] = {}
    for i, tid in enumerate(search_ids):
        if i >= len(score_plan):
            break
        nd = tree.nodes.get(tid)
        if nd is None or score_plan[i] is None:
            continue
        d.world_model.record_observation("dev", tid, float(score_plan[i]),
                                         bool(score_plan[i] >= 0.5))
        written[tid] = float(score_plan[i])
    rep = d.dream(k2_max=4)
    v = rep.v_by_version.get("π0")
    nodes_scored = {nid: nd.score for nid, nd in tree.nodes.items()
                    if nd.score is not None}
    return {
        "injected": written,
        "v_pi0": v,
        "n_scored_nodes": len(nodes_scored),
        "max_s_in_tree": max(nodes_scored.values()) if nodes_scored else None,
        "min_s_in_tree": min(nodes_scored.values()) if nodes_scored else None,
        "V_eq_max_s": (v == (max(nodes_scored.values())
                             if nodes_scored else None)),
        "per_world": [(p[0], round(p[1], 6), p[2], p[3])
                      for p in rep.per_world],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "docs",
                                                  "v_saturation_probe.json"))
    args = ap.parse_args()
    anch = _anchors()
    sp = anch.get("_split") or {}
    search_ids = list(sp.get("search", []))
    if len(search_ids) < 3:
        print("★ D_search <3 ⇒ 探针不可用 ⇒ not_applicable")
        return 2

    # 三档（每档换 max 的组合; 全档含 0.0 证明 max 吃掉低分）
    n = len(search_ids)
    plans = {
        "all_ones": [1.0] * n,
        "one_zero_at_head": [0.0] + [1.0] * (n - 1),
        "one_zero_at_tail": [1.0] * (n - 1) + [0.0],
        "zeros_then_one": [0.0] * (n - 1) + [1.0],
        "no_ones_at_all": [0.0] * n,
    }
    results = {k: probe(v, search_ids) for k, v in plans.items()}
    out = {
        "probe": ("V_max_saturation: 论文式 V = max s_v − β₁N + β₂(N/max(1,k)) "
                  "的 s_v 在观测面取 max ⇒ max 饱和 ⇒ 观测面有满分即 "
                  "V 与低分无关（结构性质实测, 非 bug 非论文违反）"),
        "n_d_search": n,
        "results": results,
        "conclusions": {
            "all_ones_v": results["all_ones"]["v_pi0"],
            "one_zero_head_v": results["one_zero_at_head"]["v_pi0"],
            "one_zero_tail_v": results["one_zero_at_tail"]["v_pi0"],
            "zeros_then_one_v": results["zeros_then_one"]["v_pi0"],
            "no_ones_v": results["no_ones_at_all"]["v_pi0"],
            "saturates": bool(
                results["one_zero_at_head"]["v_pi0"]
                == results["all_ones"]["v_pi0"]
                == results["one_zero_at_tail"]["v_pi0"]),
            "★ 结论": ("一有 1.0 在观测面, 0.0 放头/尾都不影响 V; "
                       "只有全 0.0(无满分节点)V 才掉 —— max 饱和")
            if (results["one_zero_at_head"]["v_pi0"] == results["all_ones"]["v_pi0"]
                == results["one_zero_at_tail"]["v_pi0"])
            else "★ 异常: 0.0 影响了 V — 记录实际值, 不套结论",
            "含义": ("⇒ R127`V 恒等`根因=此结构性质(与 executor 无关): "
                     "起底只要有一个任务全对, 任何策略变体的 V 都顶格; "
                     "要测搜索策略差异, 须改的是**观测面构成**或**用 judge "
                     "逐任务分**, 不是换 executor"),
        },
        "caveats": [
            "本探针用注入观测（不走真执行）— 目的是隔离出 V 的算术性质",
            "β₁/β₂ 从 config/replay.yaml 读（论文无报值 ⇒  Suficiency 初值）",
            "V 的观测面=全量跨段累计（R102 段式; revealed_all ∪ root）",
        ],
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    for k, r in results.items():
        print("%-18s V=%s (scored=%s max=%s)" % (
            k, r["v_pi0"], r["n_scored_nodes"], r["max_s_in_tree"]))
    print("写出:", args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
