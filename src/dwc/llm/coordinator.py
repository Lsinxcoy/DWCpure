# -*- coding: utf-8 -*-
"""R303-⑤ Coordinator（对标 Cursor Projects coordinator 规则版前半）。

plan(task)：纯规则拆活，零 LLM。只支持 2 种可判定型：
  并列（含 且/和/并/同时）→ 切块（上限 3，dep 全空）；
  顺承（含 先…再…/然后）→ 按序切（后块 dep 前块）；
  其他 → 单块原样（绝不硬拆）。
run_plan(blocks, kanban_path, emit)：串行发块（emit 为单块执行函数，
  默认 R223 delegate 由调用方注入），状态回写 kanban.jsonl
  （每块 queued→done/fail 两行，append-only）。

定位声明（DWC-AUTO · 自我强化）：多块任务编排执行 ⇒ 属 DWC-AUTO。
"""
from __future__ import annotations

import json
import re
from typing import Any, Callable, Dict, List

MAX_BLOCKS = 3

_SPLIT_RE = re.compile(r"(?:且|和|并|同时|、)")
_SEQ_RE = re.compile(r"先(.+?)再(.+)")


def mark(kanban_path: str, sub: str, status: str) -> bool:
    """★ R305-T4 · 单行 kanban 记账（供并发路径：delegate 并行不用 run_plan
    串行，但每 sub queued→done/fail 两行格式与 run_plan 同）。
    返回 True=写成，False=失败（记数由调用方定，不静默吞）。永不抛错。"""
    try:
        import os
        _d = os.path.dirname(os.path.abspath(kanban_path))
        if _d:
            os.makedirs(_d, exist_ok=True)
        with open(kanban_path, "a", encoding="utf-8") as _fh:
            _fh.write(json.dumps({"sub": str(sub), "status": str(status)},
                                 ensure_ascii=False) + "\n")
        return True
    except Exception:
        return False


def plan(task: str) -> List[Dict[str, Any]]:
    """返回 [{"sub","dep"}]。永不抛错（坏输入返回单块）。"""
    try:
        t = str(task or "").strip()
        if not t:
            return [{"sub": t, "dep": []}]
        m = _SEQ_RE.search(t)
        if m:
            parts = [m.group(1).strip(), m.group(2).strip()]
            parts = [p for p in parts if p][:MAX_BLOCKS]
            if len(parts) >= 2:
                return [{"sub": parts[0], "dep": []},
                        {"sub": parts[1], "dep": [0]}]
        parts = [p.strip() for p in _SPLIT_RE.split(t) if p.strip()]
        if len(parts) >= 2:
            return [{"sub": p, "dep": []} for p in parts[:MAX_BLOCKS]]
        return [{"sub": t, "dep": []}]
    except Exception:
        return [{"sub": str(task), "dep": []}]


def run_plan(blocks: List[Dict[str, Any]], kanban_path: str,
             emit: Callable[[Dict[str, Any]], Any] = None) -> List[str]:
    """串行执行，结果 ["done"/"fail"...]。emit 缺省为空跑（只记账不执行）。"""
    states: List[str] = []
    drops = 0  # ★ G7 · kanban 写失败计数（静默丢行不许，直接记数回写）
    try:
        fh = open(kanban_path, "a", encoding="utf-8")
    except OSError:
        fh = None
    def _w(sub: str, st: str) -> None:
        nonlocal drops
        if fh is None:
            drops += 1
            return
        try:
            fh.write(json.dumps({"sub": sub, "status": st},
                                ensure_ascii=False) + "\n")
        except Exception:
            drops += 1
    try:
        for b in blocks:
            sub = str((b or {}).get("sub", ""))
            _w(sub, "queued")
            try:
                if emit is not None:
                    emit(b)
                states.append("done")
                _w(sub, "done")
            except Exception:
                states.append("fail")
                _w(sub, "fail")
    finally:
        try:
            if fh is not None:
                if drops:
                    fh.write(json.dumps({"event": "kanban_drop", "n": drops},
                                        ensure_ascii=False) + "\n")
                fh.close()
        except Exception:
            drops += 1  # ★ 关闭期失败计入 drops（本轮内存可见，不静默）
    return states
