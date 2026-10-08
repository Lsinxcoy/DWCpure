# -*- coding: utf-8 -*-
"""world_model · 第七器官 · 承载进化循环环节⑥ 探索（ARCHITECTURE §4.7）。

定位声明 · **DWC-AUTO**（自我强化 · 判据 G1 定位门）
  ★ 为什么不标 DWC-MEM（照 llm/client 的判词）: 它不碰 MemoryKernel、
    不参与记忆读写 —— 树存的是「候选与观测」不是记忆节点；
    它服务环节⑥（生成下一轮往哪探索）= 自我强化的探索端。
  ★ 不抢位: 不声明 REPLACES（它补的是 v3 漏掉的第七器官，不替代谁）。

★★★ TRUTH_SOURCE（判据 G2: 含判定能力的模块必须声明）
  本模块**不产生**成功判定 —— observe(score, success) 的两个值都是
  调用方从 judge 判完回填的观测；simulated 节点没有任何写 score 的路径。
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, NamedTuple, Optional

from dwc.foundation.dial_config import load_world_tree

#: 系统外真值源（G2）—— score/成功永远来自 judge，不来自本模块
TRUTH_SOURCE = {
    "声明": "本模块不自判：observe(score, success) 两个值由调用方从 judge 传入",
    "真值源位置": "dwc.organs.judge.TRUTH_SOURCE（config/anchors/dev.json）",
    "自判禁止": "simulated 节点无 score 写入路径（WORLD_TREE 约束1/2）；"
                "收束排序只吃布尔观测的信息增益，不吃任何 confidence（W4）",
}

#: provenance 枚举（W2 —— 想象与真实必须可区分）
PROVENANCES = {"observed", "simulated"}
#: score/conf 从哪来的标注（审计用，不参与任何排序）
CONFIDENCE_SOURCES = {"judge_dev", "dynamics", "none"}


class WorldModelError(Exception):
    """世界树的违规必须大声报错（不许静默降级 —— G7 静默门同族）。"""


@dataclass
class WorldNode:
    """树节点 —— 一套结构、两种节点（WORLD_TREE §4.1 约束3）。

    ★ provenance / confidence_source / depth **必填无默认**（与 G11/K4/X1
      同款纪律: 隐式默认会把「没想过」伪装成「想过了」）—— 这就是 W2 的落点。
    ★ score 只能经 WorldTree.observe() 写入（构造期恒 None）：
      simulated 节点**永远**不会有分数 —— 「想象的分数不可信」（约束2）。
    ★ n_obs/n_pass = 谱系上的布尔观测史（EL 调度器只要布尔观测,
      2609.04128: 零模型依赖）—— 信息增益的唯一输入（W4）。
    """

    id: str
    parent_id: Optional[str]
    action: str
    provenance: str          # W2 ∈ {observed, simulated} —— 无默认
    confidence_source: str   # ∈ {judge_dev, dynamics, none} —— 无默认
    depth: int               # 无默认
    score: Optional[float] = None
    branch: Optional[str] = None   # simulated 节点必有（add_child 自动锚定）
    cost: float = 0.0
    children: List[str] = field(default_factory=list)
    n_obs: int = 0
    n_pass: int = 0


class Candidate(NamedTuple):
    """select() 的输入单元：(树 id, 节点) —— 收束必须能跨树比较。"""

    tree: str
    node: WorldNode


def information_gain(n_obs: int, n_pass: int) -> float:
    """★ 收束判据 = 谱系 pass-rate 的不确定性（二元熵，Laplace 平滑）。

    ★ 依据: WORLD_TREE §4.3 理由3 —— 「哪个分支的 pass-rate 最不确定,
      先探它」（2609.04128 EL 调度器按信息量选，零模型依赖，只要布尔观测）。
    ★ 聚合口径: **沿谱系路径求和**（root→节点）—— 与 2609.04128 的轨迹和
      Δ_θ=Σ_t 同形（方向不同: 那是难度差，这里是布尔观测）。
      ★★ 路径求和是**我的实例化**，不是论文逐字 —— 见模块诚实边界。
    ★★★ W4 落点: 本函数只吃 n_obs / n_pass 两个整数 —— **不读任何
      confidence 字段**（ARSI avg_conf=count/20 是反面教材）。
    """
    p = (n_pass + 1.0) / (n_obs + 2.0)
    if p <= 0.0 or p >= 1.0:          # Laplace 下不会发生，防御性保留
        return 0.0
    return -(p * math.log2(p) + (1.0 - p) * math.log2(1.0 - p))


class WorldTree:
    """唯一树结构 —— 全仓 `class .*Tree` 只许这一个（判据 W1）。

    ★ legal_actions 语义（§4.7 职责一原文）:
        「W.legal_actions() = **未揭示的叶子** ← 任务列表」
      未揭示 = score is None；叶子 = 无子。root 初始未揭示自然在列。
      ★ 与 2609.14858 论文 A(T)={root}∪leaves 的差异**明写不藏**:
        那是回放语义（branch opening 含 root），DWC 这里是任务源语义 ——
        root 揭示后由其子叶子接替。
      ★ 未揭示的分数保持未知（prefix-only，不许偷看未来）。
    """

    def __init__(self, tree_id: str, root_action: str,
                 depth_limit: int, max_nodes: int):
        # ★ W6: 两个上限都**必填无默认** —— 展开深度外部化
        #   （ARSI adaptive_depth 硬编码 0.15/0.30/0.50 是反面）
        # ★ max_nodes = 池子上限（母巢 L3 教训: 1,447 生 / 5 死）——
        #   剪枝策略未定（WORLD_TREE 诚实边界⑤）之前，超限**显式拒绝**。
        for name, v in (("depth_limit", depth_limit), ("max_nodes", max_nodes)):
            if isinstance(v, bool) or not isinstance(v, int) or v < 1:
                raise WorldModelError("%s 须为 ≥1 的整数（必填无默认）, 实得 %r"
                                      % (name, v))
        self.tree_id = tree_id
        self.depth_limit = depth_limit
        self.max_nodes = max_nodes
        self.nodes: Dict[str, WorldNode] = {}
        root = WorldNode(id="root", parent_id=None, action=root_action,
                         provenance="observed",  # root = 初始工作区（已存在）
                         confidence_source="judge_dev", depth=0)
        self.nodes[root.id] = root
        self.root_id = root.id

    # ── 展开（收束三段的①: 从真实节点长出候选）──────────────
    def add_child(self, parent_id: str, *, node_id: str, action: str,
                  provenance: str, confidence_source: str = "none") -> WorldNode:
        parent = self.nodes.get(parent_id)
        if parent is None:
            raise WorldModelError("父节点不存在: %r（%s）" % (parent_id, self.tree_id))
        if node_id in self.nodes:
            raise WorldModelError("节点 id 重复: %r" % node_id)
        if provenance not in PROVENANCES:
            raise WorldModelError("W2: provenance=%r 不在 %s 内"
                                  % (provenance, sorted(PROVENANCES)))
        if confidence_source not in CONFIDENCE_SOURCES:
            raise WorldModelError("confidence_source=%r 不在 %s 内"
                                  % (confidence_source, sorted(CONFIDENCE_SOURCES)))
        depth = parent.depth + 1
        if depth > self.depth_limit:
            raise WorldModelError("W6: 深度 %d 超过 depth_limit=%d（深度外部化，"
                                  "不许静默越界）" % (depth, self.depth_limit))
        if len(self.nodes) >= self.max_nodes:
            raise WorldModelError("池子超限: %d/%d —— 超限显式拒绝（母巢 L3: "
                                  "只生不汰；剪枝策略未定前的最小防线）"
                                  % (len(self.nodes), self.max_nodes))
        node = WorldNode(id=node_id, parent_id=parent_id, action=action,
                         provenance=provenance,
                         confidence_source=confidence_source, depth=depth)
        if provenance == "simulated":
            anchor = self._observed_anchor(parent_id)
            if anchor is None:
                raise WorldModelError("simulated 节点找不到已观察祖先（树损坏）")
            node.branch = anchor     # WORLD_TREE §4.1: simulated 必带 branch
        self.nodes[node_id] = node
        parent.children.append(node_id)
        return node

    def _observed_anchor(self, node_id: str) -> Optional[str]:
        """最近的已观察祖先（simulated 节点的 branch 锚点）。root 恒 observed。"""
        cur = self.nodes.get(node_id)
        while cur is not None and cur.provenance != "observed":
            cur = self.nodes.get(cur.parent_id) if cur.parent_id else None
        return cur.id if cur else None

    # ── 观测回填（simulated → observed 的唯一通路）───────────
    def observe(self, node_id: str, score: float, success: bool) -> WorldNode:
        """执行结果回填。W5: provenance 只许 simulated→observed，且真值不许覆盖。"""
        node = self.nodes.get(node_id)
        if node is None:
            raise WorldModelError("节点不存在: %r（%s）" % (node_id, self.tree_id))
        if node.score is not None:
            raise WorldModelError(
                "W5: %r 已带真值 score=%s —— provenance 单向（只许 "
                "simulated→observed）且判分不可覆盖" % (node_id, node.score))
        if score is None or (isinstance(score, bool) or not isinstance(score, (int, float))):
            raise WorldModelError("score 必须是数值, 实得 %r（真值必须来自 judge）"
                                  % score)
        # 单向转换只发生在这一次赋值里 —— 全模块没有任何反向路径（W5）
        node.provenance = "observed"
        node.confidence_source = "judge_dev"
        node.score = float(score)
        node.n_obs += 1
        node.n_pass += 1 if success else 0
        return node

    # ── 环节⑥ 的树侧接口 ────────────────────────────────────
    def legal_actions(self) -> List[WorldNode]:
        """未揭示的叶子（§4.7 职责一: 任务列表）。"""
        return [n for n in self.nodes.values() if n.score is None and not n.children]

    def judgeable(self) -> List[WorldNode]:
        """★ W3: judge 的输入不得含 provenance=simulated 的节点。"""
        return [n for n in self.nodes.values() if n.provenance == "observed"]

    def lineage_obs(self, node_id: str) -> tuple:
        """沿 root→node 路径求和的布尔观测（信息增益的输入口径）。"""
        n_obs = n_pass = 0
        cur = self.nodes.get(node_id)
        if cur is None:
            raise WorldModelError("节点不存在: %r（%s）" % (node_id, self.tree_id))
        while cur is not None:
            n_obs += cur.n_obs
            n_pass += cur.n_pass
            cur = self.nodes.get(cur.parent_id) if cur.parent_id else None
        return n_obs, n_pass


class WorldModel:
    """第七器官本体: 持有 𝒲（树集合）+ 环节⑥ 的两个输出（任务源 / 收束）。

    ★ config 复用 foundation.dial_config.load_world_tree()（Z1–Z6 校验已在
      那 —— 「没有校验器的 yaml 只是文本」），本模块不重造校验。
    ★ Z6 卡住检测的 n_stuck/on_stuck 读 config（不硬编码）。
    """

    def __init__(self, depth_limit: int, max_nodes: int,
                 config_path: Optional[str] = None):
        # ★ W6: 深度外部化 —— 构造必填，无默认
        for name, v in (("depth_limit", depth_limit), ("max_nodes", max_nodes)):
            if isinstance(v, bool) or not isinstance(v, int) or v < 1:
                raise WorldModelError("%s 须为 ≥1 的整数（必填无默认）, 实得 %r"
                                      % (name, v))
        self.depth_limit = depth_limit
        self.max_nodes = max_nodes
        #: Z1–Z6 配置面（strategy/pareto_dim/n_pareto_min/stuck/…，缺字段即 DialError）
        #: ★ None = 用默认 config/world_tree.yaml（不能显式传 None 进去 ——
        #:   load_world_tree(path) 的默认值会被 None 顶掉，实测踩过）
        self.config = (load_world_tree(config_path) if config_path
                       else load_world_tree())
        wt = self.config["world_tree"]
        self.strategy = wt["strategy"]
        self.stuck_cfg = wt["stuck"]
        self.trees: Dict[str, WorldTree] = {}
        #: Z6: 卡住事件留痕（触发过什么处置，可观测）
        self.stuck_events: List[Dict[str, Any]] = []
        self._stuck_streak = 0

    # ── 播种（§4.7: 初始播种 sealed 任务）──────────────────
    def seed(self, tree_id: str, root_action: str) -> WorldTree:
        if tree_id in self.trees:
            raise WorldModelError("树 id 已存在: %r" % tree_id)
        t = WorldTree(tree_id, root_action, self.depth_limit, self.max_nodes)
        self.trees[tree_id] = t
        return t

    def tree(self, tree_id: str) -> WorldTree:
        t = self.trees.get(tree_id)
        if t is None:
            raise WorldModelError("树不存在: %r（已有: %s）"
                                  % (tree_id, sorted(self.trees)))
        return t

    # ── 环节⑥ 接口①: 下一轮任务源（§4.7 职责一）────────────
    def candidate_nodes(self) -> List[Candidate]:
        """全部树的未揭示叶子（跨树，默认按树 id、节点 id 稳定排序）。"""
        out: List[Candidate] = []
        for tid in sorted(self.trees):
            for n in sorted(self.trees[tid].legal_actions(), key=lambda x: x.id):
                out.append(Candidate(tid, n))
        return out

    def legal_actions(self) -> List[Dict[str, Any]]:
        """★ 环节⑥ 的任务源（run_term._next_task_source 消费的形态）。

        ★ 语义: 未揭示的叶子 = 下一轮该执行的候选任务（不是结算报告）。
        """
        return [{"tree": c.tree, "node": c.node.id, "action": c.node.action,
                 "depth": c.node.depth, "branch": c.node.branch}
                for c in self.candidate_nodes()]

    # ── 观测回填（执行后）──────────────────────────────────
    def record_observation(self, tree_id: str, node_id: str,
                           score: float, success: bool) -> None:
        self.tree(tree_id).observe(node_id, score, success)

    # ── 收束③: 选信息增益最大（不是选最高分）────────────────
    def select(self, candidates: Optional[List[Candidate]] = None,
               current: Optional[Candidate] = None) -> List[Candidate]:
        """收束三段的第三段（WORLD_TREE §4.2/§4.3）。

        ★ 排序键**只有**信息增益（谱系布尔观测的熵）——
          observed 节点的真实 score 会保留在输出里，但**不参与排序**：
          「收束不选模拟最高分」（§4.3 理由1/2）。
        ★ 不回退保证（§4.7）: current 必在返回集 ⇒ V^{m⋆} ≥ V^0。
        ★ W4: 计算路径上不读任何 confidence 字段（见 information_gain）。
        """
        items = self.candidate_nodes() if candidates is None else list(candidates)
        seen = set()
        picked: List[Candidate] = []
        for c in items:
            if c.tree not in self.trees:
                raise WorldModelError("候选引用了不存在的树: %r" % c.tree)
            if (c.tree, c.node.id) in seen:
                continue
            seen.add((c.tree, c.node.id))
            picked.append(c)
        if current is not None and (current.tree, current.node.id) not in seen:
            if current.tree not in self.trees:
                raise WorldModelError("current 引用了不存在的树: %r" % current.tree)
            picked.append(current)     # ★ 不回退保证
        return sorted(picked,
                      key=lambda c: (-information_gain(
                          *self.trees[c.tree].lineage_obs(c.node.id)),
                          c.tree, c.node.id))

    # ── Z6: 卡住检测（路线①的已知病, Figure 6a）─────────────
    def record_round(self, improved: bool) -> Optional[str]:
        """每轮汇报「有没有改进」；连续 n_stuck 轮无改进 ⇒ 返回处置动作。

        ★ Z6 依据: Figure 6a「repeatedly attempts to refine it, fails to
          improve, and ultimately depletes the budget」—— 不设检测就是
          明知有病不设防。n_stuck / on_stuck **读 config**，不硬编码。
        ★ 触发一次即复位（处置后重新计），事件进 stuck_events 留痕。
        """
        if improved:
            self._stuck_streak = 0
            return None
        self._stuck_streak += 1
        if self._stuck_streak >= int(self.stuck_cfg["n_stuck"]):
            action = self.stuck_cfg["on_stuck"]
            self.stuck_events.append({"streak": self._stuck_streak,
                                      "action": action})
            self._stuck_streak = 0
            return action
        return None


# ══════════════════════════════════════════════════════════
# 诚实边界（本轮 = R60 的范围，别把「声明」当「生效」）
# ══════════════════════════════════════════════════════════
# ★★ 已做: 一套树(W1) + provenance 双节点(W2/W3/W5) + 收束三段的信息增益版
#         + 深度/池上限外部化(W6) + Z6 卡住检测 + 环节⑥任务源接口
# ★ 未做（下轮, 依赖 TaskScorePoint 历史或另需裁决）:
#   · 残差难度 δ_θ（裁决的路线丙 组内基线, ARCHITECTURE §4.7 ②）
#   · 三方向枚举 FORWARD / LATERAL / REVERSE（§4.7 ③）
#   · EL 完整调度器（窗口 B=8 τ=6/8 —— 本轮只取了「布尔观测」这一半）
#   · Z4 候选持久化 / Z5 merge 三条件（config 声明在, 实现未落 ——
#     与 world_tree.yaml 诚实边界② 同步标注）
# ★ 谱系路径求和的聚合口径是**我的实例化**（与 Δ_θ 轨迹和同形）,
#   论文没给「信息增益该怎么聚合」的逐字公式 —— 未与第二人复核。
# ★ 剪枝策略仍是 WORLD_TREE 诚实边界⑤（未定）—— max_nodes 只是
#   硬上限防线，不是剪枝方案。
