# -*- coding: utf-8 -*-
"""DWC-AUTO · 改动评估器 U —— GAI (arXiv:2609.13406) 五元组里的 modification critic。

## 论文依据（取证）

GAI Definition 1 原文：

    χ = (π, V, m, U, ρ)
    U : X → ℝ   **评估提议的改动是否服务于 G** (evaluate whether a proposed
                 modification serves the external goal G)

GAI 对 U 与 V 的分工（Definition 2）原文：
    "policy 层用 V，agent 层用 U"
    —— V 评的是**动作**好不好；U 评的是**改动**好不好。

**这就是 DWC 缺的那个角色**：DWC 有 V（判据层），但没有独立的 U。
缺 U 的后果（GAI Table 4 第一条缺陷的形态）：
    改进器自己评自己的提议 ⇒ 坍缩为自确认循环。

## 为什么 U 必须与 m 分离（authority boundary）

GAI Figure 2 原文：环上**恰好一条 authority boundary**。
若 m 与 U 是同一个模块，环上出现第二条边界，退化为自确认。
因此本模块**只做裁决，不产生任何候选**。

## U 的判据来源（不是本模块发明的）

U 的裁决规则逐条来自论文：

  ① **pub/priv 信号解耦** —— AIDE² (arXiv:2609.26457) §2.1 原文：
     "separating the inner loop's optimization signal r_t^pub from the outer
      loop's selection signal g (driven by r_t^priv) prevents the inner-loop
      agent from directly optimizing the criterion used for outer-loop selection."
     ⇒ U **只读 r_priv**，绝不读 r_pub。

  ② **固定预算** —— 同篇原文：
     "evaluating all agents under the same per-task budget b_t constrains
      improvements to arise from a better algorithm rather than from spending
      additional compute."
     ⇒ 预算不等则直接否决（不管分数多高）。

  ③ **非补偿式** —— RRSI (arXiv:2609.24972) §3.3 原文，顺序不可换：
     0) leakage screen BEFORE evaluation
     1) noise floor  Ŝ ≥ S* − δ
     2a) ΔS > δ  → cost rule   ΔC ≤ β0 + β1·ΔS
     2b) ΔS ≤ δ  → shaped      ws·ΔS − wc·ΔC + wn·ν_str > 0
     3) domain guards

  ④ **双 split** —— Self-Harness (arXiv:2606.09498) Algorithm 1 line 13 原文：
     if Δ_in ≥ 0 and Δ_ho ≥ 0 and max(Δ_in, Δ_ho) > 0 then Accept
     ⇒ 只有一组 split 就无法区分"可复用改进"与"过拟合"。

## TRUTH_SOURCE 声明（gate.py G2 要求）

TRUTH_SOURCE = "sealed_eval" —— U 的裁决输入必须来自系统外（held-out 判分器），
且 U 自身**不可被它裁决的改动所修改**（GAI grounded 双条件之②：
base 本身在 agent 外）。若调用方传入 r_priv 的 truth_source 不在
EXTERNAL_SOURCES 内，U 必须返回 UNKNOWN 而非放行。

## 本模块不做什么

- 不产生候选（那是 m）
- 不落地（那是 applier）
- 不读 r_pub（那会破坏信号解耦）
- 不评估"改动好不好"以外的任何东西（V 评动作）
"""
from __future__ import annotations

import math

__all__ = [
    "TRUTH_SOURCE",
    "EXTERNAL_SOURCES",
    "Verdict",
    "Signals",
    "evaluate_modification",
    "leakage_screen",
]

# ── gate.py G2 要求的真值源声明 ───────────────────────────────────
TRUTH_SOURCE = "sealed_eval"

# 允许的 r_priv 来源（系统外）。不在表内 ⇒ UNKNOWN。
# 对齐 ARSI foundation/effect_anchor.py 的 EXTERNAL_SOURCES 语义：
# 效果/裁决类主张必须来自系统之外。
EXTERNAL_SOURCES = frozenset({
    "sealed_eval",      # 密封评估器（held-out）
    "host_outcome",     # 宿主真实结果
    "heldout_split",    # held-out 切分
    "quality_gate",     # 独立质量门
    "behavior_trace",   # 行为轨迹（外部回执）
})

_UNKNOWN = "UNKNOWN"
_ACCEPT = "ACCEPT"
_REJECT = "REJECT"


