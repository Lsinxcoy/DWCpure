# -*- coding: utf-8 -*-
"""candidate_bridge · Candidate → 门组输入适配（V2 §5.4 候选环的入口面）。

定位声明 · **DWC-AUTO**（自我强化 · 判据 G1 定位门）
  ★ 补链: R152 门组入链已建, 但 run_term 是六层链（无候选流）⇒ 门①⑥
    常驻 not_applicable/blocked。本模块把**早已 live 的 Candidate**
    （candidates.py L57 — patch+grounding+component）投影成门组输入,
    让候选形态下六门全部拿到真对象。
  ★ 不抢位: 不生成候选（candidates.py 的 CandidateGenerator）· 不判分
    （judge）· 不采纳（evolver）; 本模块只做**投影**（G2: 不重算, 只转
    口径）。
  ★ 与 R152 的分工: R152 管 run_term 形态（无候选 ⇒ 三态如实）; 本模块
    管候选形态（Candidate 在场 ⇒ ①⑥ 可判）。两条路都保留 — 不是替代。

★★★ TRUTH_SOURCE（判据 G2）
  · diff 文本 ← Candidate.patch（逐字, 不改写）
  · edits ← (component, hunk) 展开（hunk 优先取 grounding 的 diff id,
    缺则退化到 patch 前 80 字符哨兵 — **显式退化标注**, 不假装精确）
  · vocabulary（门①词表）← 调用方给的评测词表（不是从 patch 猜）
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .gates import TermFacts, run_gates


class BridgeError(Exception):
    """投影期的显式拒绝（Candidate 无 patch / 无 component / 词表口径混用）。"""


def _hunk_of(cand: Any) -> str:
    """★ hunk 句柄: 优先 grounding 的 diff id（可归因到具体证据）;
    缺 ⇒ 退化到 patch 文本哨兵（前 80 字符 + '…'）—— 显式降级, 不假装。"""
    try:
        g = getattr(cand, "grounding", None) or []
        if g and isinstance(g[0], dict):
            for key in ("diff_id", "id", "task", "key"):
                v = g[0].get(key)
                if isinstance(v, str) and v:
                    return v
    except Exception:                                  # noqa: BLE001 — 降级不炸
        pass
    patch = str(getattr(cand, "patch", "") or "")
    if not patch:
        raise BridgeError("Candidate.patch 空 ⇒ 无可数 hunk（空候选不算候选）")
    return patch[:80] + "…"


def to_facts(cands: Sequence[Any], *, vocabulary: Tuple[str, ...] = (),
             pass_rate: Optional[float] = None,
             noise_band: Optional[float] = None,
             delta_s: Optional[float] = None,
             delta_c: Optional[float] = None,
             score_star: Optional[float] = None,
             nu_str: Optional[float] = None,
             domain_guard_ok: Optional[bool] = None,
             split_verdict: Optional[Dict[str, Any]] = None) -> TermFacts:
    """★ Candidate[] → TermFacts（门组输入 — 投影, 不重算）。"""
    from dwc.organs.budget import EditItem

    if not isinstance(cands, (list, tuple)):
        raise BridgeError("cands 须序列")
    if not cands:
        raise BridgeError("空候选列表 ⇒ 无可投影对象（没候选≠干净, 同上）")
    edits: List[EditItem] = []
    diffs: List[str] = []
    for c in cands:
        comp = getattr(c, "component", None)
        if not comp:
            raise BridgeError("Candidate.component 空 ⇒ EditItem 不可构造"
                              "（可归因性缺边, 与 budget 计数口径冲突）")
        edits.append(EditItem(comp, _hunk_of(c)))
        diffs.append(str(getattr(c, "patch", "") or ""))
    diff_text = "\n".join(diffs)
    return TermFacts(
        pass_rate=pass_rate, score_star=score_star, delta_s=delta_s,
        delta_c=delta_c, nu_str=nu_str, noise_band=noise_band,
        domain_guard_ok=domain_guard_ok,
        not_evaluated=0,                        # 候选环由 caller 给（本模块不知）
        candidate_diff=diff_text,
        vocabulary=tuple(vocabulary),
        edits=edits, split_verdict=split_verdict)


def run_candidate_gates(cands: Sequence[Any], *,
                        vocabulary: Tuple[str, ...] = (),
                        **kw: Any) -> Dict[str, Any]:
    """★ 一步: Candidate[] → 门组链（①③⑤⑥ 可判; ④ 候给 split_verdict 才判）。"""
    facts = to_facts(cands, vocabulary=vocabulary, **kw)
    out = run_gates(facts)
    out["bridge"] = {
        "n_candidates": len(cands),
        "n_edits": len(facts.edits or ()),
        "diff_chars": len(facts.candidate_diff or ""),
        "vocabulary_size": len(vocabulary),
        "note": "投影自 candidates.Candidate（patch/grounding 逐字 — 不重写）",
    }
    return out


BRIDGE_MECHANICS: Dict[str, str] = {
    "source": "Candidate[patch+component+grounding]（candidates.py — 早已 live）",
    "edits_derivation": "EditItem(component, hunk) — hunk 优先 grounding diff id; 缺 ⇒ patch 前 80 字符哨兵（显式降级）",
    "diff_text": "各 patch 逐字拼接（不改写原始文本 — G2 投影）",
    "vocabulary_external": "门①词表由调用方给（不从 patch 猜词 — 那是语义判断, 越权）",
    "role": "候选环入口: 让六门全部拿到真对象（R152 已覆盖无候选形态）",
    "not_replacing": "不替代 candidates.py 生成 / judge 判分 / evolver 采纳",
}
