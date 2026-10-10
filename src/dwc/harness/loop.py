# -*- coding: utf-8 -*-
"""loop · 真 round_fn 生产形态（R165 — daemon 驱动的单轮闭环）。

定位声明 · **DWC-AUTO**（自我强化 · 判据 G1 定位门）
  ★ R164 daemon 只驱动 + 记账 + 熔断; 本模块给它**真 round_fn** —
    单轮闭环全部复用既有器官（零新判定）:
      execute_task(actor, judge, task) ⇒ observation
      judge.evaluate(task, split, observed) ⇒ Verdict（真判分）
      fail ⇒ evolver.diagnose(sig) ⇒ proposals
      gate_all(proposals)（R162 两层: 静态门→六门链）
      pipeline.run_round(...) 六面（R156-R163: 含链/采纳/记账/落地）
  ★ 长生命周期对象全在 `Loop` 类里（evolver/applier/ledger/judge 跨轮
    存活 ⇒ proposals/seen 累积不丢）; daemon 只管轮转。
  ★ 不抢位: 不判分/不提案/不落地 — 只是编排（与 pipeline 同纪律）。

★★★ TRUTH_SOURCE（判据 G2）
  · 单轮动作 ← 现有器官返回值（本模块不重算）
  · 跨轮分数序列 ← score_history.jsonl（judge 落盘路径 — e2e 同一文件）
  · 任务面 ← judge.anchors 的 dev split（10 条 — 非硬编码单 task,
    e2e 的 TASK 写死只适合演示, 循环要全 task 轮转）

★★ 任务选择裁决（R73 同族 — 无设计不发明选择器）
  · task_i = dev_tasks[round_no % len(dev_tasks)] — 轮转（可解释默认）
  · 真"选哪个"（价值优先/失败频次优先）**无设计依据** ⇒ 不实现,
    如实记为机械轮转（direction 选择策略的 backlog 同源）
"""
from __future__ import annotations

import io
import json
import os
from typing import Any, Dict, List, Optional

from dwc.organs.actor import Actor, execute_task
from dwc.organs.applier import Applier
from dwc.organs.evolver import Evolver
from dwc.organs.judge import Judge
from dwc.harness.pipeline import run_round
from dwc.organs.replay import (no_worse_than_current, select_policy,
                               shortlist_candidates)
from dwc.harness.splitfeed import feed_pair
from dwc.harness.candidate_bridge import BridgeError


class LoopError(Exception):
    """真 round_fn 组装的显式拒绝（anchors 空/落盘路径同侧缺）。"""


