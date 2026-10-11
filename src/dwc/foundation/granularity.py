# -*- coding: utf-8 -*-
"""granularity · 干预粒度的三层记账面（R195 · 债 Y2 — **收口, 不是新造**）。

定位声明 · **DWC-AUTO**（自我强化 · 判据 G1 定位门）
  ★ 只读字段 + 纯查询; **零常量、零新判据、零缓存**（不碰判据面）。

★★★ TRUTH_SOURCE（判据 G2）
  本模块不判分、不自造类别 — 它只回答"这个干预在哪一层"。

★★★ 为什么这是收口而不是新组件（R189 误判第二次修正）
  R189 对账判 granularity ABSENT, 依据是 `(def|class)(Granularit|turn_boundary)`
  0 hits。实测: **三层一直在场**, 只是散在 Proposal 的字段里（没有叫
  granularity 的函数而已）:
      L1 = Proposal.direction（R78 加, ensure_direction 校验; R188 补控制器）
      L2 = Proposal.component + Proposal.target_layer
           （𝒦9∪𝒦_meta5 经 A1 唯一入口 check_component; 层经 layer_of — R38 逐项）
      L3 = Proposal.target + Proposal.patch（约束 4: 一处干预）
  ⇒⇒ R189 的 grep **第二次**栽在"用函数名猜实现"（前一次 gdi/split）。
     本模块的正确形态 = 给已有三层**一个查询入口**, 不是造第二真源。

★★★ 与 Astar 2608.27287 三级 taxonomy 的映射（论文给名字, DWC 已有字段）
  论文 §2.2.1 逐字:
      (Level-1) Coarse-Grained Direction
      (Level-2) Fine-Grained Modification Action
      (Level-3) Concrete Modification Plan
  DWC 映射（逐层同构 — 已在本文件 tests 里锁死）:
      L1_direction     ← Proposal.direction            （方向）
      L2_component     ← component + target_layer      （组件/层）
      L3_intervention  ← target + patch 摘要           （具体干预点）

★★★ 诚实边界（论文没给的, DWC 不虚构）
  Astar 全文**未列完整类别表**（只给一个 MoE 改造实例）⇒ 本模块只做
  "已有字段的三层记账", **不发明类别枚举**; 类别表若将来要, 须用户裁决
  或论文补 —— R73 无据不发明。
"""

from __future__ import annotations

from typing import Any, Tuple

#: 三层的全序（coarse → fine）— 用于"哪个更粗"的比较, **不碰选优**
GRANULARITY_LEVELS: Tuple[str, ...] = (
    "L1_direction", "L2_component", "L3_intervention")

#: L3 记账时 patch 的摘要长度（记"改哪", 不记全文 — 防账本膨胀）
_PATCH_SUMMARY_CHARS = 24


def granularity_of(proposal: Any) -> Tuple[str, str, str]:
    """proposal ⇒ (L1, L2, L3) 三层记账（只读字段, 不重算）。

    ★ L1 未声明 ⇒ **"undeclared"**（不是 None — R188「None 不是第四方向」
      同族: 未声明是一等输出, 不许拿空值糊弄）。
    ★ L2 拿不到层（component 不在两表内）⇒ 由 `layer_of` 显式 raise
      （调用方自行决定拦/记 — 本模块不吞错误, G7 同族）。
    ★ L3 = target@patch摘要（摘要截断; patch 空 ⇒ 只记 target）。
    """
    d = getattr(proposal, "direction", None)
    l1 = "undeclared" if d is None else str(d)
    comp = str(getattr(proposal, "component", "") or "")
    layer = ""
    if comp:
        from dwc.organs.evolver import layer_of      # A1 族: 层的唯一入口
        layer = layer_of(comp)
    l2 = "%s:%s" % (comp or "undeclared", layer or "unassigned")
    target = str(getattr(proposal, "target", "") or "")
    patch = str(getattr(proposal, "patch", "") or "")
    l3 = target + ("@" + patch[:_PATCH_SUMMARY_CHARS] if patch else "")
    return (l1, l2, l3)


def level_of(name: str) -> int:
    """层名 ⇒ 序号 0/1/2（L1_direction=0 最粗）— 未知 ⇒ raise（不猜）。"""
    try:
        return GRANULARITY_LEVELS.index(name)
    except ValueError:
        raise ValueError(
            "粒度层 %r 不在 %r 内（三层是 Astar 2608.27287 taxonomy 的 DWC"
            "映射 — 不加第四层, 与 direction 锁 3 同纪律）"
            % (name, list(GRANULARITY_LEVELS)))


def is_coarser(a: str, b: str) -> bool:
    """a 比 b 更粗？（L1 < L2 < L3）— 同级或反序 ⇒ False。"""
    return level_of(a) < level_of(b)


def coarsest(g: Tuple[str, ...]) -> str:
    """给定若干层名 ⇒ 最粗的那个（空 ⇒ raise — 不返回 None 冒充）。"""
    if not g:
        raise ValueError("coarsest: 空层级清单 ⇒ 无最粗可判（None 不是层）")
    return min(g, key=level_of)


GRANULARITY_MECHANICS = {
    "no_second_source": "三层全是 Proposal 既有字段的投影 — 不复制值, 不新造判据",
    "paper_alignment": "Astar 2608.27287 §2.2.1 三级 taxonomy 逐层映射（论文未给类别表 ⇒ DWC 不虚构）",
}
