# -*- coding: utf-8 -*-
"""R268-A · 反事实反思探针（论文 §7 反思训练 → DWC 机判 eval 版）。

★★★ 设计：
  · 反事实截断提问：只给任务描述（不给解法/答案），问"做到一半被打断，
    此刻最该警惕的一件事是什么"，单轮 complete（不进执行链）。
  · 机判 rubric（零基线 — Rule C）：按 kind 分三组风险词，命中率即分。
  · task_ok 复用最近 bench2/ablation 跑批同 id 行；无则记 null 不瞎填。
  · LLM 不可用记 probe_score=null（缺测≠零分 — Rule 12 大声报错）。

用法: python scripts/dwc_reflect_probe.py [--limit 3]
输出: var/eval/reflect_probe.jsonl + stdout 预测力小结
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

TASKS = os.path.join(_ROOT, "config", "eval_tasks.jsonl")
EVAL_DIR = os.path.join(_ROOT, "var", "eval")
OUT = os.path.join(EVAL_DIR, "reflect_probe.jsonl")

PROBE_TMPL = ("你是 DWC 任务执行者。任务做到一半被打断，只剩一句话机会。"
              "请说出此刻做这个任务最该警惕的一件事，只答一句话，不要解释。\n"
              "任务：%s")

# ★ kind → 风险词组（命中率即分；未知 kind 走 default 组）
RISK_WORDS = {
    "read": ["原文", "核对", "文档", "字符", "确切", "位置"],
    "run": ["重跑", "独立", "验证", "返回码", "环境", "路径"],
    "default": ["覆盖", "路径", "完整", "检查", "确认", "边界"],
}


def _group(kind: str) -> list:
    k = (kind or "").lower()
    if k.startswith("read"):
        return RISK_WORDS["read"]
    if k.startswith("run"):
        return RISK_WORDS["run"]
    return RISK_WORDS["default"]


def score_reflection(kind: str, text: str) -> tuple:
    """零基线打分：命中词数/组大小。空串 0.0；非 str 抛 TypeError。"""
    if not isinstance(text, str):
        raise TypeError("text must be str, got %r" % type(text))
    words = _group(kind)
    hits = [w for w in words if w in (text or "")]
    return (len(hits) / len(words),
            "hit %d/%d: %r" % (len(hits), len(words), hits))


def _latest_task_ok(task_id: str, eval_dir: str = EVAL_DIR):
    """最近跑批（run_*/ablation_*）同 id 行的 ok；无则 None。"""
    best = None
    for pat in ("run_*.jsonl", "ablation_*.jsonl"):
        for p in glob.glob(os.path.join(eval_dir, pat)):
            if os.path.basename(p) == os.path.basename(OUT):
                continue
            try:
                mtime = os.path.getmtime(p)
            except OSError:
                continue
            try:
                fh = io.open(p, encoding="utf-8")
            except OSError:
                continue
            with fh:
                for line in fh:
                    try:
                        r = json.loads(line)
                    except ValueError:
                        continue
                    if r.get("id") == task_id and (
                            best is None or mtime >= best[0]):
                        best = (mtime, bool(r.get("ok")))
    return best[1] if best else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--max-tokens", type=int, default=200)
    args = ap.parse_args()

    from dwc.llm.client import LLMClient
    llm = LLMClient()
    if not getattr(llm, "configured", False):
        print("✗ LLM 未配置")
        return 1
    tasks = [json.loads(l) for l in io.open(TASKS, encoding="utf-8")
             if l.strip()]
    if args.limit:
        tasks = tasks[:args.limit]
    os.makedirs(EVAL_DIR, exist_ok=True)

    hi_ok, hi_n, lo_ok, lo_n = 0, 0, 0, 0
    for i, t in enumerate(tasks, 1):
        time.sleep(3)  # ★ 节流（端点限流实测）
        res = llm.complete(PROBE_TMPL % t["task"],
                           max_tokens=args.max_tokens)
        if not getattr(res, "ok", False):
            row = {"id": t["id"], "kind": t["kind"], "probe_score": None,
                   "probe_how": "llm-unavailable: %s" % (
                       getattr(res, "error", "?")),
                   "task_ok": _latest_task_ok(t["id"])}
        else:
            s, how = score_reflection(t["kind"], res.text or "")
            ok = _latest_task_ok(t["id"])
            row = {"id": t["id"], "kind": t["kind"],
                   "probe_score": round(s, 3), "probe_how": how,
                   "task_ok": ok}
            if ok is not None:
                if s >= 0.5:
                    hi_ok, hi_n = hi_ok + (1 if ok else 0), hi_n + 1
                else:
                    lo_ok, lo_n = lo_ok + (1 if ok else 0), lo_n + 1
        with io.open(OUT, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        print("[探针 %d/%d] %s %-12s score=%s ok=%s" % (
            i, len(tasks), t["id"], t["kind"],
            row["probe_score"], row["task_ok"]), flush=True)

    if hi_n + lo_n:
        print("\n预测力（有历史 ok 才计）：高分组 %d/%d=%.0f%%，低分组 %d/%d=%.0f%%"
              % (hi_ok, hi_n, 100 * hi_ok / max(1, hi_n),
                 lo_ok, lo_n, 100 * lo_ok / max(1, lo_n)))
    else:
        print("\n无历史 task_ok 可对照（先跑 bench2/ablation 再看预测力）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
