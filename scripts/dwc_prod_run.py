# -*- coding: utf-8 -*-
"""R205 · DWC 生产运行器 —— P0-1 常驻运行器 + P0-2 持久化落盘。

★★★ 为什么存在（P0 审计 2026-10-12）:
  此前 run_term 只有一次性脚本（trial_run/e2e）调用, 无任何东西持续喂系统;
  且全部构造 db_path=":memory:" ⇒ 生产数据零持久。本脚本是**受护栏的
  多 term 生产轮**: 持久 db + budget 护栏 + 崩溃留痕 + 逐轮 JSONL 台账。

★ 运行形态（hermes-cron-feishu 惯例 · no_agent）:
  正常 = rc 0 + 空 stdout（health=silence）; 异常 = rc 1 + stderr（cron 告警）。
  逐轮明细落 var/dwc_prod_log.jsonl（不是 stdout —— stdout 是告警通道）。

★ 执行器二选一（能力通道诚实）:
  --llm     ⇒ LLMExecutorFactory(LLMClient()) 真 LLM 执行通道（R126）
  默认      ⇒ execute_task 真断言执行（golden checks — 链路活+断言真跑）
  ★ 两者都**不是** R25 自造观测（那条只在 executor=None 时出现, 本运行器不用）

★ 护栏（先停后报, 不静默吞）:
  · budget: 逐 term term_cost 累计 ≥ budget ⇒ 正常停（台账标 stopped_budget）
  · 崩塌: 曾经 pass_rate>0.1 后连续 2 轮 < 0.1 ⇒ 停 + rc 1（退化型崩塌
    → cron 告警）。★ 冷启动全败不算崩塌 —— 那是**当前真实能力状态**
    （台账如实记 pass=0.0, 可审计）, 不是退化（R205 首跑护栏误伤校准）
  · 异常: 任何未捕获异常 ⇒ 写台账 + rc 1
"""
from __future__ import annotations

import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.core import DWC                                    # noqa: E402
from dwc.organs.actor import Actor, execute_task, Receipt   # noqa: E402

#: 生产落盘位（P0-2: 摆脱 :memory:; var/ 已 gitignore — 库不是代码）
VAR = os.path.join(ROOT, "var")
DB = os.path.join(VAR, "dwc_prod.sqlite")
LOG = os.path.join(VAR, "dwc_prod_log.jsonl")
#: dev 任务轮询序（真值源 config/anchors/dev.json 的任务 id; 加载时以文件为准）
DEV_POOL = ("code_fix_001", "code_fix_002", "code_fix_003", "code_fix_004",
            "code_fix_005", "code_fix_006", "code_fix_007",
            "reasoning_001", "reasoning_002", "reasoning_003",
            "reproduce_001", "reproduce_002", "reproduce_003")
#: 崩塌护栏: 连续 N 轮 pass_rate 低于该值 ⇒ 停 + 非零退出
COLLAPSE_RATE = 0.1
COLLAPSE_STREAK = 2


def _log(entry: dict) -> None:
    entry["ts"] = time.strftime("%Y-%m-%dT%H:%M:%S+08:00")
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _make_executor(d: DWC, use_llm: bool):
    """执行器: --llm 走 R126 真 LLM 通道; 默认 execute_task 真断言执行。"""
    if use_llm:
        from dwc.llm.client import LLMClient
        from dwc.llm.executor import LLMExecutorFactory
        return LLMExecutorFactory(LLMClient()).make(memory=d.memory)
    actor = Actor()

    def exe(task):
        r = execute_task(actor, d.judge, task["task_id"])
        return Receipt(ok=bool(r["observation"]),
                       detail={"observed": r["observation"]},
                       verified=True)
    return exe


def main(argv) -> int:
    n_terms = int(argv[argv.index("--terms") + 1]) if "--terms" in argv else 3
    n_steps = int(argv[argv.index("--steps") + 1]) if "--steps" in argv else 2
    budget = float(argv[argv.index("--budget") + 1]) if "--budget" in argv else 10.0
    use_llm = "--llm" in argv
    os.makedirs(VAR, exist_ok=True)

    d = DWC(depth_limit=3, max_nodes=50, budget=budget, db_path=DB)
    d.executor = _make_executor(d, use_llm)
    d.runner.executor = d.executor

    cost_total = 0.0
    streak = 0
    best_pass = 0.0          # ★ 退化判据的基线: 曾经的最好 pass_rate
    for t in range(n_terms):
        task = DEV_POOL[t % len(DEV_POOL)]
        try:
            rep = d.run_term(task, n_steps=n_steps)
        except Exception as exc:  # noqa: BLE001 — 运行器边界: 留痕 + 非零退出
            _log({"term": t, "task": task, "error": "%s: %s"
                  % (type(exc).__name__, exc)})
            print("term %d crashed: %s" % (t, exc), file=sys.stderr)
            return 1
        cost = float((rep.cost_after or {}).get("term_cost", 0.0) or 0.0)
        cost_total += cost
        pr = rep.score_delta
        adv = rep.iwm_advice or {}
        ir = rep.iron_report or {}
        _log({"term": t, "task": task, "n_steps": rep.n_steps,
              "cost": cost, "cost_total": round(cost_total, 3),
              "pass_rate": pr,
              "n_pass": (rep.judgement or {}).get("pass"),
              "n_fail": (rep.judgement or {}).get("fail"),
              "next_tasks": [x.get("kind") for x in
                             (rep.next_task_source or {}).get("tasks", [])],
              "advice_degrade": bool(adv.get("degrade_to_baseline")),
              "advice_consumed": adv.get("consumed_action"),
              "iron_block": ir.get("block"), "iron_warn": ir.get("warn"),
              "drift": (rep.drift or {}).get("gdi")})
        # ── 护栏 ──
        if cost_total >= budget:
            _log({"event": "stopped_budget", "cost_total": cost_total,
                  "budget": budget})
            return 0                       # 预算内正常停（不是错误）
        if pr is not None and pr > best_pass:
            best_pass = pr
        if (pr is not None and pr < COLLAPSE_RATE and best_pass > COLLAPSE_RATE):
            streak += 1          # ★ 只有"曾经好过"的下跌才算退化崩塌
            if streak >= COLLAPSE_STREAK:
                _log({"event": "stopped_collapse", "pass_rate": pr,
                      "streak": streak})
                print("pass_rate collapsed: %.3f for %d terms"
                      % (pr, streak), file=sys.stderr)
                return 1                   # 健康异常 → cron 告警
        else:
            streak = 0
    _log({"event": "completed", "terms": n_terms,
          "cost_total": round(cost_total, 3), "best_pass": best_pass,
          "use_llm": use_llm})
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
