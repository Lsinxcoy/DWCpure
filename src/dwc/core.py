# -*- coding: utf-8 -*-
"""DWC 主类 —— 一个主类持有全部器官，三入口驱动。

定位声明（DWC-MEM · 记忆底座 · 判据 G1 定位门）
  ★ 主类含 ingest（记忆写入）与 term 编排 ⇒ 与 harness 同判 DWC-MEM；
    它**组装**但不重新实现任何器官（器官逻辑仍在 organs/*，判据 P1）。
  ★ 落点依据: ARCHITECTURE §11.2「core.py ★ 一个主类，器官在此组装」+
    §2.1 形状（七器官 + 三入口）。

★★★ TRUTH_SOURCE（判据 G2: 含判定能力的模块必须声明）
  本类**不判成功** —— success 只能来自 judge 或工具回执（actor §3.3）；
  ingest 只校验「痕迹合格性」（失败必须带失败定位），不产生任何判定。

=== 三入口（ARCHITECTURE §三, ARSI 三入口照搬）===
  ingest(...)  痕迹 → 记忆（§3.1: 必须带 outcome / 失败必须带签名）
  step()       一次决策 + 执行（§3.2: 三层决策 + 显式动作集）
  run_term(n)  一个改进周期（§3.3: 委托 TermRunner —— 六步已在那里实现）

=== 诚实边界 ===
  ★ §3.2 决策第一层「pre-enactment（ARSI Layer2 dynamics 预测）」DWC **没有**
    ⇒ 层标记 available=False 显式缺席，决策直接落 LLM/heuristic —— 不冒充。
    （iwm.governor_advice 的 downweight_pre_enactment 是同位概念, 但其 State
      依赖尚未进 step 流程 —— 见 R61 知识档边界）
  ★ 动作集选择已记录（decision.action），但**分发只实现 remember**（=ingest）；
    learn/dream/evolve 需要前置参数（签名/语料），本轮不路由 —— 显式 not_dispatched。
  ★ iron_laws 字段 = 配置面加载（id/severity 清单）—— 逐条 check_fn 的运行时
    执行在 gate 与各器官（散落），调用点>0 的 I8 核验是 PROGRESS 老债未销。
"""
from __future__ import annotations

import io
import os
import uuid
from typing import Any, Callable, Dict, List, Optional

import yaml

from dwc.foundation import dial_config
from dwc.harness.run_term import TermRunner, TermReport
from dwc.organs.actor import Actor, Trace
from dwc.organs.el_sched import ELScheduler
from dwc.organs.evolver import Evolver
from dwc.organs.iwm import IwmOrgan, Observations
from dwc.organs.judge import Judge, SPLIT_DEV
from dwc.organs.memory import MemoryKind, MemoryKernel
from dwc.organs.world_model import WorldModel

#: 系统外真值源（G2）—— 成功判定永远在 judge/回执, 不在本类
TRUTH_SOURCE = {
    "声明": "DWC 主类不判成功：success 由 judge.evaluate 或工具回执给出；"
            "ingest 只校验痕迹合格性",
    "真值源位置": "dwc.organs.judge.TRUTH_SOURCE（config/anchors/dev.json）",
    "自判禁止": "step 的 decision 只记录动作来源（llm/heuristic），不产出 success",
}

#: §3.2: 候选动作是**显式动作集**（不是「由任务类型决定」—— v2 那句是退步）
ACTIONS: tuple = ("remember", "learn", "dream", "maintain", "evolve")

_IRON_LAWS_PATH = os.path.join(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))), "config", "iron_laws.yaml")
_SEVERITIES = {"block", "warn", "meta"}


class DwcError(Exception):
    """主类入口的违规必须大声报错（不许静默降级 —— G7 静默门同族）。"""


def _load_iron_laws(path: str = _IRON_LAWS_PATH) -> Dict[str, Any]:
    """铁律配置面加载（id/severity 清单校验 —— 没校验的 yaml 只是文本）。"""
    obj = yaml.safe_load(io.open(path, encoding="utf-8").read())
    if not isinstance(obj, dict) or "version" not in obj:
        raise DwcError("iron_laws.yaml 缺 version")
    laws = obj.get("laws")
    if not isinstance(laws, list) or not laws:
        raise DwcError("iron_laws.yaml 的 laws 必须是非空列表")
    seen = set()
    for law in laws:
        lid = law.get("id")
        if not lid or lid in seen:
            raise DwcError("铁律 id 缺失或重复: %r" % lid)
        seen.add(lid)
        if law.get("severity") not in _SEVERITIES:
            raise DwcError("铁律 %s severity=%r ∉ %s"
                           % (lid, law.get("severity"), sorted(_SEVERITIES)))
    return obj


