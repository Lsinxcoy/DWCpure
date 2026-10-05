# -*- coding: utf-8 -*-
"""DWC-AUTO · 改进器 m —— GAI (arXiv:2609.13406) 五元组里的 modifier。

## 论文依据（取证）

GAI Definition 1 (System and Agent) 原文把系统定义为五元组：

    χ = (π, V, m, U, ρ)

其中：

    m : X → Δ(X_Ag)   **提议系统应该如何改变** (propose how the system should change)
    U : X → ℝ         **评估提议的改动是否服务于 G** (critic of the proposal)

GAI Figure 2 的关键结构约束原文：
    环上**恰好一条 authority boundary**（exactly one authority boundary）。

本模块实现 **m**（提议侧）。裁决侧是 U（见 `modification_critic.py`）。
**两者必须分离** —— GAI Remark/§2.3 的 authority boundary 要求
"模型提议、确定性代码裁决"；若同一模块既提议又裁决，环上就会出现
第二条 authority boundary，退化为自确认循环。

## 本模块的机制来源

m 的**形态**来自 GAI（提议者）；
m 的**约束**来自 RRSI (arXiv:2609.24972) §3.2 的三个正则器：

    (1) L₀-Style Annealed Update Sparsity —— 退火编辑预算 b_t
        式 4: b_t = ⌈ b_min + (b_max − b_min) · ½(1 + cos(π t / T)) ⌉
        论文: "不约束的 proposer 会把很多互不相关的修改捆成一个候选…
              any measured change is difficult to attribute to a particular mechanism"

    (3) Structured Exploration —— 停滞时把配额留给"从未被测量过的组件"
        式 13: σ_t = 1[Ŝ_t − Ŝ_{t−w} ≤ δ]

## 本模块**不**做什么

- 不裁决（那是 U 的职责，见 authority boundary）
- 不落地（那是 applier 的职责）
- 不评估候选好坏（只产生候选）

## 诚实边界

本模块是**提议侧的约束层**，不是"能自己发明改动的 LLM"。
真正的改动内容由调用方注入的 `proposer` 回调产生；
本模块负责的是**过滤与配额**：把任意 proposer 的输出约束到
「≤ b_t 个可独立归因的原子编辑、组件名必须在 𝒦 内」。
"""
from __future__ import annotations

import math

from .component_taxonomy import COMPONENT_VOCAB, unknown_components

__all__ = [
    "annealed_budget",
    "stall_detected",
    "Edit",
    "Proposal",
    "ProposalRejected",
    "make_proposal",
    "structured_quota",
]


# ─────────────────────────────────────────── RRSI 式 4：退火编辑预算

def annealed_budget(t: int, T: int, b_min: int = 1, b_max: int = 8) -> int:
    """RRSI 式 4 —— 第 t 轮（共 T 轮）允许的原子编辑数上限。

        b_t = ⌈ b_min + (b_max − b_min) · ½(1 + cos(π t / T)) ⌉

    t=0 ⇒ b_t = b_max（最宽松）；t=T ⇒ b_t = b_min。
    论文三个 instance 全是 `b_min = 1` —— **最后一轮只允许一个
    可独立归因的编辑**。

    退化处理（不抛）：
      T <= 0        ⇒ 返回 b_min（无退火可言，取最严）
      t < 0         ⇒ 按 t = 0
      t > T         ⇒ 按 t = T
      b_min > b_max ⇒ 交换（保证 b_min <= b_max）
    """
    b_min = int(b_min)
    b_max = int(b_max)
    if b_min > b_max:
        b_min, b_max = b_max, b_min
    if b_min < 0:
        b_min = 0
    if T <= 0:
        return b_min
    t = max(0, min(int(t), int(T)))
    frac = 0.5 * (1.0 + math.cos(math.pi * t / T))
    return int(math.ceil(b_min + (b_max - b_min) * frac))


# ─────────────────────────────────────────── RRSI 式 13：停滞检测

def stall_detected(score_history, w: int = 3, delta: float = 0.01) -> bool:
    """RRSI 式 13 —— σ_t = 1[Ŝ_t − Ŝ_{t−w} ≤ δ]。

    用"最近 w 轮的分数没有超过 δ 的改善"判定停滞。
    历史不足 w+1 条 ⇒ False（不够证据判停滞，不臆测）。
    """
    if not score_history:
        return False
    try:
        h = [float(x) for x in score_history if x is not None]
    except (TypeError, ValueError):
        return False
    w = int(w)
    if w <= 0 or len(h) < w + 1:
        return False
    return (h[-1] - h[-1 - w]) <= float(delta)


# ─────────────────────────────────────────── 数据结构

