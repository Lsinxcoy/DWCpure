"""vocabulary · 词表单一真源（R193 债 X4 — 收口, 不是新造）。

定位声明 · **DWC-AUTO**（自我强化 · 判据 G1 定位门）
  ★ 只放**常量**与**纯查询**, 不判分不写盘。

★★★ TRUTH_SOURCE（判据 G2）
  本模块的值全部转抄自既有真源, **不新增也不改动一个词**:
    𝒦(9)        ← docs/COMPONENT_VOCABULARY.md §2.1 + papers_txt/2609.24972.txt 式12
    𝒦_meta(5)   ← docs/COMPONENT_VOCABULARY.md §2.2（每项 editable 明标）
    𝒦_meta_readonly(2) ← 同节 K3（evaluator/external_source 必须 editable:False）

★★★ 为什么收口（R193 债 X4 — 诚实记账）
  R189 对账判 vocab "未收口" — 半对半错:
    · **半对**: evolver.py 里确实两张并列表（COMPONENT_VOCAB / K_META）, 外层文档
      docs/COMPONENT_VOCABULARY.md 是唯一汇总面 ⇒ 代码层没有单一入口。
    · **半错**: R189 把 `organs/dimension.py` 的九维 D1-D9 也算词表散点 — **那是
      误认**。DIMENSIONS 是**模块声明维度**（ModuleDeclaration / declares_valid_hook
      / find_conflicts）, 与 RRSI 𝒦 组件词表**不同物** ⇒ 收口**不并入**它
      （并进去 = 把两种不同语义混成一张表, 那是本次修的副作用）。
  ★ 收口后的唯一性验收: evolver.py 不再自持常量; 全部 `from
    dwc.foundation.vocabulary import ...`。测试锁 `evolver.COMPONENT_VOCAB is
    vocabulary.COMPONENT_VOCAB`（同一对象, 不是相等值）。
"""

from __future__ import annotations

#: ★★ 𝒦 · 组件层词表 9 项（RRSI 2609.24972 式 12 逐字 — 值一字不动）
#:   转抄自 evolver.py 原 frozenset 字面量（R193 收口, 未增删改）
COMPONENT_VOCAB: frozenset[str] = frozenset({
    "prompt", "control_flow", "config", "output_plumbing",
    "context_mgmt", "client_tool", "skill", "memory", "subagent",
})

#: ★★ 结构型组件（式 15: 取新颖度奖励 ν_str — 转抄值不变）
STRUCTURAL: frozenset[str] = frozenset(
    {"client_tool", "skill", "memory", "subagent"})

#: ★★★ 𝒦_meta · 系统层 5 项（每项 editable 明标 — K4: 必填无默认）
#:   转抄自 evolver.py 原 dict 字面量（R193 收口, 未增删改）
K_META: dict[str, bool] = {
    # name → editable（**K4: 必填无默认** —— 每项都要明写）
    "code": True,           # §3.1 可编辑，但 ν_t=0（不给新颖度奖励）
    "architecture": True,   # §3.2 可编辑，但**须人工批准**（G3 人类主权）
    "meta_evolution": True,  # §3.3 定义性组件（m 改 m ⇒ 递归闭合在 m）
    "evaluator": False,     # §3.4 ★ 不可编辑（G10 密封 + grounded 第二条件）
    "external_source": False,  # §3.5 只读登记（须 provenance）
}

#: ★★ K3 · 两项必须 editable: False（机械可查 — "在表里但禁止" ≠ "不在表里"）
K_META_READONLY: tuple[str, ...] = ("evaluator", "external_source")


def is_component(name: str) -> bool:
    """name ∈ 𝒦 ∪ 𝒦_meta（越界 ⇒ False — 调用方自行决定拒/记）。

    ★★★ A1 纪律（R37 实测三处不同源后的收敛）: 「component ∈ 词表」的判定
      **只许一个入口** = `evolver.check_component`。本函数是它的薄包装
      （**不在本文件另写 直接判词表** — R193 收口时第一版正是在
      这里又造了一个判据来源, 被 test_a1 当场逮住 ⇒ 改为 import 真源,
      函数内 import 避开 foundation→organs 的循环依赖）。
    """
    from dwc.organs.evolver import check_component  # A1 唯一入口
    return not check_component(name)                   # 空 list = 合法


def is_structural(name: str) -> bool:
    """name ∈ 结构型子集（ν_str 奖励面）。

    ★ A1 边界: 本函数查的是 STRUCTURAL 常量（不是"component 合法性"判据）
      ⇒ 不在 A1 收敛面内（A1 管的是 𝒦∪𝒦_meta 归属判定）。如实标注,
      不借"收口"之名把别的判据也吞进来。
    """
    return name in STRUCTURAL


def k_meta_editable(name: str) -> bool:
    """系统层项是否可编辑（**未知名 ⇒ False — 保守, 不放任**）。

    ★ 为什么未知名不是 raise: 本函数是查询面, 拒绝未知是调用方的纪律
      （R73: 不做无据发明 — 未知名不进表, 自然不可编辑）。
    """
    return bool(K_META.get(name, False))
