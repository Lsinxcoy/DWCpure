"""R304-B · 机制留痕统一（DWC-MEM · 记忆底座）。

sec_review/monitor/kanban 三处留痕统一 {"mech","event","ok","ts"}，
写 sessions/prod 日志（调用方传 path，缺省不写只返回串）。
project_hint④ 直接拼装（已预留接口）。永不抛错。
"""
from __future__ import annotations

import json
import time
from typing import Any


def emit(entry: Any, path: str | None = None) -> str | None:
    """合法才写：dict 且含 mech/event/ok(bool)。返回所写行（None=未写）。"""
    try:
        if not isinstance(entry, dict):
            return None
        if not entry.get("mech") or "event" not in entry \
                or not isinstance(entry.get("ok"), bool):
            return None
        line = json.dumps({**entry, "ts": entry.get("ts") or
                           time.strftime("%Y-%m-%dT%H:%M:%S+08:00")},
                          ensure_ascii=False)
        if path:
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(line + "\n")
        return line
    except Exception:
        return None


def read_mech_events(path: str) -> list[dict[str, Any]]:
    """读回含 mech 键的行；坏行跳过。"""
    out: list[dict[str, Any]] = []
    try:
        with open(path, encoding="utf-8") as fh:
            for ln in fh.read().splitlines():
                try:
                    d = json.loads(ln)
                except Exception:
                    continue
                if isinstance(d, dict) and d.get("mech"):
                    out.append(d)
    except OSError:  # audit: 读失败返回空（调用方判空=无事件，不静默）
        return out
    return out
