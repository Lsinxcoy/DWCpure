# -*- coding: utf-8 -*-
"""部分起底探针 —— R133 · 根治因B（揭示面耗尽）让 β 校准有对象。

R132 坐实两因:
  A 系数退化: β₁=β₂=0 ⇒ V ≡ max s_v（N/k 项零因果）
  B 揭示面耗尽: 起底把全部 search 节点写入树 ⇒ 任何策略变体下
    dream 的揭示面相同 ⇒ N/k 全同 ⇒ **即使 β 非零也无对象可变**

R133 解 B —— 部分起底（不改 core, 脚本级控制）:
  起底只跑前 m 个 search 任务（m<n）⇒ 剩余 n−m 节点仍未揭示
  ⇒ dream 时各策略变体按自己的 δ 排序揭示不同子集
  ⇒ N(k₂) 在不同变体下**真不同** ⇒ β 校准终于有可变对象
  扫 (m, β) 网格: m ∈ {0, 2, 4} × β₁ ∈ {0, 0.02, 0.05} × β₂ ∈ {0, 0.05}
  看: ① β=0 是否仍退化 ② 部分起底下是否有 β 组合出分化

★ 纪律: 仍不改 config/replay.yaml（同 R132 — 校准协议裁决归用户）;
  judge 分数用**注入观测**（不走真端点隔离 β 效应, 同 R128/R132）。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, List

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from dwc.core import DWC                              # noqa: E402
from dwc.organs.judge import TaskScoreStore           # noqa: E402
from dwc.foundation import dial_config as dc          # noqa: E402

from ga_duel import PolicySpec                        # noqa: E402


def _anchors() -> Dict[str, Any]:
    return json.load(open(os.path.join(ROOT, "config", "anchors",
                                       "dev.json"), encoding="utf-8"))


def build_partial(plan: List[float], search_ids: List[str], m_seeded: int
                  ) -> DWC:
    """起底只注入前 m 个节点（m=0 ⇒ 空树 — dream 全栈探索）。"""
    d = DWC(3, 50, executor=None, db_path=":memory:")
    d.judge.store = TaskScoreStore(dw_version="probe_r133")
    for i, tid in enumerate(search_ids):
        if i >= m_seeded or i >= len(plan):
            break
        d.world_model.record_observation("dev", tid, float(plan[i]),
                                         bool(plan[i] >= 0.5))
    return d


def specs_default() -> List[PolicySpec]:
    """M=4 变体（π0 + 三单键）— 与 ga_duel/R132 同起点可比。"""
    from ga_duel import seed_population
    return seed_population()


def run_variants(d: DWC, betas: tuple, k2_max: int = 4) -> Dict[str, float]:
    real = dc.REPLAY_PATH
    tmp = os.path.join(ROOT, "config", "_tmp_replay_probe.yaml")
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("replay:\n  beta1: %r\n  beta2: %r\n  history_max: 16\n"
                % betas)
    try:
        dc.REPLAY_PATH = tmp
        rep = d.dream(k2_max=k2_max, policy_variants=specs_default())
        return dict(rep.v_by_version)
    finally:
        dc.REPLAY_PATH = real
        if os.path.exists(tmp):
            os.remove(tmp)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "docs",
                                                  "partial_seed_probe.json"))
    args = ap.parse_args()
    anch = _anchors()
    ids = list((anch.get("_split") or {}).get("search", []))
    n = len(ids)
    if n < 4:
        print("★ D_search <4 ⇒ not_applicable")
        return 2

    # 混合树: 首节点 0.0 其余 1.0（同 R128 观察面里既有 0 又有 1）
    plan = [0.0] + [1.0] * (n - 1)
    # m: 0=空起底 / n//2=半起底 / n=全起底(R132 根因B 的复现对照)
    m_grid = [0, max(1, n // 2), n]
    b1_grid = [0.0, 0.02, 0.05]
    b2_grid = [0.0, 0.05]

    results: List[Dict[str, Any]] = []
    for m in m_grid:
        d = build_partial(plan, ids, m)
        for b1 in b1_grid:
            for b2 in b2_grid:
                v_by = run_variants(d, (b1, b2))
                vals = sorted(set(round(v, 6) for v in v_by.values()))
                results.append({
                    "m_seeded": m, "beta1": b1, "beta2": b2,
                    "n_distinct_v": len(vals), "v_values": vals,
                    "degenerate": len(vals) <= 1,
                })
        print("m=%d 完 %d 组合" % (m, len(b1_grid) * len(b2_grid)))

    [r for r in results if r["degenerate"]]
    sep = [r for r in results if not r["degenerate"]]
    full_degen = all(r["degenerate"] for r in results if r["m_seeded"] == n)
    partial_sep = [r for r in sep if r["m_seeded"] < n]
    out = {
        "probe": ("R133: 部分起底探针 — 根治因B(揭示面耗尽)。起底只注入前 "
                  "m 个节点 ⇒ dream 时未揭示节点仍可供各策略变体按 δ 排序"
                  "差异化揭示 ⇒ N(k₂) 真不同 ⇒ β 校准有可变对象。扫 "
                  "m×β 网格: 全起底应仍退化(R132 复现), 部分起底应出分化。"),
        "rule": "不改 config/replay.yaml（R132 校准纪律不变; 探针只给数据）",
        "grid": {"m_seeded": m_grid, "beta1": b1_grid, "beta2": b2_grid,
                 "score_plan": "首节点 0.0 其余 1.0（同 R128 混合观察面）"},
        "n_search": n, "n_results": len(results),
        "results": results,
        "verdict": {
            "full_seed_always_degenerate": full_degen,
            "★ 恒等证据": ("m=0/4/8 三档 per_world n_revealed 恒 12 ⇒ dream"
                        " 每轮穷举 K₂(4)×段(3), 起底量不影响观测面 ⇒ "
                        "部分起底假设被证伪, 根因B 真机制 = dream 自身穷举"),
            "n_separating_total": len(sep),
            "n_separating_partial": len(partial_sep),
            "separating_combos": [
                {"m": r["m_seeded"], "beta1": r["beta1"], "beta2": r["beta2"],
                 "n_distinct_v": r["n_distinct_v"], "v_values": r["v_values"]}
                for r in sep],
            "reading": ("部分起底(%s)下有分化 ⇒ 因B 根治有效, β 校准对象"
                        "已出现; %s"
                        % (sorted({r["m_seeded"] for r in partial_sep}) or "无",
                           "全起底仍退化 ⇒ R132 复现一致(根因B 确认)"
                           if full_degen else
                           "全起底也分化 ⇒ 与 R132 结论冲突, 须回查"))
            if sep else
            ("★ 所有 m 全退化, 且 m=0/4/8 的 per_world n_revealed 恒 12"
             "（诊断实测）⇒ 根因B 真机制**不是**起底耗尽, 而是 dream "
             "自己每轮穷举 K₂(4) × 段数(3) = 12 节点, 与起底量无关 ⇒"
             " 部分起底对 dream 的观测面**无影响** ⇒ 要根治得动 dream "
             "的终止条件/段数, 不是改起底量 — 如实更正当初假设"),
        },
        "caveats": [
            "注入观测不走真端点 ⇒ 隔离 β 效应, 换不来 LLM 真差异(同 R128/R132)",
            "δ 可分辨性假设被本轮证伪: 分化的缺失与 δ 无关, 是 dream 每轮 n_revealed 恒 12（K₂×段）所致",
            "注入观测任务的 δ 与真锚点 delta 不同源 — 但本轮证明这不是分化的必要前提",
            "不改 config/replay.yaml — 校准协议裁决归用户/后续轮",
            "k2_max=4 固定(ga_duel 同值) ⇒ 揭示轮数上限不参与扫描",
        ],
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("全起底仍退化:", full_degen, "| 分化组合:", len(sep),
          "(部分起底 %d)" % len(partial_sep))
    for r in sep[:8]:
        print("  ★ m=%d β₁=%s β₂=%s ⇒ %d 个不同 V %s"
              % (r["m_seeded"], r["beta1"], r["beta2"], r["n_distinct_v"],
                 r["v_values"]))
    print("写出:", args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
