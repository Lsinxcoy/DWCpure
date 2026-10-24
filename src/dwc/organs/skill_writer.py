# -*- coding: utf-8 -*-
"""R457 · 把"学到的做法"写进记忆 —— 让 skill 不再是 0 条。

★★★ 定位（G1）: **DWC-AUTO** —— 自我强化：自己学到的做法，自己存成可检索的记忆。

为什么必须有
------------
实测（R457 前）：生产记忆库 `memory_node` 5,073 条里 **skill = 0**，
而 `var/dwc_lessons.jsonl` 里躺着 **905 条 success_pattern**（904 条带
"成功做法（...）"）—— 系统一直在学，只是学到的做法**从未进入记忆**。

后果是两条链同时断：

1. `dwc/llm/executor.py::memory_text()` 只读 `kind='skill'` ⇒ 恒返回空
   ⇒ 模型 prompt 里的"已知参考资料"永远是「（无）」
2. 记忆库的 EXPERIENCE 区只有 failure_sig（失败），没有"做对了什么"
   ⇒ 检索面只有负样本

★ D6 纪律：SKILL 属 EXPERIENCE，payload 必须含
  `scene / method / boundary / invalid_conditions / recovery_strategies`。
  缺一项就**不写**（fail-closed）—— 不编恢复策略。
  本模块的 `recovery_strategies` 不是编的：它写的是系统真实行为
  （本条失效 ⇒ 本轮失败签名进 evolver 重新诊断），见 `_RECOVERY`。

★ 去重：`src_key = sha1(task + method)`。同一做法重复出现只写一次；
  近重复由 `MemoryKernel.remember` 自己的合并逻辑处理（R104）。
"""
from __future__ import annotations

import hashlib
import io
import json
import os
from typing import Any, Dict, Iterable, Optional, Set

from dwc.organs.memory import MemoryKind

#: 成功做法失效后的真实去向（不是策略发明：失败签名本来就进 evolver）
_RECOVERY = "失效时按本轮失败签名重新诊断（evolver 通道），不沿用本条"

#: 只收这类 fail_mode（成功路径）；失败类不进 SKILL
_SUCCESS_PREFIX = "success_pattern"


def _clip(s: Any, n: int) -> str:
    return str(s or "").strip()[:n]


def src_key(task: Any, method: Any) -> str:
    """做法指纹（task + method）。同一做法只写一次。"""
    raw = "%s\x00%s" % (_clip(task, 400), _clip(method, 800))
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def lesson_to_payload(row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """把一条 lesson 变成 SKILL payload；不合格返回 None（fail-closed）。

    合格条件（全部满足才写）：
      · fail_mode 以 `success_pattern` 开头
      · task 与 detail 都非空
    """
    if not isinstance(row, dict):
        return None
    fm = _clip(row.get("fail_mode"), 120)
    if not fm.startswith(_SUCCESS_PREFIX):
        return None
    task = _clip(row.get("task"), 400)
    detail = _clip(row.get("detail"), 800)
    # ★ 太短的 task/detail 是占位或测试残留（实测台账里混进过
    #   task="任务X" detail="假答案" 这种行）—— 不做成"经验"。
    if len(task) < 4 or len(detail) < 12:
        return None
    return {
        "scene": task,
        "method": detail,
        "boundary": fm,
        # 什么时候不适用：不属于这一类任务时
        "invalid_conditions": "任务不属于 %s 类，或该任务已有更新的成功做法" % fm,
        "recovery_strategies": _RECOVERY,
        "src_key": src_key(task, detail),
        "task_id": _clip(row.get("task_id"), 80),
        "quality": row.get("quality"),
        "at": row.get("at"),
    }


def existing_keys(memory: Any) -> Set[str]:
    """库里已有做法的 src_key 集合（一次查询，供批量去重）。"""
    keys: Set[str] = set()
    try:
        rows = memory._conn.execute(
            "SELECT payload FROM memory_node WHERE kind='skill'").fetchall()
    except Exception:                     # noqa: BLE001 — 库不可读 ⇒ 空集
        return keys
    for r in rows:
        try:
            d = json.loads(r[0])
        except (ValueError, TypeError):
            continue
        k = d.get("src_key")
        if k:
            keys.add(str(k))
    return keys


def promote_lesson(memory: Any, row: Dict[str, Any],
                   seen: Optional[Set[str]] = None) -> Optional[str]:
    """写一条；重复或不合格返回 None。"""
    p = lesson_to_payload(row)
    if p is None:
        return None
    if seen is not None:
        if p["src_key"] in seen:
            return None
    else:
        if p["src_key"] in existing_keys(memory):
            return None
    nid = memory.remember(MemoryKind.SKILL, p)
    if seen is not None:
        seen.add(p["src_key"])
    return nid


def promote_pending(memory: Any, path: Optional[str] = None,
                    limit: Optional[int] = None) -> Dict[str, int]:
    """把 lessons 里尚未入库的成功做法写成 SKILL。

    返回 `{n_seen, n_written, n_dup, n_skip}` —— 四个数必须能对上 n_seen，
    否则就是有分支没记账（G7 精神：不许静默跳过）。
    """
    path = path or os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))))),
        "var", "dwc_lessons.jsonl")
    out = {"n_seen": 0, "n_written": 0, "n_dup": 0, "n_skip": 0}
    seen = existing_keys(memory)
    try:
        fh = io.open(path, encoding="utf-8")
    except OSError:
        return out
    with fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            out["n_seen"] += 1
            try:
                row = json.loads(line)
            except ValueError:
                out["n_skip"] += 1
                continue
            p = lesson_to_payload(row)
            if p is None:
                out["n_skip"] += 1
                continue
            if p["src_key"] in seen:
                out["n_dup"] += 1
                continue
            memory.remember(MemoryKind.SKILL, p)
            seen.add(p["src_key"])
            out["n_written"] += 1
            if limit is not None and out["n_written"] >= int(limit):
                break
    return out


def skill_count(memory: Any) -> int:
    """生产核对用：库里 skill 节点数。"""
    try:
        return int(memory._conn.execute(
            "SELECT COUNT(*) FROM memory_node WHERE kind='skill'").fetchone()[0])
    except Exception:                     # noqa: BLE001
        return -1
