# -*- coding: utf-8 -*-
"""score_revisions · 修订质量评分（R258 gap 偿还 — grounded 率）。

★ 方法（AEWM FActScore 式 §5.1）: 把修订后的规矩分解为**要求/限定**,
  逐条判"是否被源教训（lessons 事件流中同 fail_mode 的 detail）支持"。
  grounded 率 = 受支持要求 / 总要求。
★ 诚实边界: judge 是任务 LLM（弱于 AEWM 的专训模型）⇒ 有乐观偏差;
  这是**代理指标**, 不是修订效用的终证（效用终证=counterfactual 重跑, 贵, 留后续）。
★ 数据源: dwc_skills/.hist/ 下的修订存档对（旧版）+ 当前 md（新版）。

用法: python scripts/score_revisions.py [--limit N]
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "src"))

SKILLS = os.path.join(_ROOT, "var", "dwc_skills")
LESSONS = os.path.join(_ROOT, "var", "dwc_lessons.jsonl")


def _source_lessons(fail_mode: str) -> str:
    """同 fail_mode 的源教训事件（grounded 的判据源 — 修订内容的证据）。"""
    if not os.path.exists(LESSONS):
        return ""
    out = []
    for line in io.open(LESSONS, encoding="utf-8", errors="replace"):
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if d.get("fail_mode") == fail_mode:
            out.append("- %s | %s" % (d.get("task", "")[:80],
                                      d.get("detail", "")[:160]))
    return "\n".join(out[-6:])


def score(limit: int = 0) -> int:
    from dwc.llm.client import LLMClient
    hist = os.path.join(SKILLS, ".hist")
    if not os.path.isdir(hist):
        print("✗ 无修订存档（.hist 空）— 先跑有失败任务的批次")
        return 1
    llm = LLMClient()
    pairs = []
    for fn in sorted(os.listdir(hist)):
        if not fn.endswith(".md"):
            continue
        mode = fn.rsplit(".", 2)[0]
        cur = os.path.join(SKILLS, "%s.md" % mode)
        if not os.path.exists(cur):
            continue
        try:
            old = io.open(os.path.join(hist, fn), encoding="utf-8").read()
            new = io.open(cur, encoding="utf-8").read()
        except OSError:
            continue
        pairs.append((mode, old, new))
    if limit:
        pairs = pairs[:limit]
    if not pairs:
        print("✗ 无修订对")
        return 1
    results = []
    for mode, old, new in pairs:
        src = _source_lessons(mode)
        prompt = (
            "把「修订后规矩」分解为逐条要求/限定, 判每条是否被「源教训」支持。\n"
            "源教训（唯一证据源 — 规矩之外的知识一律不支持）:\n%s\n\n"
            "修订后规矩:\n%s\n\n"
            "只输出 JSON: {\"requirements\": [{\"req\": \"…\", "
            "\"supported\": true/false}], \"note\": \"…\"}"
            % (src or "(无源教训记录 — 全部按 unsupported 计)", new[:800]))
        try:
            r = llm.complete(prompt, json_mode=True, tag="rev_score")
            obj = json.loads(r.text or "{}") if getattr(r, "ok", False) else {}
        except Exception as exc:                    # noqa: BLE001
            print("  ✗ %s: judge 失败 %s" % (mode, exc))
            continue
        reqs = obj.get("requirements") or []
        n_sup = sum(1 for x in reqs if x.get("supported"))
        n = len(reqs)
        rate = round(n_sup / n, 3) if n else 0.0
        results.append({"mode": mode, "n_req": n, "n_supported": n_sup,
                        "grounded_rate": rate})
        print("  [%s] %d/%d supported = %.3f" % (mode, n_sup, n, rate))
    if not results:
        print("✗ 无有效评分")
        return 1
    avg = round(sum(x["grounded_rate"] for x in results) / len(results), 3)
    total = sum(x["n_supported"] for x in results), sum(x["n_req"] for x in results)
    print("\n==== 修订 grounded 率: 平均 %.3f（%d 对, %d/%d 要求受源支持）===="
          % (avg, len(results), total[0], total[1]))
    print("★ 诚实边界: judge 为任务 LLM（弱于 AEWM 专训）⇒ 乐观偏差; "
          "代理指标, 非效用终证。")
    with io.open(os.path.join(_ROOT, "var", "eval",
                              "revision_scores.json"), "w",
                 encoding="utf-8") as fh:
        json.dump({"avg_grounded": avg, "pairs": results}, fh,
                  ensure_ascii=False, indent=1)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    return score(args.limit)


if __name__ == "__main__":
    raise SystemExit(main())