class DWC:
    """一个主类持有全部器官。三入口驱动（ARCHITECTURE §2.1 形状）。"""

    def __init__(self, depth_limit: int, max_nodes: int, *,
                 db_path: str = ":memory:",
                 executor: Optional[Callable[[Dict[str, Any]], Any]] = None,
                 llm: Optional[Any] = None,
                 budget: float = 10.0,
                 iwm_baseline: Optional[Observations] = None):
        """组装七器官 + harness。

        ★ depth_limit / max_nodes **必填无默认**（W6 同款: 组装者必须显式
          想过这两个数, 不许在主类里埋默认深度 —— ARSI adaptive_depth 反面）。
        ★ executor 由调用方注入（DWC 不自带执行环境）。
        ★ iwm_baseline 缺省 = 构造时点的空库观测（θ₀ = 初始状态, App.A.2）。
        """
        for name, v in (("depth_limit", depth_limit), ("max_nodes", max_nodes)):
            if isinstance(v, bool) or not isinstance(v, int) or v < 1:
                raise DwcError("%s 须为 ≥1 的整数（必填无默认）, 实得 %r"
                               % (name, v))
        #: ── §2.1 七器官（平级持有, 组装不实现）──
        self.memory = MemoryKernel(db_path)
        # ★★★ C3' · TS3 生产接线: 判分点 → 逐任务分数序列落盘
        #   （★ 测试/旁路构造的 Judge() 不传路径 = 内存模式零污染;
        #     只有 DWC 主类走生产链时才落 config/anchors/ 两文件）
        _anch = os.path.join(os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.abspath(__file__)))), "config", "anchors")
        self.judge = Judge(
            store_path=os.path.join(_anch, "task_scores.jsonl"),
            evidence_path=os.path.join(_anch, "evidence.jsonl"))
        self.actor = Actor()
        self.world_model = WorldModel(depth_limit=depth_limit,
                                      max_nodes=max_nodes)
        self.evolver = Evolver()
        self.iwm = IwmOrgan(baseline=iwm_baseline or self._initial_obs())
        self.iron_laws = _load_iron_laws()
        # ★ R76 批1 · EL 调度器 —— **一个 agent 一台状态机**:
        #   A（本类 step 缺省取任务）与 B（runner._next_task_source 标注）
        #   共用 self.el（提案批1 硬约束: 分裂 = 调度语义废）
        self.el = ELScheduler()
        #: A 侧节律 token（世界树 Σn_obs 没变 ⇒ 不重复推进）
        self._el_token = -1
        self._el_last = None
        #: R77 批2 · 任务级 δ 缓存（判分点数变才重算）
        self._delta_token = -1
        self._delta_map = None
        # ★★★ R77 · §4.7 职责一「初始播种」—— 构造即播:
        #   **此前世界树生产上永远为空**（src 内 seed/expand 零生产调用 ——
        #   R76 核出: 批1 的 el_selected 在生产永不出现的两层原因之二）⇒
        #   任务源/EL/δ 排序全部空转。播种后 node_id=judge task_id 同域。
        self.world_model.seed_tasks(
            [t for t in self.judge.anchors if not t.startswith("_")])
        #: ── 组装件（执行环境 / LLM / term 编排）──
        self.executor = executor
        self.llm = llm
        #: run_term 委托给 TermRunner —— **共享同一 memory**（一个 agent
        #: 一份记忆, 不许入口各存各的）
        self.runner = TermRunner(db_path=db_path, memory=self.memory,
                                 judge=self.judge, budget=budget,
                                 world_model=self.world_model, iwm=self.iwm,
                                 el_scheduler=self.el)

    def _initial_obs(self) -> Observations:
        """θ₀ = 构造时点的状态（空库 → usage_stats 结构标量）。"""
        s = self.memory.usage_stats()
        return Observations(structural={
            "total": float(s.get("total", 0)),
            "used": float(s.get("used", 0)),
            "effective": float(s.get("effective", 0)),
            "used_ratio": float(s.get("used_ratio", 0.0)),
            "effective_ratio": float(s.get("effective_ratio", 0.0)),
        })

    # ══════════════════════════════════════════════════════
    # 入口① · ingest —— 痕迹进记忆（§3.1）
    # ══════════════════════════════════════════════════════
    def ingest(self, trace: Any, chain_id: str) -> str:
        """摄入一条痕迹 → MemoryKind.TRACE（PROXY 区）。返回 MemoryId。

        ★ 不变量（§3.1 + ACTOR_DESIGN §4.3）:
          ① 必须可评价: outcome 或 success 至少一个非 None
             —— 否则 is_meaningful_success 判 False（痕迹不算合格）
          ② 失败（raised / success=False）必须带 failure_signature
             —— 「没有失败定位的痕迹, 不算合格痕迹」
        ★ 只收 dict 或带 to_dict() 的对象（Trace）—— 不猜其他形态。
        """
        if hasattr(trace, "to_dict"):
            td = trace.to_dict()
        elif isinstance(trace, dict):
            td = dict(trace)
        else:
            raise DwcError("ingest 只收 Trace 或 dict, 实得 %r"
                           % type(trace).__name__)
        outcome, success = td.get("outcome"), td.get("success")
        if outcome is None and success is None:
            raise DwcError(
                "ingest 不变量①: 痕迹既无 outcome 也无 success ⇒ 不可评价 "
                "（§3.1: 必须带 outcome, 否则 is_meaningful_success 判 False）")
        failed = (outcome == "raised") or (success is False)
        if failed and not td.get("failure_signature"):
            raise DwcError(
                "ingest 不变量②: 失败痕迹必须带 failure_signature "
                "（ACTOR_DESIGN §4.3: 没有失败定位的痕迹不算合格痕迹）")
        return self.memory.remember(MemoryKind.TRACE, td, chain_id=chain_id)

    # ══════════════════════════════════════════════════════
    # 入口② · step —— 一次决策 + 执行（§3.2）
    # ══════════════════════════════════════════════════════
    def step(self, task: Optional[Dict[str, Any]] = None, *,
             executor: Optional[Callable] = None) -> Dict[str, Any]:
        """一次决策 + 执行 + 痕迹入记忆（§3.2 三层决策, 见模块诚实边界）。

        ★ task 缺省 ⇒ 从世界树未揭示叶子取（环节⑥: 任务自产, 不编造）。
        ★ 执行器必须注入（本类或本方法）—— 没有执行环境就不假装能行动。
        """
        exe = executor or self.executor
        if exe is None:
            raise DwcError(
                "step 需要 executor（执行环境由调用方注入, DWC 不自带）—— "
                "没有执行器就不许假装能行动")
        if task is None:
            acts = self.world_model.legal_actions()
            if not acts:
                raise DwcError(
                    "step 没给 task 且世界树无未揭示叶子 ⇒ 没有可执行对象"
                    "（先 seed() 或显式给 task —— 不编造任务）")
            # ★ R76 批1-A: EL 采样替代 acts[0]（ARCHITECTURE L592 三段式①
            #   「legal_actions → 采样(EL 调度器) → 本轮任务」—— 设计明文非发明）
            a = self._el_pick(acts)
            task = {"task_id": a["node"], "kind": "world_tree_action",
                    "action": a["action"], "task_source": "world_model:%s"
                    % a["tree"]}
        if "task_id" not in task:
            raise DwcError("task 缺 task_id（actor.act 的硬前置）")

        decision = self._decide(task)
        trace = self.actor.act(task, executor=exe, decision=decision)
        chain_id = decision.pop("_chain_id")
        mem_id = self.ingest(trace, chain_id)
        return {"decision": decision, "trace": trace, "memory_id": mem_id,
                "chain_id": chain_id,
                "action_dispatched": ("remember" if decision.get("action")
                                      == "remember" else
                                      "not_dispatched: %s 只记录不路由"
                                      "(见模块诚实边界)"
                                      % decision.get("action"))}

    def _task_deltas(self) -> Dict[str, float]:
        """★ 任务级 δ（批2-C, C1 落点）—— 缓存: 判分点数变才重算。"""
        pts = self.judge.task_scores(split=SPLIT_DEV)
        token = len(pts)
        if token != self._delta_token or self._delta_map is None:
            from dwc.organs.weakness import task_delta_map
            self._delta_map = task_delta_map(
                pts, self.judge.store.evidence)
            self._delta_token = token
        return self._delta_map

    def _el_pick(self, acts: List[Dict[str, Any]]
                 ) -> Dict[str, Any]:
        """★ L592 三段式① 的采样核心: acts → (δ 排序) → EL 状态机 → act。

        ★ 节律: 世界树 Σn_obs 没变 ⇒ **不重复推进**（EL 判定绑定观测变化 —
          论文「窗口满 B 判一次」的速率口映射; 没判过则首判必走）。
        ★ insufficient（无观测）⇒ index 不动 ⇒ acts[0] —— **与接线前行为
          一致**（接线不改变"没数据时"的选择, 只在有观测后才开始调度）。
        ★ 批2-C δ 排序（C1: **只排任务源, 不动 select**）:
          有任务级 δ>0 ⇒ 按 δ 降序（罕见失败任务优先探 — 稳定排序, 同 δ
          保 candidate_nodes 原序）; 全 0/无判分 ⇒ **原序**（零历史=真保底）。
        ★ 候选收缩致 index>n ⇒ 游标拉回 1（环境数变, 游标失效 —— 实例化规则,
          不触发 el_sched 的 k>N raise）。
        """
        dmap = self._task_deltas()
        if any(dmap.get(a["node"], 0.0) > 0.0 for a in acts):
            acts = sorted(acts, key=lambda a: -dmap.get(a["node"], 0.0))
        n = len(acts)
        if self.el.index > n:
            self.el.index = 1
        token = self.world_model.observed_count()
        if token != self._el_token:
            self._el_last = self.el.decide_from_rate(
                self.world_model.observed_rate(), n)
            self._el_token = token
        d = self._el_last
        idx = d.index if d is not None else 1
        return acts[(idx - 1) % n]

    def _decide(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """§3.2 三层决策（诚实降级链, 每层的可用性都记进 layers）。"""
        layers: List[Dict[str, Any]] = [
            {"layer": "pre_enactment", "available": False,
             "why": "DWC 无 ARSI Layer2 dynamics 预测层 ⇒ 显式缺席（不冒充）"},
        ]
        chain = "CH_step_" + uuid.uuid4().hex[:8]
        if self.llm is not None and getattr(self.llm, "configured", False):
            try:
                raw = self.llm.complete(
                    "从动作集 %s 里为本任务选一个动作, 只回动作名。任务: %s"
                    % (list(ACTIONS), str(task.get("kind", task))[:120]),
                    system="只输出一个动作名, 不解释。")
                choice = (raw or "").strip().split("\n")[0].strip().strip("` ")
                if choice in ACTIONS:
                    layers.append({"layer": "llm", "available": True,
                                   "why": "选定 %r" % choice})
                    return {"source": "llm", "action": choice,
                            "layers": layers, "_chain_id": chain}
                layers.append({"layer": "llm", "available": True,
                               "why": "返回非动作 %r ⇒ 降级 heuristic"
                                      % choice[:40]})
            except Exception as exc:   # noqa: BLE001 —— 降级但**必须留痕**（G7）
                layers.append({"layer": "llm", "available": True,
                               "why": "调用失败 %s: %s"
                                      % (type(exc).__name__, str(exc)[:80])})
        else:
            layers.append({"layer": "llm", "available": False,
                           "why": "llm 未注入或未配置"})
        # 层3 heuristic 兜底
        layers.append({"layer": "heuristic", "available": True,
                       "why": "兜底: step 的执行链是 act→ingest ⇒ 默认 remember"})
        return {"source": "heuristic", "action": "remember",
                "layers": layers, "_chain_id": chain}

    # ══════════════════════════════════════════════════════
    # 入口③ · run_term —— 一个改进周期（§3.3）
    # ══════════════════════════════════════════════════════
    def run_term(self, task: str, n_steps: int = 3,
                 **kwargs) -> TermReport:
        """★ 进化的计量单位 —— 委托 TermRunner（六步/前测后测/盘点在那）。

        ★ 不在本类重写 term: TermRunner 已实现 T1–T4 判据, 重写=第二套。
        ★ R71 核实: judge 的注入在 TermRunner **构造**处（L129 judge=self.judge）
          —— 不是本方法的参数（judge 是构造注入不是 run_term kwarg）。
        """
        return self.runner.run_term(task, n_steps=n_steps, **kwargs)

    # ══════════════════════════════════════════════════════
    # δ_θ 生产喂入口（R72 · 器官⑥ weakness 的活链）
    # ══════════════════════════════════════════════════════
    def difficulty(self, group_id: str, *, split: str = SPLIT_DEV
                   ) -> List[Dict[str, Any]]:
        """★ 从**本 agent 的判分史**算组内残差难度排序（弱→强, 排序偏置）。

        ★ 活链（R69 算法 × R71 数据 × R72 投影, 三轮接成一条）:
          judge.task_scores（C3' 分数点）→ z_history_from_scores
          （z=失败签名族 (c,q), 经 store.evidence 拉回）→ DifficultyEstimator
          .weak_ranking（路线丙 [−log r]₊）
        ★ 返回 = weak_ranking 的有序表（[{"z_id","delta","n_obs"}]）——
          只给**顺序**不给阈值（ARCHITECTURE L1105「只可作排序偏置」）。
        ★ 无观测 ⇒ `[]`（不装数 —— X2 同族: 没数据 ≠ 零难度）。
        ★ split 默认 dev: 分难度史不跨 split 混算真值源（judge split 纪律）。
        """
        from dwc.organs.weakness import (
            DifficultyEstimator, z_history_from_scores)
        pts = self.judge.task_scores(split=split)
        if not pts:
            return []
        hist = z_history_from_scores(pts, self.judge.store.evidence)
        return DifficultyEstimator(hist).weak_ranking(group_id)
