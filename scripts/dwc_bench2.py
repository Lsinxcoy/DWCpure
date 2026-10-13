# -*- coding: utf-8 -*-
"""dwc_bench2 · 真实任务跑批 + 进化 A/B（R259 · 短板 1 效果证明层）。

★★★ G2 纪律（验收在 agent 外）:
  · run-verify 类: **验收器独立重跑 cmd**（不采信 agent 的 answer/rc）
  · write 类: **验收器独立读文件**（不采信 agent 自述）
  · fact/locate/analyze 类: 机器判 answer 文本（contains/regex — 不是 LLM 判 LLM）
  · 全程零 LLM 自评成功。

=== A/B 设计（唯一变量 = 进化面）===
  A 臂: DWC_STEP_JUDGE=0 + ctx=None（无 lessons 注入, 无修订 — bench 直调
        execute_user_task 天然绕过 agent 的 lessons/revision 面）
  B 臂: judge 默认开 + ctx=lessons_context(task)（模拟 agent 生产路径）
  两臂同 max_rounds（防轮数混淆变量）。A 先跑（无修订不污染 B）；
  B 臂在线进化是其真实语义（"进化开着的系统"）。

用法:
  python scripts/dwc_bench2.py --arm A --limit 5     # smoke
  python scripts/dwc_bench2.py --arm A                # 全量 A 臂
  python scripts/dwc_bench2.py --arm B                # 全量 B 臂（A 之后）
  python scripts/dwc_bench2.py --report               # 读最近两跑出对比报告
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import subprocess
import sys
import time

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "src"))

TASKS = os.path.join(_ROOT, "config", "eval_tasks.jsonl")
EVAL_DIR = os.path.join(_ROOT, "var", "eval")
PY = sys.executable
THROTTLE = 3   # ★ 单间节流秒数（端点限流实测）


# ══════════ 验收器（agent 外独立判）══════════

def _file_of(path_rel: str) -> str:
    return os.path.join(_ROOT, path_rel)


def verify(check: dict, answer: str) -> tuple:
    """返回 (ok: bool, how: str)。how 记录判定依据（审计）。"""
    t = check.get("type")
    ans = answer or ""
    if t == "contains":
        return (check["target"] in ans, "answer contains %r" % check["target"][:40])
    if t == "regex":
        return (bool(re.search(check["pattern"], ans)),
                "answer regex %r" % check["pattern"][:40])
    if t == "contains_any":
        hits = [x for x in check["target"] if x in ans]
        return (bool(hits), "answer any-of %r" % hits[:3])
    if t == "contains_all":
        miss = [x for x in check["target"] if x not in ans]
        return (not miss, "answer all-of; miss=%r" % miss)
    if t == "rc_and_contains":
        # ★ 独立重跑（不信 agent 自述的 rc/输出）
        cmd = check["cmd"]
        try:
            r = subprocess.run(
                (cmd.replace("python ", PY + " ", 1)
                 if cmd.startswith("python ") else cmd),
                shell=True, capture_output=True, text=True, timeout=300,
                cwd=_ROOT, encoding="utf-8", errors="replace")
        except Exception as exc:                    # noqa: BLE001
            return (False, "verify-rerun failed: %s" % exc)
        ok = r.returncode == 0 and (not check["target"]
                                    or check["target"] in (r.stdout + r.stderr))
        return (ok, "rerun rc=%d anchor=%r" % (r.returncode,
                                               check["target"][:30]))
    if t in ("file_contains", "file_contains_all", "file_lines"):
        p = _file_of(check["path"])
        if not os.path.exists(p):
            return (False, "file missing: %s" % check["path"])
        body = io.open(p, encoding="utf-8", errors="replace").read()
        if t == "file_contains":
            return (check["target"] in body, "file contains %r"
                    % check["target"][:30])
        if t == "file_contains_all":
            miss = [x for x in check["target"] if x not in body]
            return (not miss, "file all-of; miss=%r" % miss)
        if t == "file_lines":
            n = len([l for l in body.splitlines() if l.strip()])
            return (n == check["lines"] and check["target"] in body,
                    "file lines=%d want=%d" % (n, check["lines"]))
    return (False, "unknown check type %r" % t)


# ══════════ 跑批 ══════════

def run_arm(arm: str, limit: int = 0, max_rounds: int = 30) -> dict:
    from dwc.llm.client import LLMClient
    from dwc.llm.task_exec import execute_user_task
    if arm == "A":
        os.environ["DWC_STEP_JUDGE"] = "0"
    else:
        os.environ.pop("DWC_STEP_JUDGE", None)

    llm = LLMClient()
    if not getattr(llm, "configured", False):
        print("✗ LLM 未配置")
        return {}
    tasks = [json.loads(l) for l in io.open(TASKS, encoding="utf-8")
             if l.strip()]
    if limit:
        tasks = tasks[:limit]
    os.makedirs(EVAL_DIR, exist_ok=True)
    out_p = os.path.join(EVAL_DIR, "run_%s_%s.jsonl"
                         % (arm, time.strftime("%m%d_%H%M%S")))
    n_ok = 0
    rows = []
    for i, t in enumerate(tasks, 1):
        ctx = None
        if arm == "B":
            try:
                from dwc.agent_quality import lessons_context
                ctx = lessons_context(t["task"]) or None
            except Exception:                        # noqa: BLE001
                ctx = None
        time.sleep(THROTTLE)        # ★ 节流（连续快调触发端点限流 — 实测）
        t0 = time.time()
        rep = execute_user_task(t["task"], llm=llm, ctx=ctx,
                                task_id="eval_%s_%s" % (arm, t["id"]),
                                max_rounds=max_rounds)
        # ★ 瞬断重试: 首轮即挂（≤2 轮 incomplete）大概率端点瞬断, 退避重跑一次
        if rep.get("status") == "incomplete" and (rep.get("rounds") or 0) <= 2:
            time.sleep(10)
            rep = execute_user_task(t["task"], llm=llm, ctx=ctx,
                                    task_id="eval_%s_%s" % (arm, t["id"]),
                                    max_rounds=max_rounds)
        dt = time.time() - t0
        ok, how = verify(t["check"], str(rep.get("answer", "")))
        n_ok += 1 if ok else 0
        row = {"arm": arm, "id": t["id"], "kind": t["kind"], "ok": ok,
               "verify": how, "status": rep.get("status"),
               "rounds": rep.get("rounds"), "secs": round(dt, 1),
               "revised": bool(rep.get("revised"))}
        rows.append(row)
        with io.open(out_p, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        print("[%s %d/%d] %s %-12s %s (%.0fs, r=%s)" % (
            arm, i, len(tasks), "✓" if ok else "✗", t["id"],
            t["kind"], dt, rep.get("rounds")))
    summ = {"arm": arm, "n": len(tasks), "ok": n_ok,
            "success": round(n_ok / max(1, len(tasks)), 3),
            "by_kind": {}}
    for k in sorted({r["kind"] for r in rows}):
        sub = [r for r in rows if r["kind"] == k]
        summ["by_kind"][k] = "%d/%d" % (sum(r["ok"] for r in sub), len(sub))
    with io.open(os.path.join(
            EVAL_DIR, "summary_%s_%s.json" % (arm, time.strftime("%m%d_%H%M%S"))),
            "w", encoding="utf-8") as fh:
        json.dump(summ, fh, ensure_ascii=False, indent=1)
    print("\n==== %s 臂: %d/%d = %.1f%% ====" % (arm, n_ok, len(tasks),
                                                100 * n_ok / max(1, len(tasks))))
    print(json.dumps(summ["by_kind"], ensure_ascii=False))
    return summ


def report() -> int:
    """最近 A/B 两跑对比（进化净收益）。"""
    import glob
    def _latest(arm):
        fs = sorted(glob.glob(os.path.join(EVAL_DIR, "summary_%s_*.json" % arm)))
        return json.load(io.open(fs[-1], encoding="utf-8")) if fs else None
    a, b = _latest("A"), _latest("B")
    if not a or not b:
        print("✗ 需要 A/B 两臂各至少一跑（先跑 A 再跑 B）")
        return 1
    delta = round(b["success"] - a["success"], 3)
    print("==== 进化净收益（B 开进化 − A 关进化）====")
    print("A(关进化): %d/%d = %.1f%%" % (a["ok"], a["n"], 100 * a["success"]))
    print("B(开进化): %d/%d = %.1f%%" % (b["ok"], b["n"], 100 * b["success"]))
    print("净收益 Δ = %+.1f 个百分点" % (100 * delta))
    print("分类型 A:", json.dumps(a["by_kind"], ensure_ascii=False))
    print("分类型 B:", json.dumps(b["by_kind"], ensure_ascii=False))
    with io.open(os.path.join(EVAL_DIR, "ab_report.json"), "w",
                 encoding="utf-8") as fh:
        json.dump({"A": a, "B": b, "delta_pp": round(100 * delta, 1)},
                  fh, ensure_ascii=False, indent=1)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", choices=("A", "B"))
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--max-rounds", type=int, default=30)
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args()
    if args.report:
        return report()
    if not args.arm:
        ap.error("--arm A|B 或 --report")
    run_arm(args.arm, args.limit, args.max_rounds)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