class Edit:
    """一个**原子编辑** —— 对齐 RRSI 的原子编辑池 E_t 元素。

    字段对齐 RRSI 式 10 的信用分配台账：
        (t_i, ℓ_i, h_i, d_i, ΔS_i, ΔC_i, a_i)
    本类承载其中的**输入侧**三件：ℓ_i(component) / h_i(hypothesis) / d_i(diff)。
    ΔS/ΔC/a 是**事后**由 U 与 applier 填的，不在本类。
    """

    __slots__ = ("component", "hypothesis", "diff")

    def __init__(self, component: str, hypothesis: str = "", diff: str = ""):
        self.component = component
        self.hypothesis = hypothesis
        self.diff = diff

    def to_dict(self) -> dict:
        return {"component": self.component,
                "hypothesis": self.hypothesis,
                "diff": self.diff}

    def __repr__(self) -> str:
        return "Edit(%r, %r)" % (self.component, self.hypothesis[:24])


class Proposal:
    """一次提案 = 一组原子编辑（≤ b_t 个）。"""

    __slots__ = ("edits", "budget", "round", "note")

    def __init__(self, edits, budget: int, round_: int = 0, note: str = ""):
        self.edits = list(edits)
        self.budget = int(budget)
        self.round = int(round_)
        self.note = note

    @property
    def components(self) -> list[str]:
        return [e.component for e in self.edits]

    def to_dict(self) -> dict:
        return {"round": self.round, "budget": self.budget,
                "n_edits": len(self.edits), "note": self.note,
                "edits": [e.to_dict() for e in self.edits]}

    def __repr__(self) -> str:
        return "Proposal(round=%d, %d edits ≤ b=%d)" % (
            self.round, len(self.edits), self.budget)


class ProposalRejected(Exception):
    """提案被约束层拒绝。

    **不是**"坏提案"——是"不合规的提案"（超预算 / 组件名不在 𝒦）。
    拒绝必须显式抛出，不得静默丢弃（否则提议侧的问题永远看不见）。
    """


# ─────────────────────────────────────────── 约束层：把任意输出收进预算

def make_proposal(edits, round_: int, T: int, b_min: int = 1, b_max: int = 8,
                  reject_on_overflow: bool = True) -> Proposal:
    """把 `edits` 约束成一个合规 Proposal。

    规则（全部来自 RRSI，非本模块发明）：
      ① 组件名必须在 𝒦 内（式 12）—— 否则后续剪枝/信用分配无法计算
      ② 编辑数 ≤ b_t（式 4）
      ③ 每个编辑必须自带 component（无组件 = 无法归因）

    Args:
        edits: Edit 列表，或 [(component, hypothesis, diff), ...]
        round_: 当前轮次 t
        T: 总轮次
        reject_on_overflow: True ⇒ 超预算抛 ProposalRejected；
                            False ⇒ 截断到 b_t（并记 note）

    Returns:
        Proposal

    Raises:
        ProposalRejected: 组件名不在 𝒦 内，或（reject_on_overflow 时）超预算
    """
    b = annealed_budget(round_, T, b_min, b_max)

    norm: list[Edit] = []
    for e in (edits or []):
        if isinstance(e, Edit):
            norm.append(e)
        elif isinstance(e, (tuple, list)) and e:
            comp = e[0]
            hyp = e[1] if len(e) > 1 else ""
            dif = e[2] if len(e) > 2 else ""
            norm.append(Edit(comp, hyp, dif))
        else:
            raise ProposalRejected("无法识别的编辑元素: %r" % (e,))

    # ① 组件名准入
    bad = unknown_components([e.component for e in norm])
    if bad:
        raise ProposalRejected(
            "组件名不在 RRSI 词表 𝒦 内: %s (𝒦=%s)"
            % (", ".join(bad), sorted(COMPONENT_VOCAB)))

    # ② 预算
    note = ""
    if len(norm) > b:
        if reject_on_overflow:
            raise ProposalRejected(
                "超退火预算: %d 个编辑 > b_%d=%d"
                % (len(norm), round_, b))
        note = "截断 %d→%d (超预算)" % (len(norm), b)
        norm = norm[:b]

    return Proposal(norm, b, round_, note)


def structured_quota(all_components, measured_components, n_slots: int,
                     stalled: bool) -> list[str]:
    """RRSI §3.2(3) 结构化探索 —— 停滞时给"从未被测量过的组件"留配额。

    论文原文：
        "停滞时，把一小部分提案配额留给本轮运行中从未被测量过的组件。"

    实现：`stalled=False` ⇒ 返回空（不做干预）；
          `stalled=True`  ⇒ 从 𝒦 中选出未测组件，最多 n_slots 个。

    返回的是**建议优先探索的组件名**（字典序，确定性），
    调用方把它喂给自己的 proposer；本函数不产生编辑。
    """
    if not stalled:
        return []
    n_slots = int(n_slots)
    if n_slots <= 0:
        return []
    measured = set()
    for c in (measured_components or []):
        if isinstance(c, str):
            measured.add(c)
    pool = set()
    for c in (all_components or COMPONENT_VOCAB):
        if isinstance(c, str) and c in COMPONENT_VOCAB:
            pool.add(c)
    unmeasured = sorted(pool - measured)
    return unmeasured[:n_slots]
