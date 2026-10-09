# -*- coding: utf-8 -*-
"""Proposal 遵循率报表 —— R98 方案 3a（T4 归因 · 两读数 + 四模式诊断表）。

方案原文（proposal_architecture_completion_dualpaper.html §⑥T4）:
  · 两读数 = 激活率（工件被相关路径调用吗）+ 忠实遵循率（调用后行为按工件走了吗）
  · 四模式 = 错误教训 / 超范围适用 / 不调用 / 牺牲旧能力 —— 每个已采纳 Proposal
    连「证据 → 后续使用 → 新旧任务效果」三列（知识档形态是骨架, 补连接字段）
  · 验收 = 每个已采纳 Proposal 三列连接齐全 · 遵循率报表可复跑

★ DWC 映射（对象考古实录, 不硬编）:
  · 源A = memory MemoryKind.PROPOSAL（D6 consumer_declared; recall→access/
    record_effect→effect 正是两读数记账）—— 报表主源
  · 源B = evolver Proposal 状态机（PROPOSAL_STATES）—— **进程态**（proposals
    持久化=config/anchors/rules.json, 当前不存在 ⇒ n_adopted=not_instrumented
    显式, 不装数）
  · ★★ 生产喂数缺口（诚实发现, 入报不做声）: recall()/record_effect() 在
    生产路径**零调用方**（仅 memory.py 自身 demo）⇒ 源A 当前 n=0 是
    「读数存在/数据断供」—— 正是 T4 定位「改完没被算数」的实测证据;
    四模式之「牺牲旧能力」需新旧任务对照臂（3b 等预算臂未建）⇒ not_assessable。

读:  MemoryKernel(PROPOSAL 节点)
写:  docs/proposal_follow.json
用法: python scripts/proposal_follow.py
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, List

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.organs.memory import MemoryKernel  # noqa: E402


# ── 四模式（纯函数, 方案 §⑥T4 四诊断行）─────────────────────────
MODE_BENEFICIAL = "followed_beneficial"          # 调用了且产生效果
MODE_NOT_INVOKED = "not_invoked"                 # 不调用（模式④候选）
MODE_INVOKED_NO_EFFECT = "invoked_not_followed"  # 调了但没按工件走（模式③）
MODE_SACRIFICED = "sacrificed_old_ability"       # 牺牲旧能力（需新旧对照臂）


def classify(access: int, effect: int,
             old_new_available: bool = False,
             regressed: bool = False) -> str:
    """四模式判读（纯）。★ sacrificed 仅在有新旧对照时可判, 否则由调用方
    归入 invoked_not_followed 并在行内标 not_assessable。"""
    if access <= 0:
        return MODE_NOT_INVOKED
    if old_new_available and regressed:
        return MODE_SACRIFICED
    return MODE_BENEFICIAL if effect > 0 else MODE_INVOKED_NO_EFFECT


def three_columns(node_id: str, payload: Dict[str, Any],
                  access: int, effect: int) -> Dict[str, Any]:
    """★ 三列连接（验收字面: 证据 → 后续使用 → 新旧任务效果）—— 每行必齐,
    缺数据用 not_assessable/not_instrumented 显式, 不留空键。"""
    return {
        "evidence": {
            "node_id": node_id,
            "consumer_declared": payload.get("consumer_declared"),
            "scene": payload.get("scene"),
        },
        "subsequent_use": {
            "access": access, "effect": effect,
            "instrumented": True,   # 记账口存在（recall/record_effect）
        },
        "old_vs_new_effect": {
            "status": "not_assessable",
            "why": "需新旧任务对照臂（3b 等预算臂未建）",
        },
    }


def build_report(mem: MemoryKernel) -> Dict[str, Any]:
    rows: List[Dict[str, Any]] = []
    conn = mem._conn  # 报表只读扫描（与 contribution_report 同款）
    recs = conn.execute(
        "SELECT node_id, payload, access_count, effect_count, chain_id"
        " FROM memory_node WHERE kind='proposal' AND archived_at IS NULL"
        " ORDER BY created_at").fetchall()
    for r in recs:
        payload = json.loads(r["payload"])
        acc, eff = int(r["access_count"]), int(r["effect_count"])
        rows.append({
            "node_id": r["node_id"], "chain_id": r["chain_id"],
            "mode": classify(acc, eff),
            "activated": acc > 0,
            "faithfully_followed": eff > 0,
            "columns": three_columns(r["node_id"], payload, acc, eff),
        })
    n = len(rows)
    n_act = sum(1 for x in rows if x["activated"])
    n_fol = sum(1 for x in rows if x["faithfully_followed"])
    return {
        "protocol": ("T4 两读数+四模式: 激活率=access>0/总; 忠实遵循率="
                     "effect>0/已激活; 三列连接每行齐全(缺=显式)"),
        "sourceA_memory_proposal": {
            "n_proposals": n,
            "activation_rate": (n_act / n) if n else None,
            "faithful_follow_rate": (n_fol / n_act) if n_act else None,
            "rows": rows,
        },
        "sourceB_evolver": {
            "n_adopted": "not_instrumented",
            "why": ("evolver proposals 进程态, 持久化=config/anchors/"
                    "rules.json 当前不存在 ⇒ 不装数"),
        },
        "data_gap": ("①生产路径 recall()/record_effect() 零调用方"
                     "（仅 demo 自调）⇒ 激活/遵循记账断供; ②DWC 默认"
                     "db_path=':memory:' ⇒ 记忆节点跨进程不存 —— 双缺口"
                     "叠加 = T4 『改完没被算数』的实测证据（接线+落盘="
                     "候选硬规则, 不默认动）"),
        "mode_histogram": {m: sum(1 for x in rows if x["mode"] == m)
                           for m in (MODE_BENEFICIAL, MODE_NOT_INVOKED,
                                     MODE_INVOKED_NO_EFFECT, MODE_SACRIFICED)},
        "assessment_note": ("sacrificed_old_ability 固定 not_assessable 直至 "
                            "3b 新旧对照臂; 四模式行由 classify() 纯判"),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "dwc.db"))
    ap.add_argument("--out", default=os.path.join(ROOT, "docs",
                                                  "proposal_follow.json"))
    args = ap.parse_args()
    if args.db not in (":memory:",) and not os.path.exists(args.db):
        # ★ 父目录可能不存在（sqlite 能建文件但不能建目录）— 空库照样出
        #   结构报表 + 缺口声明（可复跑验收不依赖数据量）
        d = os.path.dirname(os.path.abspath(args.db))
        os.makedirs(d, exist_ok=True)
        print("★ 库不存在: %s ⇒ 空库出结构+缺口声明" % args.db)
    mem = MemoryKernel(db_path=args.db)
    rep = build_report(mem)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=1)
    sa = rep["sourceA_memory_proposal"]
    print("PROPOSAL n=%s 激活率=%s 遵循率=%s"
          % (sa["n_proposals"], sa["activation_rate"],
             sa["faithful_follow_rate"]))
    print("四模式:", rep["mode_histogram"])
    print("缺口:", rep["data_gap"][:60], "…")
    print("写出:", args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
