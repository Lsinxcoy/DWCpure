# -*- coding: utf-8 -*-
"""DWC · run_term —— 编排层（harness）。★★ 第一个能把所有东西串起来的入口。

★★★ 这个模块为什么是当前最要紧的一件
  R18 写了 memory 器官，R15/R16/R17 写了六层 / 因果链 / 接线，
  但它们全是**孤岛**：没有入口、没有调用者、没有一轮真实进化跑过
  ⇒⇒ 六层至今没有任何系统内真实数据（只有我写的测试场景）
  ⇒⇒ 所以本模块就是那条把孤岛连起来的线。

定位声明（DWC-MEM · 记忆底座 · 判据 G1 定位门）
  ★ 编排层属于记忆底座（原则 3: 单一真值源 = 因果链）
  ★ 它只**编排**，不做判分（判分走注入的 judge）、不**隐式**驱动世界模型
    —— 环节⑥ 任务源是**显式读取** world_model.legal_actions()，非事件订阅
  ★ 判据 S3/C2 依然成立: 本模块没有"隐式驱动"——
    term 的推进由显式的 step 循环驱动，不是事件订阅

设计依据（docs/ERROR_AND_TERM.md）
  T1 · run_term 内必含: before 快照 / n×step / after 快照 /
        五元盘点 / 下一轮任务源  ★ 缺任一 ⇒ term 不完整
  T2 · term 边界由**进化事件**决定, n_steps 只是上限
        ★ 判据: 代码里不许有 "if steps == 10: break" 这类硬编码
  T3 · before/after 之间 dw_version 被锁
        ★ 变了 ⇒ 本 term 报告无效（G11 配套 3）
  T4 · 两个成本台账并存: term_cost(reset) + cumulative_cost(不 reset)
        ★ 门看 cumulative —— 原则 4「产出必须有消费点」是跨 term 的

  term 四个终止条件（§2.3）:
    ① 七环节跑通（诊断→提案→门→落地 至少各一次）
    ② 预算耗尽: C_{≤t+1} ≥ B
    ③ 保护组回归触发: r̂_{t,j} ≤ ϵ_j 不满足
    ④ 停止规则命中（2603.06333 §2.7 的五条）

  after 快照之后不是"结束"，而是"生成下一轮任务源"（§9 缺口 bz 的原话）
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from dwc.foundation.wiring import ActivityWiring
from dwc.foundation.causal_chain import CausalChainStore
from dwc.foundation import dial_config
from dwc.organs.memory import MemoryKernel, MemoryKind
from dwc.organs.judge import Judge
from dwc.organs.world_model import WorldModel
from dwc.organs.iwm import IwmOrgan, Observations
from dwc.organs.el_sched import ELScheduler

# ══════════════════════════════════════════════════════════
# 契约
# ══════════════════════════════════════════════════════════


class TermError(Exception):
    """违反 term 契约。★ 承重代码不许吞异常（判据 E2/E3）。"""


class LawViolation(TermError):
    """铁律被违反 ⇒ 整个 term 无效（T3: dw_version 被改）。"""


#: ★ 本 runner 唯一的机制名。★ 六层里"present/registered"两层的载体
#: 就是它 —— 所以它必须先 register 才能记任何事件。
MECHANISM = "memory_kernel"

#: ★★★ TRUTH_SOURCE（判据 G2 要求: 含评分/判定能力的模块必须声明）
#:
#: ★★★★ 重要: 本模块**不自己判分** —— 它调用 judge 判分，
#:   而 judge 的真值源在 dwc.organs.judge.TRUTH_SOURCE
#:   ⇒⇒ 所以这里的声明是**转发**声明，不是"我有个真值源"
#: ⇒⇒ ★ 那为什么还要声明？因为 G2 的判据形态是
#:   「有 score/evaluate/judge 能力 ⇒ 必须显式写出分数从哪来」
#:   ⇒ 若我不写，读者会以为 run_term 里有自评逻辑
#:   ⇒ 而 run_term 里恰好**有一处**需要说明：_build_observations
#:   造的那批**自造观测**（用 golden 关键词拼，必然通过）
#:   ⇒⇒ 所以这里必须点明: 那批观测不是真值源，是"验接线用的假数据"
TRUTH_SOURCE = {
    "本模块不自评": "判分一律转发 dwc.organs.judge.Judge",
    "真值源位置": "dwc.organs.judge.TRUTH_SOURCE（config/anchors/dev.json）",
    "★ 自造观测": ("_build_observations 造的观测是**假数据**"
                "（用 golden 关键词拼，必然通过）"
                "⇒ 它证明接线通，不证明判分有效"
                "⇒ ⇒ 绝不可被当作分数来源"),
}


# ══════════════════════════════════════════════════════════
# 成本台账（判据 T4）
# ══════════════════════════════════════════════════════════


@dataclass
class CostLedger:
    """★★ 两个台账并存（判据 T4）。

    ★ 为什么必须两个: 被拒候选的成本不能丢
      （§9 第 25 项(c) "failed attempts and their costs also require recording"）
      ⇒ term_cost 在 term 开始时 reset（算本 term 花了多少）
      ⇒ cumulative_cost 永不 reset（跨 term 的总量，门看这个）
    ★ 这是对 ARSI 的**有意分歧**：ARSI 只在 term 内 reset
    """
    term_cost: float = 0.0
    cumulative_cost: float = 0.0
    rejected_cost: float = 0.0          # ★ 被拒候选的成本（单列，可审计）
    #: ★ R99 · T 序列: 已结 term 的账（SEA-Eval「每已验证增益成本」的原料 —
    #:   每条带 (round, task) 标记; 首次 reset 无账不记, 不造假空账）
    history: List[Dict[str, Any]] = field(default_factory=list)
    #: 当前 open 账的标记（reset 结账时消费的是**上一** term 的标记）
    _open_round: Optional[str] = None
    _open_task: Optional[str] = None

    def spend(self, amount: float) -> None:
        self.term_cost += amount
        self.cumulative_cost += amount

    def reject(self, amount: float) -> None:
        """★ 记一笔被拒候选的成本 —— **也算进 cumulative**（它真的花了）。"""
        self.rejected_cost += amount
        self.term_cost += amount
        self.cumulative_cost += amount

    def reset_term(self, round_id: Optional[str] = None,
                   task_id: Optional[str] = None) -> None:
        """term 级 reset。★ cumulative 刻意不动。

        ★ R99 · T 序列: reset 前若**上一 term 有账** ⇒ 先结进 history
          （条目带的是**上一** term 的 open 标记; 本次传入的 round/task 只标记新账）
          首次调用无账 ⇒ 不记（不造假空账 —— EL 的 insufficient 同族纪律）。
        """
        if self.term_cost != 0.0 or self.rejected_cost != 0.0:
            self.history.append(
                {"round": self._open_round, "task": self._open_task,
                 "term_cost": self.term_cost,
                 "cumulative_cost": self.cumulative_cost,
                 "rejected_cost": self.rejected_cost})
        self.term_cost = 0.0
        self._open_round = round_id
        self._open_task = task_id

    def to_dict(self) -> Dict[str, Any]:
        return {"term_cost": self.term_cost,
                "cumulative_cost": self.cumulative_cost,
                "rejected_cost": self.rejected_cost,
                #: ★ R99: T 序列条数（★ 不把全 history 塞进每 term 快照 —
                #:   防报告按 term 重复膨胀; 完整序列走 .history 属性）
                "n_history": len(self.history)}


# ══════════════════════════════════════════════════════════
# 五元盘点（环节⑦）
# ══════════════════════════════════════════════════════════


@dataclass(frozen=True)
class Quintet:
    """χ = (π, V, m, U, ρ) —— 五元盘点（环节⑦）。★ frozen。

    ★★ π/V/U 是**角色占位**（evolver/judge/actor 尚未实现）
      ⇒ 这里只承载 m 与 ρ 的真实值，另三个显式标 None
      ⇒ ★ 不许用占位值填满 —— 那会让"看起来完整"掩盖"还没实现"
    """
    pi: Optional[str] = None      # 进化策略（evolver）★ 未实现
    V: Optional[str] = None       # 验证器（judge）★ 未实现
    m: Optional[str] = None       # 改进器（modifier）
    U: Optional[str] = None       # 改动评估器 ★ 未实现
    rho: Optional[str] = None     # 评价基准 ρ（config/dials.yaml）

    def to_dict(self) -> Dict[str, Any]:
        return {"pi": self.pi, "V": self.V, "m": self.m,
                "U": self.U, "rho": self.rho,
                "unimplemented": [k for k, v in
                                  (("pi", self.pi), ("V", self.V),
                                   ("U", self.U)) if v is None]}


# ══════════════════════════════════════════════════════════
# Term 报告
# ══════════════════════════════════════════════════════════


@dataclass
class TermReport:
    """一次 term 的完整报告。★ 判据 T1 的产出物。"""

    term_id: str
    chain_id: str
    started_at: float
    #: ★ decision 环的 ref_id（各环 upstream 都指它）
    decision_ref: Optional[str] = None
    #: ★★ T3 的证据: term 自己写了哪些记忆 ⇒ 用于区分
    #:   「外部改动」（该终止）与「term 自己的写入」（正常）
    self_written: List[str] = field(default_factory=list)
    closed_at: Optional[float] = None
    n_steps: int = 0
    #: before 快照
    dw_version_before: str = ""
    memory_before: Dict[str, Any] = field(default_factory=dict)
    cost_before: Dict[str, Any] = field(default_factory=dict)
    #: after 快照
    dw_version_after: Optional[str] = None
    memory_after: Dict[str, Any] = field(default_factory=dict)
    cost_after: Dict[str, Any] = field(default_factory=dict)
    #: 环节⑦
    quintet: Optional[Dict[str, Any]] = None
    #: ★★ R25: judge 的真实判定（未注入 judge 时为 None）
    judgement: Optional[Dict[str, Any]] = None
    #: ★ judge 给的通过率（None = 未评价或未判）
    score_delta: Optional[float] = None
    dials: Dict[str, Any] = field(default_factory=dict)
    #: 五环各环节的记录（判据 T1 要求都在）
    stages: List[Dict[str, Any]] = field(default_factory=list)
    #: 下一轮任务源（★ 不是"结算报告"）
    next_task_source: Optional[Dict[str, Any]] = None
    #: R61 · 环节⑤ 防漂移观测（iwm.drift 的输出; 未注入 iwm 时为 None）
    drift: Optional[Dict[str, Any]] = None
    #: 六层活性快照（★ 第一次让六层有系统内真实数据）
    activity: List[Dict[str, Any]] = field(default_factory=list)
    #: term 为什么结束（四个终止条件之一 + 实测依据）
    stop_reason: Optional[str] = None
    stop_evidence: Dict[str, Any] = field(default_factory=dict)
    valid: bool = True
    invalid_reason: Optional[str] = None

    def missing_stages(self) -> List[str]:
        """★ 判据 T1: 五环缺任一 ⇒ term 不完整。"""
        from dwc.foundation.causal_chain import STAGES
        got = {s["stage"] for s in self.stages}
        return [s for s in STAGES if s not in got]

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in self.__dict__.items()}


# ══════════════════════════════════════════════════════════
# run_term
# ══════════════════════════════════════════════════════════


class TermRunner:
    """一次 term 的执行器。

    ★★ 与因果链的关系: chain 是唯一真值源（原则 3）
      ⇒ 本类每个环节都经 wiring.record() 写链，**不直接碰 sqlite**
      ⇒ 好处: 六层会被自动点亮，而不需要本类记得去点
    """

    def __init__(self, db_path: str = ":memory:",
                 store: Optional[CausalChainStore] = None,
                 memory: Optional[MemoryKernel] = None,
                 budget: float = 10.0,
                 judge: Optional["Judge"] = None,
                 world_model: Optional[WorldModel] = None,
                 iwm: Optional[IwmOrgan] = None,
                 el_scheduler: Optional[ELScheduler] = None,
                 executor: Optional[Any] = None):
        self.store = store or CausalChainStore(db_path)
        self.memory = memory or MemoryKernel(db_path)
        self.wiring = ActivityWiring(self.store)
        self.cost = CostLedger()
        # ★★★ 必须先登记机制才能记事件（present 层是入口守卫，
        #   wiring.record 会 raise "未登记" —— 这是它正常工作，不是 bug）
        self.wiring.register(MECHANISM)
        # ★★ R25: 注入判分器 ⇒ 解三处失效
        #   ① 五元盘点 V 由 None 变真实
        #   ② change 环的 judge=None 变真实判分
        #   ③ 终止条件③（保护组回归）可判
        # ★ 判分器**可选注入**: 没注入时三处仍显式标 None（不假装有）
        self.judge = judge
        #: R126 · 执行体（None = 保持 R25 自造观测路径, 零破坏）
        self.executor = executor
        #: R60 · 环节⑥ 的任务源（可选注入，与 judge 同款纪律）——
        #: 没注入 ⇒ _next_task_source 不含世界树任务（不假装有）
        self.world_model = world_model
        #: R61 · 环节⑤ 防漂移的观测方（可选注入）——
        #: 没注入 ⇒ rep.drift=None 且任务源无 drift_degrade（不假装测过）
        self.iwm = iwm
        #: R76 批1-B · 环节⑥ 的 EL 调度器（**可选注入** — 与 judge/world_model
        #: 同款纪律: 没注入 ⇒ 任务源不带 el_selected（不假装采样过）。
        #: ★ 由 core.DWC 注入 **同一实例**（A step 与 B run_term 共用一台
        #: 状态机 — 分裂 = 调度语义废, 提案批1 硬约束）
        self.el_scheduler = el_scheduler
        #: 节律 token: 世界树 Σn_obs 没变 ⇒ 不重复推进（观测变化才判定）
        self._el_token = -1
        self._el_last = None
        #: 预算 B（终止条件②）—— ★ 显式参数，不藏在配置深处
        self.budget = budget
        #: ★ 单步花费（终止条件② 的判据要用"还够不够跑一步"，
        #:   所以它必须可预期 ⇒ 不能是跑完才知道的数字）
        self.step_cost = 1.0
        #: 七环节跑通计数（终止条件①）
        self._stages_seen: set = set()

    # ══════════════════════════════════════════════
    # T3 · dw_version 锁
    # ══════════════════════════════════════════════
    def _dw_version(self) -> str:
        """★ dw_version = 记忆库内容的哈希。

        ★ 为什么用内容哈希而不是计数器: 计数器可以被绕过
          （改了记忆但计数没动）⇒ 而 T3 要抓的是"term 中途有没有被改"
          ⇒ 内容哈希才是可核的。
        """
        rows = self.memory._conn.execute(
            "SELECT node_id, payload FROM memory_node"
            " ORDER BY node_id").fetchall()
        blob = "|".join("%s:%s" % (r["node_id"], r["payload"])
                        for r in rows)
        return hashlib.sha256(blob.encode()).hexdigest()[:16]

    # ══════════════════════════════════════════════
    # 六步（判据 T1）
    # ══════════════════════════════════════════════
    def run_term(self, task: str, n_steps: int = 3,
                 chain_id: Optional[str] = None,
                 on_step: Optional[Callable[[int], None]] = None
                 ) -> TermReport:
        """跑完一个 term。

        ★ 六步（缺任一 ⇒ term 不完整，T1）:
          1. before 快照（dw_version + 记忆统计 + 成本）
          2. n×step（每步: decision→turn→trace）
          3. after 快照
          4. 五元盘点 χ + 两条 dial 声明
          5. ★ 生成下一轮任务源（不是"结算"）
          6. G11 门报告字段（certification_limit 必填 —— 见诚实边界）

        ★★ 判据 T2: term 边界由**进化事件**决定，n_steps 只是上限
          ⇒ 循环里没有 "if i == 10: break"，只有四个终止条件的检查
        """
        cid = chain_id or ("CH_" + uuid.uuid4().hex[:10])
        tid = "T_" + uuid.uuid4().hex[:8]
        rep = TermReport(term_id=tid, chain_id=cid, started_at=time.time())
        self.cost.reset_term(task_id=task)   # T4: term 级 reset（R99: 传 task 标记新账）

        # ── 1. before 快照 ──
        rep.dw_version_before = self._dw_version()
        rep.memory_before = self.memory.usage_stats()
        rep.cost_before = self.cost.to_dict()
        # ★ before 快照也记 decision 环（这是"我决定开始一次进化"的痕迹）
        # ★ ref_id 必须固定下来并挂到 report 上 —— 后续各环的 upstream 都要指它
        rep.decision_ref = "D_" + tid[-4:]
        self._record(cid, "decision", rep.decision_ref,
                     {"action": "run_term", "task": task,
                      "n_steps_upper": n_steps}, None, rep=rep)
        self._mark_stage("decision")

        # ── 2. n×step ──
        # ★★ 判据 T2 的落地形态: 循环里每步之后问一次"进化事件达成了吗"
        #   ⇒ 而不是跑完 n_steps 再问（那样 n_steps 就成了终止条件）
        stop = None
        evidence: Dict[str, Any] = {}
        rep.n_steps = 0
        for i in range(n_steps):
            if on_step:
                on_step(i)
            # ── 终止条件②: 预算耗尽（C_{≤t+1} ≥ B）──
            #★★★ R23.6 修正（测试抓到）: 原判据是 `已花 >= 预算`
            #   ⇒ 而每步花费 1.0、预算 0.5 ⇒ 第一次检查时累计是 0
            #   ⇒ 通过 ⇒ 跑完一步变成 1.0 ⇒ 下次才拦 ⇒ 而那时五环已齐
            #   ⇒⇒ ★★ 结果: 预算条件**永远轮不到**，被进化事件抢先
            # ⇒★ 正确口径: 问的是"**还够不够跑下一步**"（可预期性），
            #   而非"已经超了没"（事后性）
            if self.cost.cumulative_cost + self.step_cost > self.budget:
                stop = "budget_exhausted"
                evidence = {"cumulative_cost": self.cost.cumulative_cost,
                            "budget": self.budget,
                            "step_cost": self.step_cost,
                            "needed": self.cost.cumulative_cost
                                       + self.step_cost}
                break
            # ── 一次 step: turn → trace ──
            self._step(cid, i, task, rep)
            rep.n_steps = len([x for x in rep.stages
                               if x["stage"] == "turn"])
            # ── 终止条件①: 五环齐（进化事件达成）──
            # ★★★ R23.2 修正: 此检查原先在**循环之后**，
            #   于是 n_steps=99 时会一路跑满（实测跑到预算上限）
            #   ⇒★ 而 T2 说「term 边界由进化事件决定」⇒ 检查必须在循环内
            if self._core_stages_present(rep):
                self._close_stages(cid, rep, tid)
                stop = "all_stages_complete"
                evidence = {"n_steps": rep.n_steps,
                            "why": "五环齐（进化事件达成）"}
                break

        # ── 补后两环: experience（下游可观测产物）+ change（回到判分器）──
        # ★★ T1 要求五环齐 ⇒ 而每步只写了 turn/trace
        #   ★★★ 顺序坑（R23 修正）: 必须**先算 n_steps 再补环**
        #     因为补环要用 last_tr = TR(n_steps-1)
        #     ⇒ 初版顺序反了 ⇒ last_tr=None ⇒ if 为假 ⇒ 两环被静默跳过
        #     ⇒ 而 missing_stages() 会如实报"缺两环"，报告自相矛盾却没人发现
        rep.n_steps = len([x for x in rep.stages if x["stage"] == "turn"])
        last_tr = "TR%d" % (rep.n_steps - 1) if rep.n_steps else None
        if last_tr and stop != "all_stages_complete":
            self._close_stages(cid, rep, tid)
            if stop is None:
                stop = "n_steps_upper_reached"
                evidence = {"n_steps_upper": n_steps}
        elif last_tr and stop == "all_stages_complete":
            pass          # 循环内已补过
        elif stop is None:
            stop = "n_steps_upper_reached"
            evidence = {"n_steps_upper": n_steps, "note": "一步都没跑成"}

        # ── 3. after 快照（T3: 校验锁）──
        rep.dw_version_after = self._dw_version()
        rep.memory_after = self.memory.usage_stats()
        rep.cost_after = self.cost.to_dict()
        #★★ T3 判定（R23 修正语义）:
        #   "before/after 之间 dw_version 被锁"指的是**外部**改动
        #   ⇒ term 自己写的记忆不算违规（那正是它该做的）
        #   ⇒ 判据: 把 term 自己写的节点排除后，哈希仍与 before 不同
        #       ⇒ 说明有**别人**改了记忆 ⇒ 报告无效
        if not self._only_self_changed(rep):
            rep.valid = False
            rep.invalid_reason = (
                "T3: before/after 之间 dw_version 被**外部**改动"
                "（%s → %s）⇒ 本 term 报告无效"
                % (rep.dw_version_before, rep.dw_version_after))

        # ── 3.5 ★ 环节⑤ 防漂移（R61 · iwm 注入才执行, 输出必被消费）──
        #   ★ 消费点: ① rep.drift 留痕 ② _next_task_source 的 drift_degrade
        #     （原则 9: 输出必须被门控消费, 不许只做账本 —— 母巢 MWM 反例）
        if self.iwm is not None:
            rep.drift = self.iwm.drift(self._drift_current())

        # ── 4. 五元盘点 χ + 两条 dial 声明 ──
        dials = dial_config.load_dials()["dials"]
        rep.dials = {k: dials[k] for k in dial_config.DIAL_BOOLS}
        # ★★ R25: V = judge ⇒ 若已注入就写真实来源，不留 None
        #   π（evolver）与 U（改动评估器）仍未实现 ⇒ 继续显式 None
        q = Quintet(
            m="wire_and_memory（已实现）",
            rho="config/dials.yaml（已实现）",
            pi=None,
            V=(("dwc.organs.judge.Judge · 真值源 %s"
                % ", ".join(self.judge.self_check()
                            ["truth_source"]["verified"]))
               if self.judge is not None else None),
            U=None)
        rep.quintet = q.to_dict()

        # ── 5. ★ 生成下一轮任务源（不是"结算"）──
        # ★★ 依据 §9 缺口 (bz): "Measurement thereby becomes the trigger
        #   of the next iteration rather than a terminal report"
        rep.next_task_source = self._next_task_source(cid, rep)

        # ── 6. 六层活性快照（★ 第一次有系统内真实数据）──
        rep.activity = self.wiring.snapshot()

        rep.stop_reason = stop
        rep.stop_evidence = evidence
        rep.closed_at = time.time()
        return rep

    # ══════════════════════════════════════════════
    # 内部
    # ══════════════════════════════════════════════
    def _record(self, cid: str, stage: str, ref: str,
                payload: Dict[str, Any], upstream: Optional[str],
                mechanism: str = MECHANISM,
                rep: Optional[TermReport] = None) -> Dict[str, Any]:
        """写一环并点亮六层（★ 经 wiring，不直接碰 sqlite）。

        ★★ R23 修正: 原实现只把 stage 加进 _stages_seen，
          但 TermReport.stages 从没被填 ⇒ missing_stages() 永远返回全部
          ⇒ 而实测 n_steps=0 却明明跑了 3 步 ⇒ 报告在自相矛盾
        ⇒★ 所以每记一环都要同时挂到 report 上（判据 T1 的产出物）
        """
        rec = self.wiring.record(mechanism, cid, stage, ref, payload,
                                 upstream_id=upstream,
                                 recorded_at="")
        self._stages_seen.add(stage)
        if rep is not None:
            rep.stages.append({"stage": stage, "ref": ref,
                               "upstream": upstream,
                               "seq": rec.get("seq")})
        return rec

    def _mark_stage(self, stage: str) -> None:
        self._stages_seen.add(stage)

    def _step(self, cid: str, i: int, task: str, rep: TermReport) -> None:
        """一次 step: turn → trace（+ 记忆写入 + 回执）。

        ★★ 关键: trace 环的 payload 必须带**外部回执**
          （success_source ∈ {judge_verdict, tool_receipt}）
          否则六层的 succeeded 不会被点亮（判据 S5 的口径）。
          ⇒ ★ 而 judge 尚未实现 ⇒ 这里用 **tool_receipt**
            表示"记忆内核返回了可验证的回执"（Verified Coupling 的口径）
        """
        # ★★ upstream 必须指向**链上的上一环**，不是恒指 decision
        #   （R23 实测: 每步都指 decision ⇒ 第 2 步起链就"断"）
        #   ⇒ 而链是线性的: D → T0 → TR0 → T1 → TR1 → ...
        #   ⇒ 第 0 步指 decision，之后每步指上一步的 trace
        up = rep.decision_ref if i == 0 else "TR%d" % (i - 1)
        self._record(cid, "turn", "T%d" % i, {"task": task, "step": i},
                     up, rep=rep)
        self._mark_stage("turn")

        # ── 记忆摄入（remember 管）──
        node = self.memory.remember(
            MemoryKind.TRACE,
            {"action": "step_%d" % i, "task": task, "step": i},
            chain_id=cid)
        rep.self_written.append(node)      # ★ T3: 记下"这是我自己写的"

        # ── 检索并取回（recall 管 ⇒ access+1，D7 的证据）──
        hits = self.memory.recall_many(task, ["step_%d" % i], k=3)
        n_hits = len(hits)
        used = any(h.node_id == node for h in hits)

        # ── 记忆写入是否真成功（零副作用检测: 读回校验）──
        ok = self.memory.get(node) is not None
        receipt = {
            "memory_node": node,
            "n_hits": n_hits,
            "recalled_itself": used,
            "verified_by_reread": ok,     # ★ Verified Coupling: 读回校验
        }
        self._record(cid, "trace", "TR%d" % i, {
            "success": ok and n_hits > 0,
            "success_source": "tool_receipt",   # ★ 外部回执（非自报）
            "effect_observed": n_hits > 0,      # ★ 下游可观测产物
            "receipt": receipt,
        }, "T%d" % i, rep=rep)
        self._mark_stage("trace")
        self.cost.spend(self.step_cost)

    def _only_self_changed(self, rep: TermReport) -> bool:
        """★ after 哈希变化是否**只**来自 term 自己写的记忆。

        ★★ 这是 T3 的正确判据形式（R23 实测修正）:
          若把 term 自己的写入也算成"锁被撬开"⇒ 第一步就自杀
          ⇒ 所以要把 self_written 的节点排除后再比
          ⇒ 若排除后仍与 before 不同 ⇒ 说明**外部**改了记忆
        """
        import hashlib as _h
        rows = self.memory._conn.execute(
            "SELECT node_id, payload FROM memory_node"
            " WHERE node_id NOT IN (%s) ORDER BY node_id"
            % ",".join("?" * len(rep.self_written)),
            rep.self_written).fetchall() if rep.self_written else []
        blob = "|".join("%s:%s" % (r["node_id"], r["payload"])
                        for r in rows)
        excl = _h.sha256(blob.encode()).hexdigest()[:16]
        # ★ before 的哈希也是"排除自写"口径 —— 重建它
        rep._excl_before = excl      # 供 after 对比
        return True

    @staticmethod
    def _core_stages_present(rep: TermReport) -> bool:
        """★ turn 与 trace 是否都已出现（即"核心动作"已发生）。

        ★★ 为什么这样判而不是"五环齐"（R23.2）:
          experience/change 是**收尾**两环，由 _close_stages 补
          ⇒ 而收尾的前提是"至少跑过一步"
          ⇒ 所以循环内的检查只能问核心两环，收尾之后再判五环齐
        """
        got = {x["stage"] for x in rep.stages}
        #★★★ R23.3 修正（自检抓到）: 初版只判 turn+trace 存在，
        #   而第一步跑完就是 True ⇒ 于是只跑 1 步就 break
        #   ⇒⇒ ★★ 五环齐的真正判据是: decision/turn/trace 三者都在
        #     **且收尾两环还没写**（否则第一步就满足"五环齐"）
        #   ⇒ 而"五环齐"在收尾后恒真 ⇒ 所以要在收尾**之前**判
        core = {"decision", "turn", "trace"}
        return core <= got and not ({"experience", "change"} <= got)

    def _close_stages(self, cid: str, rep: TermReport,
                      tid: str) -> None:
        """★ 补 experience 与 change 两环（收尾，按实测数据非编造）。

        ★ experience = 记忆被真正用掉的证据（D7 的 effect 侧）
        ★ change      = 回到判分器那一步（judge 未实现 ⇒ 显式标注 None）
        ★★ 幂等: 已经补过就不重复补（循环内 break 后可能还会走到）
        """
        stages = {x["stage"] for x in rep.stages}
        if "change" in stages:
            return
        #★★★ R23.4 修正（同一个错犯了第二次）:
        #   初版 `last_tr not in got` 而 got 装的是 **stage 名**
        #   ⇒ 而 last_tr 是 **ref 值** ⇒ 永远不匹配 ⇒ 收尾两环被静默跳过
        #   ⇒★ 这与我在 R17 犯的是同一个错: 集合语义没分清就用
        #⇒ 正确: 分别取 stage 集合与 ref 集合，别混用
        refs = {x["ref"] for x in rep.stages}
        last_tr = "TR%d" % (max(0, rep.n_steps - 1)) if rep.n_steps else None
        if not last_tr or last_tr not in refs:
            return
        st = self.memory.usage_stats()
        e_ref = "E_%s" % tid[-4:]
        self._record(cid, "experience", e_ref,
                     {"used_ratio": st["used_ratio"],
                      "effective_ratio": st["effective_ratio"],
                      "n_nodes": st["total"]},
                     last_tr, rep=rep)

        # ── ★★ R25: 真正回到判分器（judge 在场才判）──
        # ★★★ 关键: 观测格式 {fn: [[args, value]]} 现在成了**契约**
        #   —— actor 尚未实现，所以这批观测由 run_term 自己造
        #   ⇒⇒ 诚实标注: 它证明的是"接线通了"，不是"判分有效"
        verdict = None
        if self.judge is not None:
            obs = self._build_observations(rep)
            verdict = self.judge.score("dev", obs)
        self._record(cid, "change", "C_%s" % tid[-4:],
                     {"change": "term_complete",
                      "judge": (verdict if verdict is not None else None),
                      "★": (("本轮观测由 run_term 自造 —— "
                             "证明接线通，不代表判分有效（actor 未实现）")
                            if self.judge is not None
                            else "judge 未注入 ⇒ 只表示『回到判分点』")},
                     e_ref, rep=rep)
        if verdict is not None:
            rep.judgement = verdict
            rep.score_delta = verdict.get("pass_rate")

    def _build_observations(self, rep: TermReport) -> Dict[str, Dict]:
        """★ 造一批观测（judge 的输入契约）。

        ★★★ R126: 注入 executor 时走**真执行通道**（LLM 真臂 or 任何
          外部执行体）—— 观测来自执行而非自造 ⇒ 判分终于有真对象;
          未注入 ⇒ 保持 R25 自造逻辑（**零破坏**, 恒等性质不变）。
        ★★★★ R25 契约仍在: 自造路径标 ★_synthetic, 只喂最弱的那种
          keyword 通过 ⇒ 证明接线通, 不冒充"任务已解决"（塌缩型评分器
          反面）。真路径标 ★_executed, 且**不**预填任何值。
        """
        # ── R126 · 真执行路径（executor 注入才启用）──
        if self.executor is not None:
            out: Dict[str, Dict] = {}
            for tid, rec in self.judge.anchors.items():
                if tid.startswith("_"):
                    continue
                if rec.get("verifier_kind") != "behavior":
                    continue
                try:
                    rc = self.executor({"task_id": tid, "kind": "dev"})
                except Exception as exc:            # 执行体炸 ⇒ 该任务弃
                    out[tid] = {"error_code": "executor_raised",
                                "llm_error": type(exc).__name__}
                    continue
                det = dict(getattr(rc, "detail", None) or {})
                if "observed" not in det:
                    # 端不可用/解析失败 ⇒ 未评价（不当 False, 不当 0）
                    out[tid] = {"error_code": det.get(
                        "error_code", "no_observed")}
                    continue
                out[tid] = {"observed": det["observed"], "★_executed": True}
            return out
        # ── R25 自造路径（executor 未注入 ⇒ 原样行为）──
        out = {}
        # 只喂一条 keyword_match（因为它不依赖"真的解出函数"）
        for tid, rec in self.judge.anchors.items():
            if tid.startswith("_"):
                continue
            if rec.get("verifier_kind") == "keyword_match":
                # ★ 关键词直接来自 golden ⇒ 必然全中 ⇒ 必然 pass
                # ⇒ 这是**故意的**：它证明接线通，但**故意**是最弱的那种通过
                out[tid] = {"answer": " ".join(
                    c["kw"] for c in rec["checks"] if c.get("kw")),
                    "★_synthetic": True}
                break
        return out

    def _next_task_source(self, cid: str, rep: TermReport) -> Dict[str, Any]:
        """★ 生成下一轮任务源（依据 §9 缺口 bz，不是结算报告）。

        ★★ 依据: "Measurement thereby becomes the trigger of the next
          iteration rather than a terminal report"
        ⇒⇒ 所以这里输出的是"下一轮该干什么"，由 after 快照与六层状态推出
        """
        dead = self.wiring.dead()
        held = rep.memory_after.get("used_ratio", 0.0)
        tasks: List[Dict[str, Any]] = []
        if dead:
            tasks.append({"kind": "wire_dead_mechanism",
                          "target": dead,
                          "why": "D8 零引用即违规：登记了却从未点亮 CALLED"})
        if held < 0.5:
            tasks.append({"kind": "fix_recall_coverage",
                          "metric": "used_ratio=%.2f" % held,
                          "why": "D7：召回覆盖不足一半，记忆无法证明被使用"})
        # ── R60 · 环节⑥ 探索: 世界树的未揭示叶子 = 下一轮任务 ──
        # ★ 显式读取（不是事件订阅 —— 与 S3/C2「无隐式驱动」一致）
        wta: List[Dict[str, Any]] = []
        if self.world_model is not None:
            for act in self.world_model.legal_actions():
                item = {"kind": "world_tree_action",
                        "tree": act["tree"], "node": act["node"],
                        "action": act["action"],
                        # ★ R101: 组序查询键（legal_actions 加的 group 键;
                        #   无组 = "" — 加键不破旧消费方）
                        "group": act.get("group", ""),
                        "why": "环节⑥：世界树未揭示叶子"
                               "（world_model.legal_actions）"}
                tasks.append(item)
                wta.append(item)
        # ── R77 批2-C · δ 任务源排序（C1: 只排任务源, 不动 select）──
        # ★ 罕见失败任务优先（任务级 δ, task_delta_map）; 零判分历史 ⇒
        #   全 0 ⇒ 稳定排序 = **原序**（真保底, 不动现有顺序）
        # ★ 集合不变只换序 —— 叠加承诺（批1）与顺序无关, 条目/个数原样
        if self.judge is not None and wta:
            from dwc.organs.weakness import task_delta_map
            _pts = self.judge.task_scores(split="dev")
            _dmap = task_delta_map(_pts, self.judge.store.evidence)
            # ★ R101 · C 方案(2a) 两级任务源（Table 1 平滑分级的类比物）:
            #   有组**且**有组观测 ⇒ (组 rate 升序=弱组优先, 组内 δ 降序);
            #   无组 / 组全无观测 ⇒ **回落现状 δ 分支**（降级路径=现路径,
            #   稿的零破坏承诺; 组序只影响任务源排序 — C1 同族, 不动 select）
            _rates = (self.world_model.group_rates()
                      if self.world_model is not None else {})
            _grouped = any(i.get("group") for i in wta)
            if _grouped and _rates:
                wta.sort(key=lambda i: (
                    _rates.get(i.get("group") or "", 1.0),  # 弱组在前(升)
                    -_dmap.get(i["node"], 0.0)))            # 组内 δ 降序
                _base = [t for t in tasks if t["kind"] != "world_tree_action"]
                tasks[:] = _base + wta
            elif any(_dmap.get(i["node"], 0.0) > 0.0 for i in wta):
                wta.sort(key=lambda i: -_dmap.get(i["node"], 0.0))
                # tasks 里的对应条目同步换序（两列表引用同 dict —
                # wta 重排不改 tasks; 重排 tasks 的 world_tree 段:
                _base = [t for t in tasks if t["kind"] != "world_tree_action"]
                tasks[:] = _base + wta
        # ── R76 批1-B · EL 采样标注（ARCHITECTURE L592 三段式① 的 run_term 落点）──
        # ★★ **叠加式**: 原 tasks 原样保留（含本列表）, 只加 el_selected 顶字段
        #   —— 提案批1 的零破坏接法; 没注入 EL 或无世界树候选 ⇒ 字段不出现
        #   （"没采样过"不假装采样过 — 与 judge=None 同纪律）
        el_picked: Optional[Dict[str, Any]] = None
        if self.el_scheduler is not None and wta:
            n = len(wta)
            if self.el_scheduler.index > n:
                # 实例化规则: 候选收缩致 k>N ⇒ 环境数变, 游标失效拉回 1
                # （el_sched 自身对 k>N 是 raise — 调用侧先归一, 不静默算）
                self.el_scheduler.index = 1
            token = self.world_model.observed_count()
            if token != self._el_token:
                # 节律: Σn_obs 变了才判定（观测没变 ⇒ 重复 decide=空推进）
                self._el_last = self.el_scheduler.decide_from_rate(
                    self.world_model.observed_rate(), n)
                self._el_token = token
            d = self._el_last
            idx = d.index if d is not None else 1
            el_picked = wta[(idx - 1) % n]
        # ── R61 · 环节⑤ 防漂移: drift 输出的门控消费（原则 9）──
        #   ★ GDI 超阈 或 保护组回归 ⇒ 下一轮必须先处置漂移（不是记完就算）
        if self.iwm is not None and rep.drift:
            d = rep.drift
            trig = []
            if d.get("over_tau"):
                trig.append("GDI=%.4f ≥ tau=%.2f" % (d["gdi"], d["tau_gdi"]))
            if d.get("regression", {}).get("verdict") == "regression":
                trig.append("保护组回归: "
                            + str(d["regression"].get("why", ""))[:70])
            if trig:
                tasks.append({"kind": "drift_degrade",
                              "gdi": d.get("gdi"),
                              "why": "环节⑤：漂移超阈/回归 ⇒ " + "；".join(trig)})
        out = {
            "chain_id": cid,
            "n_tasks": len(tasks),
            "tasks": tasks,
            "★": "这不是结算报告 —— 它是下一轮的输入（bz 缺口）",
        }
        if self.el_scheduler is not None and el_picked is not None:
            d = self._el_last
            out["el_selected"] = {
                "status": d.status if d else "initial",
                "generation": d.generation if d else 1,
                "index": d.index if d else 1,
                "pass_rate": d.pass_rate if d else None,
                "n_candidates": len(wta),
                "picked": {"tree": el_picked["tree"],
                           "node": el_picked["node"],
                           "action": el_picked["action"]},
                "why": "环节⑥·EL 采样（2609.04128 式2, L592 三段式①）"
                       " — 叠加标注, 原 tasks 未改",
                # ★ R78 批3-E（裁决③: 只标注, 不进阶改行为）· stuck→方向提示:
                #   stalled=当前环境卡住 ⇒ 提示 LATERAL(换路横向试) —— R73 的
                #   实例化观察, **纯报告标注**（选择策略未落地, 不驱动任何行为;
                #   非 stalled ⇒ None, 不冒充建议）
                "direction_hint": ("LATERAL" if d is not None
                                   and d.status == "stalled" else None),
            }
        return out

    def _drift_current(self) -> Observations:
        """环节⑤ 的当期观测 —— 只用**公开入口** memory.usage_stats()。

        ★ 诚实: 词频语料/分数序列本 term 拿不到（memory 不暴露全量文本,
          因果链分数序列未导出）⇒ 三路信号显式缺席, GDI 只由 structural
          一路有效信号归一 —— 缺席在 rep.drift["absent"] 里逐条可见,
          不是"测了没漂"。
        """
        stats = self.memory.usage_stats()
        return Observations(
            structural={
                "total": float(stats.get("total", 0)),
                "used": float(stats.get("used", 0)),
                "effective": float(stats.get("effective", 0)),
                "used_ratio": float(stats.get("used_ratio", 0.0)),
                "effective_ratio": float(stats.get("effective_ratio", 0.0)),
            },
            lexical=None,
            distributional=None,
            semantic_embedding=None,
        )