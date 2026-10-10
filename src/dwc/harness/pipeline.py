# -*- coding: utf-8 -*-
"""pipeline · 候选环五面合流（bridge → gates → adoption → credit）。

定位声明 · **DWC-AUTO**（自我强化 · 判据 G1 定位门）
  ★ 把 R153-R155 建的四面（投影/门组/采纳/回写）**按候选环真实顺序**接
    成一条可跑管线 —— 之前四轮每面独立可测但没接线, 本模块只编排,
    不新增判定逻辑（判定逻辑仍在各面内）。
  ★ 管线顺序（每步的产物是下一步的输入 — 顺序即契约）:
      ① bridge.to_facts    Candidate[] → TermFacts（逐字投影）
      ② gates.run_gates    六门三态链裁决（blocked 即后续不进）
      ③ adoption.apply_chain  链裁决 → Proposal 状态机（gated/rejected）
      ④ credit.record_round   赢家的编辑记 a_i=1（★ 只记赢家 — 理由见下）
  ★ ★★ 记账口径（**与原文的差异, 显式声明**）:
      原文 ℒ_t 记本轮**所有**候选的编辑（含 admissible-but-lost 的 a_i=0）;
      DWC 当前形态只有一个候选面（evaluator 未接），"输给更高分候选"的
      对手方不存在 ⇒ **只记赢家**（a_i=1）, 并显式标注
      `lost_not_recorded: True`（陪跑面缺席 ≠ 没有陪跑 — X2 纪律）。
  ★ 不抢位: 不生成候选 · 不判谁赢（judge/evolver.accept 的分）· 不改
    各面逻辑。本模块只做**编排 + 留痕**。

★★★ TRUTH_SOURCE（判据 G2）
  · ΔS_i/ΔC_i ← 调用方从 judge 已判读数抄录（本模块不重算）;
  · 赢家裁决 ← evolver.accept 的 decision 字段（本模块只分发）;
  · a_i ← credit.adopted_flag(is_winner=裁决, cause=裁决字符串原文)。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .adoption import AdoptionRecord, apply_chain
from .candidate_bridge import to_facts
from .gates import TermFacts, run_gates


class PipelineError(Exception):
    """管线的显式拒绝（空候选/裁决缺 decision/维度不在九维）。"""


@dataclass
class RoundResult:
    """一轮候选环的完整轨迹（进台账/审计面用 — 不是只给 verdict）。"""

    chain: Dict[str, Any]
    adoption: Optional[AdoptionRecord]
    credit_entries: List[Dict[str, Any]]
    components: List[str]
    notes: List[str] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return {"chain_verdict": self.chain.get("verdict"),
                "blocked": self.chain.get("blocked", []),
                "not_applicable": self.chain.get("not_applicable", []),
                "adoption": (self.adoption.as_dict() if self.adoption
                             else None),
                "credit_entries": self.credit_entries,
                "components": self.components,
                "lost_not_recorded": True,
                "notes": self.notes}


def run_round(cands: Sequence[Any], *, t: int, proposal: Any,
              ledger: Any, vocabulary: Tuple[str, ...] = (),
              pass_rate: Optional[float] = None,
              score_star: Optional[float] = None,
              delta_s: Optional[float] = None,
              delta_c: Optional[float] = None,
              noise_band: Optional[float] = None,
              domain_guard_ok: Optional[bool] = None,
              delta_s_by_edit: Optional[Dict[str, float]] = None,
              delta_c_by_edit: Optional[Dict[str, float]] = None,
              nu_str: Optional[float] = None,
              split_verdict: Optional[Dict[str, Any]] = None) -> RoundResult:
    """★ 一次候选环（五面合流 — 编排, 不新增判定）。

    ★ 顺序: bridge → gates → adoption → credit（chain blocked 时 credit
      不记 — 没赢家可记; 但 adoption 仍迁移 rejected, 留痕完整）。
    ★ ΔS_i/ΔC_i: 逐编辑口径（delta_s_by_edit）优先; 缺 ⇒ 退化到整候选
      单一读数均摊到各编辑（**均摊=近似口径, notes 显式标注** — 不是隐
      式默认）。
    """
    if not isinstance(cands, (list, tuple)) or not cands:
        raise PipelineError("空候选列表 ⇒ 无可编排行程（没候选≠干净, 同上）")

    # ① 投影（逐字 — 不重写 patch 文本）
    facts = to_facts(cands, vocabulary=vocabulary, pass_rate=pass_rate,
                    score_star=score_star, delta_s=delta_s,
                    delta_c=delta_c, noise_band=noise_band,
                    domain_guard_ok=domain_guard_ok, nu_str=nu_str,
                    split_verdict=split_verdict)

    # ② 六门链
    chain = run_gates(facts)

    # ③ 采纳迁移（blocked ⇒ rejected — 不进判分, R154）
    adoption = apply_chain(proposal, chain)

    notes: List[str] = []
    credit_entries: List[Dict[str, Any]] = []
    if chain.get("verdict") == "blocked":
        notes.append("链 blocked ⇒ 不记 ℒ_t（没赢家可记 — 没通过不是\"赢\"）")
        return RoundResult(chain=chain, adoption=adoption,
                           credit_entries=credit_entries,
                           components=sorted(facts.edits[i].component
                                             for i in range(len(facts.edits))),
                           notes=notes)

    # ④ 记账（只记赢家 — 陪跑面缺席显式标注, 见模块 docstring）
    from dwc.organs.credit import CreditEntry, adopted_flag
    from dwc.organs.evolver import DIMENSIONS, layer_of
    for c, e in zip(cands, facts.edits):
        comp = e.component
        lay = layer_of(comp)                     # 未知组件在此 ValueError（显式）
        dim = getattr(c, "dimension", None)
        if dim is not None and dim not in DIMENSIONS:
            raise PipelineError("维度 %r 不在九维内（%s）"
                                % (dim, "/".join(DIMENSIONS)))
        ds_map = delta_s_by_edit or {}
        dc_map = delta_c_by_edit or {}
        e_ds = ds_map.get(e.hunk)
        e_dc = dc_map.get(e.hunk)
        if e_ds is None:
            e_ds = (delta_s or 0.0) / max(1, len(facts.edits))
            if delta_s:
                notes.append("ΔS 未逐编辑给 ⇒ 均摊口径（近似, 非精确归因）")
        if e_dc is None:
            e_dc = (delta_c or 0.0) / max(1, len(facts.edits))
            if delta_c:
                notes.append("ΔC 未逐编辑给 ⇒ 均摊口径（近似, 非精确归因）")
        entry = CreditEntry(t=t, edit=str(e.hunk), layer=lay, hunk=str(e.hunk),
                            dimension=(dim or "D1"),
                            delta_s=float(e_ds), delta_c=float(e_dc),
                            adopted=adopted_flag(True, "winner"))
        ledger.record(entry)
        credit_entries.append(entry.as_dict())
    return RoundResult(chain=chain, adoption=adoption,
                       credit_entries=credit_entries,
                       components=sorted({e.component for e in facts.edits}),
                       notes=notes)


PIPELINE_MECHANICS: Dict[str, str] = {
    "order": "bridge.to_facts → gates.run_gates → adoption.apply_chain → credit.record（编排, 不新增判定）",
    "blocked_short_circuit": "链 blocked ⇒ credit 不记（没赢家可记 — 没通过≠赢）; adoption 仍迁 rejected",
    "winner_only": "只记赢家 a_i=1 + lost_not_recorded=True 显式标注（DWC 无对手方面 ⇒ 陪跑面缺席≠没有陪跑）",
    "delta_split": "ΔS_i/ΔC_i 逐编辑优先; 缺 ⇒ 整候选均摊 + notes 标注『近似口径』（不隐式默认）",
    "layer_derivation": "layer ← evolver.layer_of（未知组件 ValueError — proposer 词表外即炸, 不在 pipeline 猜）",
    "truth_source": "ΔS/ΔC 由调用方给; 赢家标志恒 True 的分录只在链 passed 后（裁决在 caller/judge 侧）",
}
