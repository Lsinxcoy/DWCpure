# -*- coding: utf-8 -*-
"""R268-D · 外化完整度分析（论文 GSM8K 论据 → 反向用，零 LLM 成本）。

★★★ 设计（只读历史数据）:
  · 外化分（零基线，缺项不得分）：rounds>=3 +0.25；report.answer 非空
    +0.25；actions_log 非空 +0.25；artifacts 非空 +0.25。
  · 读 var/eval/run_*.jsonl + ablation_*.jsonl（同 id 取最新），关联
    var/reports/<task_id>.json（ablation/bench 的 task_id 形如
    abl_<臂>_<id>/eval_<臂>_<id>，取末段匹配）。
  · 结论只报相关性（高分组成功率 − 低分组成功率）；接近 0 就写"无信号"，
    不准调权重凑数（Rule C + 诚实底线）。

用法: python scripts/dwc_externalization.py
输出: var/eval/externalization.jsonl（难度表 stdout）
"""
from __future__ import annotations

import glob
import io
import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "src"))

EVAL_DIR = os.path.join(_ROOT, "var", "eval")
REPORTS = os.path.join(_ROOT, "var", "reports")
OUT = os.path.join(EVAL_DIR, "externalization.jsonl")


def ext_score(row: dict, report: dict | None) -> tuple:
    """零基线：四项各 0.25；report 缺席对应项记 0，不抛错。"""
    s = 0.0
    why = []
    if (row.get("rounds") or 0) >= 3:
        s += 0.25
        why.append("rounds>=3")
    rep = report or {}
    if str(rep.get("answer") or "").strip():
        s += 0.25
        why.append("answer")
    if rep.get("actions_log"):
        s += 0.25
        why.append("actions_log")
    if rep.get("artifacts"):
        s += 0.25
        why.append("artifacts")
    return (round(s, 2), "+".join(why) if why else "无外化痕迹")


def _load_rows() -> list:
    """所有跑批行，同 id 取 mtime 最新。"""
    best: dict = {}
    for pat in ("run_*.jsonl", "ablation_*.jsonl"):
        for p in glob.glob(os.path.join(EVAL_DIR, pat)):
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
                    rid = r.get("id")
                    if not rid:
                        continue
                    if rid not in best or mtime >= best[rid][0]:
                        best[rid] = (mtime, r)
    return [r for _, r in best.values()]


def _load_report(task_id: str):
    """task_id 末段匹配 var/reports/<tid>.json（bench 侧命名不一，取末段）。"""
    tail = str(task_id).split("_")[-1]
    cands = glob.glob(os.path.join(REPORTS, "*.json"))
    for p in cands:
        base = os.path.basename(p)[:-5]
        if base == task_id or base.endswith(tail):
            try:
                return json.load(io.open(p, encoding="utf-8"))
            except (ValueError, OSError):
                return None
    return None


def _difficulty(rows: list, reports: dict) -> dict:
    """纯函数：按 kind 聚成功率 + 平均外化分 + 样本数（测试直测）。"""
    d: dict = {}
    for r in rows:
        k = r.get("kind", "?")
        s, _ = ext_score(r, reports.get(r.get("id")))
        e = d.setdefault(k, {"n": 0, "ok": 0, "ext": 0.0})
        e["n"] += 1
        e["ok"] += 1 if r.get("ok") else 0
        e["ext"] += s
    for k, e in d.items():
        e["success"] = round(e["ok"] / e["n"], 3)
        e["ext_avg"] = round(e["ext"] / e["n"], 3)
        del e["ok"]
        del e["ext"]
    return d


def _gap(rows: list, reports: dict) -> tuple:
    """纯函数：高/低外化组成功率差；任一组为空返回 (0.0, 无意义说明）。"""
    hi = [r for r in rows
          if ext_score(r, reports.get(r.get("id")))[0] >= 0.5]
    lo = [r for r in rows
          if ext_score(r, reports.get(r.get("id")))[0] < 0.5]
    if not hi or not lo:
        return (0.0, "高组 n=%d / 低组 n=%d：样本为空，差距无意义（需 reports 关联）"
                % (len(hi), len(lo)))
    gap = (sum(1 for r in hi if r.get("ok")) / len(hi)
           - sum(1 for r in lo if r.get("ok")) / len(lo))
    note = "" if abs(gap) >= 0.05 else "（≈无信号）"
    return (round(gap, 3), note)


def main() -> int:
    rows = _load_rows()
    if not rows:
        print("✗ var/eval 下无跑批行（先跑 bench2/ablation）")
        return 1
    reports = {r.get("id"): _load_report(r.get("id")) for r in rows}
    d = _difficulty(rows, reports)
    gap, note = _gap(rows, reports)
    os.makedirs(EVAL_DIR, exist_ok=True)
    with io.open(OUT, "w", encoding="utf-8") as fh:
        json.dump({"difficulty_by_kind": d,
                   "ext_success_gap": round(gap, 3),
                   "n": len(rows)}, fh, ensure_ascii=False, indent=1)
    print("==== 外化完整度 → 难度（n=%d）====" % len(rows))
    for k in sorted(d):
        print("%-14s n=%-3d 成功率=%.0f%% 外化均分=%.2f" % (
            k, d[k]["n"], 100 * d[k]["success"], d[k]["ext_avg"]))
    print("高/低外化组成功率差 %+.1fpp%s" % (100 * gap, note))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
