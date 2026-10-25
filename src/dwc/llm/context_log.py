# -*- coding: utf-8 -*-
"""R448 · 上下文决策留痕（先把三元组变成可观测，再谈可进化）。

★★★ 定位（G1）: **DWC-AUTO** —— 自我强化的上下文层：把"这次怎么压的"记下来。

为什么先只记不改
----------------
DWC 的压缩只有一条硬编码路径：留最近 2 轮原文 + 更早的拼成前情摘要。
Cache Engineering 的 trigger/selector/reposition 三元组要有**多个形态**才谈得上选择；
现在换 selector 没有对照数据，改了就是拍脑袋。

所以本模块只做一件事：**每次压缩写一行**。
有了分布之后，才知道哪两个 selector 值得 A/B。

纪律
----
- 旁路失败只 stderr 留痕，**不许**因为写日志把任务打断。
- 不记录任何任务正文（只记计数与长度）—— 日志不是第二个上下文。
"""
from __future__ import annotations

import io
import json
import os
import sys
import time
from typing import Any, Dict, Optional

LOG_REL = "context_decisions.jsonl"


def _root() -> str:
    return os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))))


def log_path() -> str:
    d = os.environ.get("DWC_VAR_DIR") or os.path.join(_root(), "var")
    return os.path.join(d, LOG_REL)


def record(*, round: int, trigger: str, selector: str, reposition: bool,
           n_kept: int, n_compressed: int, falsified: int,
           before_chars: int, after_chars: int,
           path: Optional[str] = None) -> Dict[str, Any]:
    """写一行压缩决策。返回该行（写盘失败也返回，调用方可忽略）。"""
    row: Dict[str, Any] = {
        "ts": time.time(),
        "round": int(round),
        "trigger": str(trigger or ""),
        "selector": str(selector or ""),
        "reposition": bool(reposition),
        "n_kept": int(n_kept),
        "n_compressed": int(n_compressed),
        "falsified": int(falsified),
        "before_chars": int(before_chars),
        "after_chars": int(after_chars),
    }
    p = path or log_path()
    try:
        parent = os.path.dirname(p)
        if parent and not os.path.isdir(parent):
            os.makedirs(parent, exist_ok=True)
        with io.open(p, "a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError as e:      # noqa: BLE001 — 旁路失败只留痕
        sys.stderr.write("上下文决策落盘失败: %r\n" % (e,))
    return row


def summary(path: Optional[str] = None) -> Dict[str, Any]:
    """按 (trigger, selector) 汇总：次数与平均压缩比。空库 ⇒ {}（不猜）。"""
    p = path or log_path()
    acc: Dict[str, Dict[str, Any]] = {}
    try:
        with io.open(p, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                k = "%s|%s" % (r.get("trigger"), r.get("selector"))
                a = acc.setdefault(k, {"n": 0, "before": 0, "after": 0})
                a["n"] += 1
                a["before"] += int(r.get("before_chars") or 0)
                a["after"] += int(r.get("after_chars") or 0)
    except OSError:
        return {}
    for a in acc.values():
        a["ratio"] = (float(a["after"]) / a["before"]) if a["before"] else None
    return acc
