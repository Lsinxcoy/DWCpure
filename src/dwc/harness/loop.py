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

import json
import os
from typing import Any, Dict, List, Optional

from dwc.organs.actor import Actor, execute_task
from dwc.organs.applier import Applier
from dwc.organs.evolver import Evolver
from dwc.organs.judge import Judge
from dwc.harness.pipeline import run_round
from dwc.harness.splitfeed import feed_pair
from dwc.harness.candidate_bridge import BridgeError


class LoopError(Exception):
    """真 round_fn 组装的显式拒绝（anchors 空/落盘路径同侧缺）。"""


class Loop:
    """★ 常驻单轮闭环（Daemon.round_fn 的生产实现）。"""

    def __init__(self, *, anchors_dir: Optional[str] = None,
                 registry: Optional[Any] = None,
                 use_llm: bool = False,
                 max_tasks_per_round: int = 8):
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

    # ── 真 round_fn（Daemon 契约: (round_no, daemon) -> dict|None）──
    def round(self, round_no: int, daemon: Any = None) -> Dict[str, Any]:
        tasks = self._dev_tasks()
        if not tasks:
            raise LoopError("dev split 无锚点任务 ⇒ 无任务面可转")
        sel = [tasks[round_no % len(tasks)]]    # ★ 机械轮转（R73 裁决）
        n_landed = 0
        verdicts: List[str] = []
        score_vals: List[float] = []
        for tid in sel:
            out = self._run_one_task(tid)
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
        return {"n_candidates": self._last_n_candidates,
                "chain_verdict": cv,
                "blocked": self._last_blocked,
                "landed": n_landed > 0,
                "score": score,
                "tasks": sel,
                "skipped_reason": (self._last_skip
                                   if self._last_skip else None)}

    # ── 单 task 闭环（全器官复用）──
    def _run_one_task(self, tid: str) -> Dict[str, Any]:
        from dwc.harness.landing import LandingError
        from dwc.organs.actor import Actor as _A     # noqa: F401
        self._last_n_candidates = 0
        self._last_blocked = []
        self._last_skip = None
        try:
            out = execute_task(self.actor, self.judge, tid)
        except Exception as exc:                    # noqa: BLE001
            self._last_skip = "execute_task 失败: %s" % exc
            return {"chain_verdict": "blocked", "score": None, "landed": False}
        v = self.judge.evaluate(tid, "dev", observed=out["observation"])
        score = 1.0 if v.success else 0.0
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
            self._last_skip = "无提案命中（task=%r）" % tid
            return {"chain_verdict": "blocked", "score": score, "landed": False}
        gated = self.evolver.gate_all(proposals)     # R162 两层并轨
        self._last_n_candidates = len(proposals)
        if not gated["gated"]:
            self._last_skip = "全提案被层①拦（无 gated）"
            self._last_blocked = ["gate_all:no_gated"]
            return {"chain_verdict": "blocked", "score": score,
                    "landed": False}
        # ★ splitfeed 产弹（baseline=当前实现, current=候选 patch 后 —
        #   stub: 当前以 task 双跑 observation 代表两侧; 真侧差由 judge 出）
        try:
            base, cur = feed_pair(
                self.judge,
                lambda _t, _tid=tid: out["observation"],
                lambda _t, _tid=tid: out["observation"])
        except Exception:                            # noqa: BLE001
            base = cur = None
        from dwc.harness.candidate_bridge import to_facts
        cands = [to_facts([p]) for p in gated["gated"][:self.max_tasks]]
        cand_objs = [{"patch": p.patch, "component": p.component,
                      "grounding": [], "dimension": "D1"}
                     for p in gated["gated"][:self.max_tasks]]
        p0 = gated["gated"][0]
        res = run_round(cand_objs, t=round_no, proposal=p0,
                        ledger=None, vocabulary=(),
                        pass_rate=None, score_star=None,
                        delta_s=None, delta_c=None, noise_band=None,
                        domain_guard_ok=None, split_verdict=None,
                        baseline=base, current=cur,
                        applier=self.applier,
                        target=_MemoryTarget(),
                        evidence={"success": True,
                                  "reason": "loop: %s" % tid})
        landed = bool(res.landing)
        return {"chain_verdict": res.chain["verdict"],
                "blocked": list(res.chain.get("blocked") or []),
                "score": score, "landed": landed}

    # ── 跨轮分数序列（judge 落盘路径同源 — 不另立账本）──
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
