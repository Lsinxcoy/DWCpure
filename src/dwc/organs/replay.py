# -*- coding: utf-8 -*-
"""replay · 回放仿真器（器官⑥ search/ 第四件 · 2609.14858 §2.2–2.7「Dreaming」）。

定位声明 · **DWC-AUTO**（自我强化 · 判据 G1 定位门）
  ★ 服务环节⑥ 探索的**离线回放评估**，不碰记忆读写 ⇒ 非 DWC-MEM。
  ★ 不抢位: 不声明 REPLACES。

★★★ TRUTH_SOURCE（判据 G2）
  本模块**不产分数** —— 节点 s_v 由 WorldTree.observe() 写入（judge 判分观测,
  W2: 想象的分数不可信 ⇒ simulated 节点恒无分）。replay 只做**读取与重排**。

=== 论文机制（docs/papers/2609.14858.md §2.2–2.7 深读报告逐条）===
  §2.2 Discovery Tree: 根=初始工作区; 每非根恰一 primary parent;
        节点存 inherited history + score s_v
        ⇒ ★ DWC 承载: WorldTree 天然同构（root_id/nodes/parent_id/children 已在,
          R60 建树时就与本节对齐 —— WorldTree docstring 已预留差异标注）
  §2.3 共享决策接口（Online/Offline 共用）:
        A(𝒯) = {r} ∪ {观测树的叶子}   ·   A(𝒯; W) = { C ⊆ A(𝒯) : |C| ≤ W }
  §2.5 Offline「Dreaming」: ℋ 固定; replay **确定性返回记录子节点**,
        **绝不生成新节点** —— 根返回其**最早**已记录子节点
        ★ 论文自陈根本偏置: "只能重排, 不能探索新分支"
  §2.6 V = max_{v∈终态} s_v − β₁·N + β₂·(N / max{1, k})
        （discovery quality / execution cost / parallelism bonus）
        ★★ 论文**未报告 β₁/β₂ 具体值** ⇒ 本模块必传无默认
        （有出处才能给默认 — NOISE_DELTA 纪律的反面）
  §2.7 π* = argmax_m V^m · **候选集必含 current ⇒ V(m*) ≥ V(current)**
        ★★ 单调性的确切边界（逐字）: 保证的是「**固定历史**上平均 replay 分
        不劣于当前」, **不是在线发现性能不劣**（replay 只能重排）

=== 落点差异（与 §5 深读建议的接口对照, 明写不藏）===
  §5 建议落 src/dwc/memory/replay_sim.py（记忆节点加 parent/children/score）——
  **本模块不采纳该落点**: DWC 的记忆不是树（key-value/fact）, 而世界树**已是**
  真树且节点三字段齐 ⇒ 落 organs/replay.py 操作 WorldTree（组件树
  ⑥ search/replay.py 为准, 同 weakness/el_sched/direction 平铺惯例）。
"""
from __future__ import annotations

import math
from typing import Dict, Iterable, Set, Tuple


class ReplayError(Exception):
    """回放违规必须大声报错（G7 静默门同族）。"""


