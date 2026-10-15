# -*- coding: utf-8 -*-
"""credit · 证据感知信用分配 ℒ_t（2609.24972 §3.3 正则器(2) · V2 L244）。

定位声明 · **DWC-AUTO**（自我强化 · 判据 G1 定位门）
  ★ 服务进化环的**归因面**: 每轮把候选的编辑 i、层级 ℓ_i、hunk h_i、
    维度 d_i、收益 ΔS_i、成本 ΔC_i、以及**采纳标志 a_i** 记成一笔 ——
    后续按 a_i 加权时, "赢家编辑"和"陪跑编辑"不会被混同。
  ★★ a_i 判据（原文, 逐字语义）:
      a_i = 1 当且仅当携带编辑 i 的**候选成为该轮赢家**（采纳/落地）;
      a_i = 0 当且仅当"通过了所有门但输给更高分候选"（**admissible
        but lost** —— 这不是失败, 是公平竞争后的归位, 原文显式要记）。
  ★ 不抢位: 不判谁赢（judge/evolver.accept 的分）· 不推进议程状态
    （budget.py 的 b_t）; 本模块只**记账**（append-only 台账）。
  ★ 与 budget.py 的关系: 那边管"本轮允许几处编辑"（proposer 侧约束）,
    这边管"每处编辑最终归了多少因"（评估侧留痕）—— 同一正则器族的
    两半, 不可互替。

★★★ TRUTH_SOURCE（判据 G2）
  · ΔS_i/ΔC_i ← 调用方从 judge/evolver 的已判读数抄录（本模块不重算）;
  · a_i ← 调用方给裁决结果（winner 与否 — 判定权在 evolver/judge）;
  · 台账只增不改（epoch_ledger 铁律同款 — 事后改账=销毁证据）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

#: 台账字段（原文 ℒ_t 七元组 — 值枚举, 顺序即契约）
LEDGER_FIELDS: Tuple[str, ...] = ("t", "edit", "layer", "hunk", "dimension",
                                  "delta_s", "delta_c", "adopted")

#: a_i 枚举（原文二元 — 不给 0.5/None 的"待定"混入加权计算)
A_WINNER = 1
A_LOST = 0

#: 认可的 a_i 字面来源（调用方给的原因串 — 留痕, 不是枚举约束）
A_CAUSES: Tuple[str, ...] = ("winner", "admissible_but_lost", "rejected_gate",
                             "blocked_gate")


class CreditError(Exception):
    """台账契约的显式拒绝（a_i 非 0/1 / ΔS-ΔC 非数值 / t 倒退）。"""


@dataclass(frozen=True)
class CreditEntry:
    """一笔 ℒ_t 记录（七字段 — frozen ⇒ 事后不可改, 只可追加）。"""

    t: int                       # 轮次（议程坐标 — 与 budget.schedule 同源）
    edit: str                    # 编辑 id（可归因锚点 — 空即拒）
    layer: str                   # 组件层（assets / architecture / …）
    hunk: str                    # hunk 句柄（grounding id 或哨兵 — R153 口径）
    dimension: str               # 九维 D1..D9
    delta_s: float               # 该编辑的收益归属（调用方抄录 — 本模块不算）
    delta_c: float               # 该编辑的成本归属
    adopted: int                 # a_i ∈ {0, 1}（赢家=1; 陪跑=0）

    def __post_init__(self) -> None:
        if isinstance(self.t, bool) or not isinstance(self.t, int) or self.t < 0:
            raise CreditError("t 须 ≥0 整数, 实 %r" % (self.t,))
        for name in ("edit", "layer", "hunk", "dimension"):
            if not isinstance(getattr(self, name), str) or not getattr(self, name):
                raise CreditError("%s 须非空串（可归因性缺边 ⇒ 拒）" % (name,))
        for name in ("delta_s", "delta_c"):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                raise CreditError("%s 须数值, 实 %r" % (name, v))
        if self.adopted not in (0, 1):
            raise CreditError(
                "a_i 须 ∈ {0,1}（winner=1; admissible_but_lost=0 —"
                " 不许 0.5/None 的\"待定\"混入加权计算）, 实 %r" % (self.adopted,))

    def as_dict(self) -> Dict[str, Any]:
        return {"t": self.t, "edit": self.edit, "layer": self.layer,
                "hunk": self.hunk, "dimension": self.dimension,
                "delta_s": self.delta_s, "delta_c": self.delta_c,
                "adopted": self.adopted}


class CreditLedger:
    """★ 证据感知信用台账（append-only — 只增不改/不删）。"""

    def __init__(self) -> None:
        self._entries: List[CreditEntry] = []
        self._flushed = 0          # ★ R289 · 已落盘笔数（只追加新增的游标）

    def record(self, e: CreditEntry) -> None:
        """★ 追加一笔（不许覆盖/中途改写 — 事后改账=销毁证据）。"""
        if not isinstance(e, CreditEntry):
            raise CreditError("只收 CreditEntry, 实 %r"
                              % (type(e).__name__,))
        self._entries.append(e)

    def record_round(self, t: int,
                     entries: Sequence[Dict[str, Any]]) -> List[CreditEntry]:
        """★ 批量录一轮（每笔独立校验 — 一笔坏不拖垮整轮, 但坏的显式炸）。"""
        out = []
        for raw in entries:
            try:
                e = CreditEntry(t=t, **raw)
            except TypeError as exc:
                raise CreditError("字段名不符 ℒ_t 七元组: %s" % (exc,))
            self.record(e)
            out.append(e)
        return out

    def entries(self) -> List[CreditEntry]:
        return list(self._entries)               # 副本 — 外部无法改内部

    def flush(self, path: str) -> int:
        """★ R289 · 落盘：只追加新增（append-only 物理保证）。

        返回本次追加笔数；无新增 ⇒ 0 且不碰文件（无账不假装有）。
        文件坏/写不动 ⇒ 抛（调用方隔离 —— 台账语义不许静默丢账）。
        """
        new = self._entries[self._flushed:]
        if not new:
            return 0
        import io
        import json as _json
        with io.open(path, "a", encoding="utf-8") as f:
            for e in new:
                f.write(_json.dumps(e.as_dict(), ensure_ascii=False) + "\n")
        self._flushed = len(self._entries)
        return len(new)

    def load(self, path: str) -> int:
        """★ R289 · 启动载回：文件缺席 ⇒ 0 不炸（首轮无文件是常态）。

        坏行 ⇒ 大声炸（账坏了不停就是销毁证据 —— 宁可停）。
        载回的笔视为已落盘（游标同步 —— 不翻倍追加）。
        """
        import io
        import json as _json
        import os as _os
        if not _os.path.exists(path):
            return 0
        n = 0
        with io.open(path, encoding="utf-8") as f:
            for i, line in enumerate(f):
                line = line.strip()
                if not line:
                    continue
                try:
                    raw = _json.loads(line)
                except ValueError as exc:
                    raise CreditError(
                        "credit 台账第 %d 行坏账（停 —— 不静默跳过）: %s"
                        % (i + 1, exc))
                # ★ R289-补 · 兼容 R276-③ 信封格式 {round, task, entry:{七元组}}
                #   （Loop._persist_credit 写的旧账 —— 同文件两写盘路径，
                #   读侧兼容，写侧统一七元组平铺。新账一律平铺。）
                if isinstance(raw, dict) and "entry" in raw \
                        and isinstance(raw["entry"], dict):
                    raw = raw["entry"]
                try:
                    e = CreditEntry(**{k: raw[k] for k in LEDGER_FIELDS})
                except Exception as exc:      # KeyError/TypeError/CreditError
                    raise CreditError(
                        "credit 台账第 %d 行字段不符七元组/契约（停）: %s"
                        % (i + 1, exc))
                self._entries.append(e)     # 构造期载回 — 非事后改账
                n += 1
        self._flushed = len(self._entries)
        return n

    def summary(self) -> Dict[str, Any]:
        """★ 聚合面: 按维度/层的 a_i 加权与输赢计数（归因体检）。"""
        n = len(self._entries)
        if n == 0:
            return {"n": 0, "note": "空台账 — 缺席≠0（没记≠没发生, 只是没测）"}
        by: Dict[str, Dict[str, Any]] = {}
        for e in self._entries:
            for key_name, key in (("dimension", e.dimension), ("layer", e.layer)):
                slot = by.setdefault(key_name, {}).setdefault(
                    key, {"n": 0, "n_winner": 0, "sum_ds": 0.0, "sum_dc": 0.0})
                slot["n"] += 1
                slot["n_winner"] += e.adopted
                slot["sum_ds"] += e.delta_s
                slot["sum_dc"] += e.delta_c
        n_winner = sum(e.adopted for e in self._entries)
        return {"n": n, "n_winner": n_winner, "n_lost": n - n_winner,
                "winner_rate": n_winner / n,
                "sum_ds": sum(e.delta_s for e in self._entries),
                "sum_dc": sum(e.delta_c for e in self._entries),
                "by_dimension": by.get("dimension", {}),
                "by_layer": by.get("layer", {}),
                "rounds": sorted({e.t for e in self._entries})}


def adopted_flag(is_winner: bool, cause: str = "winner") -> int:
    """★ 裁决 → a_i（winner=1; 其余=0 — cause 只留痕不进加权）。"""
    if not isinstance(is_winner, bool):
        raise CreditError("is_winner 须 bool（不接受 None=待定 — 0/1 二元纪律）")
    if not cause:
        raise CreditError("cause 非空（a_i=0 也要可归因 — 陪跑不是没原因）")
    return A_WINNER if is_winner else A_LOST


CREDIT_MECHANICS: Dict[str, str] = {
    "ledger_fields": "ℒ_t 七元组: (t_i, ℓ_i, h_i, d_i, ΔS_i, ΔC_i, a_i)",
    "a_i_rule": "a_i=1 ⟺ 携带编辑 i 的候选成为该轮赢家; a_i=0 = admissible but lost（过全门但输给更高分 — 原文显式要记）",
    "binary_only": "a_i 只 0/1 — 不许 0.5/None 待定混入加权（归因可算性优先）",
    "append_only": "台账只增不改（epoch_ledger 铁律同款 — 事后改账=销毁证据）",
    "not_judge": "ΔS/ΔC 由调用方抄录已判读数; a_i 由调用方给裁决 — 本模块不重算不判赢",
    "vs_budget": "budget 管本轮允许多少编辑(proposer 侧); credit 管每处编辑归多少因(评估侧) — 同正则器族两半",
}
