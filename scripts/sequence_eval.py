# -*- coding: utf-8 -*-
"""序列任务流评测 —— Evo-memory(2604.08988) 序列任务编排的 DWC 版（R103 · 阶段2c②）。

★★ 论文口径（报告 62/63 行）: 同任务重复 + 插入干扰的**序列**跑法, 看 T 沿序列
   收敛（K_eff）而非孤立 episode; **换槽变体**= 变体生成器 DWC 无 ⇒ 标缺（不造）。
★★ DWC 实测映射:
   · 序列 = [weak, weak, strong(干扰), weak, …] —— weak/strong 由 success_stats
     与失败史确定性挑选（无历史 ⇒ 字典序保底, 不猜）
   · 每步 run_term(指定任务) —— 重复与干扰是**编排**不是新任务（node_id 同域不变）
   · 观测: behavior 锚点的 golden 对值/错值**合成**（weak=错值模拟失败链）——
     ★ 与 run_term._build_observations 同族: 证明**编排与统计链**通, 不证明判分
     有效（TRUTH_SOURCE 纪律, 脚本内显式标注 synthetic）
   · 指标: 逐次判分序列 · K_eff（最长连续通过 & 尾部连续通过）· 总通过率
     ★ Evo-memory 的「伪进化联合判据 K_eff→0 ∧ K_SR→0」**口径未核**（原报告
     只记了结论未逐字核公式）⇒ 本脚本只报基础序列与 K_eff, 联合判据不冒充。

读:  config/anchors/dev.json · config/capability_groups.yaml（组内挑干扰）
写:  docs/sequence_eval.json
用法: python scripts/sequence_eval.py [--n 12]
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import sys
from typing import Any, Dict, List, Optional

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.core import DWC  # noqa: E402
from dwc.organs.judge import TaskScoreStore  # noqa: E402
from dwc.organs.actor import Receipt  # noqa: E402


def _coerce(x: str) -> Any:
    try:
        return ast.literal_eval(str(x))
    except (ValueError, SyntaxError):
        return x


def obs_for(anchors: Dict, tid: str, *, wrong: bool) -> Optional[Dict]:
    """按 golden 造观测: wrong=False 全对 / True 错值（args 对位, 值错）。"""
    obs: Dict[str, Any] = {}
    for c in anchors.get(tid, {}).get("checks", []):
        if "fn" not in c:
            continue
        arg = _coerce(c.get("args", ""))
        v = _coerce(c["expected"])
        if wrong:
            if isinstance(v, bool):
                v = not v
            elif isinstance(v, (int, float)):
                v = v + 1000
            else:
                v = str(v) + "_wrong"
        obs.setdefault(c["fn"], []).append([arg, v])
    return obs or None


def build_sequence(d: DWC, n: int) -> List[Dict[str, Any]]:
    """确定性编排: weak（失败史/streak 低）重复 + strong 干扰插入。"""
    anchors = d.judge.anchors
    tids = sorted(t for t in anchors
                  if not t.startswith("_")
                  and anchors[t].get("verifier_kind") == "behavior")
    stats = d.success_stats()
    # weak = 有失败史 rate 低; strong = 全成或无失败史（字典序保底）
    weak = sorted((t for t in tids if stats.get(t, {}).get("rate", 1.0) < 1.0),
                  key=lambda t: (stats.get(t, {}).get("rate", 1.0), t))
    if not weak:
        weak = tids[:1]                     # 无失败史: 首任务当 weak（保底）
    # ★ strong 必须在 weak **定稿后**重算（首版先算 ⇒ 保底 weak 的任务
    #   还留在 strong 里 ⇒ 同任务两边都出现 — 编排 bug, 测试抓到）
    strong = [t for t in tids if t not in weak]
    if not strong:
        strong = tids[-1:]
    seq: List[Dict[str, Any]] = []
    wi = si = 0
    while len(seq) < n:
        # 两步 weak（重复）+ 一步 strong（干扰）
        for _ in range(2):
            if len(seq) >= n:
                break
            t = weak[wi % len(weak)]
            seq.append({"task": t, "role": "weak_repeat"})
            wi += 1
        if len(seq) < n:
            t = strong[si % len(strong)]
            seq.append({"task": t, "role": "strong_interfere"})
            si += 1
    return seq


def k_eff(outcomes: List[bool]) -> Dict[str, Optional[int]]:
    """连续通过读数（两口径; Evo-memory 联合判据口径未核 ⇒ 不冒充）。"""
    longest = trail = 0
    for ok in outcomes:
        if ok:
            longest += 1
            trail += 1
        else:
            trail = 0
    return {"longest_pass_run": longest, "trailing_pass_run": trail}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=12)
    args = ap.parse_args()

    d = DWC(3, 50, executor=None)
    d.judge.store = TaskScoreStore(dw_version="seq-eval-r103")
    anchors = d.judge.anchors
    seq_plan = build_sequence(d, args.n)
    # ★ 合成观测: weak=错值（模拟失败链）/strong=对值 — 编排验证口径,
    #   非判分有效（与 _build_observations 同族, 显式 synthetic 标注）。
    #   任务→角色定映射（同任务同角色 ⇒ 无状态闭包坑）
    role_by_task = {s["task"]: (s["role"] == "weak_repeat")
                    for s in seq_plan}

    def _exec(task):
        tid = task.get("task_id", "")
        wrong = role_by_task.get(tid, False)
        obs = obs_for(anchors, tid, wrong=wrong)
        return Receipt(ok=True, verified=True,
                       detail=({"observed": obs,
                                "★_synthetic": True} if obs else {}))

    d.executor = _exec

    outcomes: List[bool] = []
    rows: List[Dict[str, Any]] = []
    # ★ 执行→判分链 = core.step（R84: step 尾自动 judge.evaluate + 树回填）——
    #   trial_run 同款入口; run_term 是 term 编排报告, 不执行任务（首版用错,
    #   judged 恒 None — 教训: 先抄生产链再另起炉灶）
    for i, step in enumerate(seq_plan, 1):
        out = d.step({"task_id": step["task"], "kind": "dev"})
        j = out.get("judgement") or {}
        succ = j.get("success")
        if not isinstance(succ, bool):
            raise AssertionError(
                "★ R84 契约: 带 observed 应自动判分 (%s) 实得 %r"
                % (step["task"], succ))
        outcomes.append(succ)
        rows.append({"i": i, "role": step["role"], "task": step["task"],
                     "success": succ, "synthetic_obs": True})
    n_eval = len(outcomes)
    out = {
        "protocol": ("Evo-memory 序列任务流的 DWC 版: weak 重复 + strong 干扰; "
                     "★ 观测合成（weak=错值/strong=对值）= 编排与统计链验证, "
                     "非判分有效; ★ 换槽变体无生成器 ⇒ 缺（不造）"),
        "n_steps": args.n,
        "sequence": rows,
        "outcomes": outcomes,
        "pass_rate": (sum(outcomes) / n_eval) if n_eval else None,
        "k_eff": k_eff(outcomes),
        "caveat": ("Evo-memory 的伪进化联合判据（K_eff→0 ∧ K_SR→0）口径未核 "
                   "（原报告未逐字核公式）⇒ 只报基础序列与 K_eff, 不冒充"),
        "success_stats_after": d.success_stats(),
    }
    p = os.path.join(ROOT, "docs", "sequence_eval.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("序列 %d 步 | 通过率=%s | K_eff=%s"
          % (args.n, out["pass_rate"], out["k_eff"]))
    print("success_stats 任务数:", len(out["success_stats_after"]))
    print("写出:", p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