class ReplaySimulator:
    """把**已记录的树**变成可回放的决策世界（§2.5 Dreaming 侧）。

    ★ 树用鸭子类型接（root_id / nodes[v].children）—— 不 import world_model
      类本体之外的实现细节; 实测与 WorldTree 直配（集成测试锁）。
    ★ Online rollout（策略冻结跑一轮产新树）**不在本模块** ——
      DWC 的在线侧=世界树 expand/observe 已有; 本模块只承载离线回放。
    """

    def __init__(self, tree):
        if not getattr(tree, "root_id", None) or \
                not isinstance(getattr(tree, "nodes", None), dict):
            raise ReplayError(
                "tree 须有 root_id 与 nodes dict（WorldTree 形态）, 实得 %r"
                % (type(tree).__name__,))
        self.tree = tree

    # ── §2.3 决策接口 ─────────────────────────────────────
    def eligible(self, observed: Iterable[str]) -> Set[str]:
        """A(𝒯) = {r} ∪ {观测树的叶子}（§2.3 逐字）。

        ★ "leaves determined from the **currently observed** tree" ——
          叶子只看 observed 内部: 记录了但未揭示的子节点**不解除**父的叶子身份
          （否则 replay 还没 step 父就不是候选了, 决策接口就断了）。
        ★ 根**恒在**（branch opening 含 root —— WorldTree.legal_actions 的
          docstring 已明写与本接口的任务源语义差异, 两口并存不混用）。
        """
        obs = set(observed)
        self._check_observed(obs)
        leaves = {v for v in obs
                  if not (set(self.tree.nodes[v].children) & obs)}
        return {self.tree.root_id} | leaves

    def validate_batch(self, batch: Iterable[str], observed: Iterable[str],
                       W: int) -> None:
        """A(𝒯; W) 合法性: C ⊆ A(𝒯) 且 |C| ≤ W（§2.3）。

        ★ 只**校验**不**枚举**集合族 —— A(𝒯;W) 是 2^|A| 级的组合空间,
          枚举即爆炸; 论文给的是定义域不是生成器（诚实标注）。
        ★ 空批次**合法**（§2.4 终止条件之一 = 策略选空 batch）。
        """
        if isinstance(W, bool) or not isinstance(W, int) or W < 1:
            raise ReplayError("W（并行度）须为 ≥1 整数, 实得 %r" % (W,))
        batch = list(batch)
        A = self.eligible(observed)
        bad = [v for v in batch if v not in A]
        if bad:
            raise ReplayError(
                "批次含非候选节点 %r — A(𝒯)=%r（C ⊆ A 才是合法批次）"
                % (bad, sorted(A)))
        if len(batch) > W:
            raise ReplayError(
                "批次大小 %d > 并行度 W=%d（|C| ≤ W）" % (len(batch), W))

    # ── §2.5 replay 转移（确定性, 只揭示不生成）────────────
    def step(self, observed: Iterable[str],
             batch: Iterable[str], W: int = 10 ** 9) -> Set[str]:
        """T^{m,k+1} = T^{m,k} ∪ ⋃ Child(v; 𝒯, T^{m,k})（§2.5 逐字）。

        ★ Child(v) = v 在 𝒯 中**记录且未被观测**的子节点 —— 只揭示,
          **绝不生成**（replay 的根本性质; 违反 = 把 replay 变成 online）。
        ★ 根特殊（§2.5 逐字）: 若 v 是根, 返回根的**最早**已记录子节点
          （children 是创建插入序 ⇒ [0] 即最早）。
        ★ observed 只增不减（揭示是单调的）。
        """
        obs = set(observed)
        self._check_observed(obs)
        self.validate_batch(batch, obs, W)
        new = set(obs)
        for v in batch:
            if v == self.tree.root_id:
                kids = self.tree.nodes[v].children
                cand = [kids[0]] if kids else []      # 根 → 最早子
            else:
                cand = [c for c in self.tree.nodes[v].children
                        if c not in new]              # 记录且未观测
            new |= set(cand)
        return new

    def _check_observed(self, obs: Set[str]) -> None:
        unknown = [v for v in obs if v not in self.tree.nodes]
        if unknown:
            raise ReplayError(
                "observed 含树外节点 %r — 观测集必须 ⊆ 𝒯" % (unknown,))


# ══════════════════════════════════════════════════════════
# §2.6 / §2.7 —— 评分与选择（纯函数, 树外可用）
# ══════════════════════════════════════════════════════════