class Signals:
    """一次改动的**成对**观测。

    字段命名对齐论文符号，便于与原文对照：

        r_priv        外环选择信号（AIDE² 的 g）
        budget_used   本次改动消耗的预算（含解执行成本）
        budget_cap    固定预算上限 b_t
        d_score       经验分数变化 ΔS = Ŝ(candidate) − Ŝ(incumbent)
        d_cost        经验成本变化 ΔC（相对值，论文式 3 的 Ĉ 之差）
        nu_structural 结构型组件新颖度 ν_str（RRSI 式 15）
        d_in          held-in 切分上的变化（Self-Harness）
        d_ho          held-out 切分上的变化（Self-Harness）
        leaked       泄漏筛查结果（RRSI 第 0 步，必须在评估之前得出）
        noise_floor   噪声地板 S* − δ 的 S*（论文式 1 的 S*）
        truth_source  r_priv 的来源标识（必须在 EXTERNAL_SOURCES 内）
    """

    __slots__ = ("r_priv", "budget_used", "budget_cap", "d_score", "d_cost",
                 "nu_structural", "d_in", "d_ho", "leaked", "noise_floor",
                 "truth_source")

    def __init__(self, r_priv=None, budget_used=0.0, budget_cap=None,
                 d_score=None, d_cost=0.0, nu_structural=0,
                 d_in=None, d_ho=None, leaked=False, noise_floor=None,
                 truth_source=None):
        self.r_priv = r_priv
        self.budget_used = budget_used
        self.budget_cap = budget_cap
        self.d_score = d_score
        self.d_cost = d_cost
        self.nu_structural = nu_structural
        self.d_in = d_in
        self.d_ho = d_ho
        self.leaked = leaked
        self.noise_floor = noise_floor
        self.truth_source = truth_source


class Verdict:
    """U 的裁决输出。

    `decision` ∈ {ACCEPT, REJECT, UNKNOWN}。
    **UNKNOWN 是一等输出** —— 不可评时不许伪装成 ACCEPT 或 REJECT
    （对齐 ModularRSI 的"弃权是一等输出"与 gate.py G2 的诚实要求）。
    """

    __slots__ = ("decision", "reason", "branch", "detail")

    def __init__(self, decision: str, reason: str, branch: str = "",
                 detail: dict | None = None):
        self.decision = decision
        self.reason = reason
        self.branch = branch
        self.detail = detail or {}

    @property
    def accepted(self) -> bool:
        """★ 只有显式 ACCEPT 才算通过；UNKNOWN 一律不通过。

        这是防"不可评 ⇒ 默认放行"的关键：`if v.accepted` 对 UNKNOWN 为 False。
        """
        return self.decision == _ACCEPT

    def to_dict(self) -> dict:
        return {"decision": self.decision, "reason": self.reason,
                "branch": self.branch, "detail": self.detail}

    def __repr__(self) -> str:
        return "Verdict(%s, %s)" % (self.decision, self.reason)


def leakage_screen(train_items, eval_items) -> bool:
    """RRSI 第 0 步 —— 泄漏筛查，**必须在评估之前**。

    原文顺序原文（accept.py docstring）：
        "Order matters: 0) leakage screen BEFORE evaluation"

    返回 True 表示**发现泄漏**（应当直接否决）。
    判据：训练侧与评测侧出现相同条目。空输入 ⇒ False（无证据不臆测）。
    """
    try:
        tr = {str(x) for x in (train_items or [])}
        ev = {str(x) for x in (eval_items or [])}
    except (TypeError, ValueError):
        return False
    if not tr or not ev:
        return False
    return bool(tr & ev)


def _is_num(x) -> bool:
    if x is None or isinstance(x, bool):
        return False
    try:
        v = float(x)
    except (TypeError, ValueError):
        return False
    return not (math.isnan(v) or math.isinf(v))


def evaluate_modification(sig: Signals, *,
                          delta: float = 0.01,
                          beta0: float = 0.0,
                          beta1: float = 1.0,
                          ws: float = 0.0,
                          wc: float = 1.0,
                          wn: float = 0.1,
                          valid_drop_max: float = 0.03,
                          valid_before=None,
                          valid_after=None) -> Verdict:
    """U 的裁决入口 —— 严格按 RRSI 的顺序，逐条不可换。

    顺序（论文原文顺序）：
        0) 泄漏筛查
        1) 噪声地板
        2a/2b) 成本规则 / 整形
        3) 领域守卫
      外加 AIDE² 的固定预算前置与 Self-Harness 的双 split。

    任何一步**不可评**（输入缺失）⇒ 返回 UNKNOWN，不猜。

    永不抛：任何异常 ⇒ UNKNOWN（保守），不伪装通过。
    """
    try:
        return _evaluate(sig, delta=delta, beta0=beta0, beta1=beta1,
                         ws=ws, wc=wc, wn=wn, valid_drop_max=valid_drop_max,
                         valid_before=valid_before, valid_after=valid_after)
    except Exception as e:                                   # noqa: BLE001
        # 裁决器故障不能变成"放行"。显式返回 UNKNOWN 并带原因。
        return Verdict(_UNKNOWN, "evaluator_error:%s" % type(e).__name__,
                       branch="error")


