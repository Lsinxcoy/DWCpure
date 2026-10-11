# -*- coding: utf-8 -*-
"""树结构与扩池影响面探查 —— R135 · 扩树/扩任务池的施工前测绘。

R134 判定: 策略轴无区分的终极根因之一是树太小（12 可揭示节点 =
2 组根 + 10 叶, C=∅ 抢先）。本探查**不改 anchors**（属数据决策,
  归用户）, 只做施工前测绘 — 回答三个问题:
  Q1 树的节点构成（组根/叶/root）与 n_revealed 的账
  Q2 扩池 N 档（合成注入叶 ×{2,4,8}）后, K₂ 饱和点移动多少
  Q3 扩池后策略轴是否可能出现区分（w_delta/seg_order 的 N 分化）

★ 只读探针 + 内存合成叶（不动 config/anchors/dev.json）;
  合成叶 delta 用等差数列 ⇒ 检验『揭示子集重合』是否随 N 增大而解开。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, List, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from dwc.core import DWC                              # noqa: E402
from dwc.organs.judge import TaskScoreStore           # noqa: E402

from ga_duel import seed_population                    # noqa: E402


def _anchors() -> Dict[str, Any]:
    return json.load(open(os.path.join(ROOT, "config", "anchors",
                                       "dev.json"), encoding="utf-8"))


def tree_topology(d: DWC) -> Dict[str, Any]:
    """Q1: 树的节点账（root/组根/叶分层 + n_revealed 对账）。"""
    T = d.world_model
    out = {}
    for wname, tree in (T.trees.items() if hasattr(T, "trees") else []):
        root_children = tree.nodes[tree.root_id].children
        groups = {}
        for c in root_children:
            groups[c] = len(tree.nodes[c].children)
        out[wname] = {
            "n_nodes": len(tree.nodes),
            "root_id": tree.root_id,
            "group_roots": groups,
            "n_leaves": sum(groups.values()),
            "n_revealable_excl_root": len(tree.nodes) - 1,
        }
    return out


def synth_leaves(d: DWC, ids: List[str], *, how_many: int) -> int:
    """Q2/Q3: 内存合成叶（等差数列 delta ⇒ 揭示顺序可分辨）,
    返回加入后的可揭示节点数。合成叶只进内存树, 不写 anchors。"""
    wm = d.world_model
    trees = getattr(wm, "trees", None)
    if not trees:
        return -1
    base = None
    for wname, tree in trees.items():
        base = (wname, tree)
        break
    if base is None:
        return -1
    wname, tree = base
    g = tree.nodes[tree.root_id].children[0]     # 挂第一个组根下
    before = len(tree.nodes)
    for i in range(how_many):
        nid = "synth_%03d" % i
        tree.add_child(g, node_id=nid, action="synth_%s" % nid,
                       provenance="simulated", confidence_source="none")
    return len(tree.nodes) - before


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "docs",
                                                  "tree_expansion_probe.json"))
    args = ap.parse_args()
    anch = _anchors()
    ids = list((anch.get("_split") or {}).get("search", []))
    if not ids:
        print("★ 无 _split ⇒ not_applicable")
        return 2

    plan = [0.0] + [1.0] * (len(ids) - 1)
    base = DWC(3, 50, executor=None, db_path=":memory:")
    base.judge.store = TaskScoreStore(dw_version="probe_r135")
    for i, tid in enumerate(ids):
        base.world_model.record_observation(
            "dev", tid, float(plan[i]), bool(plan[i] >= 0.5))

    topo = tree_topology(base)
    rep0 = base.dream(k2_max=4, policy_variants=seed_population())

    # Q2/Q3: 逐档合成叶后重跑 dream, 看 (k2, n_revealed, v_distinct)
    tiers = [0, 2, 4, 8]
    tiers_out = []
    for add in tiers:
        d = DWC(3, 50, executor=None, db_path=":memory:")
        d.judge.store = TaskScoreStore(dw_version="probe_r135_tier")
        for i, tid in enumerate(ids):
            d.world_model.record_observation(
                "dev", tid, float(plan[i]), bool(plan[i] >= 0.5))
        n_added = synth_leaves(d, ids, how_many=add)
        # 合成叶给分: 交替 0/1 ⇒ 组内既有 0 又有 1
        wm = d.world_model
        for wname, tree in wm.trees.items():
            for j, nid in enumerate([n for n in tree.nodes
                                     if n.startswith("synth_")]):
                tree.nodes[nid].score = 0.0 if j % 2 == 0 else 1.0
        rep = d.dream(k2_max=4, policy_variants=seed_population())
        per = rep.per_world[0] if rep.per_world else None
        tiers_out.append({
            "added_leaves": n_added,
            "per_world": list(per) if per else None,
            "n_distinct_v": len(set(rep.v_by_version.values())),
            "v_set": sorted(set(rep.v_by_version.values())),
            "separates": len(set(rep.v_by_version.values())) > 1,
        })

    # 饱和判定 = 末档 n 达到该档树的**可揭示上限**（节点数-1）⇒
    # dream 每轮都穷举完（C=∅ 抢先）, 与起底量无关（R133/R134 同款）
    per_n = [t["per_world"][3] if t["per_world"] else None
             for t in tiers_out]
    last_tree_revealable = topo.get("dev", {}).get(
        "n_revealable_excl_root", 0) + tiers_out[-1]["added_leaves"]
    exhausted = (per_n[-1] == last_tree_revealable)
    saturated = [t for t in tiers_out if t["per_world"] and
                 t["per_world"][3] == (per_n[-1] if per_n[-1] else None)]
    sep_tiers = [t for t in tiers_out if t["separates"]]
    out = {
        "probe": ("R135: 扩池施工前测绘 — Q1 节点构成账 / Q2 扩叶后 K₂ 饱和"
                  "点移动 / Q3 扩池能否解开策略轴区分（子集重合是否解除）"),
        "Q1_topology": topo,
        "Q1_baseline": {"per_world": list(rep0.per_world[0]),
                        "n_segments": len(rep0.segments),
                        "v_set": sorted(set(rep0.v_by_version.values()))},
        "Q2_Q3_tiers": tiers_out,
        "verdict": {
            "baseline_revealable": topo.get("dev", {}).get(
                "n_revealable_excl_root"),
            "dream_exhausts_tree_every_tier": exhausted,
            "last_tree_revealable": last_tree_revealable,
            "max_n_revealed": (tiers_out[-1]["per_world"][3]
                               if tiers_out[-1]["per_world"] else None),
            "expansion_unlocks_separation": bool(sep_tiers),
            "reading": (
                # ★ R199: 穷举性改按布尔条件句（原模板**无论 exhausted 真假
                #   都念"穷举到底"** — R199 加 rung3 锚点后树变大,
                #   k2_max=4 预算不再覆盖全树 ⇒ False 时旧模板成谎话）
                ("扩池(%s 叶)后每档 dream 都穷举到底(n_revealed=%d); "
                 if exhausted else
                 "扩池(%s 叶)后 dream **未**穷举全树(末档 n_revealed=%d < "
                 "可揭示 %d — k2_max=4 固定预算随树变大不再全覆盖, "
                 "穷举性是**规模相关**而非与起底量无关); ")
                % ((tiers, tiers_out[-1]["per_world"][3]) if exhausted else
                   (tiers, tiers_out[-1]["per_world"][3],
                    last_tree_revealable)) +
                "策略区分 %s — %s"
                % ("已出现" if sep_tiers else "仍未出现",
                   ("⇒ 扩池确实能造出 N 差异, 但 dream 每轮上限仍受 "
                    "k2_max=4 约束 ⇒ 若区分源于 k2 内的选择顺序, 扩池"
                    "是出路; 若仍聚合饱和, 还须配合 R128/R129 口径")
                   if sep_tiers else
                   ("⇒ 单纯扩池不解锁策略区分（子集仍重合/仍饱和）⇒ "
                    "扩池非充分条件, 需与 k2_max 提升或 judge 口径"
                    "（R129）联合"))),
        },
        "caveats": [
            "合成叶带交替 0/1 分 ⇒ 测的是『扩池+分布变化』的联合效应, 不是纯节点数效应",
            "合成叶只在内存树（不动 config/anchors/dev.json）⇒ 结论关于机制, 不直接改生产数据",
            "k2_max 固定 4（ga_duel 同值）⇒ 扩池若提上限须另测",
            "合成叶挂在首个组根下 ⇒ 组间平衡未动（真扩池应顾及, 留待数据轮）",
        ],
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("Q1:", json.dumps(topo, ensure_ascii=False))
    print("baseline:", out["Q1_baseline"]["per_world"])
    for t in tiers_out:
        print("  +%d叶 ⇒ per_world=%s v_distinct=%s separates=%s"
              % (t["added_leaves"], t["per_world"], t["n_distinct_v"],
                 t["separates"]))
    print("扩池解锁区分:", out["verdict"]["expansion_unlocks_separation"])
    print("写出:", args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
