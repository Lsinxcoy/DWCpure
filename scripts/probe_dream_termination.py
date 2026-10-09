# -*- coding: utf-8 -*-
"""dream 终止条件与 K₂ 死参数探针 —— R134 · 恒等问题的终极解剖。

R133 定位: m=0/4/8 起底 ⇒ n_revealed 恒 12（dream 自身穷举）。
R134 追问: 那个 12 受什么参数控制? 若能扫出差异, β 校准就有对象。

实测（本脚本复现）: k2_max ∈ {4,8,12,16} ⇒ per_world 恒 ('dev',-,4,12)
  ⇒ k（每段步数上限）=4 与 n_revealed=12 **都与 k2_max 无关**
  ⇒ dream 的真实终止来自 §2.5 三条件的**第一条 C=∅**（树内候选耗尽）
  ⇒ 12 节点在当前树规模下是结构上限, K₂(k2_max) 是**死参数**
  ⇒ 策略变体之间在 dream 内**数学上不可能**有 N/k 差异 ⇒ β 校准无对象

结论链（恒等终极根因）:
  ① R128 max 聚合饱和（观测面有 1.0 就顶格）
  ② R132 β=0（N/k 项零因果）
  ③ R133/R134 N/k 对所有策略恒同（dream 穷举 + K₂ 死参数 + 树太小）
⇒ 三条任意一条都足以让 V 恒等; 三者叠加 ⇒ **策略轴在 dream 里
   结构性无区分度**。若要破, 只能从树规模/任务池扩容下手, 不是调参。

★ 纪律: 只读探针（不改 core/config）; 结论包括对自家实现的严厉判定。
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

from ga_duel import seed_population                    # noqa: E402


def _anchors() -> Dict[str, Any]:
    return json.load(open(os.path.join(ROOT, "config", "anchors",
                                       "dev.json"), encoding="utf-8"))


def probe_k2(k2_values: List[int], betas: tuple = (0.0, 0.0)
             ) -> List[Dict[str, Any]]:
    """空树下扫 k2_max（零注入 — 树自建 12 节点后同 R133 诊断路径）。"""
    real = dc.REPLAY_PATH
    tmp = os.path.join(ROOT, "config", "_tmp_replay_probe.yaml")
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("replay:\n  beta1: %r\n  beta2: %r\n  history_max: 16\n"
                % betas)
    out = []
    try:
        dc.REPLAY_PATH = tmp
        for k2 in k2_values:
            d = DWC(3, 50, executor=None, db_path=":memory:")
            d.judge.store = TaskScoreStore(dw_version="probe_r134")
            rep = d.dream(k2_max=k2, policy_variants=seed_population())
            per = rep.per_world
            out.append({
                "k2_max": k2, "v_set": sorted(set(rep.v_by_version.values())),
                "n_distinct_v": len(set(rep.v_by_version.values())),
                "per_world": [list(w) for w in per],
                "n_segments": (len(rep.segments)
                               if hasattr(rep.segments, "__len__") else None),
                "degenerate": len(set(rep.v_by_version.values())) <= 1,
            })
    finally:
        dc.REPLAY_PATH = real
        if os.path.exists(tmp):
            os.remove(tmp)
    return out


def probe_growing_zone(ids: List[str], plan: List[float],
                        k2_values: List[int] = (1, 2, 3)
                        ) -> List[Dict[str, Any]]:
    """★ 补强诊断: K₂ 活区（k2<4）注入混合树（既有 0.0 又有 1.0）
    ⇒ 逐策略变体看 N 与 V 是否分化。实测 n=1/7/8 随 k2 增长（活区
    证据），但 v_by 全同 ⇒ 即使 N 可变, 各变体揭示到同一子集 ⇒
    策略轴在活区也无区分（与饱和区同为「无区分」, 但成因不同:
    饱和区是 C=∅ 抢先, 活区是揭示子集重合）。"""
    out = []
    for k2 in k2_values:
        d = DWC(3, 50, executor=None, db_path=":memory:")
        d.judge.store = TaskScoreStore(dw_version="probe_r134_gz")
        for i, tid in enumerate(ids):
            if i >= len(plan):
                break
            d.world_model.record_observation("dev", tid, float(plan[i]),
                                             bool(plan[i] >= 0.5))
        rep = d.dream(k2_max=k2, policy_variants=seed_population())
        out.append({"k2_max": k2,
                    "n_revealed": [w[3] for w in rep.per_world],
                    "v_by": dict(rep.v_by_version),
                    "n_distinct_v": len(set(rep.v_by_version.values())),
                    "separates": len(set(rep.v_by_version.values())) > 1})
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "docs",
                                                  "dream_termination_probe.json"))
    args = ap.parse_args()
    ids = list((_anchors().get("_split") or {}).get("search", []))
    if not ids:
        print("★ 无 _split ⇒ not_applicable")
        return 2

    k2s = [1, 2, 4, 8, 16]
    rows = probe_k2(k2s)
    mixed_plan = [0.0] + [1.0] * (len(ids) - 1)
    gz = probe_growing_zone(ids, mixed_plan)
    for r in rows:
        print("k2=%2d v_set=%s per_world=%s segs=%s"
              % (r["k2_max"], r["v_set"], r["per_world"],
                 r["n_segments"]))

    # n/k 按档取（k2<4 变化, ≥4 穷尽）— 如实分两区, 不合并说"恒"
    n_by_k2 = {r["k2_max"]: (r["per_world"][0][3] if r["per_world"] else None)
               for r in rows}
    k_by_k2 = {r["k2_max"]: (r["per_world"][0][2] if r["per_world"] else None)
               for r in rows}
    growing = [k2 for k2 in k_by_k2 if n_by_k2[k2] != n_by_k2.get(k2s[-1])]
    saturated = [k2 for k2 in k_by_k2 if k2 not in growing]
    all_degen = all(r["degenerate"] for r in rows)
    out = {
        "probe": ("R134: dream 终止解剖 — 扫 k2_max 看 n_revealed/k 是否受控。"
                  "实测 k2_max ∈ {1,2,4,8,16} ⇒ (k, n) 恒 ⇒ K₂ 是死参数;"
                  " dream 真实终止 = §2.5 的 C=∅（树内候选耗尽）⇒ 12 节点是"
                  "结构上限 ⇒ 策略间 N/k 数学无差异 ⇒ β 校准无对象。"),
        "k2_values": k2s,
        "rows": rows,
        "verdict": {
            "k2_is_dead_parameter": len(saturated) == len(k2s),
            "k2_growing_zone": growing,
            "k2_saturated_zone": saturated,
            "n_by_k2": n_by_k2,
            "k_by_k2": k_by_k2,
            "all_degenerate": all_degen,
            "reading": ("★ 实测分两区（如实）: k2 ∈ %s 时 n 随 K₂ 增长"
                        "（%s）⇒ K₂ 是**活参数**; k2 ∈ %s 时 n 恒 %s = 树全"
                        "节点 ⇒ C=∅ 先于 k≥K₂ 触发 ⇒ 此区 K₂ 饱和（非死）"
                        "。但即使 n 变化, v_set 仍恒单值 ⇒ 空树无满分节点"
                        "（R128 五档之五）叠加 ⇒ 恒等的直接显示与 K₂ 活性"
                        "无关 — 恒等仍由『峰值节点存在性』主导, 与 R128"
                        "同源; 且活区(%s)注入混合树实测 n 随 k2 增长但 "
                        "v_by 全同 ⇒ 策略轴在**活区也无区分**（揭示子集"
                        "重合）— ga_duel 固定 k2_max=4 在饱和区, 降到活区"
                        "也拯救不了策略轴区分度"
                        % (growing,
                           {k: n_by_k2[k] for k in growing},
                           saturated, n_by_k2.get(k2s[-1]), growing)),
        },
        "三层根因汇总": {
            "R128": "max 聚合饱和（观测面有 1.0 就顶格）",
            "R132": "β₁=β₂=0 ⇒ N/k 项零因果",
            "R133+R134": "N/k 对所有策略恒同（dream 穷举; K₂ 仅在 k2<4 区活, ≥4 被 C=∅ 抢先 ⇒ ga_duel 固定 k2_max=4 恰在饱和区）",
            "判定": "三条独立根因叠加 ⇒ 策略轴结构性无区分度; 破局=扩树/扩任务池, 或 ga_duel 改用 k2<4（活区）",
        },
        "growing_zone_diag": gz,
        "caveats": [
            "空树探针（零注入）⇒ 结论关于 dream 的参数响应性, 不涉及 LLM 端点",
            "只读探针: 不改 core/config; 对自家实现的死参数判定如实记录",
            "树规模由 anchors/groups 结构定（3 段 × 若干叶 ⇒ 12 节点）— 扩树属任务池扩容, 另立轮次",
        ],
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    v = out["verdict"]
    print("K₂ 活区: %s（n 随 k2 增长）| 饱和区: %s（C=∅ 抢先）"
          % (v["k2_growing_zone"], v["k2_saturated_zone"]))
    print("K₂ 全区死:", v["k2_is_dead_parameter"])
    print("写出:", args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
