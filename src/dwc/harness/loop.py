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
import sys
from typing import Any

from dwc.harness.pipeline import run_round
from dwc.harness.splitfeed import feed_pair
from dwc.organs.actor import Actor, execute_task
from dwc.organs.applier import Applier
from dwc.organs.direction import (
    DirectionAttempt,
    DirectionDecision,
    DirectionError,
    ensure_direction,
    reverse_candidates,
)
from dwc.organs.direction import next_action as dir_next_action
from dwc.organs.evolver import Evolver
from dwc.organs.judge import Judge
from dwc.organs.replay import no_worse_than_current, select_policy, shortlist_candidates


class LoopError(Exception):
    """真 round_fn 组装的显式拒绝（anchors 空/落盘路径同侧缺）。"""


class Loop:
    """★ 常驻单轮闭环（Daemon.round_fn 的生产实现）。"""

    def __init__(self, *, anchors_dir: str | None = None,
                 registry: Any | None = None,
                 use_llm: bool = False,
                 planner_live: bool = False,
                 max_tasks_per_round: int = 8,
                 impl_floor: str = "broken",
                 impl_source: str | None = None):
        """impl_floor: "broken"(R170 默认 — 初值错误) | "golden"(旧行为).
        impl_source: 开局实现文件（缺省 anchors_dir/broken_dev.json）."""
        self.registry = registry
        self.use_llm = use_llm
        # ★★ R185 · planner 现场层（门②的 FGGM 现场合成 — 默认关同
        #   use_llm 纪律: LLM 有成本且非确定, 调用方显式开）
        self.planner_live = bool(planner_live)
        # ★ 痕迹字段常驻初始化（否则 round 从 replay/kept_current 等
        #   早退路径返回时属性不存在 ⇒ 读方 AttributeError — 实测两红）
        self._last_planner_trace = None
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
        #: ★ R276-① · 进化记忆挂钩（默认 None＝零行为变化；daemon/
        #   e2e 经 attach_memory 接生产或隔离库 — Loop 本体不建库）。
        self.memory = None
        self.max_tasks = int(max_tasks_per_round)
        #: ★★ R170 · 可变实现集（task_id → 当前实现源码）— agent 的"手":
        #   开局 = broken_dev（初值错误）; `landing` 每次落地成功 ⇒ 写回
        #   本表 ⇒ 下轮 judge 评的是**修过的**实现 ⇒ 分数变化 = agent 真干活
        #   （对比: 此前 execute_task(implementation=None) 走 REFERENCE,
        #     task 恒过 ⇒ 闭环空转 — R171 实测 12 轮 n_landed=0 的根因）
        self.impl_store: dict[str, str] = {}
        self.impl_floor = str(impl_floor or "golden")
        #: ★ R172: EL 调度状态（与 core.DWC 同款 — 双池共用机制不分裂）
        self.el = None
        self._el_last = None
        self._el_token = -1
        self._el_last_task: str | None = None    # ★ R172: p̂ 归因环境
        self._last_consolidation: dict | None = None  # ★ R173 固化痕迹
        self._last_replay_pick: dict | None = None    # ★ R174 replay 选择痕迹
        self._last_a_train: float | None = None       # ★ R176 A_train 痕迹
        self._last_a_train_why: str = ""                 # ★ R176 缺席原因
        self._last_metric_pick: dict | None = None     # ★ R180 Metric Loop 选优痕迹
        self._metric_loop_why: str = ""                  # ★ R180 缺席/异常原因
        self._last_adopt: dict | None = None          # ★ R183 adopt 痕迹
        self._adopt_why: str = ""                        # ★ R183 不采纳原因
        self._load_impl_floor(impl_source)

    def _load_impl_floor(self, impl_source: str | None) -> None:
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
            raw = json.load(open(path, encoding="utf-8"))
        except Exception as exc:                  # noqa: BLE001 — 留痕不静默
            raise LoopError("开局实现文件读不了: %s: %s"
                            % (path, exc))
        n = 0
        self.rules_known: dict[str, bool] = {}
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
        self._last_ledger_entries: list[Any] = []
        # ★★★ R188 · DirectionController 在途状态（跨调用点传链:
        #   _run_one_task 内一次取方向 → 候选 → 判停滞 → 换向; 每任务
        #   每轮一条链, round 入口清空（串行生产, 无并发问题）
        #   dict[task_id] = List[DirectionAttempt]
        self._dir_attempts: dict[str, list[DirectionAttempt]] = {}
        #: R188 决策痕迹（读窗口 — 监控/测试可查; 每 _run_one_task 出口更新）
        self._last_dir_decision: DirectionDecision | None = None

    # ── 真 round_fn（Daemon 契约: (round_no, daemon) -> dict|None）──
    def round(self, round_no: int, daemon: Any = None) -> dict[str, Any]:
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
        # ★ R188 · 方向链按轮重建（跨轮的尝试账本由 ledger 持久化,
        #   进程内只保当前轮 — daemon 重启=重新开始, 保守默认同 R183）
        self._dir_attempts = {}
        sel = [self._pick_task(tasks)]
        n_landed = 0
        verdicts: list[str] = []
        score_vals: list[float] = []
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
        from dwc.daemon import RoundLog
        from dwc.organs.metrics import metrics_from_round
        self.last_metrics = metrics_from_round(
            RoundLog(round_no=round_no, started_at=0.0,
                     n_candidates=getattr(self, "_last_n_candidates", 0),
                     chain_verdict=cv, landed=n_landed > 0,
                     score=score),
            ledger_entries=self._last_ledger_entries)
        # ★ R180: Metric Loop tick（观察面 — 只读选+留痕, 不换判据树;
        #   dev 真数据现在已被本轮判分追加（_run_one_task 内 judge.evaluate
        #   落点）⇒ 此处读的是"含本轮"的 dev 面 — 顺序不能反]
        self._metric_loop_tick()
        return {"n_candidates": self._last_n_candidates,
                "chain_verdict": cv,
                "blocked": self._last_blocked,
                "landed": n_landed > 0,
                "score": score,
                "tasks": sel,
                "metric_pick": self._last_metric_pick,
                "metric_adopt": self._last_adopt,
                "adopt_why": (self._adopt_why if self._adopt_why else None),
                "metric_loop_why": (self._metric_loop_why
                                    if self._metric_loop_why else None),
                "skipped_reason": (self._last_skip
                                   if self._last_skip else None)}

    # ── 单 task 闭环（全器官复用）──
    # ── R188 · DirectionController（三方向 fallback 链）─────────
    def _dir_archive_path(self) -> str:
        """方向台账路径（archive/direction_ledger.jsonl — 与知识档同目录）。"""
        import os as _os
        root = getattr(self, "repo_root", None)
        if root is None:
            root = _os.path.dirname(_os.path.dirname(_os.path.dirname(
                _os.path.dirname(_os.path.abspath(__file__)))))
        return _os.path.join(root, "archive", "direction_ledger.jsonl")

    def _broken_impl_for_fn(self, rec: dict[str, Any]) -> str | None:
        """R189-B · train behavior 面的实现回退面（broken_dev 同 fn 初值）。

        ★ 原则: train 观测必须是 **agent 产出**。impl_store 未载该 tid 时
          回退到 broken_dev 里同 fn 的 broken_impl（agent 的"初值错误"态）;
          再没有 ⇒ None（调用方跳过 — 不拿 REFERENCE 基准冒充产出）。
        """
        try:
            import json as _json

            from dwc.organs.judge import TRUTH_SOURCE as _TS
            # TRUTH_SOURCE[0][1] = dev.json 的路径 ⇒ 取它的目录找 broken_dev
            _dev_path = (_TS[0][1] if _TS and isinstance(_TS[0], tuple)
                         else None)
            if not _dev_path:
                return None
            bd_path = os.path.join(os.path.dirname(_dev_path),
                                   "broken_dev.json")
            if not os.path.exists(bd_path):
                return None
            with open(bd_path, encoding="utf-8") as _fh:
                bd = _json.load(_fh)
            want = {(c or {}).get("fn")
                    for c in (rec.get("checks") or []) if isinstance(c, dict)}
            for k in sorted(bd):                # 排序 ⇒ 同 fn 多条时确定选
                v = bd[k]
                if k.startswith("_") or not isinstance(v, dict):
                    continue
                if v.get("fn") in want and v.get("broken_impl"):
                    return v["broken_impl"]
            return None
        except Exception:                      # noqa: BLE001 — 观察面自吞
            return None

    def _dir_pick_candidates(self, tid: str, sig: dict[str, str],
                             round_no: int, score: float | None,
                             sigs: list[dict[str, str]] | None = None) -> list:
        """FORWARD 空 ⇒ 沿 fallback 序换向生成候选（R188 R1/R2/R3）。

        ★ 三条规则的在此的形态:
          R1 停滞即换 — evolver 对应入口产出 0 候选 ⇒ 记 attempt
             (n_candidates=0) ⇒ 下一跳 next_action 换向;
          R2 序内 fallback — fallback_order(round_no, tid) 派生确定性
             全序（sha256 种子 — 同输入同输出, 不用真随机）;
          R3 全败记账 — DirectionError ⇒ 台账 + []（调用方 blocked,
             与 R173 硬编码返回语义一致, 旧行为不回归）。
        ★★★ R173 的伦理边界不变: 候选生成 ≠ 采纳; 泛化 patch
          修不好 ⇒ 门/试跑拦 ⇒ 弃权, 不硬过。
        """
        from dwc.organs.evolver import COMPONENT_VOCAB
        attempts = self._dir_attempts.setdefault(tid, [])
        # ★ FORWARD 的尝试已由调用方完成（diagnose 空 ⇒ 才进本函数）⇒
        #   必须先记一笔 attempt（否则 next_action 会把 FORWARD 当"未试
        #   过"再选一次 — R188 smoke 抓到: 实测链首跳 LATERAL 后又回到
        #   FORWARD, 与 04128 "fall back" 向前不回退的语义相反）
        if not any(a.direction.value == "FORWARD" for a in attempts):
            attempts.append(DirectionAttempt(
                direction=ensure_direction("FORWARD"), n_candidates=0,
                note="R188: FORWARD 无签名命中 ⇒ 记停滞（入链起点）"))
        for _hop in range(3):                    # 三方向, 一方向一跳
            try:
                dec = dir_next_action(
                    attempts, round_no=round_no, task_id=tid)
            except DirectionError as exc:
                # R3 · 全败 ⇒ 台账（自吞异常不冒泡断主链 — G7 观察面纪律）
                self._dir_ledger_append(tid, attempts, terminal=str(exc))
                self._last_skip = ("三方向全败（terminal — R3）: task=%r; "
                                   "%s" % (tid, exc))
                return []
            self._last_dir_decision = dec
            _kind = (self.judge.anchors.get(tid) or {}).get(
                "verifier_kind")
            # ★ R202 prefer: 文本任务 → prompt 组件; behavior → 代码组件
            #   （COMPONENT_VOCAB 去 prompt — 偏好组空时 propose_lateral
            #    自动回落全集, 不弃候选）
            _prefer = ((("prompt",) if _kind in ("keyword_match",
                                                "expected_values")
                        else tuple(c for c in COMPONENT_VOCAB
                                   if c != "prompt"))
                       if _kind else None)
            cands = self._dir_generate(dec.direction, sig, sigs=sigs,
                                       prefer_components=_prefer)
            self._dir_ledger_append(
                tid, attempts, direction=dec.direction,
                n_candidates=len(cands), reason=dec.reason)
            if cands:
                # 候选生成 ≠ 算成功（采纳仍归门+试跑 ⇒ 不加"成功"语义）
                # ★ 但**必须记账**: 不记 ⇒ next_action 认该方向"未试过"
                #   下轮再选它一次（04128 序内不回退被破 — R188 smoke
                #   抓到: LATERAL 在 r2 生成候选, r3 又从 LATERAL 起跳）
                attempts.append(DirectionAttempt(
                    direction=dec.direction, n_candidates=len(cands),
                    note="R188: %s 生成 %d 候选（入链）"
                         % (dec.direction.value, len(cands))))
                return cands
            # R1 形态③: 本方向无对象 ⇒ 记停滞, 下一跳换向（链不回退）
            attempts.append(DirectionAttempt(
                direction=dec.direction, n_candidates=0,
                note="R188: %s 无候选 ⇒ 换向" % dec.direction.value))
        # 理论不可达（3 跳 = 三方向全试 → 上面已 terminal）; 留痕不静默
        self._last_skip = ("三方向均已试且无候选（task=%r — R3 旁路）" % tid)
        return []

    def _dir_generate(self, direction, sig: dict[str, str],
                      sigs: list[dict[str, str]] | None = None,
                      prefer_components: tuple | None = None) -> list:
        """R188 · 按方向调 evolver 对应入口（表驱动, 防 if-elif 漂移）。

        ★ FORWARD  = diagnose 的签名命中（本 fn 的专有修法）
        ★ LATERAL  = propose_lateral（同 (c,q) 近亲泛化 — R173 起就在）
        ★ REVERSE  = reverse_candidates 查"更简单"目标表; **现 RULES
                     无此类 target ⇒ 如实 []**（不编造候选 — R188
                     诚实边界: 表驱动登记位, 将来 RULES 长出简化类
                     target 时这里是唯一入口）
        ★★★ R191 · REVERSE 只动**提案侧**（target/patch — 能力的退一步,
          2603.25111 的 f_d 形状）; 降 verifier_rung / 改 checks 这类
          **判据侧**降阶由 reverse_candidates 里 DirectionError 挡住
          （G2 判据在系统外 / 门⑥账本只认"落地了" / split 分离 — 见
          direction.py REVERSE_SCOPE 与 R191 裁决文档）
        """
        if direction.value == "LATERAL":
            try:
                # ★ R202: 同 component 优先（文本任务借 prompt kin,
                #   behavior 借代码 kin — 见 Mutator.propose_lateral 注）
                lat = self.evolver.propose_lateral(
                    sig, prefer_components=prefer_components)
                return [lat] if lat is not None else []
            except Exception as exc:            # noqa: BLE001 — 留痕不静默
                self._last_skip = "LATERAL 泛化失败: %s" % exc
                return []
        if direction.value == "REVERSE":
            comps = reverse_candidates(self._dir_rules_index(),
                                       (sig.get("c") or ""))
            if not comps:
                self._last_skip = ("REVERSE: 无更简单 target 可回退"
                                  "（c=%r; RULES 无简化类 — 如实 []）"
                                  % sig.get("c"))
            return []      # 返 [] — 候选位由 RULES 表驱动判"有无";
                           # 真候选生成仍归 evolver（不在此造 patch）
        # FORWARD（缺省分支 — 显式三选一, 不猜）
        try:
            # ★★ R197 ①: 与主路径同口径吃全量签名簇; 未传 ⇒ 回退 [sig]
            #   （旧调用方行为逐字节不变 — 单签名等价）
            return list(self.evolver.diagnose(list(sigs or []) or [sig])
                        .get("proposals", []))
        except Exception as exc:                # noqa: BLE001
            self._last_skip = "diagnose 失败: %s" % exc
            return []

    def _dir_rules_index(self) -> dict[str, dict]:
        """RULES 表引用（REVERSE 判据的输入 — 不复制, 取真源）。"""
        ev = self.evolver
        for attr in ("RULES", "_RULES", "rules"):
            tbl = getattr(ev, attr, None)
            if isinstance(tbl, dict):
                return tbl
        return {}

    def attach_memory(self, mem: Any) -> Any:
        """★ R276-① · 接记忆库（生产 Memory 或隔离库；返 mem 供链式）。"""
        self.memory = mem
        return mem

    def _remember_failure(self, tid: str, sigs: Any, verdict: Any = None) -> int:
        """★ R276-① · 失败签名回灌 EXPERIENCE（judge→memory 的线）。

        未 attach ⇒ 0；缺 c/q/m 跳过（D6）；异常 stderr 留痕不阻断诊断。

        ★★★ R审计-P2 · 补 scene / detail（记忆内容强化 — P0-1/2）:
          现场实测: failure_sig 的 payload 只有 {c,q,m,task}，task 是任务 ID
          ⇒ recall 路1 用自然语言场景词匹配 ⇒ **永不命中**
          ⇒ 129 条失败签名只有 8 条被访问过（6.2%）。
          修法（只补字段，不改语义）:
            scene  = judge.anchors[tid]["prompt"]（任务描述原文 — 真实场景词）
            detail = verdict.reason + diffs 摘要（judge 已产出的失败原因，
                     此前没存进记忆 ⇒ dream 的 boundary 永远是"未知"）
          ⇒ 不发明内容: 全部取自 judge 已有的真值面。
        """
        if self.memory is None:
            return 0
        # ★ 场景词 + 失败原因（judge 真值面 — 缺则留空，不编）
        scene = ""
        detail = ""
        try:
            _anch = getattr(getattr(self, "judge", None), "anchors", None) or {}
            scene = str((_anch.get(tid) or {}).get("prompt") or "")
        except Exception:                            # noqa: BLE001
            scene = ""
        if verdict is not None:
            _why = str(getattr(verdict, "reason", "") or "")
            _diffs = getattr(verdict, "diffs", None) or []
            _d0 = []
            for _d in _diffs[:3]:
                if isinstance(_d, dict):
                    _d0.append("%s:%s" % (_d.get("check") or _d.get("fn") or "?",
                                          _d.get("got", _d.get("why", "")))[:80])
            detail = (_why + (" | " + "; ".join(_d0) if _d0 else ""))[:300]
        n = 0
        try:
            from dwc.organs.memory import MemoryKind
            for s in (sigs or []):
                s = dict(s or {})
                if not (s.get("c") and s.get("q") and s.get("m")):
                    continue
                _pl = {"c": s["c"], "q": s["q"], "m": s["m"], "task": tid}
                if scene:
                    _pl["scene"] = scene
                if detail:
                    _pl["detail"] = detail
                self.memory.remember(MemoryKind.FAILURE_SIGNATURE, _pl)
                n += 1
        except Exception as exc:                     # noqa: BLE001
            sys.stderr.write("evolve 回灌跳过: %s\n" % exc)
        return n

    def _var_path(self, name: str) -> str:
        """★ R276-③ · repo var 下路径（与 anchors 同口径上溯 4 层）。"""
        return os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(
                os.path.dirname(os.path.abspath(__file__))))),
            "var", name)

    def _persist_credit(self, tid: str, round_no: int) -> int:
        """★ R276-③ · 本轮 ledger 账落盘（append-only jsonl；异常留痕）。"""
        try:
            rows = list(self._last_ledger_entries or [])
            with open(self._var_path("credit_ledger.jsonl"), "a",
                         encoding="utf-8") as fh:
                fh.writelines(json.dumps(
                        {"round": round_no, "task": tid, "entry": e},
                        ensure_ascii=False, default=str) + "\n" for e in rows)
            return len(rows)
        except Exception as exc:                     # noqa: BLE001
            sys.stderr.write("credit 落盘跳过: %s\n" % exc)
            return 0

    def _dir_ledger_append(self, tid: str, attempts, direction=None,
                           n_candidates: int = 0, reason: str = "",
                           terminal: str = "") -> None:
        """R188 方向台账（观察面 — 自吞异常留痕, 不冒泡断主链）。"""
        try:
            import json as _json
            import os as _os
            entry = {"gen": "R188",
                     "task": tid,
                     "direction": (direction.value if direction is not None
                                   else "TERMINAL"),
                     "n_candidates": n_candidates,
                     "reason": reason,
                     "terminal": terminal,
                     "attempts_so_far": [a.direction.value
                                         for a in attempts]}
            path = self._dir_archive_path()
            _os.makedirs(_os.path.dirname(path), exist_ok=True)
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(_json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as exc:        # F3: 写失败**留痕**（审计轨迹不许
            # 静默丢 —— G7 同族; 不炸主链: 观察面失败不拦进化决策）
            self._last_archive_error = ("%s: %s"
                                        % (type(exc).__name__,
                                           str(exc)[:120]))

    def _run_one_task(self, tid: str, round_no: int = 0
                      ) -> dict[str, Any]:
        from dwc.organs.actor import Actor as _A  # noqa: F401
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
        # ★★★ R197 ① · diagnose 入参从 [主签名] 扩为 **全量签名簇**
        #   （judge 已产 Verdict.sigs — 每个 notok check 一条, 去重）。
        #   · diagnose 已按 (c,q,m) 聚类 ⇒ 传多个**不会重复提案**（约束 4 逐字）
        #   · 旧行为: 单签名时 `sigs=[sig]` ⇒ 与旧 `[sig]` **等价**（回退保底）
        sig = dict(v.failure_signature or {})
        sigs = list(getattr(v, "sigs", None) or []) or [sig]
        self._remember_failure(tid, sigs, v)  # ★ R276-① · 判败即记 EXPERIENCE
        try:
            proposals = self.evolver.diagnose(sigs).get("proposals", [])
        except Exception as exc:                    # noqa: BLE001
            self._last_skip = "diagnose 失败: %s" % exc
            return {"chain_verdict": "blocked", "score": score, "landed": False}
        # ★★★ R200 · 文本任务撞键守卫（RULES 键 = c:q:fn **不含任务维度**
        #   ⇒ 跨任务撞键真实存在: "mean" 同时是 reproduce_001/002 的失败
        #   key（R171 keyword 族当年 kw 恰好逐任务唯一, 才没暴露）。
        #   文本族 RULES 的 target = **task_id**（R171 语义, _trial_run
        #   docstring 逐字）⇒ 按 target==tid 过滤, 否则:
        #     ① 拿别任务的答案文本试跑（浪费一轮）
        #     ② 更糟: 部分 key 恰好同值时（001/002 的 mean 都是 6.00）
        #        半对答案可能赢 replay 选择 ⇒ 把别任务知识落进本任务。
        #   ★ behavior 族不滤（其 target = fn 名, 不是 task_id — 语义
        #     不同, 只在文本分支生效）。
        if ((self.judge.anchors.get(tid) or {}).get("verifier_kind")
                in ("keyword_match", "expected_values")):
            proposals = [pp for pp in proposals
                         if str(getattr(pp, "target", "")) == tid]
        # ★★★ R188 · DirectionController 接线（R186 搜论文 → R187 A×B 收敛
        #   → 本处落地）: 上面 try 拿到的 proposals = FORWARD 的候选面;
        #   空了不直接走 LATERAL 硬编码, 而是沿 fallback 序换向——
        #   前三次方向尝试各由 evolver 的对应入口生成候选, 停滞即换。
        #   ★ 分工不变: 本段只决定"试哪个方向"（生成候选）;
        #     "能不能落地"仍归六门+replay（R174/R181 原样）。
        if not proposals:
            proposals = self._dir_pick_candidates(tid, sig, round_no, score,
                                                  sigs=sigs)
            if not proposals:
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
        # ★ R176: A_train（train = 历史落地 attempt 无标签集; op 池共识面
        #   以 κ=10 reliability 接入属 R177 Metric Loop 重组 — 本轮只采集
        #   留痕, 不动 S(e) 公式（论文式不改 — memory 铁律））
        _at, _at_why = self._a_train(proposals[0].component,
                                     str(getattr(proposals[0], "target", "")))
        self._last_a_train = _at
        self._last_a_train_why = json.dumps(_at_why, ensure_ascii=False)
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
        # ★★ R185 · planner 现场层装表（R178 裁决的 Loop 端落实 — 门②
        #   读共享开关; 装前记原值 ⇒ 用完复位: 本循环的开关不泄漏给
        #   其它调用方/测试（与 R181 探针 finally 复位同纪律））
        from dwc.harness import gates as _gates_mod
        _prev_pl = _gates_mod.planner_layer_injection()
        if self.planner_live:
            _gates_mod.set_planner_layer(True)
        try:
            gated = self.evolver.gate_all(proposals)   # R162 两层并轨
        finally:
            if self.planner_live:
                _gates_mod.set_planner_layer(_prev_pl)
        self._last_n_candidates = len(proposals)
        # ★★ R185: planner 现场层痕迹（只摘最新 gated 提案的 per_contract —
        #   诚实原则: 现场层是 per-candidate 的, 不汇总成"这一轮过了"的
        #   单值。缺席 ⇒ None（planner_live=False 或层①全拦时如实）
        self._last_planner_trace = None
        if self.planner_live:
            for _p in gated.get("gated", []) or []:
                _gv = getattr(_p, "gate_verdict", None) or {}
                _pc = ((_gv.get("six_gate_chain") or {}).get("gates")
                       or [])
                for _g in _pc:
                    if _g.get("gate") == "contract":
                        _ppc = (_g.get("detail") or {}).get(
                            "per_contract") or {}
                        if "planner_live" in _ppc:
                            self._last_planner_trace = _ppc[
                                "planner_live"]
                            break
                if self._last_planner_trace is not None:
                    break
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
        self._persist_credit(tid, round_no)  # ★ R276-③ · 账落盘（内存只读快照）
        return {"chain_verdict": res.chain["verdict"],
                "blocked": list(res.chain.get("blocked") or []),
                "score": score, "landed": landed}

    def _trial_keyword(self, tid: str, answer: str
                       ) -> dict[str, Any] | None:
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
                   ) -> dict[str, Any] | None:
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
        # ★ R199: expected_values 同走文本试跑（观测契约一致 — 答案文本）
        if _rec.get("verifier_kind") in ("keyword_match", "expected_values"):
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

    def _applied_patch_for(self, tid: str, res: Any) -> str | None:
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

    def _train_outputs_consensus(self) -> float | None:
        """★★★ R184 · A_train 的**真论文口径**（2607.12790 逐字）。

        "A_train(e) = e 与 opining pool ops 在**无标注 train 输出**上的
         共识判定的一致度"

        ★ 与 R183 的差别（正确性修复, 不是功能加码）: R183 用 dev 判据点
          当 train verdicts — 但 dev 点**已被 judge 判过**（带 label）⇒
          不是"无标注输出"。R184 起: train split（R184 落的 6 条无标签
          题面）跑 actor 拿 observation（**只跑不判** — judge 不参与）
          ⇒ op 池对每个 observation 逐 op 三态 ⇒ κ=10 加权共识。
        ★ 缺席如实化: train.json 缺席 / actor 跑炸 ⇒ None（A_train 缺席,
          S(e) fail-closed — 与 R176 三态纪律同族）。
        ★ train 任务无 expected ⇒ op 判的 ctx 里 judge_success=None（喂
          不到 label — 这正是无标签: op 看到的只有跑出来的行为）
        """
        if getattr(self.judge, "train_anchors", None) is None:
            self._last_a_train_why = "train split 缺席（诚实边界④）⇒ A_train 缺席"
            return None
        try:
            from dwc.organs.actor import execute_task as _et
            from dwc.organs.drawback import Node as _N
            from dwc.organs.drawback import _eval as _ev
            from dwc.organs.metric_loop import (
                _current_tree,
                a_train_weighted,
                loo_marginal_dev,
            )

            # ★★★ R189-B · 无标签面用 **TRAIN_POOL**（= DEFAULT_POOL +
            #   exec_ok + evidence_rich — 判据键不依赖 label; 门③仍用
            #   DEFAULT_POOL 不动）⇒ 修 R184 的恒 1.0 口径洞（旧盘 6 op
            #   里 4 个在无标签 ctx 上 abstain, 只剩 parsed_ok/nonempty
            #   两个都判 ⇒ A_train 零分辨）
            from dwc.organs.ops import TRAIN_POOL as _TP
            _ops_map = {op.name: op for op in _TP}
            names = sorted(_ops_map)
            tv: list[dict[str, str]] = []
            pts_like: list[dict[str, Any]] = []
            for tid in sorted(self.judge.train_anchors):
                if tid.startswith("_"):
                    continue
                rec = self.judge.train_anchors[tid]
                # ★★★ R189-B 深层根因修复（实测抓到, 比计划更深）:
                #   train behavior 任务无 impl_store ⇒ implementation=None
                #   ⇒ PureFunctionExecutor 用 **REFERENCE（基准真码）**
                #   ⇒ 观测是"基准的输出" **不是 agent 产出** ⇒ 论文
                #     A_train（ε 与 op 在 **agent 无标注输出**上的一致度）
                #     被架空。⇒ 修法: impl 取序改为
                #     impl_store(agent当前) → broken_dev 同 fn 的 broken_impl
                #     （agent 的"初值错误"态 — 真产出）→ 都没有 ⇒ 跳过
                #     （R184 纪律: 不硬造答案冒充 train 输出）★★ 绝不跑
                #     REFERENCE: 那是基准, 不是被评的产出。
                _impl = self.impl_store.get(tid)
                if not _impl:
                    _impl = self._broken_impl_for_fn(rec)
                if rec.get("verifier_kind") == "keyword_match":
                    if not _impl:
                        continue
                    out = _et(self.actor, self.judge, tid, split="train",
                              implementation=_impl)
                else:
                    if not _impl:
                        # ★ 无 impl 的 behavior ⇒ 跳过（REFERENCE 不是产出）
                        continue
                    out = _et(self.actor, self.judge, tid, split="train",
                              implementation=_impl)
                # ★★★ R189-B · 无标签 ctx 补**质量代理**键（均不依赖 label）:
                #   exec_error — 执行异常名/None（_et 的成败投影; ActorError
                #     会走 traces 而非 observation — 如实取, 不猜）
                #   output_chars — 观测文本长度（evidence_rich 的口粮）
                # ★★ 边界: 这三个键是**代理**不是判分 — judge_success 仍
                #    恒 None（train 无 label 是论文前提; R184 纪律不破）
                _obs_raw = out.get("observation", "")
                _obs = (str(_obs_raw) if not isinstance(_obs_raw, dict)
                        else str(_obs_raw))
                _traces = out.get("traces") or []
                # ★★★ R189-B 二次纠偏（实测抓的第二个口径洞）:
                #   执行器捕异常时 actor 记的是 **outcome="raised" +
                #   observed.exception**（actor.py:284-289）; **不是**
                #   tr.error（那是 Trace 的另一个字段, 本执行路径恒 None）
                #   ⇒ 首版读 tr.error ⇒ factorial 无限递归被当 clean
                #     ⇒ exec_ok 全 clean ⇒ A_train 仍恒 1.0。
                _exec_err = None
                for _t in _traces:
                    if isinstance(_t, dict):
                        if _t.get("outcome") == "raised":
                            _o = _t.get("observed") or {}
                            _exec_err = (_o.get("exception")
                                         if isinstance(_o, dict) else None) \
                                or "raised"
                            break
                    elif getattr(_t, "outcome", None) == "raised":
                        _o = getattr(_t, "observed", None) or {}
                        _exec_err = (_o.get("exception")
                                     if isinstance(_o, dict) else None) \
                            or "raised"
                        break
                ctx = {"judge_success": None,          # ★ 无标签 — 不喂判定
                       "pass_rate": None,
                       "candidate_diff": _obs[:200],
                       "vocabulary": (),
                       "component": None,
                       "parsed_ok": True,
                       # ↓ R189-B 新增（不依赖 label）
                       "exec_error": _exec_err,
                       "output_chars": len(_obs)}
                # ★ 三态投票用 TRAIN_POOL 的 ops_map（R189-B: 池换了,
                #   map 也得换 — 否则 KeyError: exec_ok 未注册在 _POOL_OPS）
                tv.append({n: _ev(_N(kind="leaf", op=n), _ops_map,
                                  None, None, ctx) for n in names})
                pts_like.append({"label": None, "ctx": ctx})
            inc = _current_tree()
            marg = {n: loo_marginal_dev(pts_like, n, inc) for n in names
                    if n != "root_parse_ok"}
            # ★★★ R189-B: op_filter=TRAIN_POOL 全集（不由当前树限 —
            #   否则新 op 的票被静默丢 ⇒ A_train 恒 1 的第三层根因）
            a = a_train_weighted(tv, inc, marg, op_filter=names)
            self._last_a_train_why = ("train split 真无标签共识: %d outputs"
                                      % len(tv))
            return a
        except Exception as exc:              # noqa: BLE001 — 留痕不静默
            self._last_a_train_why = ("train 共识面失败: %s: %s"
                                      % (type(exc).__name__, exc))
            return None

    def _a_train_weighted(self, pts: list[dict[str, Any]]
                          ) -> float | None:
        """★★★ R183 · A_train（κ=10 加权 — R182 的 Loop 侧适配）。

        ★ train verdicts = 每个 dev 点 ctx 上**逐 op** 三态判定（与
          _eval 同路径 — 不另造口径）; m_o = 各 op 在**当前注入树**上的
          LOO marginal（R182）。缺席（无 pts/无 op 票）⇒ None。
        ★ 为什么是 dev 面而不是 rules.json learned（R176 的口径）:
          R176 的 learned 只有 1-2 条 ⇒ 共识面太薄; dev 判据点 23+ 条是真
          产出 ⇒ 论文"无标注 train 输出"的 DWC 在场形态。R176 口径保留
          在 _a_train（审计面）, 本面是喂给 S(e) 的那个。
        """
        if not pts:
            return None
        try:
            from dwc.organs.drawback import Node as _N
            from dwc.organs.drawback import _eval as _ev
            from dwc.organs.metric_loop import (
                _POOL_OPS,
                _current_tree,
                a_train_weighted,
                loo_marginal_dev,
            )
            names = sorted(_POOL_OPS)
            tv = [{n: _ev(_N(kind="leaf", op=n), _POOL_OPS, None, None,
                          (p.get("ctx") or {})) for n in names} for p in pts]
            inc = _current_tree()
            marg = {n: loo_marginal_dev(pts, n, inc) for n in names
                    if n != "root_parse_ok"}
            return a_train_weighted(tv, inc, marg)
        except Exception as exc:              # noqa: BLE001 — 留痕不静默
            self._last_a_train_why = ("a_train 加权失败: %s: %s"
                                      % (type(exc).__name__, exc))
            return None

    def _facts_from_dev_surface(self) -> list[Any]:
        """★★★ R183 · dev 真判据点 ⇒ 门组回归用的事实组（TermFacts 投影）。

        ★ 为什么这样做（深度思考记录 — 不造数据）: R172 EL 单任务每轮
          只产 1 个候选 ⇒ 1 条事实的回归快照**强度不足**（一条不变就说
          "没变严"是自证）。dev 面上全部历史判分点是**真判据投影**（evidence
          已落盘 — success/k/n/diffs 全真）⇒ 每点转成 TermFacts 给门③用
          是"把已判事实搬成门输入形态"（转换, 不是发明）。
        ★ 投影口径（与 e2e/_g3 判据源同源 — 不造第二口径）:
          pass_rate=v.k_passed/v.n_checks（微口径）; candidate_diff 不在
          evidence 判据面（R180 实测纪律: 判据与实现分离存储）⇒ None
          ⇒ 吃实现的 op 在回归里 abstain（如实 — 回归只覆盖判据面树）。
        ★ evidence 不可解析 ⇒ 跳过并留痕（不猜那点）。
        """
        from dwc.harness.gates import TermFacts
        out: list[Any] = []
        try:
            pts = self.judge.task_scores(split="dev")
        except Exception as exc:                  # noqa: BLE001 — 留痕不静默
            self._adopt_why = ("dev 面读取失败: %s: %s"
                               % (type(exc).__name__, exc))
            return out
        for p in pts:
            try:
                evi = self.judge.evidence(p.evidence_ref)
            except Exception as exc:              # noqa: BLE001 — 留痕不静默
                self._adopt_why = ("evidence %r 不可解析: %s"
                                   % (p.evidence_ref, exc))
                continue
            k = evi.get("k_passed")
            n = evi.get("n_checks")
            if not n or k is None:
                continue                          # None 不记（同 judge 纪律）
            # ★★★ R193 · 单一真源: 全部键从 R179 桥（_ctx_from_evidence）
            #   取 — 本函数只做"ctx ⇒ TermFacts"的一次搬运, 不重拼
            #   diff 文本（重拼 = 第二口径, R183 自己禁的）。
            from dwc.organs.metric_loop import _ctx_from_evidence
            ctx = _ctx_from_evidence(evi)
            out.append(TermFacts(pass_rate=ctx["pass_rate"],
                                 candidate_diff=ctx.get("candidate_diff"),
                                 not_evaluated=0,
                                 judge_success=ctx.get("judge_success"),
                                 parsed_ok=ctx.get("parsed_ok")))
        return out

    def _try_adopt_metric_tree(self) -> dict[str, Any]:
        """★★★ R183 · Metric Loop 自进化闭环: select ⇒ 门组回归 ⇒ adopt 注入。

        ★ 触发纪律（不震荡）: picked ≠ 现任 **且** S 差 > noise_band(0.01,
          与 e2e 同源口径）⇒ 才尝试 adopt; 否则留痕"不折腾"。
        ★ 回归事实组 = _facts_from_dev_surface（dev 真判据点 — 23 条级,
          不是单候选 1 条的弱回归）。
        ★ adopt 结果落 self._last_adopt（daemon/e2e 可读）; 任何异常 ⇒
          留痕 + 当前树保持（不半吊 — G7 纪律）。
        """
        from dwc.organs.metric_loop import (
            _current_tree,
            _tree_key,
            adopt,
            mechanical_candidates,
        )
        self._last_adopt = None
        mp = self._last_metric_pick
        if not mp or not mp.get("picked_key"):
            self._adopt_why = ((mp or {}).get("notes")
                               or "无选优痕迹 ⇒ 不动")
            return {"adopted": False, "why": self._adopt_why}
        cur_key = _tree_key(_current_tree())
        picked = mp["picked_key"]
        if picked == cur_key:
            self._adopt_why = "选优=现任 ⇒ 无需换（%s）" % cur_key
            return {"adopted": False, "why": self._adopt_why}
        s_new = mp.get("s")
        cand_s = [c.get("s") for c in mp.get("candidates", [])
                  if c.get("key") == cur_key and c.get("s") is not None]
        s_cur = cand_s[0] if cand_s else None
        if s_new is None or s_cur is None or (s_new - s_cur) <= 0.01:
            self._adopt_why = ("S 差未超噪声带（new=%s cur=%s band=0.01）"
                               "⇒ 不折腾" % (s_new, s_cur))
            return {"adopted": False, "why": self._adopt_why}
        new_tree = next((t for t in mechanical_candidates()
                         if _tree_key(t) == picked), None)
        if new_tree is None:
            self._adopt_why = "picked=%r 不在候选族（不注入）" % picked
            return {"adopted": False, "why": self._adopt_why}
        facts = self._facts_from_dev_surface()
        res = adopt(new_tree, lambda: facts)
        self._last_adopt = res
        self._adopt_why = res.get("why", "")
        return res

    # ── 跨轮分数序列（judge 落盘路径同源 — 不另立账本）──
    def _metric_loop_tick(self) -> dict[str, Any]:
        """★★★ R180 · Metric Loop 点火（接 R177 引擎 + R179 数据面 — 只读选+留痕）。

        ★ 边界（精准手术 — 本轮不换判据）: 本方法跑 select 拿选优结果,
          **不改 Grader 的树**（换树 = 改门③判定语义 = 影响链上所有候选
          ⇒ 须独立轮次验证门组回归; R181 才做"采纳"面）。
          本轮交付的是**可观测面**: 每轮 dev 真数据上谁该赢、赢多少 ——
          痕迹落 self._last_metric_pick（daemon 探针/e2e 可读）。
        ★ 缺席如实化: 无 dev 点/异常 ⇒ why 留痕, picked=None（不是 raise
          — 观察面不阻断主链; 引擎侧 fail-closed 已在 metric_loop 内）
        """
        try:
            from dwc.organs.metric_loop import dev_points_from_store, select
            # ★ Judge 自身委派 store 的 task_scores/evidence（judge.py
            #   L979/L981）⇒ duck-typing 直接传 self.judge（R180 实测纠偏:
            #   首版写 hasattr(judge,"store") 分支 — 多余, Judge 面就够）
            pts, notes = dev_points_from_store(self.judge, split="dev")
            # ★★ R184: A_train 优先取**真 train split**（无标签大集合
            #   — 论文口径）; 缺席（诚实边界④）回落 dev 面加权（R183 的
            #   口径, why 里如实标了回落原因 — 不放水冒充论文口径）
            _at = self._train_outputs_consensus()
            if _at is None:
                _at = self._a_train_weighted(pts)
            self._last_a_train = _at
            res = select(pts, a_train=_at)
            self._last_metric_pick = {"picked_key": res["picked_key"],
                                      "s": res["s"], "notes": res["notes"],
                                      "n_points": notes["n_points"],
                                      "n_skipped": notes["n_skipped"],
                                      "a_train": _at,
                                      # ★ R183: candidates 随痕迹带出
                                      #   （_try_adopt_metric_tree 要按
                                      #   key 查现任的 S 比噪声带 — 不带
                                      #   就恒 "cur=None" 假阴性）
                                      "candidates": res.get("candidates",
                                                           [])}
            self._metric_loop_why = ""
            # ★ R183: 选优后尝试采纳（触发纪律 — S 差 > 噪声带才动;
            #   异常自吞留痕 — 采纳面不许阻断观察面/主链）
            try:
                self._try_adopt_metric_tree()
            except Exception as exc:          # noqa: BLE001 — 留痕不静默
                self._adopt_why = ("adopt 尝试炸: %s: %s"
                                   % (type(exc).__name__, exc))
                self._last_adopt = None
            return self._last_metric_pick
        except Exception as exc:                  # noqa: BLE001 — 留痕不静默
            self._metric_loop_why = ("Metric Loop tick 缺席: %s: %s"
                                     % (type(exc).__name__, exc))
            self._last_metric_pick = None
            return {"picked_key": None, "why": self._metric_loop_why}

    def _a_train(self, component: str, target: str
                 ) -> tuple[float | None, dict[str, Any]]:
        """★★★ R176 · A_train（2607.12790 式2 的 op 池共识一致度 — DWC 版）。

        ★ 论文语义: A_train(e) = e 与"opining pool ops 在**无标注 train
          输出**上的共识判定"的一致度; train = 大、无标签（不是第二套 gold）
        ★ DWC 同构翻译（不发明）: train outputs = **已落地的历史修法**
          （rules.json learned + 本进程 ℒ_t 记账）— 它们是"没有 gold 判定
          标签的过程产物"（judge 没给它们任何 pass/fail 标签, 它们只是
          被 op 池/门收下过）⇒ op 池对这些 attempt 的判定 = 伪标签源
        ★ 一致度口径（可判定可复现 — 无 LLM）: 提案 (component, target)
          在历史 clean 修法中的出现率（clean = 门收下 = 真共识的反面证据
          不存在; 没被收的（门拦过的）不进 train 集 — 那是"有标签"的）
        ★ 无历史 train ⇒ None（A_train 缺席不是 0 — fail-closed: S(e) 里
          A_train 乘性进 A_dev ⇒ None 时保持 A_dev 单独裁决, 不伪造 1.0）
        """
        learned = self._learned_attempts()      # [(component,target,clean)]
        if not learned:
            return None, {"n_train": 0, "why": "无历史 attempt ⇒ 缺席"}
        hits = [t for t in learned if t[0] == component]
        if not hits:
            return 0.0, {"n_train": len(learned), "why":
                         "train 中无同 component 历史（冷启动 ⇒ 0, 非 None）"}
        clean_rate = sum(1 for t in hits if t[2]) / float(len(hits))
        return clean_rate, {"n_train": len(learned),
                            "n_same_component": len(hits),
                            "component": component}

    def _learned_attempts(self) -> list[tuple[str, str, bool]]:
        """★ train 集 = rules.json learned 条目（cross-process — R173 落盘面）。

        ★ clean 口径: 该键能被门收下过（进 rules.json = 过三闸 = clean）;
          ℒ_t 里 adopted=False 的记账（landed 后被拒/回滚）是**有标签**
          负面 ⇒ 不进 train（train 只装"无 gold 判定标签的" attempt）。
        """
        out: list[tuple[str, str, bool]] = []
        try:
            from dwc.organs.evolver import Mutator
            if os.path.exists(Mutator.LEARNED_PATH):
                d = json.load(open(Mutator.LEARNED_PATH, encoding="utf-8"))
                for _k, v in (d.get("learned") or {}).items():
                    out.append((str(v.get("component", "")),
                                str(v.get("target", "")), True))
        except (OSError, ValueError, KeyError) as exc:
            self._last_a_train_why = "train 读取失败: %s" % exc
            return []
        return out

    def _consolidate_rule(self, tid: str, sig: dict[str, str],
                          proposal: Any, trial: dict | None,
                          res: Any) -> dict[str, Any] | None:
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
            key = Mutator.key_for(sig)
            if key in Mutator.SEED_KEYS:
                self._last_consolidation = {"key": key, "outcome": "seed_noop"}
                return self._last_consolidation
            _rec = (self.judge.anchors.get(tid) or
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
            # ★ R202 注入: target 真源校验在生产固化路径**必过**（审计
            #   推荐② — dev task∪fn 集从已加载 judge 算, 无双源 IO）。
            rec_res = self.applier.land_rule(
                tgt, key, entry,
                {"success": bool((trial or {}).get("success")),
                 "split": "dev", "task": tid},
                lambda _k, _e: Mutator.check_entry(
                    _k, _e,
                    dev_targets=Mutator.dev_targets(self.judge.anchors)))
            self._last_consolidation = {
                "key": key, "outcome": "consolidated",
                "readback_ok": rec_res.readback_ok}
            try:  # ★ R276-② · 落地即落盘（rules.json 学到的跨进程存活）
                tgt.flush()
                self._last_consolidation["flushed"] = True
            except Exception as exc:                  # noqa: BLE001
                sys.stderr.write("consolidate 落盘跳过: %s\n" % exc)
                self._last_consolidation["flushed"] = False
            return self._last_consolidation
        except Exception as exc:                 # noqa: BLE001 — 留痕不静默
            self._last_consolidation = {"outcome": "error",
                                        "why": "%s: %s" % (type(exc).__name__,
                                                            exc)}
            return self._last_consolidation

    def _pick_task(self, tasks: list[str]) -> str:
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

    def _last_history_score(self) -> float | None:
        """★ R170: score_history 末条 score（score_star 的对照锚）。

        ★ 空文件/坏行 ⇒ None（不造 0.0 基准 — 首轮的 score_star 缺席是
          事实; σ/门⑤ 的 na 口径由 gates 自己判）。
        """
        path = os.path.join(self.anchors_dir, "score_history.jsonl")
        if not os.path.exists(path):
            return None
        try:
            last = None
            for line in open(path, encoding="utf-8"):
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

    def _append_history(self, round_no: int, tasks: list[str],
                        score: float | None, landed: int) -> None:
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

    def _dev_tasks(self) -> list[str]:
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
        self._box: dict[str, Any] = {"v": "loop_init"}
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


LOOP_MECHANICS: dict[str, str] = {
    "no_new_judgement": "单轮闭环全复用既有器官（execute_task/judge/evolver/gate_all/pipeline）— 零新判定",
    "llm_free_default": "use_llm=False 默认（LLM 提案路径由 e2e step9 覆盖; 循环的确定性面先稳）",
    "task_selection": "round_no % len(dev_tasks) 机械轮转 — 真选择器无设计不发明（R73 同族 backlog）",
    "score_history": "score_history.jsonl 沿用 judge 落盘路径同源（不另立账本 — σ_t 消费面）",
    "memory_target": "真落地面由部署方给; 循环用内存 target 证链路真跑（不写脏盘）",
    "idle_not_error": "task 已过/无提案命中/idle≠error — 与 daemon 熔断计数分族",
}
