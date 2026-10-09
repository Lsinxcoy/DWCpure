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
from copy import deepcopy
from typing import Any, Callable, Dict, List, Optional, Tuple

import yaml

from dwc.foundation import dial_config
from dwc.harness.run_term import TermRunner, TermReport
from dwc.organs.actor import Actor, Receipt, Trace
from dwc.organs.el_sched import ELScheduler
from dwc.organs.evolver import Evolver
from dwc.organs.replay import (DreamReport, PolicySpec, ReplayError,
                               ReplaySimulator,
                               no_worse_than_current, replay_score,
                               select_policy)
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

#: R101 · C 方案(2a): 能力组（播种建三深度的组表真源）
_CAP_GROUPS_PATH = os.path.join(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))),
    "config", "capability_groups.yaml")


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


def _load_capability_groups(path: str = _CAP_GROUPS_PATH
                            ) -> Dict[str, List[str]]:
    """能力组表 {组名: [sealed_task_ids]} —— R101 · C 方案播种的组真源。

    ★ 「没校验的 yaml 只是文本」（_load_iron_laws 同款）: version/groups 必在,
      组名与任务清单必填; 文件缺失/坏 ⇒ 构造期**大声 raise**（G7 不静默降级 —
      组表是播种数据前提, 缺了就该当场炸, 而不是悄悄退化成无组树）。
    """
    obj = yaml.safe_load(io.open(path, encoding="utf-8").read())
    if not isinstance(obj, dict) or "version" not in obj:
        raise DwcError("capability_groups.yaml 缺 version")
    groups = obj.get("groups")
    if not isinstance(groups, list) or not groups:
        raise DwcError("capability_groups.yaml 的 groups 必须是非空列表")
    out: Dict[str, List[str]] = {}
    for g in groups:
        gid = g.get("group_id")
        members = g.get("sealed_task_ids")
        if not gid or not isinstance(members, list) or not members:
            raise DwcError("能力组缺 group_id/sealed_task_ids: %r" % (g,))
        if gid in out:
            raise DwcError("能力组 id 重复: %r" % gid)
        out[gid] = [m for m in members if isinstance(m, str)]
    return out


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
            [t for t in self.judge.anchors if not t.startswith("_")],
            groups=_load_capability_groups())
        #: R80 · ℋ Dreaming 历史快照（设计稿裁决①: 单树时点快照,
        #: [(tree_id, deepcopy(WorldTree)), ...] — 每 run_term 尾追加,
        #: 超 history_max 丢最旧（内存环形, 不落盘）
        self._replay_history: List[Tuple[str, Any]] = []
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
        # ★★★ R84 · 执行→判分→回填 自动化（ACTOR_DESIGN §4.4 四级之首 judge_verdict）
        #   条件: ① task 是 dev 任务（有 golden 才可判）② executor 回执带显式观测
        #   （detail["observed"] = judge 的 {fn:[[args,value]]} 契约 — 显式不猜）
        #   ⇒ evaluate 进 C3'（δ 数据源）+ 回填树观测（W5: 已带真值不覆盖）
        #   ★ 条件不满足 ⇒ **不判不填**（无判据不冒充 — success_source=
        #     NOT_EVALUATED 口径; detail 无 observed 的 executor 行为不变）
        judgement = self._judge_and_backfill(task, trace)
        return {"decision": decision, "trace": trace, "memory_id": mem_id,
                "chain_id": chain_id,
                "judgement": judgement,
                "action_dispatched": ("remember" if decision.get("action")
                                      == "remember" else
                                      "not_dispatched: %s 只记录不路由"
                                      "(见模块诚实边界)"
                                      % decision.get("action"))}

    def _judge_and_backfill(self, task: Dict[str, Any],
                            trace: Trace) -> Optional[Dict[str, Any]]:
        """★ 判分+回填（R84）—— 返回 Verdict dict 或 None（未判, 不冒充）。

        ★ W5 纪律: 树观测只填未带真值的节点（provenance 单向, 判分不可覆盖）。
        ★ judge 不在 / store 不可用 ⇒ None（诚实缺席, 不炸执行链）。
        """
        if self.judge is None:
            return None
        tid = str(task.get("task_id") or "")
        obs = (getattr(trace, "observed", None) or {}).get("observed")
        if not tid or tid.startswith("_") or tid not in self.judge.anchors \
                or not isinstance(obs, dict) or not obs:
            return None                      # 无判据 ⇒ 不冒充
        try:
            v = self.judge.evaluate(tid, observed=obs)
        except Exception:                    # G7: 不静默 — 判分失败不炸执行链
            raise                             # 判分是硬环节, 出错必须大声（G7）
        node = self.world_model.trees.get("dev", None)
        if node is not None:
            nd = node.nodes.get(tid)
            if nd is not None and nd.score is None:
                self.world_model.record_observation(
                    "dev", tid, 1.0 if v.success else 0.0,
                    bool(v.success) if v.success is not None else False)
        # ★ R99: 失败事件 → 修复层（AIPC 三行映射; source=judge 由本函数产生点
        #   决定 — c 来自实测差异 ⇒ verification 层, 见 weakness.repair_layer）
        from dwc.organs.weakness import repair_layer
        sig = getattr(v, "failure_signature", None)
        return {"task_id": v.task_id, "success": v.success,
                "reason": v.reason,
                "failure_signature": sig,
                "repair_layer": (repair_layer(sig.get("c"), "judge")
                                 if sig else None)}

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
        ★ R80: term 尾**快照世界树进 ℋ**（Dreaming 设计稿裁决①）——
          快照发生在报告返回前, 后续 term 的增长不污染历史回放面。
        """
        rep = self.runner.run_term(task, n_steps=n_steps, **kwargs)
        self._snapshot_worlds()
        return rep

    def _snapshot_worlds(self) -> int:
        """把当前各世界树 deepcopy 进 ℋ（超 history_max 丢最旧）。"""
        from dwc.foundation.dial_config import load_replay
        hmax = load_replay()["history_max"]
        for tid, t in sorted(self.world_model.trees.items()):
            self._replay_history.append((tid, deepcopy(t)))
        over = len(self._replay_history) - hmax
        if over > 0:
            del self._replay_history[:over]
        return len(self._replay_history)

    # ══════════════════════════════════════════════════════
    # R80 · Dreaming 循环（设计稿三裁决落地, §2.5–2.7 编排）
    # ══════════════════════════════════════════════════════
    def dream(self, *, k2_max: int,
              seg_budget: int = 4,
              policy_variants: Optional[List[PolicySpec]] = None
              ) -> DreamReport:
        """★ 离线 Dreaming（2609.14858 §2.5–2.7 编排, 零新机制）。

        ★ M>1（R85 稿批准后实现）: policy_variants 传入 π^0 之外的变体参数集
          ⇒ 每版本在每历史树单独评估完才下一版本（§2.5 逐字）; current=π0 必含
          （单调性支点）; None ⇒ M=1 与旧行为完全一致（向后兼容零破坏）。
        ★ R102 · B 甲案: 段式回放（Eq6 subgoal 段语义的 replay 映射）——
          seg_budget = K_s 段内最大揭示步（默认 4 = R92 稿标**待校准**初值,
          β 同款纪律: 初值非终值）; 段间 re-anchor 破 R90 死锁（w 主场回归）。

        三裁决（docs/proposal_replay_dreaming_design.html）:
        ① ℋ = run_term 尾快照序列（无快照 ⇒ 当前树现快照兜底）
        ② M=1: π^0=当前策略（π^0 选择语义 = δ 降序取 eligible 最高 ——
          与任务源采样同源 _task_deltas; 同 δ 字典序小者先, 可复现）;
          单调性退化**平凡成立并显式记录**（不冒充改进 — M>1 留独立设计轮）
        ③ β 从 config/replay.yaml 读（必填无默认, 初始 0=纯 quality 退化）

        终止（§2.5 三条件, 全实现）: C=∅（无候选）· k≥K₂ · 观测面=全树。
        ★ 快照/回放只读 —— dream 不写树、不产分数（W2: 分数只来自 judge 观测）。
        """
        if k2_max < 1:
            raise DwcError("dream: k2_max 须 ≥1, 实为 %r" % (k2_max,))
        if isinstance(seg_budget, bool) or not isinstance(seg_budget, int) \
                or seg_budget < 1:
            raise DwcError("dream: seg_budget(K_s) 须 ≥1 整数, 实为 %r"
                           % (seg_budget,))
        from dwc.foundation.dial_config import load_replay
        cfg = load_replay()
        b1, b2 = cfg["beta1"], cfg["beta2"]
        worlds = list(self._replay_history) or \
            [(tid, deepcopy(t)) for tid, t in sorted(
                self.world_model.trees.items())]
        if not worlds:
            raise DwcError("dream: 无任何世界树可回放（先 seed_tasks）")
        dmap = self._task_deltas()
        # ★ M>1 版本循环（R85 稿④ · R86 实现）: current=π0 必含（单调性支点）;
        #   每版本在每历史树单独评估完才下一版本（§2.5 逐字）; None ⇒ M=1 等价
        specs = [PolicySpec()] + [v for v in (policy_variants or [])
                                   if v.pid != "π0"]
        per_by: Dict[str, List[Tuple[str, float, int, int]]] = {}
        segments_acc: List[str] = []          # R102: π0 的段序（稿审计字段）
        picks_by: Dict[str, List[str]] = {}   # R102: {pid: pick 轨迹 — 探针②原料}
        for _spec in specs:
            per: List[Tuple[str, float, int, int]] = []
            spec_picks: List[str] = []
            for tid, T_i in worlds:
                sim = ReplaySimulator(T_i)
                k = 0
                n_revealed = 0
                # ★ R102 · B 甲案段式（论文 Eq6 subgoal 段语义 → replay 映射,
                #   R92 稿 B 节推荐甲; re-anchor = elig 语义的设计变更裁决）:
                #   单循环 → 段循环（段 = root 的一个 child 分支单元）——
                #   段内「同层双观测叶」成为常态 ⇒ w_delta 的 dream 主场回归
                #   （R90 三迭代的死锁: 段间 interleave 使 nonroot 恒 0/1 元素）。
                #   k/n_revealed 跨段累计（稿: 语义不变）; V/replay_score/
                #   select_policy/no_worse 全部不动（跨段累计后同一公式）。
                # ★ R102 修正版 re-anchor: 锚集 = {root} ∪ 已完成段根 —
                #   **段的叶不进锚**（探针④字面: 段起点不含上段的叶; 首版
                #   「完成集=全量」使 re-anchor 恒等 ⇒ 无效实现, 已废）。
                #   revealed_all = 全量揭示集（V/max_s/n_revealed 跨段累计源）。
                anchor = set()
                revealed_all = set()
                kids = list(T_i.nodes[T_i.root_id].children)
                if _spec.seg_order == "delta":
                    # 段间选择用 dmap（与任务源同源; 字典 tie 可复现）
                    seg_roots = sorted(kids,
                                       key=lambda v: (-dmap.get(v, 0.0), v))
                else:
                    seg_roots = kids          # 插入序 = step(root) 顺序规定
                seg_rec: List[str] = []
                done = False

                for seg_root in seg_roots:
                    if done or k >= k2_max:
                        break

                    def _in_seg(v, _sr=seg_root):
                        # 稿明文「段内只挖本段分支」: v 在 seg_root 子树内
                        #   （含 seg_root 自身; WorldNode.parent_id 链回溯）
                        cur = v
                        while cur is not None and cur != T_i.root_id:
                            if cur == _sr:
                                return True
                            cur = getattr(T_i.nodes[cur], "parent_id", None)
                        return False

                    # re-anchor: observed = {root} ∪ 已完成段根（锚集; 叶丢弃）
                    observed = {T_i.root_id} | anchor
                    # 段内第一步 = 揭示 seg_root: 段序是对 step(root)「最早
                    #   未观测子」顺序规定的**显式化**（段语义下顺序由段序给）;
                    #   转移方程合规: seg_root 是已记录、父∈observed 的子 —
                    #   只揭示不生成（replay 根本性质不违）
                    if seg_root not in observed:
                        observed = set(observed) | {seg_root}
                        n_revealed += 1
                        k += 1
                        spec_picks.append(seg_root)   # 手动步也入轨迹（审计）
                    k_seg = 0
                    while k_seg < seg_budget and k < k2_max:
                        elig = sim.eligible(observed)

                        def _can_reveal2(v):
                            return any(c not in observed
                                       for c in T_i.nodes[v].children)

                        # 段内候选**不含 root**（根开新分支由段间承担 —
                        #   这防「段内 pick=root 揭段外节点」的越界; 段内
                        #   nonroot 空 ⇒ 段完成出段）
                        nonroot = sorted(
                            v for v in elig if v != T_i.root_id
                            and _in_seg(v)          # 段内只挖本段分支（稿明文）
                            and ((not _spec.prefer_revealable)
                                 or _can_reveal2(v)))
                        if not nonroot:
                            break             # 段内无可揭 ⇒ 段完成
                        pick = min(nonroot, key=(
                            lambda v: -_spec.w_delta * dmap.get(v, 0.0)))
                        spec_picks.append(pick)
                        new_obs = sim.step(observed, {pick})
                        gained = set(new_obs) - observed
                        if not gained:
                            break             # 段内防空转（r=False 选到已揭
                        #   完子的叶）⇒ 出段（下段可能仍有可揭 — 与单循环
                        #   「直接停全回放」不同, 段语义天然有限不死）
                        n_revealed += len(
                            (gained - {T_i.root_id}) - revealed_all)
                        revealed_all |= gained
                        observed = set(new_obs)
                        k += 1
                        k_seg += 1
                        if (observed | {T_i.root_id}) >= set(T_i.nodes):
                            done = True       # 终止③ 观测面=全树（停全部段）
                            break
                    anchor |= {seg_root}      # 段根进锚（段完成的锚化）
                    revealed_all |= observed  # 本段全量并入
                    seg_rec.append(seg_root)
                    if (revealed_all | {T_i.root_id}) >= set(T_i.nodes):
                        done = True           # 段间也查全树
                # V 的观测面 = 全量跨段累计（稿: 跨段累计后同一公式）
                observed = revealed_all | {T_i.root_id}
                max_s = max((T_i.nodes[v].score for v in observed
                             if getattr(T_i.nodes[v], "score", None)
                             is not None), default=0.0)
                V = replay_score(max_score=max_s, n_revealed=n_revealed,
                                 n_rounds=k, beta1=b1, beta2=b2)
                per.append((tid, V, k, n_revealed))
                if _spec.pid == "π0":
                    # 稿审计字段 = 本轮回放(π0 默认回放)的段序 — 多 spec 不混
                    segments_acc.extend("%s:%s" % (tid, s) for s in seg_rec)
            per_by[_spec.pid] = per
            picks_by[_spec.pid] = tuple(spec_picks)
        v_by = {pid: sum(p[1] for p in pl) / float(len(pl))
                for pid, pl in per_by.items()}
        m_star, v_star = select_policy(v_by, current="π0")
        ok = no_worse_than_current(v_by, current="π0")
        per = per_by[m_star]                # 报告 = 胜者版本的逐世界评估
        return DreamReport(
            n_worlds=len(per), v_by_version=v_by, m_star=m_star,
            v_star=v_star, betas=(b1, b2), per_world=per,
            monotone_no_worse=ok, k2_max=k2_max,
            policy_variants=tuple(specs),
            segments=tuple(segments_acc),
            picks={p: tuple(t) for p, t in picks_by.items()},
            why="环节⑥ Dreaming（§2.5–2.7; M=%d%s; β=%s/%s 为 config 初值"
                "非论文报值)" % (
                    len(specs),
                    " 评估当前策略 — 单调性平凡成立显式记录, 非改进声明"
                    if len(specs) == 1 else " 修订域=纯选择参数(锁值不进), "
                    "网格变体=搜索非反馈开发(R85 稿边界)",
                    b1, b2))

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
