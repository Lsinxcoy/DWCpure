# -*- coding: utf-8 -*-
"""adoption · 链裁决 → Proposal 采纳（R152 六门链 × evolver 第五态的桥）。

定位声明 · **DWC-AUTO**（自我强化 · 判据 G1 定位门）
  ★ 把 R152/R153 的**门组链裁决**接到 evolver 的提案状态机上:
      · 链 verdict ≠ blocked ⇒ p.gate_verdict = 链结论, state → gated
        （后续由 evolver.accept(baseline, current) 判 split ⇒ 第五态）
      · 链 verdict = blocked ⇒ state → rejected（**不进入判分** —
        链都没过就判分是浪费, 且 blocked 段会污染 ΔS 归因）
  ★★ 与 ProposalGate 的分工（**不替换**, 两层互补 — 有据）:
      · ProposalGate.check（静态, 五判据: target/rationale/词表/维度/禁触判据）
        = proposer 契约面（构造期就该发现的违规）
      · 门组链（运行时, 六门: leakage→…→budget）= 评估面（要候选数据才判）
      ⇒★ 两层都过才算"可判分"（gate_all 先静态, 链后运行时 — 顺序不可换）
  ★ 不抢位: 不判 split（evolver.accept 的固定门）· 不改 ProposalGate 语义;
    本模块只做**状态迁移 + 裁决留痕**。

★★★ TRUTH_SOURCE（判据 G2）
  · 链结论 ← harness.gates.run_gates（候选/term 两形态, 已三态）
  · Proposal 状态 ← evolver.PROPOSAL_STATES 值枚举（不造新状态）
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

#: 链 verdict → Proposal state 的映射（只映射到 evolver 既有状态）
CHAIN_PASS_STATE = "gated"
CHAIN_BLOCK_STATE = "rejected"

#: 可接受的链 verdict（链级非补偿的三种终态）
CHAIN_VERDICTS: Tuple[str, ...] = ("applicable_passed_with_na", "blocked",
                                   "error")


class AdoptionError(Exception):
    """迁移的显式拒绝（未知 verdict / 状态非法 / Proposal 无 proposal_id）。"""


def _valid_state(s: str) -> bool:
    """状态须在 evolver 五态内（防本模块造第六态）。"""
    from dwc.organs.evolver import PROPOSAL_STATES
    return s in PROPOSAL_STATES


@dataclass(frozen=True)
class AdoptionRecord:
    """一次链裁决→采纳的留痕（进 epoch 台账, 不进 Proposal 本体）。"""

    proposal_id: str
    chain_verdict: str
    blocked: Tuple[str, ...]
    not_applicable: Tuple[str, ...]
    n_gates: int
    state_before: str
    state_after: str

    def as_dict(self) -> Dict[str, Any]:
        return {"proposal_id": self.proposal_id,
                "chain_verdict": self.chain_verdict,
                "blocked": list(self.blocked),
                "not_applicable": list(self.not_applicable),
                "n_gates": self.n_gates,
                "state_before": self.state_before,
                "state_after": self.state_after}


def apply_chain(p: Any, chain: Dict[str, Any]) -> AdoptionRecord:
    """★ 把门组链裁决应用到 Proposal（状态迁移 + 裁决留痕）。

    ★★ 顺序（迁移即契约）:
      ① chain 结构校验（verdict 在场 + gates 列表非空 — 空链不是裁决）;
      ② p.state_before 记录（回滚/审计要）;
      ③ verdict ∈ 三终态; error ⇒ rejected（链执行失败 ≠ 通过 — G7 留痕）;
      ④ blocked ⇒ rejected（链级非补偿: 一门 blocked 全链 blocked）;
      ⑤ 否则 ⇒ gated（进 evolver.accept 判 split）。
    """
    if not hasattr(p, "proposal_id") or not p.proposal_id:
        raise AdoptionError("Proposal 无 proposal_id ⇒ 无可归因锚点")
    verdict = chain.get("verdict")
    if verdict not in CHAIN_VERDICTS:
        raise AdoptionError(
            "链 verdict 未知: %r（三终态: %s — 空链/半链不是裁决）"
            % (verdict, "/".join(CHAIN_VERDICTS)))
    gates = chain.get("gates") or []
    if not gates:
        raise AdoptionError("链 gates 为空 ⇒ 不是有效裁决（拒绝迁移）")

    before = getattr(p, "state", "")
    after = (CHAIN_BLOCK_STATE if verdict in ("blocked", "error")
             else CHAIN_PASS_STATE)
    if not _valid_state(after):
        raise AdoptionError("目标 state %r 不在 evolver 五态内" % (after,))

    p.gate_verdict = {"chain": chain, "via": "adoption.apply_chain"}
    p.state = after
    return AdoptionRecord(
        proposal_id=str(p.proposal_id), chain_verdict=verdict,
        blocked=tuple(chain.get("blocked") or ()),
        not_applicable=tuple(chain.get("not_applicable") or ()),
        n_gates=len(gates), state_before=before or "draft",
        state_after=after)


def apply_chain_batch(proposals: Sequence[Any], chains: Sequence[Dict[str, Any]]
                      ) -> List[AdoptionRecord]:
    """★ 批量（长度须一致 — 错位配对比报错更危险, 显式拒）。"""
    if len(proposals) != len(chains):
        raise AdoptionError(
            "proposals(%d) 与 chains(%d) 长度不一致 ⇒ 拒绝整批（错位配对"
            "会把 A 的裁决写到 B 头上 — 比报错更危险）" % (len(proposals),
                                                      len(chains)))
    return [apply_chain(p, c) for p, c in zip(proposals, chains)]


ADOPTION_MECHANICS: Dict[str, str] = {
    "state_machine": "chain verdict → gated / rejected（evolver 五态内 — 不造新状态）",
    "two_layer_gates": "ProposalGate 静态五判据(构造期) + 门组链运行时六门(需候选) — 两层互补, 顺序不可换",
    "blocked_rejects": "链 verdict=blocked ⇒ rejected（不进入判分 — 链都没过 ΔS 归因会被污染）",
    "error_rejects": "链执行 error ⇒ rejected（失败≠通过 — G7 留痕）",
    "five_state": "gated 后由 evolver.accept 判 split ⇒ adopted_not_implemented（第五态落地不混）",
    "batch_alignment": "proposals/chains 长度须一致（错位配对显式拒 — 防 A 裁决写 B 头）",
}
