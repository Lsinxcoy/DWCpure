# -*- coding: utf-8 -*-
"""R212 · 任务执行能力基准器（真任务质量度量 — 提升可证伪的前提）。

★★ 定位: 度量引擎, 不是护栏。judge/anchor 评"变什么"; 本器评"任务做得好不好"
  —— 每任务经真实执行链路（task_exec.execute_user_task, 同一代码路径）,
  结果由**可机判 verifier** 按动态计算的真值打分（不硬编码, 不人工判）。

★ 用法: python scripts/dwc_bench.py [--only T_id] [--timeout 150]
★ 输出: var/dwc_bench_results.json + stdout 汇总; 台账记 bench 事件
"""
from __future__ import annotations

import io
import json
import os
import re
import subprocess
import sys
import time

ROOT = r"E:/Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "src"))
VAR = os.path.join(ROOT, "var")
WORK = os.path.join(VAR, "inbox_work")

from dwc.llm import task_exec as TE                          # noqa: E402
from dwc.llm.client import LLMClient                         # noqa: E402
from dwc import agent_quality as Q                           # noqa: E402


# ── 真值动态计算（禁硬编码 — 仓库演进后基准不失效）──────────
def _src(*parts):
    return io.open(os.path.join(ROOT, *parts), encoding="utf-8").read()


def _truth_classes():
    import ast
    tree = ast.parse(_src("src", "dwc", "core.py"))
    return [n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]


def _truth_rung3():
    # ★ Layer 22: 判据校准 — 键名实为 verifier_rung（2026-10-12 查 dev.json
    #   顶层=任务id→dict{category,verifier_rung,prompt,...}; 首版查 "rung" 误得 0）
    data = json.loads(_src("config", "anchors", "dev.json"))
    return sum(1 for t in data.values()
               if isinstance(t, dict) and t.get("verifier_rung") == 3)


def _truth_def_count():
    n = 0
    for dp, _, fs in os.walk(os.path.join(ROOT, "src", "dwc")):
        for f in fs:
            if f.endswith(".py"):
                n += io.open(os.path.join(dp, f), encoding="utf-8"
                             ).read().count("def ")
    return n


def _truth_readme_test():
    m = re.search(r"pytest\s+(\d+)\s+项", _src("README.md"))
    return int(m.group(1)) if m else None


def _read(name):
    p = os.path.join(WORK, name)
    return io.open(p, encoding="utf-8").read().strip() if os.path.exists(p) \
        else None


def _run_py(name):
    p = os.path.join(WORK, name)
    if not os.path.exists(p):
        return None, None
    r = subprocess.run([sys.executable, p], capture_output=True, text=True,
                       timeout=30, cwd=ROOT)
    return r.returncode, r.stdout.strip()