def _evaluate(sig, *, delta, beta0, beta1, ws, wc, wn,
              valid_drop_max, valid_before, valid_after) -> Verdict:
    if not isinstance(sig, Signals):
        return Verdict(_UNKNOWN, "signals_missing")

    # ── 前置：真值源必须在系统外（GAI grounded 双条件之②）──────────
    if sig.truth_source is None:
        return Verdict(_UNKNOWN, "truth_source_missing",
                       detail={"note": "r_priv 无来源标识 ⇒ 不可评"})
    if sig.truth_source not in EXTERNAL_SOURCES:
        return Verdict(_UNKNOWN, "truth_source_not_external",
                       detail={"got": sig.truth_source,
                               "allowed": sorted(EXTERNAL_SOURCES)})

    # ── 前置：固定预算（AIDE² §2.1 第二条设计）────────────────────
    # "improvements to arise from a better algorithm rather than from
    #  spending additional compute"
    if _is_num(sig.budget_cap) and _is_num(sig.budget_used):
        if float(sig.budget_used) > float(sig.budget_cap):
            return Verdict(_REJECT, "over_budget",
                           detail={"used": sig.budget_used,
                                   "cap": sig.budget_cap})

    # ── 第 0 步：泄漏筛查（必须在评估之前）───────────────────────
    if sig.leaked is True:
        return Verdict(_REJECT, "leakage_detected", branch="0")

    # ── 第 1 步：噪声地板  Ŝ ≥ S* − δ ────────────────────────────
    if sig.noise_floor is not None:
        if not _is_num(sig.noise_floor):
            return Verdict(_UNKNOWN, "noise_floor_unparsable", branch="1")
        # r_priv 是 Ŝ；地板是 S* − δ
        if _is_num(sig.r_priv):
            floor = float(sig.noise_floor) - float(delta)
            if float(sig.r_priv) < floor:
                return Verdict(_REJECT, "below_noise_floor", branch="1",
                               detail={"r_priv": sig.r_priv,
                                       "floor": floor})

    # ── 第 2 步：分叉（需要 ΔS）─────────────────────────────────
    if not _is_num(sig.d_score):
        return Verdict(_UNKNOWN, "d_score_missing", branch="2")

    dS = float(sig.d_score)
    dC = float(sig.d_cost) if _is_num(sig.d_cost) else 0.0
    nu = int(sig.nu_structural or 0)

    if dS > delta:
        # 2a) 成本规则：ΔC ≤ β0 + β1·ΔS
        limit = float(beta0) + float(beta1) * dS
        if dC > limit:
            return Verdict(_REJECT, "cost_rule_violated", branch="2a",
                           detail={"dC": dC, "limit": limit})
    else:
        # 2b) 整形：ws·ΔS − wc·ΔC + wn·ν_str > 0
        shaped = float(ws) * dS - float(wc) * dC + float(wn) * nu
        if not shaped > 0:
            return Verdict(_REJECT, "shaped_rule_violated", branch="2b",
                           detail={"shaped": shaped})

    # ── 第 3 步：领域守卫（非补偿：主分不能补偿执行有效性）────────
    if _is_num(valid_before) and _is_num(valid_after):
        drop = float(valid_before) - float(valid_after)
        if drop > float(valid_drop_max):
            return Verdict(_REJECT, "valid_output_dropped", branch="3",
                           detail={"drop": drop, "max": valid_drop_max})

    # ── Self-Harness 双 split（Algorithm 1 line 13）──────────────
    if _is_num(sig.d_in) and _is_num(sig.d_ho):
        d_in, d_ho = float(sig.d_in), float(sig.d_ho)
        if not (d_in >= 0 and d_ho >= 0 and max(d_in, d_ho) > 0):
            return Verdict(_REJECT, "split_rule_violated", branch="split",
                           detail={"d_in": d_in, "d_ho": d_ho})
    else:
        # 缺任一组 split ⇒ 无法判定"可复用 vs 过拟合" ⇒ 不可评
        return Verdict(_UNKNOWN, "split_missing", branch="split",
                       detail={"d_in": sig.d_in, "d_ho": sig.d_ho})

    return Verdict(_ACCEPT, "passed_non_compensatory",
                   detail={"dS": dS, "dC": dC, "nu": nu})
