# -*- coding: utf-8 -*-
"""HCE 拆分读数 —— R117 · ⑥执行轮（稿⑥§⑤ gap_search_vs_val 监测）。

三口径（同一批 golden 任务, 只切换 split_mode）:
  legacy — 拆分前口径全判（对照基线, 现行为）
  search — 搜索期口径: D_val 任务返回 success=None（标签隐藏生效确认）
  select — 终评口径: D_val 任务真判（最终选择的信号源）
读数: search 集均分 / val 集均分 / gap = mean_search − mean_val
      （HCE 2603.26499 §3.3 自报 D_search vs D_val 差距 3.7–4.2pp —
        本脚本出 DWC 同款读数, 只报方向, n=8/n=2 无方差不谈显著）

读:  config/anchors/dev.json（_split）
写:  docs/hce_split_report.json
用法: python scripts/hce_split_report.py
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import sys
from typing import Any, Dict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.core import DWC  # noqa: E402
from dwc.organs.judge import TaskScoreStore  # noqa: E402


def _coerce(x):
    try:
        return ast.literal_eval(str(x))
    except (ValueError, SyntaxError):
        return x


def build_observed(task: Dict[str, Any]) -> Dict[str, Any]:
    """golden → agent 观测形态（keyword: 全 kw 串; behavior: fn→[[args,exp]]）。"""
    kind = task.get("verifier_kind")
    if kind == "keyword_match":
        kws = [c.get("kw") for c in (task.get("checks") or []) if c.get("kw")]
        return {"answer": " ".join(kws)}
    obs: Dict[str, Any] = {}
    for c in task.get("checks", []):
        if "fn" not in c:
            continue
        obs.setdefault(c["fn"], []).append(
            [_coerce(c.get("args", "")), _coerce(c["expected"])])
    return obs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "docs",
                                                  "hce_split_report.json"))
    args = ap.parse_args()

    anchors = json.load(open(os.path.join(ROOT, "config", "anchors",
                                          "dev.json"), encoding="utf-8"))
    sp = anchors.get("_split")
    if not (isinstance(sp, dict) and sp.get("val")):
        print("★ dev.json 无 _split（拆分未启用）⇒ not_applicable")
        return 2
    val_ids, search_ids = list(sp["val"]), list(sp["search"])
    task_ids = sorted(k for k in anchors
                      if not k.startswith("_")
                      and anchors[k].get("verifier_kind") in
                      ("behavior", "keyword_match"))
    assert set(task_ids) == set(val_ids) | set(search_ids), "split 不覆盖全集"

    j = DWC(3, 50, executor=None, db_path=":memory:").judge

    def grade(mode: str) -> Dict[str, bool | None]:
        out: Dict[str, bool | None] = {}
        for tid in task_ids:
            v = j.evaluate(tid, observed=build_observed(anchors[tid]),
                           split_mode=mode)
            out[tid] = v.success
        return out

    legacy, search, select = grade("legacy"), grade("search"), grade("select")

    # 隐藏生效确认: search 模式下 val 任务必须 None + reason 标签隐藏
    hidden_ok = all(search[t] is None for t in val_ids)
    # select 模式下 val 任务必须真判（非 None）
    val_judged = all(select[t] is not None for t in val_ids)

    def mean(ids, g):
        vals = [g[t] for t in ids if g[t] is not None]
        return (sum(1 for x in vals if x) / len(vals)) if vals else None

    m_s, m_v = mean(search_ids, legacy), mean(val_ids, legacy)
    gap = (m_s - m_v) if (m_s is not None and m_v is not None) else None
    report = {
        "protocol": ("HCE 拆分读数: 同批golden三口径(legacy/search/select), "
                     "gap=mean(search集)−mean(val集); 只报方向(n=8/2无方差)"),
        "split": {"search": len(search_ids), "val": val_ids},
        "legacy": {k: legacy[k] for k in task_ids},
        "search_mode": {k: search[k] for k in task_ids},
        "select_val": {k: select[k] for k in val_ids},
        "means": {"search_set_legacy": m_s, "val_set_legacy": m_v},
        "gap_search_vs_val": gap,
        "checks": {"hidden_ok": hidden_ok, "val_judged_in_select": val_judged},
        "caveats": [
            "n=8/2 只报方向不谈显著（R67/R105c 同口径）",
            "三口径同 executor golden ⇒ 语义等价是预期, gap≈0 不代表"
            "无过拟合风险 — 该读数在有真实搜索压力（LLM 臂）时才有分辨力",
            "HCE 3.7–4.2pp 是它的 30 任务数, 不外推为 DWC 预期（稿⑥§⑧）",
        ],
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    print("隐藏生效:", hidden_ok, "| val 终评真判:", val_judged)
    print("search集=%.3f val集=%.3f gap=%s" % (
        m_s or -1, m_v or -1,
        ("%.3f" % gap) if gap is not None else "None"))
    print("写出:", args.out)
    return 0 if (hidden_ok and val_judged) else 1


if __name__ == "__main__":
    sys.exit(main())
