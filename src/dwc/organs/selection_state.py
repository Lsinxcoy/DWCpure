# -*- coding: utf-8 -*-
"""R455 · 选择状态持久化 + 供给题覆盖优先。

★★★ 定位（G1）: **DWC-AUTO** —— 自我强化：保证造出来的题真的会被跑到。

为什么必须有
------------
实测（2026-10-24 17:00）：供给队列 15 道题，**只有 1 道跑过**（`fresh_range_sum`
跑了 3 次全 1.0），其余 14 道从未执行。

根因在 `scripts/dwc_agent.py`：

    _sel = {"last": None, "streak": 0, "used": [], "cooldown": {}}
    _day = {"key": ..., "terms": 0, "cost": 0.0}

两个都是**内存变量**，从不落盘。任务选择走 `pool[_day["terms"] % len(pool)]`，
进程一重启 `terms` 归零 ⇒ 永远回到 `pool[0]`。
当天重启 6 次 = 同一道题被喂了 6 遍，后面的题一次都没轮到。

纪律
----
- 状态文件坏了/缺失 ⇒ 返回默认值，**绝不抛**（选择器不该因台账损坏停摆）
- 跨天 ⇒ `terms`/`cost` 归零，但 `used`/`cooldown` 保留（覆盖进度不能因过夜清零）
- 供给题优先**只对"从未跑过"的题生效**：全覆盖之后回到正常轮转
"""
from __future__ import annotations

import io
import json
import os
import sys
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple

#: 默认状态文件（调用方可覆盖）
STATE_REL = "var/agent_sel.json"


def _defaults(today: Optional[str] = None) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    key = today or time.strftime("%Y-%m-%d")
    return ({"last": None, "streak": 0, "used": [], "cooldown": {}},
            {"key": key, "terms": 0, "cost": 0.0})


def save(sel: Dict[str, Any], day: Dict[str, Any],
         path: Optional[str] = None) -> bool:
    """落盘。写不了返回 False 并留痕（不许静默）。"""
    p = path or STATE_REL
    row = {"sel": sel, "day": day, "updated_ts": time.time()}
    try:
        parent = os.path.dirname(p)
        if parent and not os.path.isdir(parent):
            os.makedirs(parent, exist_ok=True)
        with io.open(p, "w", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        return True
    except OSError as e:                  # noqa: BLE001 — 台账写不了不掀 tick
        sys.stderr.write("选择状态写盘失败: %r\n" % (e,))
        return False


def load(path: Optional[str] = None, today: Optional[str] = None
         ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """读盘。缺失/坏/结构不对 ⇒ 默认值；跨天 ⇒ 只重置当日计数。"""
    p = path or STATE_REL
    sel, day = _defaults(today)
    try:
        with io.open(p, encoding="utf-8") as f:
            row = json.load(f)
    except (OSError, ValueError):
        return sel, day
    if not isinstance(row, dict):
        return sel, day
    s = row.get("sel")
    if isinstance(s, dict):
        used = s.get("used")
        sel["last"] = s.get("last")
        try:
            sel["streak"] = max(0, int(s.get("streak") or 0))
        except (TypeError, ValueError):
            sel["streak"] = 0
        sel["used"] = [str(x) for x in used] if isinstance(used, list) else []
        cd = s.get("cooldown")
        sel["cooldown"] = ({str(k): int(v) for k, v in cd.items()}
                           if isinstance(cd, dict) else {})
    d = row.get("day")
    if isinstance(d, dict):
        key = str(d.get("key") or "")
        if key and key == (today or time.strftime("%Y-%m-%d")):
            try:
                day["terms"] = max(0, int(d.get("terms") or 0))
            except (TypeError, ValueError):
                day["terms"] = 0
            try:
                day["cost"] = max(0.0, float(d.get("cost") or 0.0))
            except (TypeError, ValueError):
                day["cost"] = 0.0
    return sel, day


def pick_with_supply(cand: str, pool: Sequence[str],
                     supply: Sequence[str], used: Sequence[str],
                     cooldown: Optional[Dict[str, Any]] = None) -> str:
    """★ 覆盖优先：队列里还有**从未跑过**的题 ⇒ 先跑它。

    - 供给题在冷却中 ⇒ 跳过（冷却优先于覆盖，避免把刚失败的题立刻塞回去）
    - 没有未跑过的供给题 ⇒ 原样返回 `cand`（正常轮转/advice 继续生效）
    - `cand` 本身就是未跑过的供给题 ⇒ 原样返回（不无谓改动）
    """
    cd = cooldown or {}
    unrun: List[str] = [t for t in (supply or ())
                        if t not in set(used) and t not in cd and t in set(pool)]
    if not unrun:
        return cand
    if cand in unrun:
        return cand
    return unrun[0]
