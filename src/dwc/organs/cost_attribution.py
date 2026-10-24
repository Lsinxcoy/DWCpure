# -*- coding: utf-8 -*-
"""R442 · P1-b · 成本归因（按任务聚合 / 每轮快照 / 趋势）。

★★★ 定位（G1）: **DWC-AUTO** —— 自我强化的第二目标：让"花多少钱"可归因、可比较。

为什么要有这个模块
------------------
P0-a 记了每次调用，但**不知道属于哪个任务**。
进化轮要回答"这条规则落地后任务变贵了还是便宜了"，必须先能按任务聚合。

★★★ 诚实边界（必须写在代码里，不能只写在文档里）
  候选规则的**成本无法在 trial 期测量** —— trial 是纯 Python 沙箱，不调 LLM。
  规则的真实成本只在 agent 真正跑任务时产生。
  所以本模块做的是**回溯归因**（按 task_id 聚合生产用量），
  **不是**"候选成本预判"。任何声称能在 trial 期预判成本的实现都是编的。

三条纪律
--------
1. **坏行容错**：生产 jsonl 一定会有半截行（历史教训），跳过而不是掀翻。
2. **无标签不归因**：没有 tag 的调用不进任何任务的账（宁可少算，不可错算）。
3. **快照是增量的**：只统计上次快照之后的任务 —— 否则历史会把趋势抹平。
"""
from __future__ import annotations

import io
import json
import os
import sys
import time
from typing import Any, Dict, List, Optional

LEDGER_REL = "cost_ledger.jsonl"


def _root() -> str:
    return os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))))


def default_usage_path() -> str:
    from dwc.llm import cost as C
    return C.usage_log_path()


def default_ledger_path() -> str:
    """成本快照台账：`var/cost_ledger.jsonl`（与用量文件同目录）。"""
    d = os.path.dirname(default_usage_path())
    return os.path.join(d, LEDGER_REL)


def _rows(path: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    try:
        with io.open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                except ValueError:
                    continue          # ★ 半截行跳过（生产 jsonl 常态）
                if isinstance(r, dict):
                    out.append(r)
    except OSError:
        return []
    return out


def _int(v: Any) -> int:
    try:
        return max(0, int(v))
    except (TypeError, ValueError):
        return 0


def per_task(path: Optional[str] = None,
             since_ts: float = 0.0) -> Dict[str, Dict[str, Any]]:
    """按 tag 聚合：`{task_id: {calls, prompt_tokens, completion_tokens, total_tokens}}`。"""
    acc: Dict[str, Dict[str, Any]] = {}
    for r in _rows(path or default_usage_path()):
        tag = str(r.get("tag") or "").strip()
        if not tag:
            continue                  # ★ 无标签不归因
        try:
            ts = float(r.get("ts") or 0.0)
        except (TypeError, ValueError):
            ts = 0.0
        if since_ts and ts <= since_ts:
            continue
        a = acc.setdefault(tag, {"calls": 0, "prompt_tokens": 0,
                                 "completion_tokens": 0, "total_tokens": 0})
        p = _int(r.get("prompt_tokens"))
        c = _int(r.get("completion_tokens"))
        a["calls"] += 1
        a["prompt_tokens"] += p
        a["completion_tokens"] += c
        a["total_tokens"] += p + c
    return acc


def mean_tokens_per_task(path: Optional[str] = None,
                         since_ts: float = 0.0) -> Dict[str, Any]:
    """每任务平均 token（无任务 ⇒ mean_total=None，**不是 0**）。"""
    t = per_task(path, since_ts=since_ts)
    n = len(t)
    if n == 0:
        return {"n_tasks": 0, "mean_total": None,
                "mean_prompt": None, "mean_completion": None}
    return {
        "n_tasks": n,
        "mean_total": sum(v["total_tokens"] for v in t.values()) / float(n),
        "mean_prompt": sum(v["prompt_tokens"] for v in t.values()) / float(n),
        "mean_completion": sum(v["completion_tokens"] for v in t.values()) / float(n),
    }


def _last_snapshot(led: str) -> Optional[Dict[str, Any]]:
    rows = _rows(led)
    return rows[-1] if rows else None


def snapshot(usage_path: Optional[str] = None,
             ledger_path: Optional[str] = None,
             note: str = "") -> Dict[str, Any]:
    """记一次增量快照，返回该行内容。

    `since_ts` 取上一行的 `max_ts`（没有上一行 ⇒ 0，即全量）。
    """
    up = usage_path or default_usage_path()
    led = ledger_path or default_ledger_path()
    prev = _last_snapshot(led)
    since = 0.0
    if prev:
        try:
            since = float(prev.get("max_ts") or 0.0)
        except (TypeError, ValueError):
            since = 0.0
    m = mean_tokens_per_task(up, since_ts=since)
    max_ts = since
    for r in _rows(up):
        try:
            max_ts = max(max_ts, float(r.get("ts") or 0.0))
        except (TypeError, ValueError):
            continue
    row: Dict[str, Any] = {
        "ts": time.time(),
        "max_ts": max_ts,
        "since_ts": since,
        "n_tasks": m["n_tasks"],
        "mean_total": m["mean_total"],
        "mean_prompt": m["mean_prompt"],
        "mean_completion": m["mean_completion"],
    }
    if note:
        row["note"] = note
    try:
        parent = os.path.dirname(led)
        if parent and not os.path.isdir(parent):
            os.makedirs(parent, exist_ok=True)
        with io.open(led, "a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError as e:          # noqa: BLE001 — 旁路失败只留痕
        sys.stderr.write("成本快照落盘失败: %r\n" % (e,))
    return row


def trend(ledger_path: Optional[str] = None) -> Dict[str, Any]:
    """最近两次快照的走向。数据不足 ⇒ `direction="unknown"`（不猜）。"""
    rows = _rows(ledger_path or default_ledger_path())
    if len(rows) < 2:
        return {"direction": "unknown", "delta": None, "n": len(rows)}
    a = rows[-2].get("mean_total")
    b = rows[-1].get("mean_total")
    if a is None or b is None:
        return {"direction": "unknown", "delta": None, "n": len(rows)}
    try:
        delta = float(b) - float(a)
    except (TypeError, ValueError):
        return {"direction": "unknown", "delta": None, "n": len(rows)}
    direction = "flat"
    if delta > 0:
        direction = "up"
    elif delta < 0:
        direction = "down"
    return {"direction": direction, "delta": delta, "n": len(rows)}


def by_profile(path: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
    """按**档位**聚合（R447）。无档位标签的行不参与（宁可少算，不可错算）。"""
    acc: Dict[str, Dict[str, Any]] = {}
    for r in _rows(path or default_usage_path()):
        pf = str(r.get("profile") or "").strip()
        if not pf:
            continue
        a = acc.setdefault(pf, {"calls": 0, "prompt_tokens": 0,
                                "completion_tokens": 0, "total_tokens": 0,
                                "tasks": []})
        p = _int(r.get("prompt_tokens"))
        c = _int(r.get("completion_tokens"))
        a["calls"] += 1
        a["prompt_tokens"] += p
        a["completion_tokens"] += c
        a["total_tokens"] += p + c
        t = str(r.get("tag") or "").strip()
        if t and t not in a["tasks"]:
            a["tasks"].append(t)
    for a in acc.values():
        n = len(a["tasks"])
        a["n_tasks"] = n
        a["mean_total"] = (a["total_tokens"] / float(n)) if n else None
        del a["tasks"]
    return acc
