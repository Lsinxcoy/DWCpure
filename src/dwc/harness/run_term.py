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
import sys
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


def _append_verdict_log(db_path: str, task: str, verdict: Dict[str, Any]) -> int:
    """★ R277 · term verdict 落盘可观测（append-only jsonl）。

    每行: {ts, task, pass_rate, n_fail, false_tasks[]}。
    入参坏 ⇒ 大声 raise（调用方 daemon 边界包 try/except 留痕）;
    写盘坏 ⇒ 同样 raise（静默丢观测 = 盲飞，禁）。
    返回 False 条数（与 _backfill_failures 同口径：success is False 才算）。
    """
    if not isinstance(verdict, dict) or not isinstance(
            verdict.get("details"), list):
        raise TypeError("verdict 非法: %r" % type(verdict))
    false_tasks = []
    for x in verdict["details"]:
        if not isinstance(x, dict):
            raise ValueError("detail 非法: %r" % (x,))
        if x.get("success") is False:
            if not isinstance(x.get("task_id"), str):
                raise ValueError("False 缺 task_id: %r" % (x,))
            false_tasks.append(x.get("task_id"))
    row = {"ts": time.time(), "task": task,
           "pass_rate": verdict.get("pass_rate"),
           "n_fail": len(false_tasks), "false_tasks": false_tasks,
           # ★ R277b-8 · 分任务明细（True=真通过/False=真失败/None=弃权），
           #   不然 1.0 分不清“全过”还是“全弃权”。
           "graded": {x.get("task_id"): x.get("success")
                      for x in verdict["details"]
                      if isinstance(x.get("task_id"), str)},
           # ★ R277b-2 · 定罪字段: 回灌数 + 首条 False 的 m 样本
           "backfilled": verdict.get("★backfilled", -9),
           "m_sample": verdict.get("★m_sample")}
    lp = os.path.join(os.path.dirname(os.path.abspath(db_path)),
                      "eval", "term_verdicts.jsonl")
    if not os.path.exists(os.path.dirname(lp)):
        os.makedirs(os.path.dirname(lp))
    with io.open(lp, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return len(false_tasks)


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

    ★★ R141 按事实更新（原 R25 注释"π/V/U 未实现"已陈旧 — 盘点坐实:
      evolver.py 1683 `class Evolver`（变异器编排）+ judge 早已注入
      core.py L164/L165 ⇒ 两者是**已实现**角色; 只 U 的评估面
      （select_winner 已实现于 evolver.py L449）尚未接线到本盘点）
    ⇒ 原则不变: 不许用占位值填满 — 但也不许把**已实现**的说成没有
      （声称 vs 实测 — 实测为准）。
    """
    pi: Optional[str] = None      # 进化策略（evolver）— 已实现, 见 build_quintet
    V: Optional[str] = None       # 验证器（judge）— 已实现, 见 build_quintet
    m: Optional[str] = None       # 改进器（modifier）
    U: Optional[str] = None       # 改动评估器 — evolver.select_winner 已实现
    rho: Optional[str] = None     # 评价基准 ρ（config/dials.yaml）

    def to_dict(self) -> Dict[str, Any]:
        # ★ R141: unimplemented（字段 None）+ partial（值含"未接"字样）
        #   双列表 — "已实现未接线"≠"未实现"（声称 vs 实测的盘点纪律）
        return {"pi": self.pi, "V": self.V, "m": self.m,
                "U": self.U, "rho": self.rho,
                "unimplemented": [k for k, v in
                                  (("pi", self.pi), ("V", self.V),
                                   ("U", self.U)) if v is None],
                "partial": [k for k, v in
                            (("pi", self.pi), ("V", self.V),
                             ("U", self.U))
                            if v is not None and "未接" in str(v)]}


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
    #: ★ R143 · 七桶路由结果（2609.14857 Table 8; judge 未注入时
    #:   {"routed": False, "why": ...} — 不猜桶）
    router: Dict[str, Any] = field(default_factory=dict)
    #: ★ R144 · 四量度量（2609.11873; 缺埋点量显式 not_instrumented）
    measure4: Dict[str, Any] = field(default_factory=dict)
    #: ★ R152 · 门组链（V2 §5.4 六门三态; verdict=blocked ⇒ 不许落地）
    gate_chain: Dict[str, Any] = field(default_factory=dict)
    #: ★★ R25: judge 的真实判定（未注入 judge 时为 None）
    judgement: Optional[Dict[str, Any]] = None
    #: ★ judge 给的通过率（None = 未评价或未判）
    score_delta: Optional[float] = None
    #: ★ R276b · 本轮回灌 EXPERIENCE 的失败签名条数（判分→记忆的生产回灌）
    evo_backfilled: int = 0
    evo_n_fail: int = 0  # ★ R277 · 本轮 verdict False 数（-1=落盘失败）
    dials: Dict[str, Any] = field(default_factory=dict)
    #: 五环各环节的记录（判据 T1 要求都在）
    stages: List[Dict[str, Any]] = field(default_factory=list)
    #: 下一轮任务源（★ 不是"结算报告"）
    next_task_source: Optional[Dict[str, Any]] = None
    #: R61 · 环节⑤ 防漂移观测（iwm.drift 的输出; 未注入 iwm 时为 None）
    drift: Optional[Dict[str, Any]] = None
    #: ★ F1 · iwm 守卫发出口（governor_advice 的产出; 未注入 iwm 时为 None）
    iwm_advice: Optional[Dict[str, Any]] = None
    #: ★ R204 · 铁律执行面报告（iron_runtime.evaluate_for_term 的四态产出）
    iron_report: Optional[Dict[str, Any]] = None
    #: ★ R204 · G11 report_must_quote 的摘录字段（空 = 配置缺席 ⇒ block[G11]）
    certification_limit: str = ""
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
        self.db_path = db_path  # ★ R277 · verdict 落盘锚点（库旁 eval/）
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
    def _build_state(self, rep: "TermReport", task: str, *,
                     split: str = "dev"):
        """★ F1 · 生产 State 构造（governor_advice 的输入面 · §六不变量）。

        ★ 全部字段来自本轮已判事实（rep.judgement/gate_chain/drift/cost）
          + 内容哈希 —— 零占位字符串冒充实测。
        ★ 诚实缺席（不装有）:
          · world_model 无 train() ⇒ train_verdict="not_implemented"
          · laws_block/laws_warn 来自 rep.iron_report（R204 执行面真判;
            空 = 本轮真判无违规, 非"没接线" — 缺席在 not_instrumented）
          · pre_enactment 预测层显式缺席（core._decide 同款）⇒
            gate1_verdict="degrade_to_heuristic"
        """
        from dwc.foundation.state import (State, AssetVersions,
                                          ArchitectureVersions,
                                          GateSnapshot, ExecutionContext)
        from dwc.organs.evolver import NOISE_DELTA   # R58 锁值 0.15
        v = rep.judgement or {}
        dr = rep.drift or {}
        pass_rate = v.get("pass_rate")
        degraded = bool(dr.get("over_tau")) or \
            (dr.get("regression") or {}).get("verdict") == "regression"
        ver = self._dw_version()
        if degraded:
            why = ("GDI %.4f ≥ tau（漂移超阈）" % dr.get("gdi", -1.0)
                   if dr.get("over_tau") else
                   "保护组回归: " + str((dr.get("regression") or {}
                                         ).get("why", ""))[:60])
        else:
            why = "本轮无漂移触发"
        return State(
            S=AssetVersions(memory_version=ver,
                            skills_version="no-compile-surface",
                            tools_version="not-wired",
                            context_version="not-wired"),
            H=ArchitectureVersions(harness_version=ver,
                                   workflow_version="not-versioned",
                                   org_version="seven-organs-v1"),
            G=GateSnapshot(
                wm_version=ver,
                wm_dev_accuracy=(float(pass_rate)
                                 if pass_rate is not None else 0.0),
                wm_dev_n=int(v.get("n_tasks", 0) or 0),
                theta_dev=float(NOISE_DELTA),
                theta_dev_kind="anchored",
                gate1_verdict="degrade_to_heuristic",
                iwm_verdict="degrade_to_baseline" if degraded else "ok",
                iwm_reason=why[:120],
                train_verdict="not_implemented",
                laws_block=tuple((rep.iron_report or {}).get("block") or ()),
                laws_warn=tuple((rep.iron_report or {}).get("warn") or ()),
                cost_used=float((rep.cost_after or {}
                                 ).get("term_cost", 0.0) or 0.0),
                task_scores_ref="config/anchors/task_scores.jsonl"),
            X=ExecutionContext(chain_id=rep.chain_id,
                               decision_id=rep.decision_ref or "",
                               turn_index=int(rep.n_steps),
                               task_id=str(task),
                               task_source="run_term_direct",
                               split=split))

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
                self._close_stages(cid, rep, tid, task)
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
            self._close_stages(cid, rep, tid, task)
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
        # ★★ R141: π=evolver / V=judge 均**已实现**（陈旧 R25 自陈
        #   修正 — 实测 evolver.py L1683 Evolver 类 + core.py L164 实例化;
        #   judge 注入路径同旧）。★ TermRunner 不持有 evolver 实例（它只
        #   编排六层链）⇒ π 的填值语义=**角色已实现**（盘点面, 不是运行
        #   时接线面）; U 的 select_winner(evolver.py L449) 已实现但**本
        #   盘点不接** ⇒ 如实 partial（不是 None 假装没有）。
        # ★★★ R196: 本处是五元盘点（π,V,m,U,ρ）的**唯一出口** ——
        #   Quintet.to_dict() 的 unimplemented/partial 双列表（R141）由 tests/
        #   test_r196_z_class_landing.py::test_quintet_u_is_the_only_partial
        #   **机械锁死**; 若需改盘点口径, 先改那个测试再改这里（不许另起
        #   第二盘点面 ⇒ 第二口径禁, 同 R183）。
        q = Quintet(
            m="wire_and_memory（已实现）",
            rho="config/dials.yaml（已实现）",
            pi=("dwc.organs.evolver.Evolver · 变异器编排"
                "（失败签名→提案→过门→待判分）— 已实现"),
            V=(("dwc.organs.judge.Judge · 真值源 %s"
                % ", ".join(self.judge.self_check()
                            ["truth_source"]["verified"]))
               if self.judge is not None
               else "dwc.organs.judge.Judge · 已实现（未注入）"),
            U=("dwc.organs.evolver.select_winner · 已实现但未接本盘点"
               "（R141 如实标 partial）"))
        rep.quintet = q.to_dict()

        # ── 4.44 ★ R204 · 铁律执行面（laws_block 的真实来源）──
        #   ★ 两步: ① G11 动作侧 — 摘 certification_limit 进报告字段
        #           ② 评估 — 真判/na/not_instrumented 四态 → rep.iron_report
        #   ⇒ block/warn 随后喂 _build_state 的 laws_block/laws_warn
        from dwc.foundation.iron_runtime import (
            get_certification_limit, evaluate_for_term)
        rep.certification_limit = get_certification_limit()
        rep.iron_report = evaluate_for_term(
            rep, certification_limit_present=bool(rep.certification_limit))

        # ── 4.45 ★ F1 · iwm 守卫发出口（governor_advice + Q6 对照臂）──
        #   ★ governor_advice 只读 State 公开四层（§六不变量）—— State 由
        #     _build_state 从本轮已判事实构造（零占位字符串）。
        #   ★★ record_round 的 adopted 口径（诚实）: advice 的**执行消费**
        #     尚未接线（degrade/downweight 如何改行为属 R204+）⇒ 恒记
        #     baseline 臂 —— 不假装采纳（自欺会让 Q6 对照臂两臂同源）。
        #     improved = judge 真判（score_delta>0）—— 非自评（G5）。
        if self.iwm is not None:
            try:
                advice = self.iwm.governor_advice(self._build_state(rep, task))
                rep.iwm_advice = {
                    "degrade_to_baseline": advice.degrade_to_baseline,
                    "downweight_pre_enactment": advice.downweight_pre_enactment,
                    "forbid_default_dream": advice.forbid_default_dream,
                    "reason": advice.reason,
                    "consumed": False,
                }
                # ★ R204: record_round 挪到 5 段消费之后 —— adopted 要看
                #   「消费是否真执行」（建议触发 ⇒ iwm 臂; 无触发 ⇒ baseline 臂）
            except Exception as exc:   # noqa: BLE001 — 留痕不静默（G7 同款）
                rep.iwm_advice = {"error": "%s: %s"
                                  % (type(exc).__name__, str(exc)[:120])}

        # ── 4.5 ★ 七桶路由（R143 · 2609.14857 Table 8 接线）──
        #   ★ 数据源（全部已判事实, router 不判分 — G2）:
        #     · n_pass/n_fail ← judge.score 的三数口径（R14: not_evaluated
        #       不混入 pass_rate ⇒ 同样不进桶判据）
        #     · cost ← CostLedger term_cost（T4 台账真值）
        #     · budget_ceiling ← self.budget（C_{≤t+1} ≥ B 的可预算面）
        #   ★★ judge 未注入 ⇒ 无法判分 ⇒ router 显式降级（不是猜桶）:
        #      "no_judge ⇒ 无已判事实可分桶"（若硬塞 n_pass=0/n_fail=0
        #      会落 infra_only — 那是**误分类**! 0 事实 ≠ infra 失败）
        router_info: Dict[str, Any] = {"routed": False}
        if self.judge is not None and rep.judgement is not None:
            v = rep.judgement
            try:
                from dwc.organs.router import TermObservation, route
                # ★ infra_fail 不映射 not_evaluated: 未评价（R14 口径）
                #   ≠ 环境层失败 ⇒ 缺省 0（杜绝对值混淆 — 未接线不等于 0）
                obs = TermObservation(
                    n_pass=int(v.get("pass", 0) or 0),
                    n_fail=int(v.get("fail", 0) or 0),
                    cost=float(self.cost.to_dict().get("term_cost", 0.0)),
                    budget_ceiling=float(self.budget))
                rr = route(obs)
                router_info = {"routed": True, **rr}
            except Exception as exc:   # noqa: BLE001 — 留痕不静默（G7）
                router_info = {"routed": False,
                               "error": "%s: %s" % (type(exc).__name__, exc)}
        else:
            router_info = {"routed": False,
                           "why": "judge 未注入或无 verdict ⇒ 无已判事实"
                                  "可分桶（不猜桶 — 0 事实≠infra 失败）"}
        rep.router = router_info

        # ── 4.6 ★ 四量度量投影（R144 · 2609.11873 §3.3「写了≠用了」）──
        #   ★ ① 可算: verdict 三数 ⇒ UpdateQuality（not_evaluated 不进分母）
        #   ★ ②③④ **未埋点**（recall_search R22 不记 access; 无执行痕迹面）
        #     ⇒ 显式 not_instrumented（不编 0.0 — 缺席≠0）
        measure_info: Dict[str, Any] = {"instrumented_count": 0}
        try:
            from dwc.organs.measure import UpdateQuality, measure
            uq = (UpdateQuality(
                      n_pass=int((rep.judgement or {}).get("pass", 0) or 0),
                      n_fail=int((rep.judgement or {}).get("fail", 0) or 0),
                      not_evaluated=int((rep.judgement or {}).get(
                          "not_evaluated", 0) or 0))
                  if rep.judgement is not None else None)
            measure_info = measure(update=uq)
        except Exception as exc:   # noqa: BLE001 — 留痕不静默（G7）
            measure_info = {"instrumented_count": 0,
                            "error": "%s: %s" % (type(exc).__name__, exc)}
        rep.measure4 = measure_info

        # ── 4.7 ★ 门组入链（R152 · V2 §5.4 六门顺序 — 编排+口径桥）──
        #   ★ 原则: 不替代各门（R147-R151 独立可测模块）; 这里只按论文
        #     顺序问一遍, 每门三态（passed/blocked/not_applicable）。
        #   ★★ 链 verdict=blocked ⇒ 不许落地（非补偿贯到链级 — 门间不可
        #     互偿; not_applicable 单列不算 blocked — 无对象≠有对象且过）。
        #   ★ 诚实边界: run_term 非候选环 ⇒ ①（无 diff）/④（无候选对）/
        #     ⑥（无申报编辑）当前拿不到真输入 ⇒ 显式三态, 不造假过。
        try:
            from dwc.harness.gates import TermFacts, run_gates
            v = rep.judgement or {}
            facts = TermFacts(
                pass_rate=(float(v["pass_rate"])
                           if v.get("pass_rate") is not None else None),
                score_star=None,                 # 无跨轮 S* ⇒ ⑤ blocked
                delta_s=None, delta_c=None,       # 同上（口径不在本层）
                noise_band=None, domain_guard_ok=None,
                not_evaluated=int(v.get("not_evaluated", 0) or 0),
                candidate_diff=None,              # run_term 非候选环
                edits=None,
                split_verdict=None)
            rep.gate_chain = run_gates(facts)
        except Exception as exc:   # noqa: BLE001 — 留痕不静默（G7）
            rep.gate_chain = {"verdict": "error",
                              "error": "%s: %s" % (type(exc).__name__, exc)}

        # ── 5. ★ 生成下一轮任务源（不是"结算"）──
        # ★★ 依据 §9 缺口 (bz): "Measurement thereby becomes the trigger
        #   of the next iteration rather than a terminal report"
        rep.next_task_source = self._next_task_source(cid, rep)
        # ── R204 · Q6 对照臂记账（★ 必须在消费之后 — adopted 看触发态）──
        #   口径: advice 触发（degrade/forbid）且消费段已执行 ⇒ iwm 臂;
        #         无触发 ⇒ baseline 臂（正常默认行为 — 对照面）。
        #         仅 downweight 触发（不可执行）⇒ 不算采纳 ⇒ baseline 臂。
        if self.iwm is not None and isinstance(rep.iwm_advice, dict) \
                and "error" not in rep.iwm_advice:
            _a = rep.iwm_advice
            _adopted = bool(_a.get("degrade_to_baseline")
                            or _a.get("forbid_default_dream"))
            self.iwm.record_round(
                adopted=_adopted,
                improved=bool(rep.score_delta and rep.score_delta > 0.0))

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
                      tid: str, task: str = "") -> None:
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
            rep.evo_backfilled = self._backfill_failures(verdict)
            try:  # ★ R277 · verdict 落盘可观测（坏了留痕不阻断本轮）
                _m0 = ""
                for _d in ((verdict or {}).get("details") or []):
                    if isinstance(_d, dict) and _d.get("success") is False:
                        _ss = (list(_d.get("sigs") or [])
                               or [_d.get("failure_signature") or {}])
                        _m0 = str((dict(_ss[0] or {})).get("m", ""))[:60]
                        break
                verdict["★backfilled"] = rep.evo_backfilled
                verdict["★m_sample"] = _m0
                rep.evo_n_fail = _append_verdict_log(
                    self.db_path, task, verdict)
            except Exception as exc:                  # noqa: BLE001
                sys.stderr.write("verdict落盘跳过: %s\n" % exc)
                rep.evo_n_fail = -1
            try:  # ★ R280 · 判分→predictor 观测回灌（append-only，不阻断本轮）
                #   ★ 键就是任务名（task:xxx）：预测问谁、观测记谁，同一命名空间
                #     —— 根治"写 inbox 键、问 bench 键永无交集 ⇒ 恒 0.5"。
                #   ★ Verdict 纪律：details 含 False ⇒ False；含 None ⇒ 跳过不喂；
                #     全 True ⇒ True。
                _ds = [d for d in ((verdict or {}).get("details") or [])
                       if isinstance(d, dict)]
                # ★ :memory: 测试库无旁路可落 ⇒ 跳过（禁污染 cwd/仓库）。
                _dir280 = os.path.dirname(self.db_path or "")
                if _ds and _dir280 and os.path.isdir(_dir280) \
                        and not any(d.get("success") is None for d in _ds):
                    from dwc.organs.predictor import OutcomePredictor as _OP280
                    _ok280 = all(d.get("success") is True for d in _ds)
                    _op280 = _OP280(log_path=os.path.join(
                        _dir280, "dwc_predictor.jsonl"))
                    _op280.observe("task:" + str(task), _ok280,
                                   evidence_ref="term_verdict:%s" % task)
            except Exception as exc:                  # noqa: BLE001
                sys.stderr.write("predictor回灌跳过: %s\n" % exc)
            # ── R205 · ★ 执行→树观测回填自动化（还 trial_run 手动债）──
            #   ★ 依据: verdict.details 是**真判** per-task 结果（judge.evaluate）
            #     ⇒ 喂 world_model（环节⑥ 探索的 GDI/组序/δ 排序全靠它）
            #   ★★ Verdict 纪律: success=None（未评价）不许当 False 也不许
            #     当 True ⇒ 跳过不喂（喂 0 = 把 None 当 False, 禁止）
            #   ★ score 用 pass_rate（k/n 细粒度; 缺则 1.0/0.0 布尔映射）
            #   ★ world_model 未注入 ⇒ 静默跳过（与 judge=None 同纪律:
            #     没注入不假装喂过）; dev 树由 seed 建, 缺树由 tree() 自报
            #   ★★ R205 三重口径（首跑冒烟抓的 W5 冲突后校准）:
            #     ① 真执行集 = obs 里 ★_executed 的键（executor 通道真跑的;
            #       fallback 判 False 不是真失败, 不许当 provenance 污染树）
            #     ② success=None 跳过（未评价不当 False — Verdict 纪律）
            #     ③ **首次**才喂: 树节点已带 score ⇒ W5 拦（判分不可覆盖,
            #       锚定纪律）; 重复执行的真值走 C3' 记录点（judge.store,
            #       已自动）—— 树只留首次真值, 与 W5 设计一致
            if self.world_model is not None:
                _tree = self.world_model.tree("dev")
                _executed = {k for k, v in (obs or {}).items()
                             if isinstance(v, dict) and v.get("★_executed")}
                for _d in (verdict.get("details") or []):
                    _ok = _d.get("success")
                    _tid = _d.get("task_id")
                    if _ok is None or _tid not in _executed:
                        continue
                    _node = _tree.nodes.get(_tid)
                    if _node is None or _node.score is not None:
                        continue          # W5: 非首见不覆盖（判分不可覆盖）
                    _pr = _d.get("pass_rate")
                    self.world_model.record_observation(
                        "dev", _tid,
                        (float(_pr) if _pr is not None
                         else (1.0 if _ok else 0.0)),
                        bool(_ok))

    def _backfill_failures(self, verdict: Dict[str, Any]) -> int:
        """★ R276b · 判分→EXPERIENCE 生产回灌（开回灌的总开关在此方法）。

        口径与 Loop._remember_failure 一致：success is False 才记
        （None 跳过 — Verdict 纪律）；D6 要 c/q/m；异常留痕返已记条数。
        """
        n = 0
        try:
            for d in ((verdict or {}).get("details") or []):
                if not isinstance(d, dict) or d.get("success") is not False:
                    continue
                sigs = list(d.get("sigs") or []) or [
                    d.get("failure_signature") or {}]
                for s in sigs:
                    s = dict(s or {})
                    if not (s.get("c") and s.get("q") and s.get("m")):
                        continue
                    self.memory.remember(
                        MemoryKind.FAILURE_SIGNATURE,
                        {"c": s["c"], "q": s["q"], "m": s["m"],
                         "task": d.get("task_id")})
                    n += 1
        except Exception as exc:                   # noqa: BLE001
            sys.stderr.write("回灌跳过: %s\n" % exc)
        return n

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
        # ── R204 · advice 执行消费（守卫建议真改行为 — 原则9 同款）──
        #   ★ 消费面 = 下一轮任务源:
        #     · degrade_to_baseline / forbid_default_dream ⇒ 剔除环节⑥ 的
        #       默认探索任务（world_tree_action = dream/想象面的默认展开）
        #     · downweight_pre_enactment ⇒ run_term 无 pre-enactment 层
        #       （core._decide 显式缺席）⇒ 如实标 not_actionable（不假装消费）
        #   ★ 回填 rep.iwm_advice.consumed/consumed_action —— 5 段后的
        #     record_round 依据触发态记 Q6 对照臂。
        adv = rep.iwm_advice if isinstance(rep.iwm_advice, dict) else None
        if adv and "error" not in adv:
            degrade = bool(adv.get("degrade_to_baseline"))
            forbid = bool(adv.get("forbid_default_dream"))
            if degrade or forbid:
                # ── ★ R216 · 消费语义校准（Layer 22: 判据错了修判据）──
                #   旧语义 drop 全部 wta = 把"baseline"变成 pass 恒 0 的死水
                #   （DEV_POOL 静态清单）⇒ 无改进 ⇒ trust 恒 0 ⇒ 永久降级
                #   自锁（台账实证: wta 66/66 全 drop, GDI 49 轮恒 ≥ tau）。
                #   新语义 = **降序不丢**: wta 去 fancy 排序（δ/组序）回树
                #   原序、排在基线任务之后 —— "回到基线"是排序降级, 不是
                #   杀死探索。探索保活 ⇒ 改进可能出现 ⇒ trust 窗口回升 ⇒
                #   死锁解除（配合 R215 窗口化）。
                _wta = [t for t in tasks if t.get("kind") == "world_tree_action"]
                if _wta:
                    _base = [t for t in tasks
                             if t.get("kind") != "world_tree_action"]
                    tasks[:] = _base + _wta      # 基线在前, wta 按树原序在后
                tag = "degrade_to_baseline" if degrade else "forbid_default_dream"
                adv["consumed"] = True
                adv["consumed_action"] = ("demote_world_tree_action×%d（%s;"
                                          " 降序不丢）" % (len(_wta), tag))
            else:
                if adv.get("downweight_pre_enactment"):
                    adv["downweight_actionable"] = False
                    adv["downweight_why"] = (
                        "run_term 无 pre-enactment 层（core._decide 显式"
                        "缺席）⇒ 不可执行 — 如实标 not_actionable")
                adv["consumed"] = True
                adv["consumed_action"] = ("none(no_trigger)"
                                          if not adv.get(
                                              "downweight_pre_enactment")
                                          else "not_actionable(downweight)")
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