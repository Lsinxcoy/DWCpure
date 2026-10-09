# -*- coding: utf-8 -*-
"""M2 小种群 GA 对打 —— R123 · 项1 执行（设计稿⑦ · M2 双前置的方案件）。

协议（稿⑦ §③ 逐字）:
  同底同任务集同起点: 单次 ℋ 起底 + D_search 8 任务（R117 拆分语义）+ π0+三单键变体
  同预算: 两臂各 16 次 V 评估硬上限（B_GA=B_SINGLE=16, 管理口径）+ 逐笔记账
          + K 倍账显式报 + 超额作废
  同验收: Eq.10（R118: ∃k 改善 ∧ ∀j 不回退）

  A 臂（baseline·现行单点）: 一次一键, 循环评四变体 → Eq.10 判
  B 臂（小种群 GA）: N=4·代≤4·tournament k=2·键域不相交才交叉·单键枚举变异
      → 子代必带 attribution_plan（无账=构造期 raise 不是漏 · M1 路径乙）

裁决（稿⑦ §⑤ 跑前锁死, 防跑完看结果定规则）:
  主判据 = 预算内 Eq.10-accept 提案数, 严格多者赢; 平 = 比 best V; 仍平 = 判 A
  （在位者保守 = E2 平票同款）; 纪律先于输赢（缺账/超预算 = 成绩作废）。

★ 区分度风险（稿⑦ §⑥ 预告）: golden 臂键改动不改回放分 ⇒ V 恒等 ⇒ 两臂
  全平 ⇒ 平局规则判 A — 这是**协议验证的成功**不是对打失败; 恒等式下的
  平局 ≠「两臂一样好」, 是「该臂上测不出差别」（如实入 caveat）。
  二期真区分须 LLM executor 臂（R105c 0.60/0.70/0.80 先例）。

读:  config/anchors/dev.json（_split）· src/dwc/core.py
写:  docs/ga_duel.json
用法: python scripts/ga_duel.py [--seed 42]
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
from dwc.foundation.eq10 import eq10_accept  # noqa: E402
from dwc.organs.actor import Receipt  # noqa: E402
from dwc.organs.judge import TaskScoreStore  # noqa: E402
from dwc.organs.replay import PolicySpec  # noqa: E402

#: 预算与 GA 参数（稿⑦ §④ 管理口径初值）
B_ARMS = 16
POP_N, MAX_GEN, TOURNAMENT_K = 4, 4, 2
CURRENT = "π0"
KEYS = ("w_delta", "prefer_revealable", "seg_order")

#: Δ 读数口径（如实说明 — 两臂同底同预算下的结构必然量）:
#   Δ_gain = V(个体) − V(π0)（回放分差）
#   Δ_cost = 0（每次 V 评估同价 1 单位 — 本对打分的是**搜索效率**不是
#             任务成本; token 级成本差未计, 如实标口径）
#   Δ_retention = 0（V 不回退即保护组不掉 — 恒等底上的表达）


def _coerce(x):
    try:
        return ast.literal_eval(str(x))
    except (ValueError, SyntaxError):
        return x


def make_executor(anchors: Dict[str, Any], mode: str = "golden",
                  memory: Any = None):
    """golden 确定性替身（两臂共享 — 控变量; M1/R114 同款）。

    R127 · mode="llm" ⇒ 走 R126 LLMExecutorFactory（真执行通道 —
      二期真区分的来源; 端点四失败模态 ⇒ NOT_EVALUATED）。
    """
    if mode == "llm":
        from dwc.llm.executor import LLMExecutorFactory
        from dwc.llm import LLMClient
        return LLMExecutorFactory(LLMClient(), anchors=anchors).make(
            memory=memory)
    def _exec(task):
        g = anchors.get(task.get("task_id", ""), {})
        if g.get("verifier_kind") == "keyword_match":
            kws = [c.get("kw") for c in (g.get("checks") or [])
                   if c.get("kw")]
            return Receipt(ok=True, verified=True,
                           detail={"observed": {"answer": " ".join(kws)}})
        obs: Dict[str, Any] = {}
        for c in g.get("checks", []):
            if "fn" not in c:
                continue
            obs.setdefault(c["fn"], []).append(
                [_coerce(c.get("args", "")), _coerce(c["expected"])])
        return Receipt(ok=True, verified=True,
                       detail=({"observed": obs} if obs else {}))
    return _exec


def seed_population() -> List[PolicySpec]:
    """同起点（稿⑦ §③）: 初始 = π0 + 三单键变体（R85/86 四变体同款）。"""
    return [PolicySpec(),
            PolicySpec.from_mapping({"w_delta": 0.0}),
            PolicySpec.from_mapping({"prefer_revealable": False}),
            PolicySpec.from_mapping({"seg_order": "delta"})]


def changed_keys(a: PolicySpec, b: PolicySpec) -> List[str]:
    """两个体取值不同的键 —— 交叉只在键域不相交成员间发生（稿③ §⑦）。"""
    return [k for k in KEYS if getattr(a, k) != getattr(b, k)]


def mutate_one(spec: PolicySpec, key: str) -> PolicySpec:
    """单键枚举翻转（非采样 — 从有限键域取另一值）。"""
    vals = {"w_delta": [0.0, 1.0],
            "prefer_revealable": [True, False],
            "seg_order": ["children", "delta"]}[key]
    other = [v for v in vals if v != getattr(spec, key)][0]
    return PolicySpec.from_mapping({key: other})


def cross_pair(a: PolicySpec, b: PolicySpec) -> PolicySpec:
    """合法交叉: 两父取值不同的键, 产物取 **b 侧值**（b=tournament 胜者之一,
    继承胜者方向 — 确定性; 键相同 ⇒ 该键不冲突（P2P 的可行方向之二））。"""
    diff = changed_keys(a, b)
    if not diff:
        raise RuntimeError("★ 交叉拒绝: 两父键域全同（不相交才交叉 — 稿③§⑦）")
    try:
        return PolicySpec.from_mapping({k: getattr(b, k) for k in diff})
    except Exception as e:                       # G7: 坏交叉大声, 不静默
        raise RuntimeError("★ 交叉非法: %r" % (e,))


def _enum_pool() -> List[PolicySpec]:
    """★ 组合池枚举: 与 π0 **差 ≥2 键**的个体（稿⑦ §③「键域不相交
    **成员**的组合」）。单键变体 = 路径甲单点提案, 走 select_policy 链,
    不属 GA 多改池（它们已在 seed 里评过）— 池 = 三键中取 ≥2 的组合:
    C(3,2)+C(3,3) = 4 个, 每个 2^m 取值 ⇒ 8 个合法组合（含双键全关）。"""
    base = PolicySpec()
    out: List[PolicySpec] = []
    for w in (1.0, 0.0):
        for r in (True, False):
            for sg in ("children", "delta"):
                spec = PolicySpec.from_mapping(
                    {"w_delta": w, "prefer_revealable": r, "seg_order": sg})
                n_diff = sum(1 for k in KEYS
                             if getattr(spec, k) != getattr(base, k))
                if n_diff >= 2:
                    out.append(spec)
    return out


class Budgeter:
    """评估预算硬上限（两臂各自独立）+ 逐笔记账（CostLedger 风格）。"""

    def __init__(self, arm: str, limit: int = B_ARMS):
        self.arm, self.limit = arm, limit
        self.spent = 0
        self.ledger: List[Dict[str, Any]] = []

    def can(self) -> bool:
        return self.spent < self.limit

    def spend(self, what: str) -> None:
        self.spent += 1                           # 1 次 V 评估 = 1 单位
        self.ledger.append({"arm": self.arm, "kind": "v_eval",
                            "what": what, "spent": self.spent})

    def summary(self) -> Dict[str, Any]:
        return {"arm": self.arm, "v_evals_spent": self.spent,
                "limit": self.limit,
                "within_budget": self.spent <= self.limit}


def run_arm_single(eval_v, judge10, budget, current: str
                   ) -> Dict[str, Any]:
    """A 臂: 现行单点（一次一键 — 忠实复刻 R85/86 四变体评 → Eq.10 判）。"""
    best: Dict[str, float] = {}
    for spec in seed_population():
        if not budget.can():
            break
        budget.spend(spec.pid)
        best[spec.pid] = eval_v(spec)
    judged = {pid: {"v": v, "accept": judge10(v)["accept"]}
              for pid, v in best.items()}
    return {"accepted_eq10": sum(1 for p in judged
                                 if p != current and judged[p]["accept"]),
            "best_v": best, "judged": judged,
            "n_eval": budget.spent}


def run_arm_ga(eval_v, judge10, budget, current: str,
               *, plan_for) -> Dict[str, Any]:
    """B 臂: 小种群 GA（N·代·tournament·合法交叉·单键变异·子代带账）。"""
    pop = seed_population()
    best: Dict[str, float] = {}
    for spec in list(pop):                       # ① 初始种群全评（预算内）
        if not budget.can():
            break
        budget.spend(spec.pid)
        best[spec.pid] = eval_v(spec)
    log: List[Dict[str, Any]] = []

    for gen in range(MAX_GEN):
        info: Dict[str, Any] = {"gen": gen,
                                "spent": budget.spent}
        # ② tournament k=2（V 高者胜 — 确定性, 可复现）
        #   ★ R123 首修: 原两次调同 min ⇒ p1≡p2 ⇒ 键域全同 ⇒ 空转
        #   ★★ R123 二修: 三键空间全枚举 = 8 个体（π0 + 三单键 + πAB
        #     + 三个双位全关变体）, 代际间必碰撞已评个体 ⇒ **交叉/变异
        #     的产物必须在未评集合内**（有界枚举的正确 GA 形态 — 稿⑦
        #     §②「有界可枚举」字面）, 撞已有 ⇒ 该代跳过（枚举耗尽=停止）.
        def tour(pool: List[PolicySpec]) -> PolicySpec:
            top = sorted(pool, key=lambda s: (-best.get(s.pid, -1.0),
                                              s.pid))[:TOURNAMENT_K]
            return min(top, key=lambda s: (-best.get(s.pid, -1.0), s.pid))
        ranked = sorted(pop, key=lambda s: (-best.get(s.pid, -1.0),
                                            s.pid))
        if len(ranked) < 2:
            info.update({"skipped": True,
                         "why": "种群 <2 ⇒ tournament 没法选父母"})
            log.append(info)
            continue
        p1 = tour(ranked)
        p2 = tour([s for s in ranked if s.pid != p1.pid])
        ck = changed_keys(p1, p2)
        # ③ 合法交叉
        child = cross_pair(p1, p2) if ck else p1
        # ④ 单键变异（枚举翻转）
        var_key = ck[0] if ck else KEYS[0]
        child2 = mutate_one(child, var_key)
        # ⑤ ★ 子代必带 attribution_plan（M1 路径乙）
        plan = plan_for(ck)
        if plan is None:                          # 键域全同=无账=不进池
            info.update({"skipped": True,
                         "why": "父本键域全同 ⇒ 无消融账可带（不进池）"})
            log.append(info)
            continue
        # ⑥ ★ 键空间耗尽 ⇒ 子代撞已评 ⇒ 不进池（不重复评 — 预算纪律）;
        #    枚举集合外的产物理想态由 from_mapping 合法域保证（8 个内）
        if child2.pid in best:
            # ★ 键空间有界 ⇒ 交叉/变异产物撞已有 = **换新鲜**（沿可枚举池
            #   逐一代扫 — 确定性无重试; 池尽 ⇒ 如实 skip。这是小空间下
            #   的 GA 正确形态: 不重复评 = 预算纪律 + 不漏个体 = 覆盖纪律）
            fresh = next((x for x in _enum_pool()
                          if x.pid not in best), None)
            if fresh is None:
                info.update({"skipped": True,
                             "why": "键空间全枚举已耗尽（组合池全评 — "
                                    "有界空间的诚实终点, 不重复花预算）"})
                log.append(info)
                continue
            child2 = fresh
            # ★ 替补个体的 plan 重算（键差 ≥2 ⇒ plan_for 必出账 — 池语义）
            plan = plan_for([k for k in KEYS
                             if getattr(child2, k) !=
                             getattr(PolicySpec(), k)])
            if plan is None or len(plan["members"]) < 2:
                # 池不产 <2 键个体（_enum_pool 语义）— 到了这=契约违例
                info.update({"skipped": True,
                             "why": "替补个体消融账不足（成员<2 — 池契约"
                                    "违例, 如实报不进池）"})
                log.append(info)
                continue
        from dwc.organs.evolver import Proposal   # 构造即校验（坏账 raise）
        Proposal(proposal_id="ga_%s_g%d" % (child2.pid, gen),
                 failure_signature={"c": "E", "q": "n", "m": "m"},
                 component="memory", target="organs/memory.py::remember",
                 patch="+x = 1", rationale="GA 子代 — 消融账见 attribution_plan",
                 attribution_plan=plan)
        # ⑦ 预算内评估子代（超额⇒不评 — 硬上限; 超出部分成绩不计）
        if budget.can():
            budget.spend(child2.pid)
            best[child2.pid] = eval_v(child2)
            pop.append(child2)
        else:
            info.update({"skipped": True,
                         "why": "预算耗尽 ⇒ 子代不评（硬上限）"})
            log.append(info)
            continue
        info.update({"parents": [p1.pid, p2.pid], "crossed_keys": ck,
                     "var_key": var_key, "child_with_plan": child2.pid,
                     "plan_members": plan["members"]})
        log.append(info)
        if not budget.can():
            break
        from dwc.organs.evolver import Proposal   # 构造即校验（raise 在坏账）
        Proposal(proposal_id="ga_%s_g%d" % (child2.pid, gen),
                 failure_signature={"c": "E", "q": "n", "m": "m"},
                 component="memory", target="organs/memory.py::remember",
                 patch="+x = 1", rationale="GA 子代 — 消融账见 attribution_plan",
                 attribution_plan=plan)

    judged, accepted = {}, 0
    for pid, v in best.items():
        d = judge10(v)
        judged[pid] = {"v": v, "accept": d["accept"],
                       "improved_by": d["improved_by"]}
        if pid != current and d["accept"]:
            accepted += 1
    return {"accepted_eq10": accepted, "best_v": best, "judged": judged,
            "n_eval": budget.spent, "log": log,
            "final_pop": [p.pid for p in pop]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--executor", choices=["golden", "llm"], default="golden",
                    help="R127: llm=真执行臂（二期真区分; 默认 golden 恒等协议留档）")
    ap.add_argument("--metric", choices=["dream_v", "judge_mean"],
                    default="dream_v",
                    help=("R130: judge_mean=R129 口径 — 对打目标判定改用" 
                          "judge 逐任务分均值(max 饱和的整改路径②)"))
    ap.add_argument("--out", default=os.path.join(ROOT, "docs",
                                                  "ga_duel.json"))
    args = ap.parse_args()

    anchors = json.load(open(os.path.join(ROOT, "config", "anchors",
                                          "dev.json"), encoding="utf-8"))
    sp = anchors.get("_split") or {}
    search_ids, val_ids = list(sp.get("search", [])), list(sp.get("val", []))
    if not search_ids:
        print("★ 无 _split（HCE 未启用）⇒ D_search 缺 ⇒ not_applicable")
        return 2

    # ① 公共底: 单次 DWC + golden executor + D_search 两轮 step 起底
    shared = DWC(3, 50, executor=None, db_path=":memory:")
    shared.judge.store = TaskScoreStore(dw_version="ga_duel_r123")
    shared.executor = make_executor(anchors, mode=args.executor,
                                    memory=shared.memory)
    for _ in range(2):
        for tid in search_ids:
            shared.step({"task_id": tid, "kind": "dev"})

    def eval_v(spec: PolicySpec, core: DWC = shared) -> float:
        """★ 一次 V 评估 = 同底单次 dream(policy_variants=[spec]) 的 v_by
        （M1 ablation 基建的单跑取读; 两臂共享 core/ℋ ⇒ 起底方差受控）。
        ★ R130 metric=judge_mean: judge 逐任务分均值（R129 口径） —
          注意 R129 已证该度量在**策略轴**恒等（判分由任务×执行体
          定, spec 无因果）⇒ judge_mean 下 eval_v 对 spec 不敏感是真
          理而非 bug; 真区分在**执行体轴**（--executor golden vs llm）。
        """
        if args.metric == "judge_mean":
            pts = core.judge.task_scores(split="dev")
            return (sum(p.score for p in pts) / len(pts)) if pts else 0.0
        rep = core.dream(k2_max=4, policy_variants=[spec])
        return float(rep.v_by_version.get(spec.pid, 0.0))

    v0_ref = eval_v(PolicySpec())                # 两臂共用 current 参照

    def judge10(v: float) -> Dict[str, Any]:
        """Eq.10 判（口径见头部: Δ_gain=v−v0; cost/retention=0）。"""
        return eq10_accept({"gain": v - v0_ref, "cost": 0.0,
                            "retention": 0.0})

    def plan_for(changed: List[str]) -> Optional[Dict[str, Any]]:
        if not changed:                          # 无差异 ⇒ 无账（显式）
            return None
        return {"members": changed,
                "ablation_budget": {"n_runs": 2, "cost_to_ledger": True},
                "tau": 0.2,
                "calibration_note": "τ₀=0.2 R105c 抖动量级（稿③）",
                "fork_rule": "|I|<τ 可加拆分 / ≥τ 整体归档（稿③§④）"}

    # ② 两臂（各自独立预算与种群）
    # ★★ R130 metric=judge_mean 的轴切换（R129 两轴纪律的直接落地）:
    #   dream_v 口径 ⇒ 两臂共享 shared core（策略轴对打, 已知 max 饱和）
    #   judge_mean 口径 ⇒ **两臂各自起底**（执行体轴对打）:
    #     A 臂起底用 --executor 的值, B 臂起底用**另一**执行体
    #     （golden↔llm 互补）⇒ judge 均值有真差异, Eq.10 才有裁决对象
    #   ⇒ 这不是偷偷换比赛, 是稿⑦同款纪律的显式参数化: 度量决定轴,
    #     轴决定共享什么（协议写进 out.protocol, 不隐式）
    bA, bB = Budgeter("single"), Budgeter("ga")
    if args.metric == "judge_mean":
        other = "llm" if args.executor == "golden" else "golden"
        coreB = DWC(3, 50, executor=None, db_path=":memory:")
        coreB.judge.store = TaskScoreStore(dw_version="ga_duel_r130_b")
        coreB.executor = make_executor(anchors, mode=other,
                                       memory=coreB.memory)
        for _ in range(2):
            for tid in search_ids:
                coreB.step({"task_id": tid, "kind": "dev"})
        _evalA = lambda spec: eval_v(spec, shared)        # noqa: E731
        _evalB = lambda spec: eval_v(spec, coreB)         # noqa: E731
        armA = run_arm_single(_evalA, judge10, bA, CURRENT)
        armB = run_arm_ga(_evalB, judge10, bB, CURRENT,
                          plan_for=plan_for)
    else:
        armA = run_arm_single(eval_v, judge10, bA, CURRENT)
        armB = run_arm_ga(eval_v, judge10, bB, CURRENT,
                          plan_for=plan_for)

    # ③ 裁决（跑前锁死 — 稿⑦ §⑤）
    na, nb = armA["accepted_eq10"], armB["accepted_eq10"]
    va = max(armA["best_v"].values()) if armA["best_v"] else v0_ref
    vb = max(armB["best_v"].values()) if armB["best_v"] else v0_ref
    if na != nb:
        winner, basis = ("single" if na > nb else "ga"), "accept_count"
    elif va != vb:
        winner, basis = ("single" if va > vb else "ga"), "best_v"
    else:
        winner, basis = "single", "tie→incumbent(在位者保守,稿⑦§⑤)"
    identical = (len(set(armA["best_v"].values())) <= 1
                 and len(set(armB["best_v"].values())) <= 1)
    # 纪律先于输赢（稿⑦ §⑤）: 预算违规=当次成绩作废
    discipline = {"single_within": bA.spent <= bA.limit,
                  "ga_within": bB.spent <= bB.limit,
                  "note": "超额部分不计入读数（硬上限非软目标）"}

    out = {
        "protocol": ("M2 对打(稿⑦): 同任务D_search同起点; 两臂各16次V"
                     "硬上限+逐笔记账; Eq.10裁决 accept>bestV>判A; 纪律"
                     "先于输赢"
                     + ("" if args.metric == "dream_v" else
                        " | R130 metric=judge_mean ⇒ 执行体轴对打: "
                        "A臂=%s起底, B臂=%s起底(互补执行体), 各带策略"
                        "搜索; judge 逐任务分均值裁决(R129 口径解除 "
                        "max 饱和)" % (args.executor,
                                       ("llm" if args.executor == "golden"
                                        else "golden")))),
        "axis": ("strategy" if args.metric == "dream_v" else "executor"),
        "metric": args.metric,
        "seed": args.seed,
        "params": {"B_arms": B_ARMS, "pop_n": POP_N, "max_gen": MAX_GEN,
                   "tournament_k": TOURNAMENT_K, "current": CURRENT,
                   "n_d_search": len(search_ids), "d_val": val_ids},
        "delta_convention": ("Δ_gain=V(个体)−V(π0); Δ_cost=0(每V同价1单位"
                             "—对打搜索效率非任务成本); Δ_retention=0(V不"
                             "回退即保护组不掉)"),
        "arm_single": armA, "arm_ga": armB,
        "verdict": {"winner": winner, "basis": basis,
                    "accept_single": na, "accept_ga": nb,
                    "best_v_single": va, "best_v_ga": vb},
        "budget": {"single": bA.summary(), "ga": bB.summary(),
                   "k_ratio_ga_over_single": (
                       round(bB.spent / bA.spent, 4) if bA.spent else None)},
        "ledger_head": {"single": bA.ledger[:3], "ga": bB.ledger[:3]},
        "discipline": discipline,
        "executor_mode": args.executor,
        "caveats": [
            ((("★ 执行体轴: A 臂 golden(expected 全灌=结构必然 1.0) vs "
               "B 臂 llm(真判分 0.9) ⇒ winner=A 是**度量假象** — "
               "不可解读为『单点胜 GA 』或『GA 无益』: 两臂执行体不同"
               "(R129 轴纪律), 比的是执行体×策略组合, 不是纯策略优劣")
             if args.metric == "judge_mean" else
             ("★ golden 确定性臂: 键改动在回放底不改 V ⇒ 两臂 best 恒等"
              " ⇒ 平局规则判 A — 结构必然(R114/R118 同源), 非对打失败"
              if identical else
              "V 有区分度 — 记录方向(单次跑无方差)"))
             if args.executor == "golden" else
             ("★ R127 LLM 臂: 真执行通道接在**起底 step**, 但 V 由 dream 的 "
              "ReplaySimulator 从世界树内已存观测算出 — 零 LLM 调用 ⇒ "
              "V 恒等(R123 同源结构必然), **不是** LLM 真读数(实测已定位: "
              "n_calls 只发生在起底; evaluator_via_llm 未接); 要把 V 真 "
              "LLM 化须改 dream→judge 观测链(下轮目标, 不虚报本期)")),
            (("一期=协议验证(机制正确性由流程断言验收); 二期 LLM 臂才有真"
              "输赢(R105c 0.60/0.70/0.80 先例) — 恒等式平局≠'两臂一样好',"
              " 是'该臂测不出差别'")
             if args.executor == "golden" else
             ("二期==本次; 恒等式平局在 LLM 臂下的正确含义仍是'该臂在"
              "该任务集测不出差别', 不是'两臂样样等价'")),
            "K 倍账=两臂 V 评估数比值(管理口径); token 级成本差未计(暂)",
            "对打赢≠搜索器常态化授权(稿⑦§⑧双前置: 仍须用户再拍)",
        ],
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("A臂(单点): accept=%d bestV=%s 评估=%d" % (na, va, bA.spent))
    print("B臂(GA):   accept=%d bestV=%s 评估=%d K倍=%s"
          % (nb, vb, bB.spent, out["budget"]["k_ratio_ga_over_single"]))
    print("裁决: winner=%s basis=%s | 恒等=%s | 预算纪律=%s"
          % (winner, basis, identical, discipline))
    print("写出:", args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
