# -*- coding: utf-8 -*-
"""direction · 进化三方向 FORWARD/LATERAL/REVERSE（器官⑥ 探索 · Prometheus-Y）。

定位声明 · **DWC-AUTO**（自我强化 · 判据 G1 定位门）
  ★ 服务环节⑥ 探索与进化链的**方向选择**，不碰记忆读写 ⇒ 非 DWC-MEM。
  ★ 不抢位: 不声明 REPLACES。

=== 出处（EVOLUTION_CORE_V2 §8.3 · ALL_REPOS_EVOLUTION_DESIGN §六/结论2）===
  EvolutionDirection.FORWARD   前进 (在现有基础上改进)
  EvolutionDirection.LATERAL   横向 (换一个方向试)
  EvolutionDirection.REVERSE   后退 (回退到更简单的方案)

  ★ 39 仓库实测: **只有 Prometheus-Y / Omega 两个有"方向"概念**（39 仓进化矩阵
    实测 —— 本机 Prometheus-Omega 源码已 grep 无 EvolutionDirection 残留,
    以 ALL_REPOS 的 39 仓分析记录为权威实测）。
  ★ **三种是校正后口径**: DEDUP_AUDIT_6SYSTEMS L254「本轮实测方向只有 3 种,
    旧报告写 4 种是错的」—— 所以本模块**锁 3**, 第 4 个成员是历史错误。

=== 链位（ALL_REPOS 结论 2 的互补链, 方向是**第一环**）===
  方向选择 (Y) → 门 (ARSI) → 形式化验证 (MSTAR) → 落地 (MSTAR rollback)
    → 固化 (Z)
  ⇒ 方向选择发生在**门之前**（提案/展开的头）—— 这是本模块将来的接线位,
    具体接谁由设计裁决（见模块尾诚实边界）。

=== 辨析（设计原文, 别混）===
  ★ 三方向 **≠** 2609.04128 的 length/scenario/skill —— 后者是「难度方向的
    分解」（残差难度的三个分量）, 三方向是**进化操作的方向性**。
  ★ 三方向 **≠** 世界树收束（WORLD_TREE 系设计对方向零提及 —— 已 grep 核实;
    select 只吃信息增益 W4, 与方向无关）。
"""
from __future__ import annotations

from enum import Enum
from typing import Dict


class EvolutionDirection(str, Enum):
    """三方向（值枚举 —— G11 同款: 值域固定, 不许静默加第四个）。

    ★ str 混合: 与 "FORWARD" 直等、可直接 json 序列化（提案/日志携带）。
    ★ 三语义逐字来自设计（EVOLUTION §8.3 / ALL_REPOS §六）——
      改语义必须改 SEMANTICS 表, 不许只改注释（名字与实现对齐）。
    """

    FORWARD = "FORWARD"   # 前进 (在现有基础上改进)
    LATERAL = "LATERAL"   # 横向 (换一个方向试)
    REVERSE = "REVERSE"   # 后退 (回退到更简单的方案)


#: 语义表 —— 与枚举**同处存放**（两处漂移就违反"名字与实现对齐"）
SEMANTICS: Dict[EvolutionDirection, str] = {
    EvolutionDirection.FORWARD: "前进 (在现有基础上改进)",
    EvolutionDirection.LATERAL: "横向 (换一个方向试)",
    EvolutionDirection.REVERSE: "后退 (回退到更简单的方案)",
}

#: 方向总数 —— 锁 3（DEDUP L254: 旧报告的 4 种是错的, 3 是校正后口径）
N_DIRECTIONS = 3


class DirectionError(Exception):
    """方向值违规必须大声报错（G7 静默门同族）。"""


def ensure_direction(value) -> EvolutionDirection:
    """值 → EvolutionDirection（★ 精确值枚举, 拒一切外来形态）。

    ★ 拒: None（"无方向"不是第四方向 —— 没想清楚要显式说, 不许拿 None
      冒充）、大小写变体（"forward" ≠ "FORWARD" —— 值枚举精确匹配,
      猜着兼容就等于把漂移放进来）、未知值。
    """
    if isinstance(value, EvolutionDirection):
        return value
    if value is None:
        raise DirectionError(
            "方向缺失 —— None **不是**第四方向: 提案没定方向时必须显式 "
            "三选一, 不许 None 冒充「未标注」")
    if isinstance(value, str):
        for d in EvolutionDirection:
            if value == d.value:        # ★ 精确 ==, 不做 casefold
                return d
    raise DirectionError(
        "方向值 %r 不在 %r 内（值枚举精确匹配 —— 大小写变体也拒）"
        % (value, [d.value for d in EvolutionDirection]))


def semantics_of(value) -> str:
    """方向 → 逐字语义（查表, 语义只有一份真源 SEMANTICS）。"""
    return SEMANTICS[ensure_direction(value)]


# ══════════════════════════════════════════════════════════
# 诚实边界（R73 的范围, 别把「枚举在」当「选择在」）
# ══════════════════════════════════════════════════════════
# ★ 已做: 三方向枚举（锁 3）· 逐字语义表（同处防漂移）· 值枚举校验
#         （ensure_direction 精确匹配拒 None/大小写/未知）· 链位声明
#         · 与 length/scenario/skill 的辨析
# ★ 未做（**设计未给, 不发明**）:
#   · **选择策略** —— 设计只给三方向与语义, **没给"何时选哪个"的判据**
#     （EVOLUTION §8.3 / ALL_REPOS §六/结论2 全文已核, 零策略描述）
#     ⇒ 本模块不自造策略; 有据的只有链位（方向选择在门之前）
#   · **消费接线** —— 谁带 direction 字段（evolver 提案 / 探索展开 / …）
#     设计未裁决 ⇒ 不顺手改已有接口（add 方向字段=行为面变更）
#   · ★ 候选接线观察（**我的实例化, 未接未复核**）: world_tree.yaml 的
#     `stuck.on_stuck: switch_strategy`（换策略）语义近似 LATERAL、
#     「回退更简单」近似 REVERSE —— 若将来裁决联动, 这是第一落点
#   · ★ ⑥ search/ 组件树是**四件**（weakness / el_sched / replay / direction
#     —— EVOLUTION 树 L656-660 实数）: 本轮落 direction, **replay.py
#     （回放仿真器, 2609.14858, 候选集含 current）仍未做**
#     —— 此前口头说「器官⑥ 只剩一件」是**数错**, 以树为准
# ★ 未与第二人复核。
