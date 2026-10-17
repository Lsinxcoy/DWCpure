# -*- coding: utf-8 -*-
"""R303-② monitor-mode（对标 Hermes cron monitor-mode 轻量版）。

纯规则、零 LLM。常驻每轮调用：三条件同时满足才跳过本轮 LLM，
否则返回 None 正常执行。连跳≥2 轮强制执行（防饿死）。

定位声明（DWC-AUTO · 自我强化）：省 token 执行优化 ⇒ 属 DWC-AUTO。
"""
from __future__ import annotations

from typing import Optional

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
