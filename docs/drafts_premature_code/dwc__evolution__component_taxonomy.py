# -*- coding: utf-8 -*-
"""DWC-AUTO · 组件词表 𝒦 —— 对齐 RRSI (arXiv:2609.24972) 式 12/15。

## 论文原文（取证，非推断）

RRSI §3.2 式 12 给出"可编辑组件词表"：

    𝒦 = { prompt, control_flow, config, output_plumbing,
          context_mgmt, client_tool, skill, memory, subagent }

式 15 再分出"结构型组件"一档：

    𝒦_str = { client_tool, skill, memory, subagent }

## 为什么需要这张表

RRSI 的**剪枝**与**信用分配**都以组件为单位。论文式 11 的派生量
`g_t(ℓ) = max{ΔS_i : ℓ_i = ℓ, t − t_i ≤ n_prune}` 以 ℓ 为键；
没有词表，两者都无从计算。

论文原文（关于 `𝒦_str` 的用途）：
    "novelty only for structural components"
    —— 新颖度奖励 ν_str 只对结构型组件发放。

## 本模块的边界

纯常量 + 纯函数，零状态、零随机、零时钟。**不实现**剪枝与信用分配
（那是 evolver 的职责），只提供它们共同依赖的词表与查询。
"""
from __future__ import annotations

# ── 式 12：可编辑组件词表（逐字对齐论文） ──────────────────────────
COMPONENT_VOCAB = frozenset({
    "prompt",
    "control_flow",
    "config",
    "output_plumbing",
    "context_mgmt",
    "client_tool",
    "skill",
    "memory",
    "subagent",
})

# ── 式 15：结构型组件（取新颖度奖励 ν_str 的那一档） ────────────────
STRUCTURAL_COMPONENTS = frozenset({
    "client_tool",
    "skill",
    "memory",
    "subagent",
})

__all__ = [
    "COMPONENT_VOCAB",
    "STRUCTURAL_COMPONENTS",
    "is_known_component",
    "is_structural",
    "unknown_components",
    "structural_novelty",
]


def is_known_component(name: str) -> bool:
    """该组件名是否在 𝒦 内。非字符串一律 False（不抛）。"""
    return isinstance(name, str) and name in COMPONENT_VOCAB


def is_structural(name: str) -> bool:
    """该组件是否属 𝒦_str（结构型）。非字符串一律 False。"""
    return isinstance(name, str) and name in STRUCTURAL_COMPONENTS


def unknown_components(names) -> list[str]:
    """返回不在 𝒦 内的组件名（去重、字典序）。

    调用方用它做**准入前置检查**：任何编辑若标注了 𝒦 外的组件，
    后续的剪枝与信用分配都无法计算，必须在提案阶段就拒。
    """
    if not names:
        return []
    out = set()
    for n in names:
        if not is_known_component(n):
            out.add(repr(n))
    return sorted(out)


def structural_novelty(components, accepted_counts: dict) -> int:
    """ν_str —— 结构型组件里"从未在获胜编辑中出现过"的个数。

    对齐 RRSI 式 15 与 accept.py 的 `structural_novelty` 语义：
    只有结构型组件计入，且只在 accepted_counts[c] == 0 时计数。

    Args:
        components: 本次候选涉及的组件名（可含重复、可含未知名）
        accepted_counts: {组件名: 历史获胜次数}；缺键按 0 处理
    """
    if not components:
        return 0
    if not isinstance(accepted_counts, dict):
        accepted_counts = {}
    seen = set()
    for c in components:
        if not is_structural(c):
            continue
        if int(accepted_counts.get(c, 0) or 0) == 0:
            seen.add(c)
    return len(seen)