# ── verifier 表（每任务一个, 机判产物 vs 动态真值）────────────
def v_classes(rep):
    got = _read("core_classes.md") or ""
    hit = [c for c in _truth_classes() if re.search(r"\b%s\b" % c, got)]
    ok = len(hit) >= max(3, len(_truth_classes()) // 2)
    return ok, "命中类名 %d/%d" % (len(hit), len(_truth_classes()))


def v_rung3_count(rep):
    txt = _read("rung_dist.txt") or ""
    m = re.search(r"\d+", txt)
    got = int(m.group()) if m else None
    return got == _truth_rung3(), "got=%s truth=%s" % (got, _truth_rung3())


def v_run_mult3(rep):
    rc, out = _run_py("mult3.py")
    truth = len([i for i in range(1, 101) if i % 3 == 0])
    m = re.search(r"\d+", out or "")
    got = int(m.group()) if m else None
    return (rc == 0 and got == truth), "rc=%s got=%s truth=%s" % (rc, got, truth)


def v_run_dedup(rep):
    rc, out = _run_py("dedup_sort.py")
    truth = ",".join(sorted(set(["pear", "apple", "fig", "banana"])))
    got = (out or "").strip()
    return (rc == 0 and got == truth), "got=%r truth=%r" % (got, truth)


def v_def_count(rep):
    txt = _read("def_count.txt") or ""
    m = re.search(r"\d+", txt)
    got = int(m.group()) if m else None
    return got == _truth_def_count(), "got=%s truth=%s" % (got, _truth_def_count())


def v_readme_test(rep):
    txt = _read("readme_test.txt") or ""
    m = re.search(r"\d+", txt)
    got = int(m.group()) if m else None
    return got == _truth_readme_test(), "got=%s truth=%s" % (got, _truth_readme_test())


def v_incr_digits(rep):
    src = _read("numsrc.txt") or ""
    nums = [int(x) for x in src.split()] if src else []
    truth = " ".join(str(x + 1) for x in nums)
    got = _read("numdst.txt") or ""
    return (truth != "" and got == truth), "got=%r truth=%r" % (got[:40], truth[:40])


def v_sections3(rep):
    txt = _read("report3.md") or ""
    need = ["## 目标", "## 方法", "## 结论"]
    hit = [s for s in need if s in txt]
    return len(hit) == 3, "段落命中 %d/3" % len(hit)


def v_gitsha(rep):
    truth = subprocess.run(["git", "-C", ROOT, "rev-parse", "HEAD"],
                           capture_output=True, text=True, timeout=30).stdout.strip()
    got = _read("gitsha.txt") or ""
    return got == truth, "got=%s… truth=%s…" % (got[:12], truth[:12])


def v_dual_symbol(rep):
    hits = []
    for dp, _, fs in os.walk(os.path.join(ROOT, "src", "dwc")):
        for f in fs:
            if f.endswith(".py"):
                t = io.open(os.path.join(dp, f), encoding="utf-8").read()
                if re.search(r"\bjudge\b", t) and re.search(r"\banchor\b", t):
                    hits.append(f)
    got = _read("dualsym.txt") or ""
    return (len(hits) >= 1 and got in hits), "got=%r 真值集合=%s" % (got, hits[:3])


VERIFIERS = {
    "classes": v_classes, "rung3_count": v_rung3_count,
    "run_mult3": v_run_mult3, "run_dedup": v_run_dedup,
    "def_count": v_def_count, "readme_test": v_readme_test,
    "incr_digits": v_incr_digits, "sections3": v_sections3,
    "gitsha": v_gitsha, "dual_symbol": v_dual_symbol,
}


def _pre_setup():
    """增量变换任务的输入文件预生成。"""
    os.makedirs(WORK, exist_ok=True)
    io.open(os.path.join(WORK, "numsrc.txt"), "w", encoding="utf-8"
            ).write("3 17 42 8 100")


def run_one(task, timeout):
    tid = task["id"]
    t0 = time.time()
    # 真实签名（task_exec.py:94）: task 位置参数, llm/max_rounds/ctx 关键字
    # ★ LLM 瞬时拒绝重试 ×2（端点偶发 500/连接拒 — 实测同链路直调即通,
    #   不重试会把端点毛刺误记为执行能力缺失）
    # ★ R213 回路注入: 同类历史教训拼进 ctx（教训从上一轮失败积累 —
    #   学习曲线可测: round1 空注入=对照, round2+ 带注入）
    ctx = task.get("ctx") or ""
    injected = Q.lessons_context(task["task"])
    if injected:
        ctx = (ctx + "\n" + injected) if ctx else injected
    report = None
    for attempt in range(3):
        report = TE.execute_user_task(task["task"], ctx=ctx or None,
                                      llm=LLMClient(), max_rounds=6)
        why = str(report.get("why", ""))
        if not (report["status"] == "incomplete" and "LLM 失败" in why):
            break
        time.sleep(1.0)
    fn = VERIFIERS[task["verifier"]]
    try:
        ok, detail = fn(report)
    except Exception as exc:                    # noqa: BLE001 — verifier 自身错
        ok, detail = False, "verifier ERROR: %s: %s" % (type(exc).__name__, exc)
    # ★ R213 沉淀: 失败分类落 lessons（下轮/下次接单可检索）
    fm = Q.classify_fail(report, bool(ok))
    if fm != "ok":
        Q.record_lesson(tid, fm, task["task"], "verdict=%s status=%s"
                        % (detail, report["status"]))
    return {"id": tid, "exec_status": report["status"], "pass": bool(ok),
            "fail_mode": fm, "lessons_total": len(Q.load_lessons()),
            "verdict": detail, "rounds": report.get("rounds"),
            "secs": round(time.time() - t0, 1),
            "actions": [a["op"] for a in report.get("actions_log", [])],
            "why": str(report.get("why", ""))[:200]}


def main(argv) -> int:
    only = argv[argv.index("--only") + 1] if "--only" in argv else None
    timeout = int(argv[argv.index("--timeout") + 1]) if "--timeout" in argv \
        else 150
    bench = json.loads(_src("config", "task_bench.json"))
    _pre_setup()
    results = []
    for task in bench["tasks"]:
        if only and task["id"] != only:
            continue
        r = run_one(task, timeout)
        results.append(r)
        mark = "✓" if r["pass"] else "✗"
        print("%s %-18s %-10s %4.0fs  %s" % (mark, r["id"], r["exec_status"],
                                             r["secs"], r["verdict"][:60]))
    npass = sum(1 for r in results if r["pass"])
    out = {"at": time.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
           "n": len(results), "pass": npass,
           "pass_rate": round(npass / len(results), 3) if results else 0.0,
           "results": results}
    os.makedirs(VAR, exist_ok=True)
    io.open(os.path.join(VAR, "dwc_bench_results.json"), "w",
            encoding="utf-8").write(json.dumps(out, ensure_ascii=False,
                                               indent=1))
    try:                                        # 台账留痕（非 agent 事件）
        with io.open(os.path.join(VAR, "dwc_prod_log.jsonl"), "a",
                     encoding="utf-8") as fh:
            fh.write(json.dumps({"event": "bench", "ts": out["at"],
                                 "n": out["n"], "pass": out["pass"],
                                 "pass_rate": out["pass_rate"]},
                                ensure_ascii=False) + "\n")
    except Exception:                           # noqa: BLE001
        pass
    # ★ R214 自动固化: 教训 ≥ 阈值 ⇒ 技能文件（下轮注入生效）
    made = Q.consolidate_skills()
    if made:
        print("技能固化:", made)
    from collections import Counter
    fmdist = dict(Counter(r["fail_mode"] for r in results))
    out["fail_mode_dist"] = fmdist
    io.open(os.path.join(VAR, "dwc_bench_results.json"), "w",
            encoding="utf-8").write(json.dumps(out, ensure_ascii=False,
                                               indent=1))
    print("BENCH pass_rate: %d/%d = %.3f  fail_modes=%s"
          "  → var/dwc_bench_results.json"
          % (npass, len(results), out["pass_rate"], fmdist))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
