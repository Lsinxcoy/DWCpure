"""R304-A · 机制健康门（DWC-AUTO · 自我强化）。

evolver 每轮读 mechanisms.yaml，对 enabled 机制算健康分；
低分只建议+立案（action="review"），绝不自动改 yaml
（enabled true→false 是改配置，须用户拍板）。
纯函数、零 LLM。事件源 = B 的统一留痕（mech_trace）。
"""
from __future__ import annotations

from typing import Any


def health(mech: str, events: list[dict[str, Any]]) -> dict[str, Any]:
    """返回 {"n","ok_rate"}；无数据 ok_rate=None（不立案）。永不抛错。"""
    try:
        mine = [e for e in (events or [])
                if isinstance(e, dict) and e.get("mech") == mech
                and isinstance(e.get("ok"), bool)]
        if not mine:
            return {"n": 0, "ok_rate": None}
        ok = sum(1 for e in mine if e["ok"])
        return {"n": len(mine), "ok_rate": ok / len(mine)}
    except Exception:
        return {"n": 0, "ok_rate": None}


def advise(enabled: list[str],
           events: list[dict[str, Any]],
           min_n: int = 10,
           floor: float = 0.8) -> list[dict[str, Any]]:
    """低分立案：n≥min_n 且 ok_rate<floor → {"mech","n","ok_rate","action":"review"}。"""
    out: list[dict[str, Any]] = []
    try:
        for m in enabled or []:
            h = health(m, events)
            if h["n"] >= min_n and h["ok_rate"] is not None \
                    and h["ok_rate"] < floor:
                out.append({"mech": m, "n": h["n"], "ok_rate": h["ok_rate"],
                            "action": "review"})
    except Exception:  # audit: 聚合期异常返回空立案（调用方判空=无建议，不静默）
        return out
    return out
