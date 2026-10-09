# -*- coding: utf-8 -*-
"""三维解耦实验 + 等预算归因臂 —— R98 方案 3b（T4 阶段 3 收官）。

方案原文（§⑥T4）:
  · author ≠ user ≠ task 三维解耦: 修订者 agent 与执行修订的 agent **分开跑**
    = 「策略可移植吗」的最低成本实验（现 run_term 是同 agent 前后测）
  · 等预算归因臂: 报告任何增益带「同预算对照」（盲重采样式安慰剂）——
    正是 Verma 把 +12.2 变负的手段
  · 复现硬规则: 带 seed/预算/臂声明（进报告协议）
  · 验收: 对照臂进报告协议

★ DWC 映射（确定性, 无 LLM — 可复跑）:
  · author = 实例 A 跑 n_terms 沉淀 SKILL 工件（memory 节点）
  · user   = **全新**实例 B（独立库 — 这就是 author≠user 的解耦）
  · 臂1 transplant   = B 载入 A 的真工件 → 跑 m terms
  · 臂2 blind_placebo= B 载入**同数量**盲造工件（等预算安慰剂 — 随机
    payload, 与任务无关 → 若臂1≈臂2 ⇒ 增益非「工件内容」而是「有无注入」
    的安慰剂效应 — Verma 同款对照）
  · 臂3 baseline     = B 无注入
  · 判分: golden 对值 executor（确定性）· 分数=B 跑的 success 率
  · ★ 任务维度: 三臂**同一批任务**（author 的任务与 B 分开 ⇒ author≠task
    的一侧; user 三臂共任务 ⇒ 效应不混任务差）

读:  config/anchors/dev.json
写:  docs/transfer_attribution.json
用法: python scripts/transfer_and_attribution.py
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import random
import sys
from typing import Any, Dict, List, Optional

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.core import DWC  # noqa: E402
from dwc.organs.judge import TaskScoreStore  # noqa: E402
from dwc.organs.memory import MemoryKind  # noqa: E402
from dwc.organs.actor import Receipt  # noqa: E402


def _coerce(x: str) -> Any:
    try:
        return ast.literal_eval(str(x))
    except (ValueError, SyntaxError):
        return x


def make_exec(anchors: Dict, tasks: List[str], *, wrong: bool = False):
    """golden 对值 executor（确定性; wrong 留作扰动开关, 默认全对）。"""
    def _exec(task):
        tid = task.get("task_id", "")
        if tid not in tasks:
            return Receipt(ok=True, verified=True, detail={})
        obs: Dict[str, Any] = {}
        for c in anchors.get(tid, {}).get("checks", []):
            if "fn" not in c:
                continue
            v = _coerce(c["expected"])
            if wrong and isinstance(v, (int, float)):
                v = v + 1000
            obs.setdefault(c["fn"], []).append([_coerce(c.get("args", "")), v])
        return Receipt(ok=True, verified=True,
                       detail=({"observed": obs} if obs else {}))
    return _exec


def run_arms(anchors: Dict, author_tasks: List[str], user_tasks: List[str],
             n_author: int, n_user: int, seed: int) -> Dict[str, Any]:
    """★ 三臂对照（同预算同任务同判分）。每臂独立全新 DWC 实例。"""
    results: Dict[str, Any] = {}
    # ── author 实例（与 user 分离 = author≠user 解耦的第一半）──
    auth = DWC(3, 50, executor=None, db_path=":memory:")
    auth.judge.store = TaskScoreStore(dw_version="transfer-r107")
    auth.executor = make_exec(anchors, author_tasks)
    for i in range(n_author):
        auth.step({"task_id": author_tasks[i % len(author_tasks)],
                   "kind": "dev"})
    # 真取 A 的 SKILL 工件（若有; 无则臂1 与臂3 同 ⇒ 报告如实）
    rows = auth.memory._conn.execute(
        "SELECT node_id, payload FROM memory_node WHERE kind='skill'"
        " AND archived_at IS NULL").fetchall()
    real_artifacts = [json.loads(r["payload"]) for r in rows]

    rng = random.Random(seed)
    arms_spec = {
        "transplant": real_artifacts,
        "blind_placebo": [
            {"scene": "blind_%d" % i, "method": "r%d" % rng.randrange(10**6),
             "boundary": "b", "invalid_conditions": ["x"],
             "recovery_strategies": ["y"]}
            for i in range(max(len(real_artifacts), 1))],
        "baseline": [],
    }
    for arm, artifacts in arms_spec.items():
        b = DWC(3, 50, executor=None, db_path=":memory:")
        b.judge.store = TaskScoreStore(dw_version="transfer-r107")
        # ★ 载入工件（臂1真/臂2盲/臂3空 — 预算: 注入次数=同批 artifacts 数,
        #   baseline 注入 0 条但**跑同样 terms**（等算力预算））
        for a in artifacts:
            b.memory.remember(MemoryKind.SKILL, dict(a))
        b.executor = make_exec(anchors, user_tasks)
        outcomes: List[bool] = []
        for i in range(n_user):
            out = b.step({"task_id": user_tasks[i % len(user_tasks)],
                          "kind": "dev"})
            j = out.get("judgement") or {}
            succ = j.get("success")
            if isinstance(succ, bool):
                outcomes.append(succ)
        results[arm] = {
            "n_steps": len(outcomes),
            "success_rate": (sum(outcomes) / len(outcomes)) if outcomes else None,
            "n_artifacts": len(artifacts),
            "outcomes": outcomes,
        }
    return {"author_steps": n_author, "user_steps": n_user,
            "n_real_artifacts": len(real_artifacts),
            "arms": results}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-author", type=int, default=4)
    ap.add_argument("--n-user", type=int, default=8)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default=os.path.join(ROOT, "docs",
                                                  "transfer_attribution.json"))
    args = ap.parse_args()

    anchors = json.load(open(os.path.join(ROOT, "config", "anchors",
                                          "dev.json"), encoding="utf-8"))
    tasks = sorted(t for t in anchors
                   if not t.startswith("_")
                   and anchors[t].get("verifier_kind") == "behavior")
    if not tasks:
        print("★ dev.json 无 behavior 任务 ⇒ not_applicable（不装数）")
        return 2
    author_tasks, user_tasks = tasks[:1], tasks[1:] or tasks
    exp = run_arms(anchors, author_tasks, user_tasks,
                   args.n_author, args.n_user, args.seed)
    arms = exp["arms"]
    t, p, bl = (arms["transplant"]["success_rate"],
                arms["blind_placebo"]["success_rate"],
                arms["baseline"]["success_rate"])
    # ★ 归因判读: transplant 须**超安慰剂**才算工件内容的增益（Verma 手段）
    content_gain = (None if (t is None or p is None) else t - p)
    out = {
        "protocol": ("3b 三维解耦+等预算臂: author(A实例)≠user(B全新实例); "
                     "三臂同预算同任务; blind_placebo=等数量盲造工件"
                     "（Verma 同款对照 — 增益须超安慰剂才算内容效应）"),
        "seed": args.seed,
        "budget": {"n_author": args.n_author, "n_user": args.n_user},
        "author_tasks": author_tasks,
        "n_user_tasks": len(user_tasks),
        "experiment": exp,
        "attribution": {
            "transplant_minus_placebo": content_gain,
            "content_effect_verdict": (
                "not_computable" if content_gain is None else
                ("content_gain" if content_gain > 0 else
                 ("placebo_equal" if content_gain == 0 else "negative"))),
            "baseline_reference": bl,
        },
        "reproducibility_rules": [
            "seed 显式(args.seed)",
            "每臂全新实例同预算同任务",
            "盲安慰剂臂进协议（无对照臂的增益不报）",
            "确定性 golden executor（无 LLM 端点波动）",
        ],
        "caveats": [
            "n_user 小样本只报方向",
            "真工件数=0 时 transplant≈baseline =『无工件可移植』如实（不造工件）"
            " —— step 链不写 SKILL（技能沉淀在 dream/evolve 环）",
            "★ 效度边界(结构必然): golden 替身 executor **不读记忆** ⇒ 记忆"
            "→执行路径被旁路 ⇒ 三臂恒等(1.0)不是『记忆无效』的证据 —— "
            "本实验验收=解耦/安慰剂/复现**协议跑通**; 真记忆效应测法=LLM "
            "executor 臂(R105c guidance vs none 正是) —— 两实验互补",
            "任务切分 author≠user 的 task 侧=author 任务不进 user 批",
        ],
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("三臂: transplant=%s placebo=%s baseline=%s"
          % (t, p, bl))
    print("内容效应(transplant-placebo): %s ⇒ %s"
          % (content_gain, out["attribution"]["content_effect_verdict"]))
    print("真工件数:", exp["n_real_artifacts"])
    print("写出:", args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
