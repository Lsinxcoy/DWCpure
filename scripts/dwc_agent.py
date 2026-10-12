# -*- coding: utf-8 -*-
"""R208 · DWC 独立 agent 常驻宿主（生产形态修正: 批处理 → 独立 agent）。

★★★ 定位（用户 2026-10-12 纠偏）: DWC 是独立 agent, 不是 cron 喂的批处理。
  本进程是 agent 的**宿主躯壳**: 常驻 + 自主循环 + 自己触发下一轮。
  ★ 任务源自主: 首轮 seed 轮询, 之后取**上轮 run_term 自己产的**
    next_task_source（world_tree_action.node = 真任务 id）——
    "Measurement thereby becomes the trigger of the next iteration"
    （bz 缺口原文）在进程级落地: 它的测量触发它的下一轮, 外部不喂。
  ★ cron 角色修正: watchdog 只守夜（死→拉活+告警）, 不喂食。

★ 节奏与护栏（agent 自治边界内）:
  · 休眠 interval（默认 600s）—— 存活期自主连续, 非批次
  · 日预算: terms/日 与 budget/日 超限 ⇒ 优雅停 + 告警（次日 watchdog 拉活）
  · 退化崩塌: 曾经 pass>0.1 后连续 2 轮 <0.1 ⇒ 停 + 告警
  · 冻结门（人工）: var/dwc_agent_frozen 存在 ⇒ 优雅停（G3 frozen 设置方）

★ 运行: python dwc_agent.py [--interval 600] [--steps 2] [--llm]
      [--terms-per-day 48] [--budget-day 40]
      python dwc_agent.py --freeze / --unfreeze / --status
"""
from __future__ import annotations

import json
import os
import signal
import sys
import time

#: ★ 固定仓库路径（drift watch 同款）—— CRON RUNS THE COPY: 副本在
#:   %LOCALAPPDATA%/hermes/scripts 下, 按 __file__ 定位会找错 var/src
ROOT = r"E:/Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.core import DWC                                    # noqa: E402
from dwc.organs.actor import Actor, execute_task, Receipt   # noqa: E402

VAR = os.path.join(ROOT, "var")
DB = os.path.join(VAR, "dwc_prod.sqlite")
LOG = os.path.join(VAR, "dwc_prod_log.jsonl")
PID = os.path.join(VAR, "dwc_agent.pid")
HB = os.path.join(VAR, "dwc_agent_heartbeat.json")
FROZEN = os.path.join(VAR, "dwc_agent_frozen")
DEV_POOL = ("code_fix_001", "code_fix_002", "code_fix_003", "code_fix_004",
            "code_fix_005", "code_fix_006",
            "reasoning_001", "reasoning_002",
            "reproduce_001", "reproduce_002", "reproduce_003")
_day = {"key": time.strftime("%Y-%m-%d"), "terms": 0, "cost": 0.0}
_stop = {"by": None}


def _log(entry: dict) -> None:
    entry["ts"] = time.strftime("%Y-%m-%dT%H:%M:%S+08:00")
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _heartbeat(**kw) -> None:
    with open(HB, "w", encoding="utf-8") as fh:
        json.dump({"ts": time.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
                   "pid": os.getpid(), **kw}, fh, ensure_ascii=False)


def select_task(prev_rep) -> str:
    """★ agent 自主任务源: 上轮 next_task_source 优先（它的测量触发它的
    下一轮）; 无/空 ⇒ DEV_POOL 轮询（seed 语义）。"""
    tasks = ((prev_rep.next_task_source or {}).get("tasks")
             if prev_rep is not None else None) or []
    nodes = [t["node"] for t in tasks
             if t.get("kind") == "world_tree_action" and t.get("node")]
    if nodes:
        return nodes[0]
    return DEV_POOL[(_day["terms"]) % len(DEV_POOL)]


def _freeze_check() -> bool:
    if os.path.exists(FROZEN):
        _log({"event": "agent_stopped", "by": "freeze_flag"})
        _stop["by"] = "freeze"
        return True
    return False


def _budget_check(terms_per_day: float, budget_day: float) -> bool:
    if _day["terms"] >= terms_per_day or _day["cost"] >= budget_day:
        _log({"event": "agent_stopped", "by": "daily_limit",
              "terms": _day["terms"], "cost": round(_day["cost"], 3)})
        _stop["by"] = "daily_limit"
        return True
    return False