class Loop:
    """★ 常驻单轮闭环（Daemon.round_fn 的生产实现）。"""

    def __init__(self, *, anchors_dir: Optional[str] = None,
                 registry: Optional[Any] = None,
                 use_llm: bool = False,
                 max_tasks_per_round: int = 8,
                 impl_floor: str = "broken",
                 impl_source: Optional[str] = None):
        """impl_floor: "broken"(R170 默认 — 初值错误) | "golden"(旧行为).
        impl_source: 开局实现文件（缺省 anchors_dir/broken_dev.json）."""
        self.registry = registry
        self.use_llm = use_llm
        # ★ src/dwc/harness/loop.py ⇒ 上溯**4**层 = repo root（src/dwc/harness/loop
        #   — 3 层只到 src/ ⇒ judge 会指到 src/config/anchors 空目录炸
        #   FileNotFound — R165 实测层数错, 按文件真位置固定）
        _default = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(
                os.path.dirname(os.path.abspath(__file__))))),
            "config", "anchors")
        # ★ anchors_dir 缺省 or 指向不存在目录 ⇒ 回落默认（不建空 judge —
        #   空 judge 的 evaluate 会 FileNotFound, 那不是"dev 空"的语义）
        self.anchors_dir = (anchors_dir if anchors_dir
                            and os.path.isdir(anchors_dir) else _default)
        #: ★ judge 走生产落盘路径（e2e 纪律 — 判分点不可被绕开）
        store = os.path.join(self.anchors_dir, "task_scores.jsonl")
        evidence = os.path.join(self.anchors_dir, "evidence.jsonl")
        self.judge = Judge(store_path=store, evidence_path=evidence)
        self.evolver = Evolver(registry=registry)
        self.applier = Applier(window=2)
        self.actor = Actor()
        self.credit = None                       # run_round 内建 ledger
        self.max_tasks = int(max_tasks_per_round)
        #: ★★ R170 · 可变实现集（task_id → 当前实现源码）— agent 的"手":
        #   开局 = broken_dev（初值错误）; `landing` 每次落地成功 ⇒ 写回
        #   本表 ⇒ 下轮 judge 评的是**修过的**实现 ⇒ 分数变化 = agent 真干活
        #   （对比: 此前 execute_task(implementation=None) 走 REFERENCE,
        #     task 恒过 ⇒ 闭环空转 — R171 实测 12 轮 n_landed=0 的根因）
        self.impl_store: Dict[str, str] = {}
        self.impl_floor = str(impl_floor or "golden")
        #: ★ R172: EL 调度状态（与 core.DWC 同款 — 双池共用机制不分裂）
        self.el = None
        self._el_last = None
        self._el_token = -1
        self._el_last_task: Optional[str] = None    # ★ R172: p̂ 归因环境
        self._last_consolidation: Optional[Dict] = None  # ★ R173 固化痕迹
        self._last_replay_pick: Optional[Dict] = None    # ★ R174 replay 选择痕迹
        self._load_impl_floor(impl_source)

    def _load_impl_floor(self, impl_source: Optional[str]) -> None:
        """★ R170 开局实现面（agent 的"手"的初始位置）。

        · floor="broken" ⇒ 读 broken_dev.json 的 broken_impl（初值错误 —
          agent 有活干; 缺文件/坏 JSON ⇒ **显式 LoopError**（不静默回落
          golden — 那会让闭环重回空转而没人发现））
        · floor="golden" ⇒ 不载入（execute_task 缺省走 REFERENCE — 旧行为）
        """
        if self.impl_floor == "golden":
            return
        path = impl_source or os.path.join(self.anchors_dir, "broken_dev.json")
        if not os.path.exists(path):
            raise LoopError("impl_floor=broken 但开局实现文件缺: %s"
                            % path)
        try:
            raw = json.load(io.open(path, encoding="utf-8"))
        except Exception as exc:                  # noqa: BLE001 — 留痕不静默
            raise LoopError("开局实现文件读不了: %s: %s"
                            % (path, exc))
        n = 0
        self.rules_known: Dict[str, bool] = {}
        for tid, rec in raw.items():
            if tid.startswith("_") or not isinstance(rec, dict):
                continue
            impl = rec.get("broken_impl")
            if isinstance(impl, str) and impl.strip():
                self.impl_store[tid] = impl
                # ★ R170: 修法覆盖标（broken_dev 自报 — RULES 有键⇒true;
                #   false ⇒ 弃权是一等输出（论文 unfixable_now）, 不编修法）
                self.rules_known[tid] = bool(rec.get("rules_known", False))
                n += 1
        if not self.impl_store:
            raise LoopError("开局实现文件无可载入的 broken_impl: %s" % path)
        self._last_floor_n = n
        #: ★ R168 · 最近一轮的四量采集（metrics_from_round 出口 — 读窗口,
        #   daemon/监控可查; 初始全 not_instrumented 而不是 None）
        from dwc.organs.metrics import four_metrics
        self.last_metrics = four_metrics()
        self._last_ledger_entries: List[Any] = []

    # ── 真 round_fn（Daemon 契约: (round_no, daemon) -> dict|None）──
    def round(self, round_no: int, daemon: Any = None) -> Dict[str, Any]:
        tasks = self._dev_tasks()
        if not tasks:
            raise LoopError("dev split 无锚点任务 ⇒ 无任务面可转")
        # ★★★ R172: task 选择从「机械轮转」升级为 **δ_θ 排序 + EL 状态机**
        #   —— **不是发明 direction 选择器**（R73 仍有效: 三方向"何时选
        #   哪个"的设计判据全文未给 ⇒ 保持不造）; 接的是**已有据实现**:
        #   · weakness.task_delta_map（残差难度 — 罕见失败签名族优先）
        #   · el_sched.decide_from_rate（2609.04128 式 2 三段状态机）
        #   · core.DWC._el_pick 同源实例化（世界树候选池已在用, 本处是
        #     dev 任务池的同一模式 — 同机制双池, 不另立策略）
        # ★ 纪律: 无判分历史（δ 全 0 + observed 未动）⇒ 原机械序（接线
        #   不改变"没数据时"的行为 — core._el_pick 同款保底）; R170 的
        #   rules_known 机械优先**退役**（EL 上位 — 按观测说话比固定
        #   排序更论文; rules_known 仍留字段供 broken_dev 自报审计）
        sel = [self._pick_task(tasks)]
        n_landed = 0
        verdicts: List[str] = []
        score_vals: List[float] = []
        for tid in sel:
            # ★ R170 修: _run_one_task 透传 round_no（此前 L240 run_round
            #   引用外层 round_no ⇒ NameError — daemon 真跑首轮必炸的
            #   潜伏 bug, R171 才暴露; 修法是参数透传不是全局声明）
            out = self._run_one_task(tid, round_no=round_no)
            verdicts.append(out["chain_verdict"])
            if out["score"] is not None:
                score_vals.append(out["score"])
            if out["landed"]:
                n_landed += 1
        # ★ 跨轮分数序列（judge 落盘 — daemon/σ 同源）
        score = (sum(score_vals) / len(score_vals)) if score_vals else None
        self._append_history(round_no, sel, score, n_landed)
        all_verdicts = set(verdicts)
        if "error" in all_verdicts:
            cv = "error"
        elif any(v in ("blocked",) for v in verdicts):
            cv = "blocked"
        else:
            cv = ("applicable_passed_with_na"
                  if any(v == "applicable_passed_with_na" for v in verdicts)
                  else "all_applicable_passed")
        # ★ R168 四量采集（每轮出口 — 素材: RoundLog 台账 + 本轮 ledger 账;
        #   本轮的提案数从 _last_n_candidates 取（_run_one_task 出口的
        #   真实 gate_all 输入数 — 不另造统计面））
        from dwc.organs.metrics import metrics_from_round
        from dwc.daemon import RoundLog
        self.last_metrics = metrics_from_round(
            RoundLog(round_no=round_no, started_at=0.0,
                     n_candidates=getattr(self, "_last_n_candidates", 0),
                     chain_verdict=cv, landed=n_landed > 0,
                     score=score),
            ledger_entries=self._last_ledger_entries)
        return {"n_candidates": self._last_n_candidates,
                "chain_verdict": cv,
                "blocked": self._last_blocked,
                "landed": n_landed > 0,
                "score": score,
                "tasks": sel,
                "skipped_reason": (self._last_skip
                                   if self._last_skip else None)}

    # ── 单 task 闭环（全器官复用）──
    def _run_one_task(self, tid: str, round_no: int = 0
                      ) -> Dict[str, Any]:
        from dwc.harness.landing import LandingError
        from dwc.organs.actor import Actor as _A     # noqa: F401
        self._last_n_candidates = 0
        self._last_blocked = []
        self._last_skip = None
        try:
            # ★ R170: 用 store 的**当前实现**（初值 broken; 落地后是修过的）
            #   — 不传 implementation 会走 REFERENCE（恒过 ⇒ 闭环空转）
            out = execute_task(self.actor, self.judge, tid,
                               implementation=self.impl_store.get(tid))
        except Exception as exc:                    # noqa: BLE001
            self._last_skip = "execute_task 失败: %s" % exc
            return {"chain_verdict": "blocked", "score": None, "landed": False}
        v = self.judge.evaluate(tid, "dev", observed=out["observation"])
        score = 1.0 if v.success else 0.0
        # ★★ R170 试跑位（post-state 复判 — 先验证再链判的素材源）:
        #   proposal.patch 是表达式片段（RULES 的"return sum(range(n+1))"）
        #   ⇒ 试跑 = 把该 patch 合成完整源码跑 judge ⇒ 真 ΔS/真 pass_rate
        #   （论文顺序: 先有收益证据再谈采纳; 落地是采纳后的事）
        # ★ R170: 判据素材（给六门链的真弹药 — 此前全 None ⇒ ③⑤
        #   blocked「缺口径」的根因; 与 e2e 同源口径: micro k/n）
        _pass_rate = (float(v.k_passed) / float(v.n_checks)
                      if (isinstance(v.k_passed, int)
                          and isinstance(v.n_checks, int) and v.n_checks)
                      else None)
        if v.success:
            # ★ 已过 ⇒ 无失败签名可诊 ⇒ 本轮该 task 无提案（idle 不是 error）
            self._last_skip = "task %r 已通过 ⇒ 无提案（idle≠error）" % tid
            return {"chain_verdict": "all_applicable_passed",
                    "score": score, "landed": False}
        sig = dict(v.failure_signature or {})
        try:
            proposals = self.evolver.diagnose([sig]).get("proposals", [])
        except Exception as exc:                    # noqa: BLE001
            self._last_skip = "diagnose 失败: %s" % exc
            return {"chain_verdict": "blocked", "score": score, "landed": False}
        if not proposals:
            # ★★★ R173: 无本 fn 规则 ⇒ LATERAL 泛化（同 (c,q) 近亲修法）
            #   — direction.py R73 边界自己点名的第一落点
            #   （switch_strategy 语义近似 LATERAL）; 泛化 patch 无效 ⇒
            #   门/试跑拦 ⇒ 弃权, 不硬过（候选生成 ≠ 采纳）
            _lat = None
            try:
                _lat = self.evolver.propose_lateral(sig)
            except Exception as exc:            # noqa: BLE001 — 留痕不静默
                self._last_skip = "LATERAL 泛化失败: %s" % exc
            if _lat is not None:
                proposals = [_lat]
            else:
                self._last_skip = ("无提案命中（task=%r — 同族泛化也无, "
                                   "unfixable_now 是一等输出）" % tid)
                return {"chain_verdict": "blocked", "score": score,
                        "landed": False}
        # ★★★ R174 · replay 选择面（稿⑥§②+§2.7: 候选集必含 current,
        #   argmax V(m*) ≥ V(current) ⇒ 不劣于当前的保证）:
        #   v_search = {提案: 试跑分, "__current__": 当前实现分}
        #   ⇒ shortlist_candidates(top-K ∪ {current}) + select_policy(argmax)
        #   ⇒ m* == "__current__" ⇒ **不落地**（保持更好 — 没好处不动）;
        #   m* == 提案 ⇒ 继续走链（六门复试 — 选择面只判"选谁", 质量仍归门）
        #   ★ 分工: replay 管"选哪个"（历史分 argmax）; gates 管"能不能用"
        #     （六门）— 两层都过才落（不拿 replay 分绕过门 — 边界）
        _cur_impl = self.impl_store.get(tid)
        _cur_trial = self._trial_run(tid, _CurrentProposal(tid, _cur_impl)) \
            if _cur_impl else None
        _cur_score = (float(_cur_trial["pass_rate"])
                      if _cur_trial and _cur_trial.get("pass_rate")
                      is not None else 0.0)
        # ★★ R170: 提案在手 ⇒ 试跑（把 RULES patch 合成新源码 ⇒ judge
        #   复判 — 门⑤的真 ΔS 证据只从这出; 合成失败 ⇒ None ⇒ ⑤拒）
        _trial = self._trial_run(tid, proposals[0])
        _v = {"__current__": _cur_score}
        if _trial is not None and _trial.get("pass_rate") is not None:
            _v["prop"] = float(_trial["pass_rate"])
        short = shortlist_candidates(_v, current="__current__", k=2)
        _pick = select_policy(_v, current="__current__")
        self._last_replay_pick = {
            "v": _v, "shortlist": short, "picked": _pick[0],
            "argmax_score": _pick[1],
            "no_worse": no_worse_than_current(_v, current="__current__")}
        if _pick[0] == "__current__":
            # ★ current 赢（含平手 — argmax tie-break 取字典序小者,
            #   "__current__" < "prop" ⇒ 平手即 current）= 不落地
            self._last_skip = ("replay 选择: current 不劣于提案（%r）⇒ "
                               "不落地（没好处不动）" % _v)
            self.impl_store[tid] = _cur_impl or ""
            return {"chain_verdict": "kept_current", "score": _cur_score,
                    "landed": False, "blocked": []}
        gated = self.evolver.gate_all(proposals)     # R162 两层并轨
        self._last_n_candidates = len(proposals)
        if not gated["gated"]:
            self._last_skip = "全提案被层①拦（无 gated）"
            self._last_blocked = ["gate_all:no_gated"]
            return {"chain_verdict": "blocked", "score": score,
                    "landed": False}
        # ★★★ R170 splitfeed 真源（终结 R165 的"同 observation 双侧"
        #   stub — 那让 split 门永 na/相等）:
        #   · baseline = **当前实现**（impl_store[tid] — broken 或已修的）
        #   · current  = **试跑实现**（_trial["impl"] — RULES patch 合成后）
        #   · 两侧的 in=dev 全判, ho=test_sealed 真跑（R169 的 split 路由）
        #   ⇒ accept(baseline, current) 比的是"修前 vs 修后"的**真**双 split
        #   （这才是论文 split 门的语义; 试跑失败 ⇒ current 回落 baseline
        #   ⇒ 相等 ⇒ split 门判 na/blocked 如实（没差别不装提升））
        _cur_impl = (self.impl_store.get(tid)
                     if not _trial else (_trial.get("impl")
                                         or self.impl_store.get(tid)))
        try:
            base, cur = feed_pair(
                self.judge,
                lambda _t, _tid=tid, _s=None: execute_task(
                    self.actor, self.judge, tid, split=_s or "dev",
                    implementation=self.impl_store.get(tid))["observation"],
                lambda _t, _tid=tid, _s=None: execute_task(
                    self.actor, self.judge, tid, split=_s or "dev",
                    implementation=_cur_impl)["observation"])
        except Exception as exc:                    # noqa: BLE001 — 留痕
            self._last_skip = "splitfeed 产弹失败: %s" % exc
            base = cur = None
        # ★★★ R170 修 × 2: run_round 的 cands 位**直接收 Proposal 列表**:
        #   ① 首版把 to_facts 的产出（TermFacts）再喂 cands 位 ⇒ 投影面
        #      拿 TermFacts 当 Candidate（.component=None ⇒ BridgeError）
        #   ② 二版造 dict 中间层 ⇒ to_facts 只用 getattr 属性访问,
        #      dict 取不到 component ⇒ 同错（实测 dict/obj 双探针）
        #   ⇒ 结论: 投影只做一次（run_round 内部）, 传入即 Proposal
        cands = list(gated["gated"][:self.max_tasks])
        p0 = gated["gated"][0]
        self._last_p0_patch = p0.patch       # ★ R170 写回源（取落盘的优先）
        # ★ R170: score_star = 上一轮同面分数（score_history 末轮 — σ/门
        #   ⑤ 的对照锚; 首轮 None 如实, 不造 0.0 基准）; delta_s = 本轮
        #   fail→修好的预期收益（落地前无法真算 ⇒ None 交给 gates 的
        #   na/blocked 三态, 不硬设 — 与 R151 noncomp 纪律同源）
        _prev = self._last_history_score()
        # ★★ R170 ⑤noncomp 弹药（与 e2e 同源常量: delta_c=0.01/noise_band=
        #   0.01/domain_guard_ok=True; **delta_s 用试跑真值**: 提案合成
        #   后复判的 pass_rate - 当前实现的 pass_rate（试跑失败 ⇒ None
        #   ⇒ 门⑤ blocked「缺口径」— 比起 0.0 硬凑更诚实, 而真收益的
        #   提案此时才过得了门 — 这正是门组该有的样子））
        _tr = _trial or {}
        _ds = (max(0.0, (float(_tr["pass_rate"]) - float(_pass_rate))
                   if (_tr.get("pass_rate") is not None
                       and _pass_rate is not None) else 0.0)
               if _tr else None)
        # ★ R170: 真 ledger（ℒ_t 记账 — 链过了才走到记账段; 此前传
        #   None ⇒ 链一过就 AttributeError（R165 遗留: 链恒 blocked
        #   从没走到这）; Loop 持一个跨轮追加的 ledger（④downstream
        #   的素材源 — R168 metrics 靠它）
        from dwc.organs.credit import CreditLedger
        if self.credit is None:
            self.credit = CreditLedger()
        res = run_round(cands, t=round_no, proposal=p0,
                        ledger=self.credit, vocabulary=(),
                        pass_rate=(_tr.get("pass_rate")
                                   if _tr.get("pass_rate") is not None
                                   else _pass_rate),
                        score_star=_prev, delta_s=_ds,
                        delta_c=0.01, noise_band=0.01,
                        domain_guard_ok=True, split_verdict=None,
                        baseline=base, current=cur,
                        applier=self.applier,
                        target=_MemoryTarget(),
                        evidence={"success": True,
                                  "reason": "loop: %s" % tid})
        landed = bool(res.landing)
        # ★★ R170 闭环最后一环: 落地成功 ⇒ 把**修好的完整实现**写回
        #   impl_store（agent 的"手"真动了 — 下轮同 task 评的是修过的
        #   实现 ⇒ score 0→1 是 agent 干的, 不是 fixture 切的）
        # ★★ 口径（R170 实测纠偏）: 写回 **试跑的完整源码**（_trial["impl"]
        #   — 已验证 pass_rate 的那个）; **不是** landing.new_value /
        #   proposal.patch（那俩是**函数体片段** — RULES patch 风格,
        #   拿它当整函数源码 ⇒ 下轮 compile 炸: "'return' outside
        #   function" 实测抓到; store 的契约 = 完整 impl 源码）
        if landed and _trial and _trial.get("impl"):
            self.impl_store[tid] = _trial["impl"]
        # ★★★ R173 · 固化（落地经验 ⇒ RULES 新规则 — 论文核心进化环）:
        #   landed 的签名键若**非种子** ⇒ land_rule 三闸（schema +
        #   evidence.success=试跑真验 + readback）落盘 persist_learned;
        #   种子键 ⇒ 如实 no-op 记录（persist_learned 语义: learned=非种子,
        #   代码/JSON 不双源）— 不谎称"学了新的"
        if landed:
            self._consolidate_rule(tid, sig, proposals[0], _trial, res)
        # ★ R168: 本轮 ledger 账出口（④ downstream 的素材 — 只记本轮,
        # ★ R168: 本轮 ledger 账出口（④ downstream 的素材 — 只记本轮,
        #   跨轮累积由 Loop 持有者接（daemon 面 — 不在本方法内藏状态））
        self._last_ledger_entries = list(res.credit_entries or [])
        return {"chain_verdict": res.chain["verdict"],
                "blocked": list(res.chain.get("blocked") or []),
                "score": score, "landed": landed}

    def _trial_keyword(self, tid: str, answer: str
                       ) -> Optional[Dict[str, Any]]:
        """★ R171: keyword_match 试跑（答案文本 ⇒ judge 按 kw 逐条判）。"""
        try:
            o = execute_task(self.actor, self.judge, tid,
                             implementation=answer, split="dev")
            v = self.judge.evaluate(tid, "dev", observed=o["observation"])
        except Exception:                        # noqa: BLE001 — 非 fatal
            return None
        pr = (float(v.k_passed) / float(v.n_checks)
              if (isinstance(v.k_passed, int) and isinstance(v.n_checks, int)
                  and v.n_checks) else None)
        return {"success": v.success, "pass_rate": pr,
                "score": 1.0 if v.success else 0.0, "impl": answer}

    def _trial_run(self, tid: str, proposal: Any
                   ) -> Optional[Dict[str, Any]]:
        """★★★ R170: 提案试跑（post-state 复判 — 门⑤的真 ΔS 证据源）。

        ★ 合成口径: proposal.patch 是 RULES 给的**函数体片段**
          （"return sum(range(n + 1))" / "if n <= 1:\n    return 1\n"
          "return n * factorial(n - 1)"）⇒ 取 task 的 fn 名 + 片段拼成
          完整源码（不解析原实现 — 那是变异器的活, 不是这里的）。
        ★ 跑炸/合成失败 ⇒ None（⑤走"缺口径"⇒ blocked — 不硬凑收益）。
        ★ 返回值: {"pass_rate"/"success"/"score"}（judge 复判口径）。
        """
        frag = str(getattr(proposal, "patch", "") or "").strip()
        if not frag:
            return None
        fn = str(getattr(proposal, "target", "") or "").strip()
        if not fn:
            return None
        # ★★ R171: keyword_match 形态（答案修法 — patch 就是完整答案
        #   文本; target 是 task_id（judge 签名 fn=首 kw 但 RULES
        #   target 已按 task_id 记）⇒ 直接当文本试跑, 不包 def
        _rec = (self.judge.anchors.get(tid) or
                (getattr(self.judge, "sealed", None) or {}).get(tid) or {})
        if _rec.get("verifier_kind") == "keyword_match":
            return self._trial_keyword(tid, frag)
        # 片段已是完整函数体（含 return/多行）⇒ 直接包 def; 若是单行
        # 表达式（RULES 的风格）也兼容 — 只是缩进 4
        # ★★★ 签名口径（R170 实测修）: executor **按名调 fn(args)** —
        #   片段用原实现的参数名（n/xs/s…）⇒ 签名必须从**当前实现**
        #   （impl_store[tid] 的首行 def）提; 首版我写死 *a,**k ⇒
        #   片段里的 n 未定义 ⇒ 试跑必炸（pass_rate=0 的假证据）
        cur = self.impl_store.get(tid) or ""
        sig_line = ""
        for ln in cur.splitlines():
            if ln.strip().startswith("def "):
                sig_line = ln.strip()
                break
        if not sig_line:
            return None                          # 取不到签名 ⇒ 不猜
        head = "%s:" % sig_line.rstrip(":")
        src = head + "\n" + (
            "".join("    " + ln + "\n" for ln in frag.splitlines()))
        try:
            o = execute_task(self.actor, self.judge, tid,
                             implementation=src, split="dev")
            v = self.judge.evaluate(tid, "dev", observed=o["observation"])
        except Exception:                        # noqa: BLE001 — 试跑失败非 fatal
            return None
        pr = (float(v.k_passed) / float(v.n_checks)
              if (isinstance(v.k_passed, int) and isinstance(v.n_checks, int)
                  and v.n_checks) else None)
        return {"success": v.success, "pass_rate": pr,
                "score": 1.0 if v.success else 0.0, "impl": src}

    def _applied_patch_for(self, tid: str, res: Any) -> Optional[str]:
        """★ R170: 本轮落地提案的 patch（用于写回 impl_store）。

        ★ 优先级: ①res.landing 的 new_value（applier 落盘的读回值 —
          那是**真写进去的东西**; ②本轮 gated 提案（候选环 p0）的 patch。
        ★ 取不到 ⇒ None（store **不动** — 不拿 None 覆盖已有实现, 也不
          拿 REFERENCE 冒充 — 没落地成功就不改状态, 这是 R14 的纪律）。
        """
        try:
            land = getattr(res, "landing", None) or {}
            if isinstance(land, dict):
                nv = land.get("new_value") or land.get("applied", {}) \
                    .get("new_value")
                if isinstance(nv, str) and nv.strip():
                    return nv
            # ② 候选环: run_round 的首个 gated 提案 patch（p0）
            p0 = getattr(self, "_last_p0_patch", None)
            if isinstance(p0, str) and p0.strip():
                return p0
        except Exception as exc:                  # noqa: BLE001 — 留痕不静默
            self._last_skip = "patch 写回取失败（store 不动）: %s" % exc
        return None

    # ── 跨轮分数序列（judge 落盘路径同源 — 不另立账本）──
    def _consolidate_rule(self, tid: str, sig: Dict[str, str],
                          proposal: Any, trial: Optional[Dict],
                          res: Any) -> Optional[Dict[str, Any]]:
        """★★★ R173 · 固化面（landed ⇒ RULES; 三闸 + 只收非种子）。

        ★ 入口条件: landed（真落地过）— 没落地不许固化（不假装学会）。
        ★ 键: Mutator.key_for(sig)（唯一构造 — 与 propose 同口径;
          两侧不一致 ⇒ 固化了永远查不到的老病）。
        ★ 三闸走既有 applier.land_rule（schema check_entry + evidence
          success + readback — R32-R33 的四代打磨, 不重造）。
        ★ 种子键（001/003/reasoning 的签名族）⇒ **no-op 并如实记**
          （那是查表学到的, 不是新规则; persist_learned 的 learned=非
          种子语义 — 代码/JSON 不双源）。
        ★ trial["impl"] 作 patch（完整实现 — 修法经 judge 复验过的）。
        ★ 异常 ⇒ 留痕返回 None（**不许静默** — R150 纪律; 固化失败≠
          本轮失败: impl_store 已写回, 规则下次再学即可）。
        """
        try:
            from dwc.organs.evolver import Mutator
            from dwc.harness.landing import LandingError
            key = Mutator.key_for(sig)
            if key in Mutator.SEED_KEYS:
                self._last_consolidation = {"key": key, "outcome": "seed_noop"}
                return self._last_consolidation
            rec = (self.judge.anchors.get(tid) or
                   (getattr(self.judge, "sealed", None) or {}).get(tid) or {})
            entry = {
                "component": proposal.component,
                "dimension": proposal.dimension or "D1",
                "target_layer": (proposal.target_layer or ""),
                "target": tid,
                "m": (sig.get("m") or ""),
                "m_source": (sig.get("m_source") or "rule"),
                "patch": (trial or {}).get("impl") or proposal.patch,
                "rationale": ("R173 Loop 固化: task %s 由提案落地并经 judge"
                              " 复验（strategy=bridge-landed）" % tid),
            }
            tgt = _RuleTarget(Mutator, key)
            rec_res = self.applier.land_rule(
                tgt, key, entry,
                {"success": bool((trial or {}).get("success")),
                 "split": "dev", "task": tid},
                Mutator.check_entry)
            self._last_consolidation = {
                "key": key, "outcome": "consolidated",
                "readback_ok": rec_res.readback_ok}
            return self._last_consolidation
        except Exception as exc:                 # noqa: BLE001 — 留痕不静默
            self._last_consolidation = {"outcome": "error",
                                        "why": "%s: %s" % (type(exc).__name__,
                                                            exc)}
            return self._last_consolidation

    def _pick_task(self, tasks: List[str]) -> str:
        """★★★ R172: δ_θ 排序 + EL 状态机的任务采样（core._el_pick 同源）。

        ★ 节律（与 core 同款）: judge 判分点数没变 ⇒ **不重复推进** EL
          （EL 判定绑定观测变化 — 论文「窗口满 B 判一次」的速率口映射）。
        ★ δ 排序: 任一 task δ>0 ⇒ 降序（罕见失败任务优先探 — 稳定排序,
          同 δ 保 candidate 原序）; 全 0/无判分 ⇒ 原序（零历史真保底）。
        ★ EL index: decide_from_rate(p̂, n) 的 index 取 acts[idx-1];
          index>n（候选收缩）⇒ 拉回 1（不触发 el_sched 的 k>N raise）。
        ★ insufficient（无观测）⇒ index 不动 ⇒ 旧机械行为（接线前 compat）。
        """
        from dwc.organs.el_sched import ELScheduler
        from dwc.organs.weakness import task_delta_map
        if self.el is None:
            self.el = ELScheduler()
        pts = self.judge.task_scores(split="dev")
        dmap = task_delta_map(pts, self.judge.store.evidence) \
            if pts else {}
        if any(dmap.get(t, 0.0) > 0.0 for t in tasks):
            tasks = sorted(tasks, key=lambda t: -dmap.get(t, 0.0))
        n = len(tasks)
        if self.el.index > n:
            self.el.index = 1
        token = len(pts)
        if token != self._el_token:
            # ★★★ p̂ 口径（R172 实测纠偏 — probe 抓到卡死 20 轮 idle）:
            #   EL 判的是**当前环境**的 pass-rate（式2 三段: p̂≤τ ⇒ 停滞
            #   不动 / p̂>τ ⇒ index 推进）— 首版我喂**全体判分 mean**
            #   （002/004/005/006 恒 0 ⇒ mean≤τ ⇒ 永久 stalled ⇒ 001
            #   idle 19 轮）⇒ 正解: **当前被选 task**（EL index 指向的
            #   环境）的最近判分; 该 task 无判分 ⇒ None ⇒ insufficient
            #   （没观测过不冒充 — 与原纪律同; core._el_pick 用了 world
            #   observed_rate 是**世界树单环境**语义, 不是多环境混 mean）
            _mine = ([p for p in pts if p.task_id == self._el_last_task]
                     if self._el_last_task else [])
            _pr = float(_mine[-1].score) if _mine else None
            self._el_last = self.el.decide_from_rate(_pr, n)
            self._el_token = token
        idx = (self._el_last.index if self._el_last is not None else 1)
        picked = tasks[(idx - 1) % n]
        self._el_last_task = picked       # ★ 下一轮 p̂ 的归因环境
        return picked

    def _last_history_score(self) -> Optional[float]:
        """★ R170: score_history 末条 score（score_star 的对照锚）。

        ★ 空文件/坏行 ⇒ None（不造 0.0 基准 — 首轮的 score_star 缺席是
          事实; σ/门⑤ 的 na 口径由 gates 自己判）。
        """
        path = os.path.join(self.anchors_dir, "score_history.jsonl")
        if not os.path.exists(path):
            return None
        try:
            last = None
            for line in io.open(path, encoding="utf-8"):
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue                # 坏行跳过（不留痕 — 读侧容差）
                s = rec.get("score")
                if isinstance(s, (int, float)) and not isinstance(s, bool):
                    last = float(s)
            return last
        except OSError:
            return None

    def _append_history(self, round_no: int, tasks: List[str],
                        score: Optional[float], landed: int) -> None:
        path = os.path.join(self.anchors_dir, "score_history.jsonl")
        # ★ schema 与 e2e **同款**（{round, score, src}）—— R165 实测教训:
        #   首版我写 {round, tasks, score, landed} ⇒ e2e 的 natural_rise
        #   读 h["src"] 当场 KeyError ⇒ **不同写入方共用一文件必须同 schema**
        #   （另立键 = 把别人炸了; 另立文件 = 账本分家 ⇒ σ 消费面双源）
        rec = {"round": round_no, "score": score,
               "src": "loop:dev-rotation (R165 · task=%s)"
                      % (tasks[0] if tasks else "-"),
               "landed": landed, "tasks": list(tasks)}
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    def _dev_tasks(self) -> List[str]:
        return sorted(k for k in self.judge.anchors
                      if not k.startswith("_"))


