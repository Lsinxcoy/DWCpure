# -*- coding: utf-8 -*-
"""landing · 采纳后自动落地（R163 — accept 判 adopted ⇒ applier 真落地）。

定位声明 · **DWC-AUTO**（自我强化 · 判据 G1 定位门）
  ★ 补最后一环: R156 pipeline 的采纳面把 state 迁到 gated 就停;
    evolver.accept 判 adopted_not_implemented（第五态）后也停 ⇒
    "判过"与"落地"之间断链。本模块是**分发器**: gated/adopted
    Proposal + judge evidence + applier ⇒ 真写进可写面。
  ★ 不抢位: 不判分（judge 的分）· 不生成（evolver 的分）· 落地原语
    全在 applier（commit/land_rule — R30-R33 四代打磨, 不重造）。
    本模块只做**四道闸 + 分派 + 留痕**。

★★★ 四道闸（缺一不可 — 顺序不可换）
  ① state ∈ {gated, adopted_not_implemented}  — 没过门的提案不许落
  ② p.gate_verdict 双报告在（R162: proposal_gate + six_gate_chain）
     — 裸 gated（无链结论）显式拒: 归因不可查的落地 = 黑箱落地
  ③ 按 target_layer 分派落地面（land_rule 带三闸 / commit 带读回）
  ④ 写完读回（applier 判据 1 — 不一致即 raise, 分发器不绕过）

★★★ state 终态裁决（不造第六态 — PROPOSAL_STATES 只有五态）
  · 落地成功 ⇒ "adopted"（R14 立的第五态反面: adopted_not_implemented
    = "过门未落地" ⇄ adopted = "过门且落地" — 第五态一直在等这一端）
  · 落地失败 ⇒ 保持 adopted_not_implemented/gated（**不退化到 rejected** —
    判决与落地是两回事: 门过了就是过了, 落地失败单记 LandingRecord）
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

#: 可落地的 state（闸①白名单 — 与 evolver.PROPOSAL_STATES 对齐）
_LANDABLE = ("gated", "adopted_not_implemented")

#: 分派面（target_layer ⇒ 落地方法 — 决策集中在此, 便于审计）
_RULE_LAYERS = ("assets",)          # 规则条目面走 land_rule（三闸）
# 其余（architecture / 未声明层）走 commit — 由 Target 的读写决定落点


class LandingError(Exception):
    """落地闸的显式拒绝（state 不合/双报告缺/evidence 缺）。"""


@dataclass(frozen=True)
class LandingRecord:
    """一次落地的留痕（进台账 — 可回放: 谁落的/落的哪/读回是什么）。"""

    proposal_id: str
    target_layer: str
    method: str                     # "land_rule" | "commit"
    readback_ok: bool
    evidence_ref: Optional[str] = None
    state_before: str = ""
    state_after: str = ""
    detail: Dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        return {"proposal_id": self.proposal_id,
                "target_layer": self.target_layer, "method": self.method,
                "readback_ok": self.readback_ok,
                "evidence_ref": self.evidence_ref,
                "state_before": self.state_before,
                "state_after": self.state_after,
                "detail": self.detail}


def _check_gates(p: Any) -> str:
    """闸①② — state 与双报告校验（显式拒, 不静默跳过）。"""
    st = getattr(p, "state", "")
    if st not in _LANDABLE:
        raise LandingError(
            "state=%r 不可落地（白名单 %s — draft/rejected 不许落）"
            % (st, "/".join(_LANDABLE)))
    gv = getattr(p, "gate_verdict", None)
    if not isinstance(gv, dict):
        raise LandingError(
            "gate_verdict 非 dict ⇒ 拒绝落地（归因不可查 = 黑箱落地）")
    # ★★ R163 实测接缝: gate_verdict 有**两种合法报告形态**（写方不同）:
    #   ① R162 evolver.gate_all: {"proposal_gate", "six_gate_chain", "layer2"}
    #      — 静态层①报告 + 运行时链层②报告（双报告）
    #   ② R154 adoption.apply_chain: {"chain": {...}, "via": ...}
    #      — 采纳面写的链报告（候选环形态 — 无 ProposalGate 静态层,
    #        因静态门未参与该路径）
    #   ⇒ 闸②收两种: 任一形态的**链结论在场**即算归因可查;
    #     拒的是"没有任何链结论"的裸 gated（那才是黑箱）
    has_chain = ("six_gate_chain" in gv) or ("chain" in gv)
    if not has_chain:
        raise LandingError(
            "gate_verdict 无链结论（six_gate_chain/chain 都缺）⇒ 拒绝落地"
            " — 归因不可查的落地 = 黑箱落地（链结论必须可读）")
    return st


def land(p: Any, applier: Any, evidence: Dict[str, Any], *,
         target: Optional[Any] = None,
         rule_key: Optional[str] = None,
         rule_entry: Optional[Dict[str, Any]] = None,
         check_fn: Optional[Any] = None) -> LandingRecord:
    """★ 落一个提案（四道闸 + 分派 + state 迁移到 adopted）。

    ★ target: applier.Target（可写面 — 调用方构造, 持 getter/setter/flush）;
      rule_key/rule_entry/check_fn: land_rule 三件的注入（evolver 的
      schema 校 + judge evidence 形状校由 applier 三闸执行）。
    ★ 分派决策: target_layer ∈ _RULE_LAYERS ⇒ land_rule; 否则 commit。
    """
    st_before = _check_gates(p)                      # 闸①②
    if not isinstance(evidence, dict) or "success" not in evidence:
        raise LandingError(
            "evidence 缺 'success' 键 ⇒ 拒落（『引用成功判定』不可省 — "
            "没验证不许固化, applier 闸②同族）")
    if target is None:
        raise LandingError("target 缺 ⇒ 无可写面（不猜落到哪）")

    layer = str(getattr(p, "target_layer", "") or "")
    detail: Dict[str, Any] = {}
    if layer in _RULE_LAYERS and rule_key and rule_entry is not None:
        # 规则面: land_rule（schema/evidence/读回三闸 — applier 内建）
        res = applier.land_rule(target, rule_key, rule_entry, evidence,
                                check_fn=check_fn)
        method = "land_rule"
        detail = {"rule_key": rule_key,
                  "applied": res.to_dict() if hasattr(res, "to_dict")
                            else str(res)}
    else:
        # 通用面: commit（读回校验 — applier 判据 1 硬保证: commit action
        # 的 readback_ok=False 在 AppliedResult.__post_init__ 就 raise）
        res = applier.commit(p.proposal_id, target, p.patch)
        method = "commit"
        detail = {"patch_preview": str(p.patch)[:80],
                  "applied": res.to_dict() if hasattr(res, "to_dict")
                             else str(res)}
    # ── 闸④: 读回校验 ──
    # ★ applier 已在 AppliedResult 构造期对 commit/rollback 硬 raise
    #   （readback_ok=False 不许记）⇒ 到这里 res 存在即读回已过; 分发器
    #   做存在性确认 + 显式字段核对（双重保险, 不信单一来源）
    rb = getattr(res, "readback_ok", None)
    if rb is not True:
        raise LandingError(
            "读回校验字段非常量 True ⇒ 拒认落地成功（%s — 不返回'部分"
            "成功'）" % method)

    # ★ state 终态: adopted（第五态反面 — 不造第六态; 落地失败不退化 rejected）
    p.state = "adopted"
    return LandingRecord(
        proposal_id=str(p.proposal_id), target_layer=layer, method=method,
        readback_ok=True, evidence_ref=str(evidence.get("reason", ""))[:80],
        state_before=st_before, state_after="adopted", detail=detail)


def land_batch(items: List[Tuple[Any, Dict[str, Any]]], applier: Any, **kw: Any
               ) -> List[LandingRecord]:
    """★ 批量（单条失败 raise — 不跳过错的那条: 黑箱跳过比炸严重）。"""
    out = []
    for p, ev in items:
        out.append(land(p, applier, ev, **kw))
    return out


LANDING_MECHANICS: Dict[str, str] = {
    "four_gates": "①state 白名单 ②双报告在 ③按层分派 ④读回校验（缺一不可）",
    "state_terminal": "落成 ⇒ adopted（第五态反面 — 不造第六态）; 落地失败保持 gated（判决与落地分离）",
    "no_regression": "落地失败**不**退化 rejected — 门过了就是过了, 落地单记 record",
    "dispatch": "assets/规则面 ⇒ land_rule(schema+evidence+读回三闸); 其余 ⇒ commit(读回)",
    "not_judge": "evidence 由 caller 给（judge 的判定引用 — 本模块只校形状与读回, 不重判）",
    "gate_verdict_schemas": "两种合法报告形态: R162 gate_all 双报告（proposal_gate+six_gate_chain）/ R154 adoption 链报告（chain+via）— 闸②收两种, 拒的是无链结论的裸 gated",
}
