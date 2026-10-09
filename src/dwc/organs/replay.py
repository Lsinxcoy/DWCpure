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
from dataclasses import dataclass
from typing import Dict, Iterable, List, Set, Tuple


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
        ★ 根特殊（§2.5 逐字 + R81 裁决读法乙）: 若 v 是根, 返回根的
          **最早未观测**已记录子（children 创建插入序里第一个未观测的）。
          ★★ 裁决链（三层链纪律: 论文最高, 逐字裁）:
            ① 转移方程 Child(v)=「v 在 𝒯 中**未观测**的子节点集」（定义级）
            ② 「无记录后继时 = ∅」—— 返回已观测子 ≠ ∅ ≠ 新揭示 ⇒ 论文无此操作
            ③ branch opening / 并行批次的实验语义要求能开多分支
            ⇒ 例外句「最早已记录子」的功能是规定**顺序**（最早优先）,
              不放宽「未观测」这个转移本质 —— 读法甲（含已观测 ⇒ 恒返
              kids[0] 空转, 第二分支永卡）被否。
          ★ 空树/全揭 ⇒ []（与「无记录后继时=∅」同口径）。
        """
        obs = set(observed)
        self._check_observed(obs)
        self.validate_batch(batch, obs, W)
        new = set(obs)
        for v in batch:
            if v == self.tree.root_id:
                kids = self.tree.nodes[v].children
                cand = [c for c in kids if c not in new][:1]  # 最早未观测
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


# ════════════════════════════════════════════════════════════
# R117 · HCE D_val 终评链（稿⑥§⑤ · 2603.26499 §3.3
#        「最终选择只用从未参与搜索的 D_val」）
# ════════════════════════════════════════════════════════════

def shortlist_candidates(v_search: Dict[str, float], *, current: str,
                         k: int = 2) -> List[str]:
    """★ 第②步: 搜索信号 top-K **∪ {current}** — current 必进名单。

    为什么强制并入 current: §2.7 不回退保证的支点是「候选集必含
    current」（select_policy 同款约束）— 短名单是**取样不是换候选集语义**,
    把 current 排除在外 ⇒ 终评后可能选出比现状差的而无兜底 = 假保证。
    """
    if not v_search:
        raise ReplayError("v_search 空 — 短名单没有来源")
    if current not in v_search:
        raise ReplayError(
            "current=%r 不在 v_search %r 内 — 候选集必含 current"
            "（§2.7 前提, 短名单不豁免）" % (current, sorted(v_search)))
    if not isinstance(k, int) or k < 1:
        raise ReplayError("K 须 ≥1 int, 实为 %r" % (k,))
    ranked = sorted(v_search, key=lambda m: (-v_search[m], m))
    top = ranked[:k]
    return top if current in top else top + [current]


def select_with_val_fallback(v_val: Dict[str, float],
                             v_search: Dict[str, float], *,
                             current: str) -> Dict[str, object]:
    """★ 第③④步: 终评 argmax v_val + 平票/不可比分回落 v_search。

    稿⑥§⑤ 字面: 「argmax v_val（只用从未参与搜索的信号）; 平键 ⇒ 字典序
    （现行平键规则沿用）; v_val 平票/样本太小 ⇒ 回落 v_search 并标
    val_tie_fallback（诚实字段, 不装终评有分辨力）」。
    返回 {m_star, score, source: "val"|"val_tie_fallback"|"val_empty_fallback",
          tie: bool, note}。
    """
    if not v_val:
        # 空 v_val（2 任务 val 的真实可能）⇒ 回落, 不装终评有分辨力
        m_star, score = select_policy(v_search, current=current)
        return {"m_star": m_star, "score": score,
                "source": "val_empty_fallback", "tie": False,
                "note": "v_val 空（val 未出数）⇒ 回落搜索信号 — 不装数"}
    # argmax 平键检测（确定性 tie-break 仍是字典序 — 现行规则）
    top = max(v_val.values())
    tied = sorted(m for m, v in v_val.items() if v == top)
    if len(tied) > 1:
        # ★ 平票 ⇒ 回落（稿字面: 平票=终评无分辨力, 诚实回落）
        m_star, score = select_policy(v_search, current=current)
        return {"m_star": m_star, "score": score,
                "source": "val_tie_fallback", "tie": True,
                "note": ("v_val 顶分平键 %r ⇒ 终评无分辨力, 回落"
                         " v_search（诚实字段 val_tie_fallback）" % (tied,))}
    m_star = tied[0]
    return {"m_star": m_star, "score": v_val[m_star],
            "source": "val", "tie": False,
            "note": "终评 argmax v_val — 只用未参与搜索的信号（HCE §3.3）"}


# ══════════════════════════════════════════════════════════
# R80 · Dreaming 循环报告（设计稿 docs/proposal_replay_dreaming_design.html）
# ══════════════════════════════════════════════════════════

@dataclass(frozen=True)
class PolicySpec:
    """★ π^m 的可修订参数（R85 稿裁决②: 只动纯选择逻辑, 锁值不进修订域）。

    w_delta: δ 排序权重（0=纯字典序, 1=现行 δ 降序）—— dream π^0 选择键
    prefer_revealable: R81 过滤开关（False=不过滤, 可选已观测叶子）
    seg_order: ★ R102 · B 甲案段序 — "children"（root children 插入序,
      与 step(root) 的「最早未观测子」顺序规定自洽）/ "delta"（段间选择用
      dmap, 与任务源同源 — R92 稿 B 节裁决点②）。进修订域（非锁值）。
    ★ 锁值（τ/B/β/δ=0.15 等）**不在此域**: from_mapping 遇到即拒
      （混动=违校准纪律且无法归因 — 约束 4 一处变更）。
    """
    w_delta: float = 1.0
    prefer_revealable: bool = True
    seg_order: str = "children"

    def __post_init__(self):
        if isinstance(self.w_delta, bool) or not isinstance(self.w_delta, (int, float)):
            raise ReplayError("w_delta 须为数值, 实得 %r" % (self.w_delta,))
        if self.w_delta < 0:
            raise ReplayError("w_delta 须 ≥0, 实得 %r" % (self.w_delta,))
        if self.seg_order not in ("children", "delta"):
            raise ReplayError(
                "seg_order ∈ {children, delta}, 实得 %r（值枚举, 不猜）"
                % (self.seg_order,))

    @property
    def pid(self) -> str:
        # π0 = 现行默认（current 键 — select_policy/no_worse 依赖）
        if self.w_delta == 1.0 and self.prefer_revealable \
                and self.seg_order == "children":
            return "π0"
        # ★ R102: 默认段序不进格式（既有 pid 测试锁全保）; 非默认追加 s 后缀
        #   （段序是真差异 — 不追加会与同 w/r 变体撞键自覆盖, L390 防双 π0 同族）
        base = "π(w=%g,r=%s)" % (self.w_delta, int(self.prefer_revealable))
        if self.seg_order != "children":
            base = base[:-1] + ",s=%s)" % self.seg_order
        return base

    @classmethod
    def from_mapping(cls, m: Dict[str, object]) -> "PolicySpec":
        """★ 构造校验: 锁值键/未知键 raise（R85 稿② — 修订域硬边界）。"""
        _LOCKED = {"tau", "b", "beta1", "beta2", "delta", "delta_theta",
                   "history_max", "n_envs", "seed"}
        bad = set(m) - {"w_delta", "prefer_revealable", "seg_order"}
        locked = bad & _LOCKED
        if locked:
            raise ReplayError(
                "PolicySpec: 锁值键不进修订域 %s（校准纪律）" % sorted(locked))
        if bad:
            raise ReplayError("PolicySpec: 未知键 %s" % sorted(bad))
        return cls(**m)          # type: ignore[arg-type]


@dataclass(frozen=True)
class DreamReport:
    """★ dream() 的产物（叠加报告, 不驱动行为 —— M=1 时 m* 恒 π0, 见 why）。

    ★ per_world: [(tree_id, V_i^m, k_i^*, N_i^m), ...] —— 每回放世界一行可审计。
    ★ monotone_no_worse = §2.7 谓词结果（M=1 时平凡成立, 显式记录不冒充改进）。
    """
    n_worlds: int
    v_by_version: Dict[str, float]     # {"π0": V^0}（M=1, 设计稿裁决②）
    m_star: str                        # argmax 结果（M=1 ⇒ 恒 "π0"）
    v_star: float
    betas: Tuple[float, float]         # (β₁, β₂) 本次实际用值（config 读入）
    per_world: List[Tuple[str, float, int, int]]
    monotone_no_worse: bool
    k2_max: int
    why: str
    policy_variants: Tuple[PolicySpec, ...] = ()   # R86: 参评参数集（M>1 可审计）
    #: ★ R102 · B 甲案: 本轮回放的段序（"treeid:seg_root|..." 跨树拼接, 可审计）
    segments: Tuple[str, ...] = ()
    #: ★ R102 探针②原料: {pid: pick 轨迹}（w=0 vs w=1 轨迹必须不同 — R90 靶）
    picks: Optional[Dict[str, Tuple[str, ...]]] = None


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
