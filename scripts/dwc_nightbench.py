# -*- coding: utf-8 -*-
"""dwc_nightbench · 无人值守跑批（R260 · 短板 2 — 真实流量压测进化回路）。

★★★ 设计（深度思考定稿）:
  · 投 **inbox**（agent 真实消费路径 — lessons 注入/step_judge/修订全链在线），
    不直调 execute_user_task（那是 bench 的事）。这就是"无人值守水平"的语义。
  · 每日 N 单从 52 单池**轮换抽样**（rotation 记录防连续同单过拟合记忆）。
  · 验收复用 dwc_bench2.verify（机器判, agent 外 — G2）。
  · 成功判定读 agent 落盘报告 var/reports/{id}.json 的 answer → verify。
  · 曲线: var/eval/success_curve.jsonl（时间序列 — 短板 2 的收敛证据）。
  · 任务完成等待: 轮询 reports/INBOX_DONE 至超时（默认 40min/单）。

用法: python scripts/dwc_nightbench.py [--n 8] [--wait-min 40]
  cron: 每日 02:30（错开备份 03:00 / watchdog）。
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys
import time

def _find_root() -> str:
    """★ cron 拷贝跑时 __file__ 在 hermes/scripts — 向上找 .dwc_repo 标记。"""
    d = os.path.dirname(os.path.abspath(__file__))
    for _ in range(6):
        if os.path.exists(os.path.join(d, ".dwc_repo")):
            return d
        d = os.path.dirname(d)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_ROOT = _find_root()
sys.path.insert(0, os.path.join(_ROOT, "scripts"))
sys.path.insert(0, os.path.join(_ROOT, "src"))

TASKS = os.path.join(_ROOT, "config", "eval_tasks.jsonl")
# ★ 路径单源纪律（agent_rpc 为权威 — 自拼路径三处全错被抓: json/jsonl、
#   var/reports vs var/dwc_reports）:
from dwc.agent_rpc import INBOX, REPORTS   # noqa: E402
STATE = os.path.join(_ROOT, "var", "eval", "nightbench_state.json")
CURVE = os.path.join(_ROOT, "var", "eval", "success_curve.jsonl")

import importlib.util  # noqa: E402
_spec = importlib.util.spec_from_file_location(
    "dwc_bench2", os.path.join(_ROOT, "scripts", "dwc_bench2.py"))
B2 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(B2)


def _inbox_push(task: str, tid: str) -> None:
    """★ JSONL 逐行追加（agent take_inbox 读法 — 数组文件会被逐行跳过）。"""
    os.makedirs(os.path.dirname(INBOX), exist_ok=True)
    with io.open(INBOX, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"id": tid, "task": task,
                             "ts": time.strftime("%Y-%m-%dT%H:%M:%S")},
                            ensure_ascii=False) + "\n")


def _wait_report(tid: str, timeout_min: int) -> dict:
    p = os.path.join(REPORTS, "%s.json" % tid)
    deadline = time.time() + timeout_min * 60
    while time.time() < deadline:
        if os.path.exists(p):
            try:
                return json.load(io.open(p, encoding="utf-8"))
            except (ValueError, OSError):
                pass
        time.sleep(30)
    return {}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=8)
    ap.add_argument("--wait-min", type=int, default=40)
    args = ap.parse_args()
    tasks = [json.loads(l) for l in io.open(TASKS, encoding="utf-8")]
    st = {"rot": 0}
    if os.path.exists(STATE):
        try:
            st = json.load(io.open(STATE, encoding="utf-8"))
        except (ValueError, OSError):
            pass
    rot = int(st.get("rot", 0))
    picks = [tasks[(rot + i) % len(tasks)] for i in range(args.n)]
    st["rot"] = (rot + args.n) % len(tasks)
    with io.open(STATE, "w", encoding="utf-8") as fh:
        json.dump(st, fh)

    day = time.strftime("%m%d")
    n_ok = 0
    done = 0
    for i, t in enumerate(picks, 1):
        tid = "nb_%s_%02d" % (day, i)
        _inbox_push(t["task"], tid)
        print("[投单 %d/%d] %s (%s)" % (i, len(picks), tid, t["kind"]),
              flush=True)
        rep = _wait_report(tid, args.wait_min)
        ok = False
        how = "timeout/no-report"
        if rep:
            ok, how = B2.verify(t["check"], str(rep.get("answer", "")))
            done += 1
        n_ok += 1 if ok else 0
        row = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "tid": tid,
               "task_id": t["id"], "kind": t["kind"], "ok": ok, "verify": how,
               "status": rep.get("status"), "rounds": rep.get("rounds")}
        with io.open(CURVE, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        print("  → %s (%s)" % ("✓" if ok else "✗", how[:60]), flush=True)
        time.sleep(10)      # 单间隔（端点限流教训）
    print("\n本轮: %d/%d（%d 单等到报告）" % (n_ok, len(picks), done))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
