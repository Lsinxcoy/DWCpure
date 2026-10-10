# -*- coding: utf-8 -*-
"""gates · 门组入链执行器（V2 §5.4 六门顺序 · 口径桥 + 三态裁决）。

定位声明 · **DWC-AUTO**（自我强化 · 判据 G1 定位门）
  ★ 把 R147-R151 建的六个独立门**按论文顺序**串起来, 一次 term 跑完
    得到"这轮候选过到哪门"的链式结论 — 不是替代各门（它们仍是独立可测
    模块）, 本模块只做**编排 + 口径桥**（把 verdict/cost/汇编数投影成
    各门输入）。
  ★ 顺序（§5.4 原文"顺序不可换 — 每一步都建立在前一步的结论上"）:
    ① leakage → ② contract → ③ drawback → ④ split → ⑤ noncomp → ⑥ budget

★★★ 诚实边界（入链版的固有限制, 逐条如实）
  ★ DWC 当前 run_term 是**六层因果链**不是候选环（无 proposer 产出的
    diff 流）⇒ 部分门拿不到真输入。三态裁决规则:
      · passed  — 门拿到输入且判过
      · blocked  — 缺输入口径（δ 缺/守卫缺/候选缺 — 不猜值不硬跑）
      · not_applicable — 该门在 DWC 当前形态下无对象（如 ⑥无编辑清单）
    ★ 整体 verdict: ①③④⑤⑥ 中任一 blocked ⇒ 链 verdict=blocked
      （**不许把全 passed 的链当成"可以落地"** — blocked 段就是留痕）
  ★ 与 evolver split 门的关系: ④直接引用 evolver.evaluate_candidate 的
    结论（那里早有 Δ_in/Δ_ho 判定 — 不重造第二份 split 逻辑, G1 不抢位）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

#: 三态（与 G2 TRUTH_SOURCE 一致: 没输入≠通过）
GATE_PASSED = "passed"
GATE_BLOCKED = "blocked"
GATE_NOT_APPLICABLE = "not_applicable"

#: 六门顺序（V2 §5.4 — 值枚举, 顺序即契约）
GATE_ORDER: Tuple[str, ...] = ("leakage", "contract", "drawback", "split",
                               "noncomp", "budget")

#: 可在 DWC 当前形态下真判的门（其余显式 not_applicable）
_JUDGE_BACKED: Tuple[str, ...] = ("drawback",)          # judge verdict 可投影
_EVOLVER_BACKED: Tuple[str, ...] = ("split",)           # evolver 已有判定


class GateChainError(Exception):
    """链执行的显式拒绝（未知门名/仲裁重复/输入口径混用）。"""


@dataclass
class GateOutcome:
    """一门的一次裁决（三态 + 依据 + 跳过的门短路记录）。"""

    gate: str
    status: str
    detail: Dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        return {"gate": self.gate, "status": self.status,
                "detail": self.detail}


@dataclass(frozen=True)
class TermFacts:
    """一次 term 的**已判事实投影**（run_term 侧填, 本模块不重算）。

    ★ pass_rate/delta_s —— judge verdict 投影（None = 未判 ⇒ 相关门 blocked）;
      not_evaluated —— R14 口径计数（>0 时如实带进链, 不假装全判过）;
      noise_band/delta_c/domain_guards —— 调用方给（缺 ⇒ blocked）;
      candidate_diff —— 候选 diff（None ⇒ ① blocked; run_term 无候选流）;
      edits —— 显式申报编辑（空 ⇒ ⑥ not_applicable）。
    """

    pass_rate: Optional[float] = None
    score_star: Optional[float] = None
    delta_s: Optional[float] = None
    delta_c: Optional[float] = None
    nu_str: Optional[float] = None
    noise_band: Optional[float] = None
    domain_guard_ok: Optional[bool] = None
    not_evaluated: int = 0
    candidate_diff: Optional[str] = None
    vocabulary: Tuple[str, ...] = ()
    edits: Any = None      # Sequence[EditItem]（budget.check 的输入）
    split_verdict: Optional[Dict[str, Any]] = None     # evolver 的判定引用


def _g1_leakage(f: TermFacts) -> GateOutcome:
    """① leakage: 候选 diff 筛查（run_term 无候选流 ⇒ blocked — 不猜）。"""
    if f.candidate_diff is None:
        return GateOutcome("leakage", GATE_BLOCKED,
                           {"why": "无候选 diff（run_term 非候选环）⇒ ①"
                                   "不判 — 0 输入≠干净"})
    from dwc.organs.leakage import Candidate, screen_candidate
    c = Candidate(candidate_id="term", diff=f.candidate_diff,
                  task_names=f.vocabulary)
    r = screen_candidate(c)
    return GateOutcome("leakage",
                       GATE_PASSED if r.allowed else GATE_BLOCKED,
                       {"screen": r.as_dict()})


def _g2_contract(f: TermFacts) -> GateOutcome:
    """② contract: 契约注册表在场性（无候选 diff ⇒ 只查注册面）。"""
    from dwc.organs.contract import ContractRegistry, ST_NO_CONTRACT
    reg = _registry()
    if reg is None or reg.summary()["n_registered"] == 0:
        return GateOutcome("contract", GATE_BLOCKED,
                           {"why": "无契约注册（空表）⇒ ②不判 — 没契约≠"
                                   "契约满足（三值纪律, X2 同族）"})
    return GateOutcome("contract", GATE_PASSED,
                       {"n_registered": reg.summary()["n_registered"]})


def _g3_drawback(f: TermFacts) -> GateOutcome:
    """③ drawback: judge verdict 投影 (output=pass_rate, ctx=not_evaluated)。"""
    if f.pass_rate is None:
        return GateOutcome("drawback", GATE_BLOCKED,
                           {"why": "judge 未判（pass_rate None）⇒ ③不判"})
    from dwc.organs.drawback import CLEAN, DRAWBACK, Grader, Node, Op
    # 确定性 op（不引 LLM 判断 — 抗共谋, R149 口径）: 非全过 ⇒ drawback
    has_fail = f.pass_rate < 1.0
    op = Op(name="pass-rate-weak", fn=lambda t, y, c: (
        DRAWBACK if has_fail else CLEAN))
    g = Grader()
    g.register_op(op)
    g.set_tree(Node(kind="leaf", op="pass-rate-weak"))
    out = g.grade("term", f.pass_rate, {"not_evaluated": f.not_evaluated})
    return GateOutcome("drawback",
                       GATE_PASSED if out["ok"] else GATE_BLOCKED,
                       {"grade": out, "not_evaluated": f.not_evaluated,
                        "note": "clean=没找到已知缺点（非认证正确 — §2.1）"})


def _g4_split(f: TermFacts) -> GateOutcome:
    """④ split: **引用** evolver 判定（不重造第二份 split 逻辑 — G1）。"""
    if f.split_verdict is None:
        return GateOutcome("split", GATE_NOT_APPLICABLE,
                           {"why": "无候选对可判（split 判据要 baseline/"
                                   "current 对 — run_term 无候选对, evolver "
                                   "面才有）⇒ ④在此形态无对象"})
    sv = f.split_verdict
    ok = sv.get("decision") == "adopted_not_implemented"
    return GateOutcome("split",
                       GATE_PASSED if ok else GATE_BLOCKED,
                       {"split": sv})


def _g5_noncomp(f: TermFacts) -> GateOutcome:
    """⑤ noncomp: 投影 ΔS/ΔC/δ/守卫（缺口径 ⇒ blocked — 不硬设默认）。"""
    from dwc.organs.noncomp import GateInput, evaluate
    if f.delta_s is None or f.delta_c is None or f.noise_band is None:
        return GateOutcome("noncomp", GATE_BLOCKED,
                           {"why": "缺 ΔS/ΔC/δ 口径 ⇒ ⑤不判（不硬设 0 —"
                                   "静默放行禁, R150 纪律）"})
    out = evaluate(GateInput(
        score=f.pass_rate if f.pass_rate is not None else 0.0,
        score_star=f.score_star if f.score_star is not None else 0.0,
        delta_s=f.delta_s, delta_c=f.delta_c,
        nu_str=f.nu_str or 0.0,
        noise_band=f.noise_band, domain_guard_ok=f.domain_guard_ok))
    return GateOutcome("noncomp", {
        "pass": GATE_PASSED, "reject": GATE_BLOCKED,
        "blocked": GATE_BLOCKED}[out["verdict"]],
        {"noncomp": out})


def _g6_budget(f: TermFacts) -> GateOutcome:
    """⑥ budget: 显式申报编辑清单（空 ⇒ not_applicable — 不造编辑）。"""
    from dwc.organs.budget import BudgetError, check
    if not f.edits:
        return GateOutcome("budget", GATE_NOT_APPLICABLE,
                           {"why": "无显式申报编辑（run_term 不产编辑; "
                                   "applier/evolver 面才申报）⇒ ⑥无对象"})
    try:
        out = check(list(f.edits), 0)
    except BudgetError as exc:
        return GateOutcome("budget", GATE_BLOCKED,
                           {"error": str(exc)})
    return GateOutcome("budget",
                       GATE_PASSED if out["within_budget"] else GATE_BLOCKED,
                       {"budget": out})


_DISPATCH = {"leakage": _g1_leakage, "contract": _g2_contract,
             "drawback": _g3_drawback, "split": _g4_split,
             "noncomp": _g5_noncomp, "budget": _g6_budget}

#: 契约注册表的进程内共享表（②查它 — 空表 = 未注册面在档）
_SHARED_REGISTRY: Optional[Any] = None


def _registry():
    return _SHARED_REGISTRY


def install_registry(reg: Any) -> None:
    """安装共享契约表（调用方注入 — 本模块不自造契约, G2）。"""
    global _SHARED_REGISTRY
    _SHARED_REGISTRY = reg


def run_gates(facts: TermFacts, *, stop_at_first_block: bool = False
              ) -> Dict[str, Any]:
    """★ 六门顺序执行（§5.4 顺序不可换 — 前门 blocked 记后仍问后门? 否）。

    ★★ stop_at_first_block=True ⇒ 一门 blocked 即停（论文"每一步建立
      在前一步结论上"的严格执行 — 前门没过, 后门结论无意义）。
    ★ 默认 False: 全跑完但**每门自带 blocked 依据**（诊断面更全; 最终
      verdict 仍 = 有一门 blocked 就 blocked — 默认不让"其余都好"补偿,
      非补偿精神贯到链级）。
    """
    out: List[GateOutcome] = []
    for name in GATE_ORDER:
        o = _DISPATCH[name](facts)
        out.append(o)
        if stop_at_first_block and o.status == GATE_BLOCKED:
            break
    blocked = [o.gate for o in out if o.status == GATE_BLOCKED]
    na = [o.gate for o in out if o.status == GATE_NOT_APPLICABLE]
    verdict = GATE_BLOCKED if blocked else (
        "all_applicable_passed" if not na else
        "applicable_passed_with_na")
    return {"verdict": verdict,
            "gates": [o.as_dict() for o in out],
            "order": list(GATE_ORDER),
            "blocked": blocked,
            "not_applicable": na,
            "note": ("链 verdict=blocked ⇒ **不许落地**（非补偿: 门间不可"
                     "互偿 — blocked 段就是留痕, 不是'其余都好'的缓冲）")}


GATE_CHAIN: Dict[str, str] = {
    "order": "leakage → contract → drawback → split → noncomp → budget（§5.4 顺序不可换）",
    "three_states": "passed / blocked（缺口径）/ not_applicable（无对象）",
    "no_compensation": "链级 verdict: 一门 blocked ⇒ 全链 blocked（门间不可互偿）",
    "split_by_reference": "④引用 evolver evaluate_candidate 结论（不重造 — G1 不抢位）",
    "drawback_by_projection": "③投影 judge pass_rate（确定性 op — 不引 LLM 判断, R149 抗共谋）",
    "dwc_limits": "run_term 非候选环 ⇒ ①④⑥ 当前 not_applicable/blocked（如实, 不造假过）",
}
