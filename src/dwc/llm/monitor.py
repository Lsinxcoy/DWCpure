# -*- coding: utf-8 -*-
"""R303-② monitor-mode（对标 Hermes cron monitor-mode 轻量版）。

纯规则、零 LLM。常驻每轮调用：三条件同时满足才跳过本轮 LLM，
否则返回 None 正常执行。连跳≥2 轮强制执行（防饿死）。

定位声明（DWC-AUTO · 自我强化）：省 token 执行优化 ⇒ 属 DWC-AUTO。

R304-C · 计数校准：record()/calibrate() 记每轮 skip/ran，
50 轮后看空轮率给 MAX_SKIPS 建议（阈值不动，数据化后下 R 再调）。
"""
from __future__ import annotations

from typing import Any, Dict, Optional

MAX_SKIPS = 2


def monitor_skip(*, has_new_input: bool, last_done_ok: bool, skips: int) -> Optional[str]:
    """返回 None=执行；返回串=跳过原因。永不抛错（坏输入一律执行）。"""
    try:
        if has_new_input:
            return None
        if not last_done_ok:
            return None
        if int(skips) >= MAX_SKIPS:
            return None
        return "monitor跳过：无新输入+上轮全ok+连跳%d<%d" % (int(skips), MAX_SKIPS)
    except Exception:
        return None


def record(outcome: str, path: str) -> None:
    """记一轮 {"w": skip|ran}。永不抛错。"""
    try:
        if outcome not in ("skip", "ran"):
            return
        import json
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"w": outcome}) + "\n")
    except Exception as _e:  # ★ G7 · 写失败记 stderr（计数器本身，无处回写）
        import sys
        try:
            sys.stderr.write("monitor.record 写失败: %r\n" % (_e,))
        except Exception:  # audit: stderr 已不可写则放弃（外层已记日志）
            ...


def calibrate(path: str) -> Dict[str, Any]:
    """读计数给建议：skip_rate≥0.9→3；≤0.3→1；否则 2。n=0 默认 2。永不抛错。"""
    try:
        import json
        n = s = 0
        with open(path, encoding="utf-8") as fh:
            for ln in fh.read().splitlines():
                try:
                    d = json.loads(ln)
                except Exception:
                    continue
                if isinstance(d, dict) and d.get("w") in ("skip", "ran"):
                    n += 1
                    s += (d["w"] == "skip")
        if not n:
            return {"n": 0, "skip_rate": None, "suggest": 2}
        r = s / n
        return {"n": n, "skip_rate": r,
                "suggest": 3 if r >= 0.9 else (1 if r <= 0.3 else 2)}
    except OSError:
        return {"n": 0, "skip_rate": None, "suggest": 2}
    except Exception:
        return {"n": 0, "skip_rate": None, "suggest": 2}
