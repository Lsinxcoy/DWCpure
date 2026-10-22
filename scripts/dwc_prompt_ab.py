# -*- coding: utf-8 -*-
"""R434 · 提示词 A/B 归因 + 灰度晋升。

    # 1) 先造候选（单变量：基线 + 一条硬规则）
    python scripts/dwc_prompt_candidate.py --name task_exec \
        --rule "问标识符类问题（类名/变量名/文件名）时，必须先 search_code 取证再 final。"

    # 2) 同题两臂跑一遍（默认 12 单 smoke 子集）
    python scripts/dwc_prompt_ab.py --name task_exec --candidate v2

    # 3) 判定 promote 时写 manifest（stable ← candidate）
    python scripts/dwc_prompt_ab.py --name task_exec --candidate v2 --promote

★★★ 为什么必须"同题两臂"而不是"跑两轮全池"：
    全池跑一次 100 分钟，两轮之间端点/温度/缓存都在漂 —— 差异分不清是
    提示词造成的还是时间造成的。同一道题**紧挨着**跑两臂，漂移对两臂
    近似相同，差值才归因得到提示词。

★★★ 判定为什么保守（任何一单退化就 reject）：
    单轮单题是 n=1，通过率本身有 ~7pp 的抖动。宁可漏掉一个真提升，
    也不能把一个退化版本推上生产 —— 提示词是全流量生效的。

★★★ 钉版本走 `var/prompt_force.json`（prompt_ota 读，按 mtime_ns 失效），
    跑完 `finally` 删除；文件不存在 = 生产按 manifest 灰度走。
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import dwc_bench2 as B2          # noqa: E402
import dwc_nightbench as NB      # noqa: E402

PROMPTS = os.path.join(ROOT, "prompts")
MANIFEST = os.path.join(PROMPTS, "manifest.json")
TASKS = os.path.join(ROOT, "config", "eval_tasks.jsonl")
FORCE = os.path.join(ROOT, "var", "prompt_force.json")
OUT_DIR = os.path.join(ROOT, "var")

#: 默认 smoke 子集：覆盖六类 + 历史上最不稳定的几单
SMOKE = ["rf05", "rf08", "rf09", "rf12", "cl01", "cl08", "rv06", "rv08",
         "hs01", "an03", "an09", "wr01"]


def load_tasks():
    out = []
    for line in io.open(TASKS, encoding="utf-8"):
        if line.strip():
            out.append(json.loads(line))
    return {t["id"]: t for t in out}


def set_force(name: str, ver):
    """写/删钉版本文件（原子）。ver=None ⇒ 删除（回到生产灰度）。"""
    os.makedirs(os.path.dirname(FORCE), exist_ok=True)
    if ver is None:
        try:
            os.remove(FORCE)
        except OSError:
            pass
        return
    tmp = FORCE + ".tmp"
    with io.open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps({name: ver}, ensure_ascii=False))
    os.replace(tmp, FORCE)


def decide(pairs, min_tasks=10, min_wins=2):
    """纯函数：两臂结果 → 判定。

    promote = 候选至少赢 min_wins 单，且**一单都没退化**。
    reject  = 有任何一单退化（保守：提示词全流量生效，不容忍回归）。
    """
    n = len(pairs)
    wins = [p for p in pairs if p["cand_ok"] and not p["stable_ok"]]
    losses = [p for p in pairs if p["stable_ok"] and not p["cand_ok"]]
    if n < min_tasks:
        return "insufficient", wins, losses
    if losses:
        return "reject", wins, losses
    if len(wins) >= min_wins:
        return "promote", wins, losses
    return "keep", wins, losses


def _run_arm(task: dict, ver, tag: str, wait_min: float):
    """钉版本 → 投单 → 等报告 → 判据。返回 (ok, how, answer)。"""
    tid = "ab_%s_%s_%s" % (time.strftime("%m%d_%H%M%S"), tag, task["id"])
    since = time.time()
    NB._inbox_push(task["task"], tid)
    rep = NB._wait_report(tid, wait_min, since=since)
    if not rep:
        return False, "no-report", ""
    ans = rep.get("answer")
    try:
        ok, how = B2.verify(task.get("check") or {}, ans, since=since, report=rep)
    except Exception as e:                      # 判据自身坏 ⇒ 如实记，不吞
        return False, "verify-error: %s" % str(e)[:80], ans
    return bool(ok), str(how), ans


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--candidate", required=True, help="候选版本（如 v2）")
    ap.add_argument("--ids", default=None,
                    help="逗号分隔的题号；缺省用 smoke 子集")
    ap.add_argument("--wait-min", type=float, default=6.0)
    ap.add_argument("--min-tasks", type=int, default=10)
    ap.add_argument("--min-wins", type=int, default=2)
    ap.add_argument("--promote", action="store_true",
                    help="判定 promote 时写 manifest")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    cand_path = os.path.join(PROMPTS, "%s.%s.md" % (a.name, a.candidate))
    if not os.path.isfile(cand_path):
        raise SystemExit("候选不存在: %s" % cand_path)
    mf = json.load(io.open(MANIFEST, encoding="utf-8"))
    stable = (mf.get(a.name) or {}).get("stable") or "v1"
    if stable == a.candidate:
        raise SystemExit("候选 == stable（%s），没有可比对象" % stable)

    all_tasks = load_tasks()
    ids = ([x.strip() for x in a.ids.split(",") if x.strip()]
           if a.ids else list(SMOKE))
    ids = [i for i in ids if i in all_tasks]
    if not ids:
        raise SystemExit("没有可跑的题（检查 --ids）")

    print("提示词 %s：stable=%s vs candidate=%s，%d 单，每单两臂"
          % (a.name, stable, a.candidate, len(ids)))
    if a.dry_run:
        for i in ids:
            print("  -", i, "|", all_tasks[i]["task"][:50])
        return 0

    pairs = []
    try:
        for k, tid in enumerate(ids, 1):
            t = all_tasks[tid]
            set_force(a.name, stable)
            s_ok, s_how, s_ans = _run_arm(t, stable, "S", a.wait_min)
            set_force(a.name, a.candidate)
            c_ok, c_how, c_ans = _run_arm(t, a.candidate, "C", a.wait_min)
            mark = "=" if s_ok == c_ok else ("↑" if c_ok else "↓")
            print("[%2d/%d] %-5s %s  stable=%s  cand=%s"
                  % (k, len(ids), tid, mark, "✓" if s_ok else "✗",
                     "✓" if c_ok else "✗"))
            if mark == "↓":
                print("        stable: %s" % s_how[:100])
                print("        cand  : %s" % c_how[:100])
            pairs.append({"id": tid, "stable_ok": s_ok, "cand_ok": c_ok,
                          "stable_how": s_how, "cand_how": c_how,
                          "stable_answer": str(s_ans)[:400],
                          "cand_answer": str(c_ans)[:400]})
    finally:
        set_force(a.name, None)          # ★ 无论怎么退出都恢复生产
        print("已删除钉版本文件（生产回到 manifest 灰度）")

    verdict, wins, losses = decide(pairs, a.min_tasks, a.min_wins)
    ts = time.strftime("%Y%m%d_%H%M%S")
    out = os.path.join(OUT_DIR, "prompt_ab_%s_%s_%s.json"
                       % (a.name, a.candidate, ts))
    payload = {"name": a.name, "stable": stable, "candidate": a.candidate,
               "ts": ts, "verdict": verdict,
               "wins": [p["id"] for p in wins],
               "losses": [p["id"] for p in losses],
               "pairs": pairs}
    with io.open(out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(payload, ensure_ascii=False, indent=1))
    print("\n判定: %s（赢 %d / 输 %d / 共 %d）"
          % (verdict.upper(), len(wins), len(losses), len(pairs)))
    if wins:
        print("  赢:", ", ".join(p["id"] for p in wins))
    if losses:
        print("  输:", ", ".join(p["id"] for p in losses))
    print("明细:", os.path.relpath(out, ROOT))

    if a.promote:
        if verdict != "promote":
            print("未晋升（判定不是 promote）")
        else:
            bak = MANIFEST + ".bak_" + ts
            with io.open(bak, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(json.dumps(mf, ensure_ascii=False, indent=2))
            mf[a.name] = {"stable": a.candidate, "candidate": None, "pct": 0}
            with io.open(MANIFEST, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(json.dumps(mf, ensure_ascii=False, indent=2) + "\n")
            print("已晋升 %s: stable=%s（备份 %s）"
                  % (a.name, a.candidate, os.path.basename(bak)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
