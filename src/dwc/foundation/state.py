"""DWC state · 四层冻结快照 —— docs/STATE_SCHEMA.md（2026-10-04 已定）的实现。

定位声明（DWC-MEM · 记忆底座 · 判据 G1 定位门）
  ★ state 是「每轮可审计的公开快照」—— 它属记忆底座（原则 3: 单一真值源
    的一部分），不是任何器官的私有态（判据 P1: 跨器官只传 ID / 公开层）。
  ★ 不抢位: 不声明 REPLACES。

★★★ 设计依据（字段逐条照抄 STATE_SCHEMA §三, 每个字段都有写入方 = I3）:
  State = (S_t 资产版本, H_t 架构版本, G_t 门快照, X_t 执行上下文)
  ★ S_t/H_t 分量名来自 2608.03392 式(7)(8)
  ★ G_t 是核心新增（守卫① + 各门判定 + 铁律汇总 + 预算）
  ★ X_t 环内瞬时（**刻意不 frozen** —— 设计原文如此: 不留痕, 由调用方决定要不要记）
  ★ θ_t（模型参数）DWC 固定 ⇒ 不进 state（设计 §二 原文）

★ frozen 的意义（判据 I6 的构造面）: 铁律阳性测试可以构造违规 state 且
  保证中途改不动 —— 若某字段可变, "冻结"就是声称而非实测。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AssetVersions:
    """S_t · 资产层（2608.03392 式(7)）。"""

    memory_version: str      # 写入方: memory 每次落盘后变更
    skills_version: str      # 写入方: evolver 编译产物变更时
    tools_version: str       # 写入方: iron_laws.check_access 放行新工具时
    context_version: str     # 写入方: memory 组装上下文摘要时


@dataclass(frozen=True)
class ArchitectureVersions:
    """H_t · 架构层（2608.03392 式(8)）。"""

    harness_version: str     # 写入方: 代码发布
    workflow_version: str    # 写入方: evolver 改 workflow 时
    org_version: str         # 写入方: 器官拓扑变更（原则上永不自动变）


@dataclass(frozen=True)
class GateSnapshot:
    """G_t · 门的快照（STATE_SCHEMA 核心新增 —— 每个字段都有写入方）。"""

    # ── 守卫①（§9 第 20 项裁决的落点）──
    wm_version: str
    wm_dev_accuracy: float            # judge 在 dev 上外测的准确率 [0,1]
    wm_dev_n: int                     # 样本量（置信区间必需）
    theta_dev: float                  # 本轮实际使用的阈值（滑动基线）
    theta_dev_kind: str               # floor / rolling / anchored
    gate1_verdict: str                # pass / degrade_to_llm / degrade_to_heuristic
    # ── 其余三门的来自方（原则 12 ②③④）──
    iwm_verdict: str                  # ok / degrade_to_baseline / override
    iwm_reason: str
    train_verdict: str                # world_model.train() 是否成功
    # ── 铁律汇总 ──
    laws_block: tuple[str, ...] = ()  # 触发的 block 级铁律 id
    laws_warn: tuple[str, ...] = ()   # 触发的 warn 级铁律 id
    # ── 预算（§9 第 2 项 b_t）──
    b_t: int = 0                      # 本轮可归因编辑数
    cost_used: float = 0.0            # 已用预算, 供 C ≤ B 判定
    # ── 逐任务分数（2026-10-04 增补, TASK_SCORE_TRACKING）──
    task_scores_ref: str = ""         # ★ 指针而非内嵌（P2: 跨器官只传 ID）
    group_scores: tuple = ()          # 按能力组聚合（形态依赖 A6, 未定则空）
    n_assertions_min: int = 0         # 分辨率自陈（没有它退化不可审计）


@dataclass
class ExecutionContext:
    """X_t · 执行上下文（环内瞬时 —— 设计原文**不 frozen**, 不留痕）。"""

    chain_id: str                     # 对齐因果链五环第一环（原则 11）
    decision_id: str
    turn_index: int
    task_id: str
    task_source: str                  # world_node_id / sealed_dev / sealed_test
    split: str                        # in / dev / test ★ 双 split 硬约束用


@dataclass(frozen=True)
class State:
    """State = (S_t, H_t, G_t, X_t) —— 公开四层（iwm 只许读这四层）。

    ★★★ 不变量（ORGAN_INTERFACES §六）: iwm.governor_advice **不得**读
      任何器官的内部状态 —— 它的输入面就是本类。这不是风格, 是第 20 项
      裁决的根源（跨层自评 = 违规）。
    """

    S: AssetVersions
    H: ArchitectureVersions
    G: GateSnapshot
    X: ExecutionContext

    def to_dict(self) -> dict[str, Any]:
        from dataclasses import asdict
        return asdict(self)