def replay_score(*, max_score: float, n_revealed: int, n_rounds: int,
                 beta1: float, beta2: float) -> float:
    """V = max s_v − β₁·N + β₂·(N / max{1, k}))（§2.6 式 1 逐字）。

    ★ β₁/β₂ **必传无默认** —— 论文只给 "fixed coefficients" 与符号约束,
      **未报告具体取值**（深读报告诚实清单）⇒ 没出处就不许编默认值。
    ★ N = replay 揭示的**非根**节点数; k = 决策轮数; max{1,k} 按论文符号
      防 k=0 除零。
    """
    if beta1 < 0 or beta2 < 0:
        raise ReplayError(
            "论文符号约束 β₁, β₂ ≥ 0, 实得 %r/%r" % (beta1, beta2))
    if n_revealed < 0 or n_rounds < 0:
        raise ReplayError(
            "N/k 须 ≥0（N=揭示非根节点数, k=决策轮数）, 实得 %r/%r"
            % (n_revealed, n_rounds))
    return (max_score
            - beta1 * n_revealed
            + beta2 * (n_revealed / float(max(1, n_rounds))))


def select_policy(v_by_version: Dict[str, float], *, current: str
                  ) -> Tuple[str, float]:
    """π* = argmax_m V^m, 候选集**必含 current**（§2.7 不回退保证的前提）。

    ★ 返回 (m*, V(m*)) —— 由 argmax 数学事实: V(m*) ≥ V(current)。
    ★ current 不在候选 ⇒ **raise** —— 不许缺着候选装保证
      （保证的支点就是 current 兜底, 缺了还静默选 = 假保证）。
    ★ 平手: 确定性 tie-break 取**键字典序最小**（明规, 不随机 —— 可复现）。
    ★★★ 保证的确切边界（§2.7 深读逐字, 引用时别放大）:
      是「固定历史上平均 replay 分不劣于当前」, **不是在线发现性能不劣** —
      replay 的分支顺序被记录树限制, 只能重排不能探索新分支。
    """
    if not v_by_version:
        raise ReplayError("候选策略版本为空 — 空集没有 argmax")
    if current not in v_by_version:
        raise ReplayError(
            "current=%r 不在候选 %r 内 — 「候选集必含 current」是不回退"
            "保证的前提, 缺了就不许宣称保证" % (current,
                                            sorted(v_by_version)))
    # 确定性: 按 (-V, 键) 排序 ⇒ 高分优先, 平手键序小者先
    m_star = min(v_by_version, key=lambda m: (-v_by_version[m], m))
    return m_star, v_by_version[m_star]


def no_worse_than_current(v_by_version: Dict[str, float], *, current: str
                          ) -> bool:
    """★ 把 §2.7 的不等式写成可断言的谓词: V(m*) ≥ V(current)。"""
    _, best = select_policy(v_by_version, current=current)
    return best >= v_by_version[current]


# ══════════════════════════════════════════════════════════
# 诚实边界（R74 的范围, 别把「回放在」当「循环在」）
# ══════════════════════════════════════════════════════════
# ★ 已做: A(𝒯) 决策接口 · 批次校验（|C|≤W, 不枚举防爆炸）· step 确定性揭示
#         （根→最早子 / 绝不生成 / observed 单调）· V 公式（β 必传 — 论文未报告值）
#         · argmax 选择 + current 必含校验 + 不回退谓词 + 单调性边界标注
# ★ 未做（依赖裁决/依赖件）:
#   · **Online rollout 执行器**（策略冻结跑一轮产新树 𝒯_t）—— DWC 在线侧=
#     世界树 expand/observe 已有, 但「策略代码」本身的执行循环未接
#   · **M≥1 策略版本的产生**（policy-development agent 改策略代码）= LLM 循环
#     ⇒ 本轮只落**评估侧**（给一组 V 能选）, 产生侧待接线
#   · **ℋ 历史树集合的运行时累积**（ℋ_t=ℋ_{t−1}∪{𝒯_t}）—— 现状 world_model
#     .trees 是多树容器, 累积语义（每 online 轮 append 一棵）未接运行流
#   · **β₁/β₂ 的取值** —— 论文未报告 ⇒ 落地时必须显式给（config 或裁决）,
#     不许代码里编默认
#   · replay 与 evolver.accept 的关系: accept 是**采纳门**（2606.09498 两组
#     split 判据, evolver L1711 已落）, 本模块是**策略选择**（14858 §2.7）——
#     两套判据不同不互替, 别混
# ★ 未与第二人复核。
