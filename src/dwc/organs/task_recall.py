# -*- coding: utf-8 -*-
"""R457 · 让记忆参与"下一题选哪个"。

★★★ 定位（G1）: **DWC-AUTO** —— 自我强化：上一轮的失败决定下一轮做什么。

为什么必须有
------------
R457 前实测：`memory_node` 5,073 条里 **83.7% 从未被取回**，
`failure_sig` 2,108 条只被取回 4 次（0.2%）。而选择器完全是

    cand = pool[_day["terms"] % len(pool)]

—— 记忆里"这题反复失败"这件事**从未影响过"下一题选谁"**。
记忆不是没写，是没有消费者。本模块给它第一个真实消费者。

选择口径（按学习价值排序）
--------------------------
1. **跑过且有失败签名** ⇒ 最该再试（失败是唯一的学习信号）
2. **从没跑过** ⇒ 覆盖优先（新面）
3. 跑过且没失败 ⇒ 最久没碰的优先（LRU，避免连刷）

冷却中的题一律让位（与 R455 的 cooldown 语义一致）；
池里全在冷却 ⇒ 返回空串，由调用方回退。
"""
from __future__ import annotations

import json
from typing import Any, Dict, Iterable, Optional, Tuple

#: 只统计这两类节点（其余对"选哪题"没有信息量）
_FAIL_KIND = "failure_sig"
_SKILL_KIND = "skill"


def task_stats(memory: Any) -> Dict[str, Dict[str, int]]:
    """一次扫描记忆库：每题的失败签名数 / 相关做法数。

    ★ 只读 payload 里的 task 字段（失败签名写入时已带 task，
      见 `MemoryKernel` 的 failure_sig 落库路径）。
    """
    out: Dict[str, Dict[str, int]] = {}
    try:
        rows = memory._conn.execute(
            "SELECT kind, payload FROM memory_node"
            " WHERE kind IN (?, ?)", (_FAIL_KIND, _SKILL_KIND)).fetchall()
    except Exception as exc:              # noqa: BLE001 — 库不可读 ⇒ 空统计
        import sys
        sys.stderr.write("task_stats 读库失败（按无统计处理）: %r\n" % (exc,))
        return out
    for kind, raw in rows:
        try:
            d = json.loads(raw)
        except (ValueError, TypeError):
            continue
        if not isinstance(d, dict):
            continue
        if kind == _FAIL_KIND:
            t = str(d.get("task") or "")
            if t:
                st = out.setdefault(t, {"n_fail": 0, "n_skill": 0})
                st["n_fail"] += 1
        elif kind == _SKILL_KIND:
            # 做法按 task_id 归户（成功做法是从具体任务学来的）
            t = str(d.get("task_id") or "")
            if t:
                st = out.setdefault(t, {"n_fail": 0, "n_skill": 0})
                st["n_skill"] += 1
    return out


def rank_key(task: str, stats: Dict[str, Dict[str, int]],
             used: Iterable[str] = ()) -> Tuple[int, int, int]:
    """排序键：越小越先跑。纯函数，便于单测。"""
    st = stats.get(task) or {}
    n_fail = int(st.get("n_fail", 0) or 0)
    u = list(used)
    idx = u.index(task) if task in u else -1
    if idx >= 0 and n_fail > 0:
        return (0, -n_fail, idx)      # 跑过且失败过 ⇒ 最该再试（失败多的更前）
    if idx < 0:
        return (1, 0, 0)              # 从没跑过 ⇒ 覆盖
    return (2, 0, idx)                # 跑过且没失败 ⇒ 最久没碰


def pick(pool: Iterable[str], stats: Dict[str, Dict[str, int]],
         cooldown: Iterable[str] = (), used: Iterable[str] = ()) -> str:
    """按记忆排序选一道；全在冷却 ⇒ 空串（调用方回退）。"""
    cd = set(cooldown or ())
    cand = [t for t in pool if t and t not in cd]
    if not cand:
        return ""
    u = list(used or ())
    return sorted(cand, key=lambda t: rank_key(t, stats, u))[0]
