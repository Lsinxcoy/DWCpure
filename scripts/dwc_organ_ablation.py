# -*- coding: utf-8 -*-
"""R268-B · 器官级消融电池（论文 §3.5 全消融 → DWC 开关版）。

★★★ 设计（唯一变量 = 两个开关，其余全同 bench2）:
  A0: judge 关 + lessons 关（= bench2 A 臂语义）
  J : 只开 judge（DWC_STEP_JUDGE 撤掉）
  L : 只开 lessons（ctx=lessons_context）
  F : 全开（= bench2 B 臂语义）
验收复用 dwc_bench2.verify（importlib 导入，不复制 — nightbench B2 模式）。
价值表：judge 净收益=J−A0；lessons 净收益=L−A0；交互=F−J−L+A0。

用法:
  python scripts/dwc_organ_ablation.py --arm A0 --limit 2
  python scripts/dwc_organ_ablation.py --report
"""
from __future__ import annotations

import argparse
import glob
import io
import json
import os
import sys
import time

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "src"))

import importlib.util  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "dwc_bench2", os.path.join(_ROOT, "scripts", "dwc_bench2.py"))
B2 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(B2)

EVAL_DIR = os.path.join(_ROOT, "var", "eval")
THROTTLE = 3  # ★ 与 bench2 同节流

# ★ 四臂正交：(judge 开?, lessons 开?)
ARMS = {
    "A0": {"judge": False, "lessons": False},
    "J": {"judge": True, "lessons": False},
    "L": {"judge": False, "lessons": True},
    "F": {"judge": True, "lessons": True},
}


def _value_table(sums: dict) -> dict:
    """纯函数：四臂 success → 器官价值表（测试直测此处）。"""
    g = lambda k: float(sums[k]["success"])  # noqa: E731
    return {"judge_gain": round(g("J") - g("A0"), 3),
            "lessons_gain": round(g("L") - g("A0"), 3),
            "interaction": round(g("F") - g("J") - g("L") + g("A0"), 3)}


def run_arm(arm: str, limit: int = 0, max_rounds: int = 30) -> dict:
    if arm not in ARMS:
        raise ValueError("未知臂 %r（可选 %s）" % (arm, sorted(ARMS)))
    from dwc.llm.client import LLMClient
    from dwc.llm.task_exec import execute_user_task
    cfg = ARMS[arm]
    if cfg["judge"]:
        os.environ.pop("DWC_STEP_JUDGE", None)
    else:
        os.environ["DWC_STEP_JUDGE"] = "0"

    llm = LLMClient()
    if not getattr(llm, "configured", False):
        print("✗ LLM 未配置")
        return {}
    tasks = [json.loads(l) for l in io.open(B2.TASKS, encoding="utf-8")
             if l.strip()]
    if limit:
        tasks = tasks[:limit]
    os.makedirs(EVAL_DIR, exist_ok=True)
    out_p = os.path.join(EVAL_DIR, "ablation_%s_%s.jsonl"
                         % (arm, time.strftime("%m%d_%H%M%S")))
    n_ok = 0
    rows = []
    for i, t in enumerate(tasks, 1):
        ctx = None
        if cfg["lessons"]:
            try:
                from dwc.agent_quality import lessons_context
                ctx = lessons_context(t["task"]) or None
            except Exception:                        # noqa: BLE001
                ctx = None
        time.sleep(THROTTLE)
        t0 = time.time()
        rep = execute_user_task(t["task"], llm=llm, ctx=ctx,
                                task_id="abl_%s_%s" % (arm, t["id"]),
                                max_rounds=max_rounds)
        # ★ 瞬断重试（照抄 bench2：首轮即挂大概率端点瞬断）
        if rep.get("status") == "incomplete" and (rep.get("rounds") or 0) <= 2:
            time.sleep(10)
            rep = execute_user_task(t["task"], llm=llm, ctx=ctx,
                                    task_id="abl_%s_%s" % (arm, t["id"]),
                                    max_rounds=max_rounds)
        dt = time.time() - t0
        ok, how = B2.verify(t["check"], str(rep.get("answer", "")))
        n_ok += 1 if ok else 0
        row = {"arm": arm, "id": t["id"], "kind": t["kind"], "ok": ok,
               "verify": how, "status": rep.get("status"),
               "rounds": rep.get("rounds"), "secs": round(dt, 1)}
        rows.append(row)
        with io.open(out_p, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        print("[%s %d/%d] %s %-12s %s (%.0fs)" % (
            arm, i, len(tasks), "✓" if ok else "✗", t["id"],
            t["kind"], dt), flush=True)
    summ = {"arm": arm, "n": len(tasks), "ok": n_ok,
            "success": round(n_ok / max(1, len(tasks)), 3),
            "judge": cfg["judge"], "lessons": cfg["lessons"],
            "by_kind": {}}
    try:  # ★ R269-④ · 记忆快照（哪次记忆赢的，可归因）
        from dwc.agent_quality import memory_snapshot_hash
        summ["memory_sha"] = memory_snapshot_hash()
    except Exception:                            # noqa: BLE001
        summ["memory_sha"] = "unknown"
    for k in sorted({r["kind"] for r in rows}):
        sub = [r for r in rows if r["kind"] == k]
        summ["by_kind"][k] = "%d/%d" % (sum(r["ok"] for r in sub), len(sub))
    with io.open(os.path.join(
            EVAL_DIR, "ablation_summary_%s_%s.json"
            % (arm, time.strftime("%m%d_%H%M%S"))),
            "w", encoding="utf-8") as fh:
        json.dump(summ, fh, ensure_ascii=False, indent=1)
    print("\n==== %s 臂: %d/%d = %.1f%% ====" % (arm, n_ok, len(tasks),
                                                100 * summ["success"]))
    return summ


def report() -> int:
    def _latest(arm):
        fs = sorted(glob.glob(os.path.join(
            EVAL_DIR, "ablation_summary_%s_*.json" % arm)))
        return json.load(io.open(fs[-1], encoding="utf-8")) if fs else None
    sums = {a: _latest(a) for a in ARMS}
    if not all(sums.values()):
        print("✗ 需要 A0/J/L/F 四臂各至少一跑（先 A0，最后 F）")
        return 1
    t = _value_table(sums)
    print("==== 器官价值表 ====")
    for a in ("A0", "J", "L", "F"):
        print("%s: %.1f%%" % (a, 100 * sums[a]["success"]))
    print("judge 净收益 %+.1fpp；lessons 净收益 %+.1fpp；交互 %+.1fpp" % (
        100 * t["judge_gain"], 100 * t["lessons_gain"],
        100 * t["interaction"]))
    with io.open(os.path.join(EVAL_DIR, "ablation_report.json"),
                 "w", encoding="utf-8") as fh:
        json.dump({"arms": sums, "value": t}, fh, ensure_ascii=False,
                  indent=1)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", choices=sorted(ARMS))
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--max-rounds", type=int, default=30)
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args()
    if args.report:
        return report()
    if not args.arm:
        ap.error("--arm A0|J|L|F 或 --report")
    run_arm(args.arm, args.limit, args.max_rounds)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
