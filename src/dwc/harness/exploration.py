# -*- coding: utf-8 -*-
"""exploration · 停滞激活的探索编排（ℰ_t = (σ_t, 𝒰_t, m_draft) · 伪码 line 9）。

定位声明 · **DWC-AUTO**（自我强化 · 判据 G1 定位门）
  ★ 把 evolver 里**早已 live**的 σ_t/𝒰_t/ℰ_t（stall_signal L773 ·
    exploration_signal L811 · unexplored_components L582）接到候选环编排
    面 —— R156 pipeline 五面跑通但不吃停滞信号 ⇒ 停滞时仍照常全组分
    配选, 违背伪码"仅在停滞时保留预算给未探索组件"。
  ★★ 语义（原文, 逐字）: "仅在**停滞时**才把预算的一部分**保留给**
    components that have not yet been exercised"
      ⋏ σ_t == 1（停滞, 式 13 第一项）
      ⋏ 𝒰_t 非空（𝒦∪𝒦_meta_editable ∖ 𝒯_t — 未探索组件存在）
      ⋏ m_draft 在位（本轮探索草案 — 没有草案位 ⇒ ℰ_t 不完整, 不当完整用）
  ★ 不抢位: σ_t/𝒰_t 计算全在 evolver（真源唯一）; 本模块只做**编排**:
    决定本轮哪些候选标记"探索预算"（m_draft uteur 侧）。

★★★ TRUTH_SOURCE（判据 G2）
  · σ_t ← evolver.stall_signal（历史分数 + w + δ 全由调用方给）
  · 𝒰_t ← evolver.unexplored_components（真源 liquidity 优先, 近似 fallback
    在 evolver 侧已标注 T_source）
  · 本模块不重算任何信号 — 只消费 + 记账（标签 on 候选）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

#: 探索预算标签（候选环内流转用 — 与 evolver.ℰ_t 的 draft 位语义对齐）
TAG_EXPLORE = "explore"
TAG_EXPLOIT = "exploit"


class ExplorationError(Exception):
    """编排期的显式拒绝（σ_t 无效时激活 / 𝒰_t 空而声称有探索面）。"""


@dataclass(frozen=True)
class ExplorationPlan:
    """一轮探索编排结果（哪些候选走探索预算 / 走利用 — 带依据）。"""

    active: bool
    explore_components: Tuple[str, ...]
    explore_budget: int
    notes: Tuple[str, ...] = ()
    sigma: Optional[Dict[str, Any]] = None

    def tag(self, component: str) -> str:
        """★ 单个候选的打标（explore / exploit — 组件 ∈ 𝒰_t 才 explore）。"""
        return TAG_EXPLORE if component in self.explore_components else TAG_EXPLOIT

    def as_dict(self) -> Dict[str, Any]:
        return {"active": self.active,
                "explore_components": list(self.explore_components),
                "explore_budget": self.explore_budget,
                "notes": list(self.notes),
                "sigma": self.sigma}


def plan(score_history: Sequence[float], window: int, delta: float, *,
         accepted_rules: Optional[Dict[str, Any]] = None,
         liquidity: Optional[List[Dict[str, Any]]] = None,
         reserve_fraction: float = 0.5) -> ExplorationPlan:
    """★ 编排: σ_t/𝒰_t/m_draft → 本轮探索预算（不重算 — 全问 evolver）。

    ★ reserve_fraction: 停滞时把 b_t 的多大比例留给 𝒰_t（管理参数,
      论文不给值; 0 ≤ f ≤ 1; 不给 100% — 全探索=放弃利用, 也没据）。
    ★ m_draft 口径: 本模块给 plan（**draft 位由调用方持**）⇒ 三元齐备性
      看 σ_t 有效 ∧ 𝒰_t 非空 ∧ 本 plan 在场（返回本身即 draft 存在证明）。
    """
    from dwc.organs.evolver import exploration_signal

    if not (0.0 <= reserve_fraction <= 1.0):
        raise ExplorationError("reserve_fraction 须 ∈ [0,1]（管理参数, 论文不给值）")
    ev = exploration_signal(score_history, window, delta,
                            accepted_rules or {}, draft=True,
                            liquidity=liquidity)
    sigma = ev["sigma"]
    if ev["active"]:
        U = tuple(ev["unexplored"])
        # ★ b_t 这里是**预算份额比例**的落地处: 真 b_t 由 budget.schedule 算
        #   （本模块不重算议程 — 只标"这轮哪些组件可吃探索份额"）
        return ExplorationPlan(
            active=True, explore_components=U,
            explore_budget=int(round(reserve_fraction * 100)),
            notes=("σ_t=1（Ŝ_t − Ŝ_{t−w} = %s ≤ δ=%s）⇒ 保留 %.0f%% 预算给"
                   " %d 个未探索组件" % (sigma.get("delta_now"), delta,
                                       reserve_fraction * 100, len(U)),
                   "𝒰_t 真源: %s" % ev.get("T_source", "近似")),
            sigma=sigma)
    # 未激活 ⇒ 照实说为什么（**不许**把"没激活"报成"没有探索面"）
    why = ev.get("why_inactive") or "σ_t=0 或 𝒰_t 空"
    return ExplorationPlan(active=False, explore_components=(),
                           explore_budget=0,
                           notes=(str(why),), sigma=sigma)


def tag_candidates(cands: Sequence[Any], plan_: ExplorationPlan
                   ) -> List[Tuple[str, str]]:
    """★ 批量打标（(component, tag) — 顺序保序, 可复核）。"""
    return [(getattr(c, "component", ""), plan_.tag(
        getattr(c, "component", ""))) for c in cands]


EXPLORATION_MECHANICS: Dict[str, str] = {
    "trigger": "σ_t == 1 ∧ 𝒰_t ≠ ∅ ∧ draft 在位（伪码 line 9 — 三元素全齐才激活）",
    "reserve": "停滞时保留 b_t 的 reserve_fraction 给未探索组件（管理参数 — 论文不给值, 0<f<1 显式拒绝全探索=放弃利用）",
    "sigma_source": "evolver.stall_signal（Ŝ_t − Ŝ_{t−w} ≤ δ; 历史不足 ⇒ sigma 无效且不当激活 — G7 同族）",
    "u_source": "evolver.unexplored_components（liquidity 式11 真源优先; 近似 T_source 在 evolver 侧已标注）",
    "not_recompute": "本模块只消费 σ_t/𝒰_t + 打标; 不重算任何信号（判定在 evolver, 编排在 harness — G1 分工）",
    "inactive_honesty": "未激活 ⇒ notes 带 why_inactive（不报成『没有探索面』）",
}
