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

★★★ R435 · 并发波次（--wave N）：
    端点实测支持 4 路并发（12/12 合法 JSON，4.17× 加速）。一波 N 单同时
    投递、等齐再切臂 ⇒ 每单耗时从 ~5 分钟降到 ~1.5 分钟。
    前提：agent 必须以 `DWC_TASK_CONCURRENCY>=N`、`DWC_HTTP_CONCURRENCY>=N`
    启动 —— **HTTP 锁宽度 1 时，槽位再多也只会有 1 个请求在飞**。

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

    ★ 基础设施故障（任一臂为 None）**不进分母** —— 网络 502 不是候选的错。
    """
    valid = [p for p in pairs
             if p.get("stable_ok") is not None and p.get("cand_ok") is not None]
    n = len(valid)
    wins = [p for p in valid if p["cand_ok"] and not p["stable_ok"]]
    losses = [p for p in valid if p["stable_ok"] and not p["cand_ok"]]
    if n < min_tasks:
        return "insufficient", wins, losses
    if losses:
        return "reject", wins, losses
    if len(wins) >= min_wins:
        return "promote", wins, losses
    return "keep", wins, losses


def _report_path(tid: str) -> str:
    return os.path.join(NB.REPORTS, "%s.json" % tid)


def _wait_many(batch, since: float, timeout_min: float, poll: float = 10.0):
    """等一批报告到齐（或超时）。返回 {ab_tid: report}。

    ★ 与 `_wait_report` 同一条防旧报告规则：只认 mtime ≥ since 的文件。
    """
    deadline = time.time() + timeout_min * 60
    got = {}
    while time.time() < deadline:
        for ab_tid, _ in batch:
            if ab_tid in got:
                continue
            p = _report_path(ab_tid)
            try:
                if os.path.getmtime(p) < float(since) - 1.0:
                    continue
                got[ab_tid] = json.load(io.open(p, encoding="utf-8"))
            except (OSError, ValueError):
                continue
        if len(got) == len(batch):
            break
        time.sleep(poll)
    return got


def _judge(task, rep, since):
    """(ok, how, answer)。ok=None 表示**基础设施故障**（不是候选的错）。

    ★★★ R435 · 现场：wave=4 跑到 21:52–21:58 连续 6 单 `HTTP 502`，
      第一版把 `answer=None` 当成 ✗ ⇒ 判定 REJECT。这是**把网络故障
      记在候选头上** —— 与 R422 同一条铁律：基础设施故障与模型失败必须
      可区分，且不许计入 A/B 的分母。
    """
    if not rep:
        return False, "no-report", ""
    why = str(rep.get("why") or "")
    if "[infra]" in why:
        return None, "infra: %s" % why[:80], ""
    ans = rep.get("answer")
    try:
        ok, how = B2.verify(task.get("check") or {}, ans, since=since, report=rep)
    except Exception as e:                      # 判据自身坏 ⇒ 如实记，不吞
        return False, "verify-error: %s" % str(e)[:80], ans
    return bool(ok), str(how), ans


def _run_wave(name, ids, tasks, ver, tag, wait_min, results, retry_infra=1):
    """一波：同一版本并发投递 N 单，等齐后逐单判据，结果写进 results。

    ★ 基础设施故障（[infra]）重投一次；仍失败 ⇒ 记为 None（不计分母）。
    """
    set_force(name, ver)
    todo = list(ids)
    for attempt in range(max(1, retry_infra + 1)):
        if not todo:
            break
        since = time.time()
        batch = []
        for tid in todo:
            ab_tid = "ab_%s_%s_%s" % (time.strftime("%m%d_%H%M%S"), tag, tid)
            NB._inbox_push(tasks[tid]["task"], ab_tid)
            batch.append((ab_tid, tid))
        reps = _wait_many(batch, since, wait_min)
        nxt = []
        for ab_tid, tid in batch:
            ok, how, ans = _judge(tasks[tid], reps.get(ab_tid), since)
            results.setdefault(tid, {})[tag] = (ok, how, ans)
            if ok is None and attempt < retry_infra:
                nxt.append(tid)
        todo = nxt
    return len(todo)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--candidate", required=True, help="候选版本（如 v2）")
    ap.add_argument("--ids", default=None,
                    help="逗号分隔的题号；缺省用 smoke 子集")
    ap.add_argument("--wait-min", type=float, default=6.0,
                    help="一波最长等待（并发时每单更慢，建议 10）")
    ap.add_argument("--wave", type=int, default=1,
                    help="一波并发几单（需 agent 的 DWC_TASK_CONCURRENCY≥N）")
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

    wave = max(1, min(8, a.wave))
    print("提示词 %s：stable=%s vs candidate=%s，%d 单，wave=%d"
          % (a.name, stable, a.candidate, len(ids), wave))
    if a.dry_run:
        for i in ids:
            print("  -", i, "|", all_tasks[i]["task"][:50])
        return 0

    results = {}
    t_start = time.time()
    try:
        for w in range(0, len(ids), wave):
            chunk = ids[w:w + wave]
            _run_wave(a.name, chunk, all_tasks, stable, "S", a.wait_min, results)
            _run_wave(a.name, chunk, all_tasks, a.candidate, "C", a.wait_min, results)
            for tid in chunk:
                s = results[tid]["S"][0]
                c = results[tid]["C"][0]
                if s is None or c is None:
                    mark = "?"
                else:
                    mark = "=" if s == c else ("↑" if c else "↓")
                print("[%2d/%d] %-5s %s  stable=%s  cand=%s"
                      % (ids.index(tid) + 1, len(ids), tid, mark,
                         "?" if s is None else ("✓" if s else "✗"),
                         "?" if c is None else ("✓" if c else "✗")))
                if mark == "↓":
                    print("        stable: %s" % results[tid]["S"][1][:100])
                    print("        cand  : %s" % results[tid]["C"][1][:100])
            sys.stdout.flush()
    finally:
        set_force(a.name, None)          # ★ 无论怎么退出都恢复生产
        print("已删除钉版本文件（生产回到 manifest 灰度）")

    pairs = [{"id": tid,
              "stable_ok": results[tid]["S"][0], "cand_ok": results[tid]["C"][0],
              "stable_how": results[tid]["S"][1], "cand_how": results[tid]["C"][1],
              "stable_answer": str(results[tid]["S"][2])[:400],
              "cand_answer": str(results[tid]["C"][2])[:400]}
             for tid in ids]

    verdict, wins, losses = decide(pairs, a.min_tasks, a.min_wins)
    ts = time.strftime("%Y%m%d_%H%M%S")
    out = os.path.join(OUT_DIR, "prompt_ab_%s_%s_%s.json"
                       % (a.name, a.candidate, ts))
    payload = {"name": a.name, "stable": stable, "candidate": a.candidate,
               "ts": ts, "verdict": verdict, "wave": wave,
               "elapsed_s": round(time.time() - t_start, 1),
               "wins": [p["id"] for p in wins],
               "losses": [p["id"] for p in losses],
               "pairs": pairs}
    with io.open(out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(payload, ensure_ascii=False, indent=1))
    print("\n判定: %s（赢 %d / 输 %d / 有效 %d / 共 %d，用时 %.1f 分钟）"
          % (verdict.upper(), len(wins), len(losses),
             len([p for p in pairs if p["stable_ok"] is not None
                  and p["cand_ok"] is not None]), len(pairs),
             (time.time() - t_start) / 60.0))
    _infra = [p["id"] for p in pairs
              if p["stable_ok"] is None or p["cand_ok"] is None]
    if _infra:
        print("  基础设施故障（不计分母）:", ", ".join(_infra))
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
