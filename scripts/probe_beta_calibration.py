# -*- coding: utf-8 -*-
"""β 校准探针 —— R132 · 论文 V 的 β₁/β₂ 非退化扫描。

R128 已解: V = max s_v − β₁·N + β₂·(N/max{1,k}) 的 max 聚合饱和。
R132 解另一半: config/replay.yaml 现 β₁=β₂=0（初始值=β≥0 边界,
注释明写"非零值须经校准协议后才许写入"）⇒ V ≡ max s_v,
   ⇒ N/k 项对 V **数学零因果** ⇒ 策略变体只改揭示路径 ⇒ 不可能分化
这不是采样饱和, 是**系数选择**导致的退化 — 校准协议正是注释指定的
解除路径。

探针做什么（不写死"正确的 β" — 那是测量协议该回答的）:
  对 β 网格（β₁ ∈ {0, 0.02, 0.05, 0.1} × β₂ ∈ {0, 0.05, 0.1}）:
    · 用 R128 探针同款的**注入观测树**（不走 LLM, 零端点, 可复现）
    · 对同一批策略变体（w_delta / seg_order / prefer_revealable）跑 dream
    · 记录每 (β₁,β₂) 下: ① V 是否仍全恒等 ② 若分化, 变体排序如何
  输出"退化→分化"的 β 边界（供校准协议引用, 不自动写配置）

★ 纪律: 本探针**不改 config/replay.yaml**（注释明示非零须校准协议后才
  许写入; 校准协议裁决归用户/后续轮, 探针只给数据）。

用法: python scripts/probe_beta_calibration.py
写出: docs/beta_calibration.json
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import sys
from typing import Any, Dict, List, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from dwc.core import DWC                              # noqa: E402
from dwc.organs.judge import TaskScoreStore           # noqa: E402
from dwc.foundation.dial_config import load_replay    # noqa: E402

from ga_duel import PolicySpec, seed_population        # noqa: E402


def _anchors() -> Dict[str, Any]:
    return json.load(open(os.path.join(ROOT, "config", "anchors",
                                       "dev.json"), encoding="utf-8"))


def build_tree(score_plan: List[float], search_ids: List[str]
               ) -> DWC:
    """同 R128: 注入观测构造树（不走真端点）— 隔离 β 效应。"""
    d = DWC(3, 50, executor=None, db_path=":memory:")
    d.judge.store = TaskScoreStore(dw_version="probe_r132")
    for i, tid in enumerate(search_ids):
        if i >= len(score_plan):
            break
        d.world_model.record_observation("dev", tid, float(score_plan[i]),
                                         bool(score_plan[i] >= 0.5))
    return d


def run_variants(d: DWC, betas: Tuple[float, float]) -> Dict[str, float]:
    """★ 核心: 临时替换 cfg（内存内, 不落盘）后跑 M=4 变体 dream。"""
    from dwc.foundation import dial_config as dc
    real = dc.REPLAY_PATH
    tmp = os.path.join(ROOT, "config", "_tmp_replay_probe.yaml")
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("replay:\n  beta1: %r\n  beta2: %r\n  history_max: 16\n"
                % betas)
    try:
        dc.REPLAY_PATH = tmp
        specs = seed_population()          # π0 + 三单键（同 ga_duel 同起点）
        rep = d.dream(k2_max=4, policy_variants=specs)
        return dict(rep.v_by_version)
    finally:
        dc.REPLAY_PATH = real
        if os.path.exists(tmp):
            os.remove(tmp)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "docs",
                                                  "beta_calibration.json"))
    args = ap.parse_args()
    anch = _anchors()
    ids = list((anch.get("_split") or {}).get("search", []))
    if len(ids) < 3:
        print("★ D_search <3 ⇒ not_applicable")
        return 2

    cfg = load_replay()
    n = len(ids)
    # 三档树（同 R128: 全 1.0 / 含 0.0 / 全 0.0）— 看 β 在各 s_v 分布的效应
    trees = {
        "all_ones": [1.0] * n,
        "mixed_001": [0.0] + [1.0] * (n - 1),
        "all_zeros": [0.0] * n,
    }
    grid = [(b1, b2) for b1 in (0.0, 0.02, 0.05, 0.1)
            for b2 in (0.0, 0.05, 0.1)]

    results: List[Dict[str, Any]] = []
    for tree_name, plan in trees.items():
        d = build_tree(plan, ids)
        for b1, b2 in grid:
            v_by = run_variants(d, (b1, b2))
            vals = sorted(set(round(v, 6) for v in v_by.values()))
            results.append({
                "tree": tree_name, "beta1": b1, "beta2": b2,
                "n_distinct_v": len(vals),
                "v_values": vals,
                "degenerate": len(vals) <= 1,
                "v_by": v_by,
            })
        print("树=%s 完 %d 组合" % (tree_name, len(grid)))

    degen_beta0 = all(r["degenerate"] for r in results
                      if r["beta1"] == 0.0 and r["beta2"] == 0.0)
    sep = [r for r in results if not r["degenerate"]]
    out = {
        "probe": ("R132: β 校准探针 — V=max s_v−β₁N+β₂(N/max(1,k)) 中 β 非"
                  "退化扫描。现配置 β₁=β₂=0(初始边界) ⇒ V≡max s_v ⇒ N/k"
                  "项数学零因果 ⇒ 策略变体只改揭示路径 ⇒ 不可能分化。"
                  "本探针扫 β 网格找『退化→分化』边界, 不改配置。"),
        "current_config": {"beta1": cfg["beta1"], "beta2": cfg["beta2"]},
        "grid": {"beta1": [0.0, 0.02, 0.05, 0.1],
                 "beta2": [0.0, 0.05, 0.1]},
        "n_results": len(results),
        "results": results,
        "verdict": {
            "beta0_always_degenerate": degen_beta0,
            "n_separating_combos": len(sep),
            "separating_combos": [
                {"tree": r["tree"], "beta1": r["beta1"], "beta2": r["beta2"],
                 "n_distinct_v": r["n_distinct_v"], "v_values": r["v_values"]}
                for r in sep],
            "reading": ("β=0 全退化为真 ⇒ 恒等的**系数根因**坐实(与 R128"
                        "的聚合根因互补); %s"
                        % ("有 β 组合出分化 ⇒ 校准边界可见(上表)"
                           if sep else
                           "本注入树族下无 β 组合分化 ⇒ 分化还受树形/观测"
                           "面约束, 须换树族或接 judge 臂再扫")),
        },
        "caveats": [
            "注入观测(不走真端点) ⇒ 隔离 β 效应, 换不来 LLM 真差异",
            "不改 config/replay.yaml — 注释明示非零须校准协议后才许写入, 协议裁决归用户/后续轮",
            "分红依赖树形/s_v 分布/N/k 的可变性 — 单一树族结论不外推",
            "M=4 变体(π0+三单键)同 ga_duel 起点; 未含交叉/组合个体",
        ],
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("β=0 全退化:", degen_beta0, "| 分化组合数:", len(sep))
    for r in sep[:6]:
        print("  ★ %s β₁=%s β₂=%s ⇒ %d 个不同 V %s"
              % (r["tree"], r["beta1"], r["beta2"], r["n_distinct_v"],
                 r["v_values"]))
    print("写出:", args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
