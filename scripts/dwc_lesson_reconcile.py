# -*- coding: utf-8 -*-
"""R269-② · lessons 对账（RSIAgent reconciliation → DWC 版）。

★★★ 设计：
  · 按 fail_mode 分组审查：规则后备（全等 dupe 必 drop 留首条；task 全等
    detail 不同只建议 merge、不自动合）＋ LLM 组审查（每组一调用，可选）。
  · 默认 dry-run：只打印分组统计＋drop/merge 建议，不写文件。
  · --apply 才落盘（原子 tmp＋os.replace；失败 stderr＋计数，不炸）。

用法: python scripts/dwc_lesson_reconcile.py [--apply]
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys
import time

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "src"))

from dwc.agent_quality import LESSONS as _DEFAULT_LESSONS  # noqa: E402

LESSONS_PATH = _DEFAULT_LESSONS
_FAILS = 0


def _load() -> list:
    if not os.path.exists(LESSONS_PATH):
        return []
    out = []
    for ln in io.open(LESSONS_PATH, encoding="utf-8").read().splitlines():
        if ln.strip():
            try:
                out.append(json.loads(ln))
            except ValueError:
                pass
    return out


def _group_by_mode(lessons: list) -> dict:
    g: dict = {}
    for row in lessons:
        g.setdefault(str(row.get("fail_mode", "?")), []).append(row)
    return g


def _age_days(row: dict, now: str) -> float:
    """行 at/last_used 距 now 的天数（缺席按 90 天计——未知即旧）。"""
    stamp = str(row.get("last_used") or row.get("at") or "")
    try:
        then = time.mktime(time.strptime(stamp[:19], "%Y-%m-%dT%H:%M:%S"))
        ref = time.mktime(time.strptime(now[:19], "%Y-%m-%dT%H:%M:%S"))
        return max(0.0, (ref - then) / 86400.0)
    except (ValueError, OverflowError):
        return 90.0


def forget_score(row: dict, now: str) -> tuple:
    """★ R270-⑤ · 遗忘分（MSTAR 同款公式 DWC 口径）。

    fitness×0.4＋recency×0.3＋quality×0.3 → (分, 策略, why)。
    策略：≥0.5 keep；0.25–0.5 archive；0.15–0.25 merge；<0.15 drop。
    """
    fitness = min(1.0, int(row.get("use_count", 0) or 0) / 5.0)
    recency = 1.0 - min(_age_days(row, now) / 90.0, 1.0)
    quality = float(row.get("quality", 0.5) or 0.5)
    s = round(fitness * 0.4 + recency * 0.3 + quality * 0.3, 4)
    if s >= 0.5:
        strat = "keep"
    elif s >= 0.25:
        strat = "archive"
    elif s >= 0.15:
        strat = "merge"
    else:
        strat = "drop"
    return (s, strat, "fit=%.2f rec=%.2f qual=%.2f" % (
        fitness, recency, quality))


def _merge_rows(rows: list) -> dict:
    """★ 同 mode 中档行合并：detail 按句去重拼接（≤300 字），标来源数。"""
    if not rows:
        raise ValueError("merge 空行（调用方 bug）")
    seen: list = []
    for row in rows:
        for sent in str(row.get("detail", "")).replace("！", "。").split("。"):
            s = sent.strip()
            if s and s not in seen:
                seen.append(s)
    base = dict(rows[0])
    body = "。".join(seen)
    if body:
        body += "。"
    tag = " [merged_from:%d]" % len(rows)
    base["detail"] = (body + tag)[:300]
    base["use_count"] = sum(int(r.get("use_count", 0) or 0) for r in rows)
    return base


def _exact_dupes(items: list) -> list:
    """全等 dupe（task_id＋detail 全等）→ 除首条外全进 drop。"""
    seen = set()
    drops = []
    for row in items:
        key = (str(row.get("task_id")), str(row.get("detail")))
        if key in seen:
            drops.append(row)
        else:
            seen.add(key)
    return drops


def _review_group(mode: str, items: list, llm=None) -> dict:
    """一组审查 → {"keep","drop","merge"}。llm=None 走规则后备。"""
    drops = _exact_dupes(items)
    drop_ids = {id(r) for r in drops}
    keep = [r for r in items if id(r) not in drop_ids]
    merge: list = []
    if llm is not None:
        prompt = ("你是记忆对账员。同一 fail_mode 下多条教训，"
                  "指出过时/矛盾/超证据的条目序号，只答 JSON 数组 "
                  "[{\"idx\": 0, \"action\": \"drop\", \"why\": \"...\"}]。"
                  "\n条目：\n" + "\n".join(
                      "%d. [%s] %s" % (i, r.get("task_id"),
                                       r.get("detail"))
                      for i, r in enumerate(keep)))
        try:
            res = llm.complete(prompt, max_tokens=500)
            txt = getattr(res, "text", "") or ""
            start, end = txt.find("["), txt.rfind("]")
            if getattr(res, "ok", False) and start >= 0 and end > start:
                for ent in json.loads(txt[start:end + 1]):
                    i = int(ent.get("idx", -1))
                    if 0 <= i < len(keep) and ent.get("action") == "drop":
                        drops.append(keep[i])
        except Exception as exc:                     # noqa: BLE001
            global _FAILS
            _FAILS += 1
            sys.stderr.write("reconcile LLM 审查失败(跳过本组): %s\n" % exc)
    return {"keep": [r for r in keep if all(r is not d for d in drops)],
            "drop": drops, "merge": merge}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true",
                    help="落盘（默认 dry-run 只打印）")
    ap.add_argument("--dry-run", action="store_true",
                    help="显式 dry-run（与默认同义）")
    ap.add_argument("--llm", action="store_true",
                    help="启用 LLM 组审查（默认只规则后备）")
    args = ap.parse_args(argv)
    lessons = _load()
    groups = _group_by_mode(lessons)
    print("lessons=%d, 分组=%d" % (len(lessons), len(groups)))
    llm = None
    if args.llm:
        from dwc.llm.client import LLMClient
        llm = LLMClient()
        if not getattr(llm, "configured", False):
            print("✗ LLM 未配置（退回规则后备）")
            llm = None
    total_drop = 0
    kept_all = []
    for mode in sorted(groups):
        r = _review_group(mode, groups[mode], llm)
        total_drop += len(r["drop"])
        kept_all.extend(r["keep"])
        print("  [%s] n=%d keep=%d drop=%d" % (
            mode, len(groups[mode]), len(r["keep"]), len(r["drop"])))
        for d in r["drop"][:5]:
            print("    - drop [%s] %s" % (
                d.get("task_id"), str(d.get("detail"))[:60]))
    if not args.apply:
        print("dry-run：未写文件（--apply 才落盘）")
        return 0
    # ★ R270-⑤ · --apply 执行遗忘四策（keep 留 / archive 移归档 /
    #   merge 按 mode 合 / drop 弃，每条带 why）
    now = time.strftime("%Y-%m-%dT%H:%M:%S+08:00")
    final_keep: list = []
    to_archive: list = []
    merge_groups: dict = {}
    strat_drop = 0
    for row in kept_all:
        s, strat, why = forget_score(row, now)
        row["forget_score"] = s
        if strat == "keep":
            final_keep.append(row)
        elif strat == "archive":
            to_archive.append(row)
        elif strat == "merge":
            merge_groups.setdefault(
                str(row.get("fail_mode", "?")), []).append(row)
        else:
            strat_drop += 1
            print("    - forget-drop [%s] %s (%s)" % (
                row.get("task_id"), str(row.get("detail"))[:50], why))
    for mode, items in sorted(merge_groups.items()):
        if len(items) >= 2:
            final_keep.append(_merge_rows(items))
            print("    ~ merge [%s] %d→1" % (mode, len(items)))
        else:
            final_keep.append(items[0])
    tmp = LESSONS_PATH + ".tmp"
    try:
        with io.open(tmp, "w", encoding="utf-8") as fh:
            for row in final_keep:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        os.replace(tmp, LESSONS_PATH)
        if to_archive:
            from dwc.agent_quality import LESSONS_ARCHIVE
            os.makedirs(os.path.dirname(LESSONS_ARCHIVE), exist_ok=True)
            with io.open(LESSONS_ARCHIVE, "a", encoding="utf-8") as fh:
                for row in to_archive:
                    fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError as exc:
        global _FAILS
        _FAILS += 1
        sys.stderr.write("reconcile 落盘失败: %s\n" % exc)
        return 1
    print("已落盘：keep=%d archive=%d drop=%d(+dupe %d)" % (
        len(final_keep), len(to_archive), strat_drop, total_drop))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