class _CurrentProposal:
    """★★ R174: 伪提案 — 」当前实现」当候选（replay shortlist 的 current 项）。

    ★ 为什么需要它: _trial_run 吃 Proposal 接口（.patch/.target）— 当前
      实现的"修法"就是它自己（保持现状 = 恒等 patch）⇒ 用同一试跑面
      拿 V(current)（不另造口径 — 复用 judge 复验路径）。
    """

    def __init__(self, tid: str, impl: str):
        self.tid = tid
        self.impl = impl or ""
        # _trial_run keyword 分支吃 proposal.patch（答案文本）
        # behavior 分支吃 target（当前实现的 fn 名）

    def __getattr__(self, name):
        return getattr(_CurProbe(self.tid, self.impl), name)


class _CurProbe:
    def __init__(self, tid, impl):
        self.patch = impl or ""
        self.target = tid


class _RuleTarget:
    """★★ R173: Mutator.RULES 的可写面（applier.Target — e2e step8g 同款）。

    ★ flush_fn = Mutator.persist_learned（固化的跨进程存活 — R32 口径:
      种子留代码 · 学到的落盘 config/anchors/rules.json, 不双源）。
    """

    def __init__(self, mutator_cls: Any, key: str):
        from dwc.organs.applier import Target
        self._t = Target(getter=lambda: mutator_cls.RULES.get(key),
                         setter=lambda v: mutator_cls.RULES.__setitem__(key, v),
                         has_fn=lambda: key in mutator_cls.RULES,
                         delete_fn=lambda: mutator_cls.RULES.pop(key, None),
                         flush_fn=mutator_cls.persist_learned)

    def has(self):
        return self._t.has()

    def snapshot(self):
        return self._t.snapshot()

    def write(self, v):
        return self._t.write(v)

    def flush(self):
        return self._t.flush()