def main(argv) -> int:
    # ── 控制子命令（人工门）──
    if "--freeze" in argv:
        open(FROZEN, "w", encoding="utf-8").write(time.strftime("%c"))
        print("frozen: agent 下轮优雅停")
        return 0
    if "--unfreeze" in argv:
        if os.path.exists(FROZEN):
            os.remove(FROZEN)
        print("unfrozen")
        return 0
    if "--status" in argv:
        for p in (PID, HB):
            print("%s: %s" % (os.path.basename(p),
                              open(p, encoding="utf-8").read().strip()
                              if os.path.exists(p) else "(无)"))
        print("frozen:", os.path.exists(FROZEN))
        return 0

    interval = float(argv[argv.index("--interval") + 1]) \
        if "--interval" in argv else 600.0
    steps = int(argv[argv.index("--steps") + 1]) if "--steps" in argv else 2
    tpd = float(argv[argv.index("--terms-per-day") + 1]) \
        if "--terms-per-day" in argv else 48.0
    bpd = float(argv[argv.index("--budget-day") + 1]) \
        if "--budget-day" in argv else 40.0
    use_llm = "--llm" in argv
    os.makedirs(VAR, exist_ok=True)
    with open(PID, "w", encoding="utf-8") as fh:
        fh.write(str(os.getpid()))

    d = DWC(depth_limit=3, max_nodes=50, budget=bpd, db_path=DB)
    if use_llm:
        from dwc.llm.client import LLMClient
        from dwc.llm.executor import LLMExecutorFactory
        d.executor = LLMExecutorFactory(LLMClient()).make(memory=d.memory)
    else:
        actor = Actor()

        def exe(task):
            r = execute_task(actor, d.judge, task["task_id"])
            return Receipt(ok=bool(r["observation"]),
                           detail={"observed": r["observation"]},
                           verified=True)
        d.executor = exe
    d.runner.executor = d.executor

    def _sig(signum, _frame):          # 优雅停: SIGINT/SIGTERM
        _log({"event": "agent_stopped", "by": "signal%d" % signum})
        _stop["by"] = "signal"
    signal.signal(signal.SIGINT, _sig)
    signal.signal(signal.SIGTERM, _sig)

    prev = None
    collapse = 0
    best_pass = 0.0
    _log({"event": "agent_started", "pid": os.getpid(),
          "interval": interval, "use_llm": use_llm})
    while _stop["by"] is None:
        if _freeze_check() or _budget_check(tpd, bpd):
            break
        # 日界滚动（次日自动复位计数）
        if _day["key"] != time.strftime("%Y-%m-%d"):
            _day.update(key=time.strftime("%Y-%m-%d"), terms=0, cost=0.0)
        task = select_task(prev)
        try:
            rep = d.run_term(task, n_steps=steps)
        except Exception as exc:  # noqa: BLE001 — agent 边界: 留痕继续活
            _log({"event": "term_error", "task": task,
                  "error": "%s: %s" % (type(exc).__name__, exc)})
            _heartbeat(status="term_error", task=task)
            time.sleep(interval)
            continue
        pr = rep.score_delta
        cost = float((rep.cost_after or {}).get("term_cost", 0.0) or 0.0)
        _day["terms"] += 1
        _day["cost"] += cost
        ir = rep.iron_report or {}
        _log({"agent_term": _day["terms"], "task": task,
              "pass_rate": pr, "cost": round(cost, 3),
              "advice_consumed": (rep.iwm_advice or {}).get("consumed_action"),
              "iron_block": ir.get("block"), "iron_warn": ir.get("warn"),
              "drift": (rep.drift or {}).get("gdi"),
              "next": [t.get("kind") for t in
                       (rep.next_task_source or {}).get("tasks", [])]})
        _heartbeat(status="alive", terms=_day["terms"],
                   last_task=task, pass_rate=pr)
        if pr is not None and pr > best_pass:
            best_pass = pr
        if pr is not None and pr < 0.1 and best_pass > 0.1:
            collapse += 1
            if collapse >= 2:
                _log({"event": "agent_stopped", "by": "collapse",
                      "best_pass": best_pass})
                _stop["by"] = "collapse"
                break
        else:
            collapse = 0
        prev = rep
        if _stop["by"] is None:
            time.sleep(interval)
    if os.path.exists(PID):
        os.remove(PID)
    return 0 if _stop["by"] in ("freeze", "daily_limit", "signal") else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