class _MemoryTarget:
    """★ 最小可写面（内存 box — 生产 Target 的替身面, 带读回）。

    ★ R165 边界: 真生产落地面由调用方按部署形态给（文件/RULES）;
      循环本身只证明"落地链路在轮里真跑过" ⇒ 用内存 target（不写脏盘）。
    """

    def __init__(self):
        self._box: Dict[str, Any] = {"v": "loop_init"}
        from dwc.organs.applier import Target
        self._t = Target(getter=lambda: self._box.get("v"),
                         setter=lambda x: self._box.__setitem__("v", x),
                         has_fn=lambda: "v" in self._box)

    def has(self):  return self._t.has()
    def snapshot(self):  return self._t.snapshot()
    def write(self, patch):  return self._t.write(patch)


def build_round_fn(**kw: Any):
    """★ 工厂: Loop(...).round — 给 Daemon 的 round_fn 契约形状。"""
    loop = Loop(**kw)
    return loop.round


LOOP_MECHANICS: Dict[str, str] = {
    "no_new_judgement": "单轮闭环全复用既有器官（execute_task/judge/evolver/gate_all/pipeline）— 零新判定",
    "llm_free_default": "use_llm=False 默认（LLM 提案路径由 e2e step9 覆盖; 循环的确定性面先稳）",
    "task_selection": "round_no % len(dev_tasks) 机械轮转 — 真选择器无设计不发明（R73 同族 backlog）",
    "score_history": "score_history.jsonl 沿用 judge 落盘路径同源（不另立账本 — σ_t 消费面）",
    "memory_target": "真落地面由部署方给; 循环用内存 target 证链路真跑（不写脏盘）",
    "idle_not_error": "task 已过/无提案命中/idle≠error — 与 daemon 熔断计数分族",
}
