# -*- coding: utf-8 -*-
"""R446 · P4 · 改进库（Harness² 四条硬规则）。

★★★ 定位（G1）: **DWC-AUTO** —— 自我强化的记忆层：把"学到过什么"写成
**可查、可审、不可伪造**的条目，而不是散落在 rules.json 的 rationale 里。

四条硬规则（来自 Harness² `core/library.py`，逐条对上 DWC）
------------------------------------------------------------
1. **三要素缺一不入库**（`library.py:43-47`）：
   `cue`（什么信号触发）/ `lesson`（学到什么）/ `evidence`（凭什么信）。
   半条记录比没有更糟 —— 下轮按 cue 取用会拿到一条没有依据的"经验"。
2. **写库前断言树里没有判分结论**（`library.py:122-123`）：
   DWC 的对应物是**不许把 expected 值写进 lesson**（那就是把答案抄进经验）。
3. **只保留当前任务之前的条目**（`library.py:101-104`）：`before()`。
4. **存整棵树不存摘要**（`library.py:22-23`）：DWC 存整段 code / 完整 patch。

诚实边界
--------
本模块**只负责写与查**。它今天**还没有**被起草器读取（起草仍走 `rules.json`
的 `hint_code`）。要让"按 cue 选择性复用"真正生效，下一步是把
`select_family()` 的输出喂进 propose 的上下文 —— 那是另一轮的事，
不能在这里假装已经完成。
"""
from __future__ import annotations

import io
import json
import os
import time
from typing import Any, Dict, List, Optional

LIB_REL = "improvement_library.jsonl"

_REQUIRED = ("cue", "lesson", "evidence")


def _root() -> str:
    return os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))))


def default_path() -> str:
    d = os.environ.get("DWC_VAR_DIR") or os.path.join(_root(), "var")
    return os.path.join(d, LIB_REL)


def validate(entry: Any) -> Optional[str]:
    """合规返回 None；不合规返回**原因**（调用方要能说清为什么不入库）。"""
    if not isinstance(entry, dict):
        return "条目不是 dict"
    for f in _REQUIRED:
        if f not in entry:
            return "缺字段 %s" % (f,)
    if not str(entry.get("cue") or "").strip():
        return "cue 为空"
    if not str(entry.get("lesson") or "").strip():
        return "lesson 为空（没有教训就不算经验）"
    ev = entry.get("evidence")
    if not isinstance(ev, dict) or not ev:
        return "evidence 为空（没有依据就不许入库）"
    return None


def add(path: Optional[str] = None, entry: Optional[Dict[str, Any]] = None
        ) -> Optional[Dict[str, Any]]:
    """校验后追加。不合规 ⇒ **不写半条**，返回 None。"""
    why = validate(entry)
    if why:
        return None
    row = dict(entry)
    row.setdefault("ts", time.time())
    p = path or default_path()
    try:
        parent = os.path.dirname(p)
        if parent and not os.path.isdir(parent):
            os.makedirs(parent, exist_ok=True)
        with io.open(p, "a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError:
        return None
    return row


def load(path: Optional[str] = None) -> List[Dict[str, Any]]:
    """读全库。半截行跳过（生产 jsonl 常态）。"""
    p = path or default_path()
    out: List[Dict[str, Any]] = []
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
                if isinstance(r, dict):
                    out.append(r)
    except OSError:
        return []
    return out


def family(cue: str) -> str:
    """cue 的族名：`E_VALUE:wrong_magnitude:average` → `E_VALUE:wrong_magnitude`。"""
    s = str(cue or "")
    i = s.rfind(":")
    return s[:i] if i > 0 else s


def select_family(rows: List[Dict[str, Any]], cue: str) -> List[Dict[str, Any]]:
    """取同族条目（同一种失败模式的不同函数）。"""
    fam = family(cue)
    return [r for r in (rows or []) if family(str(r.get("cue") or "")) == fam]


def before(rows: List[Dict[str, Any]], ts: float) -> List[Dict[str, Any]]:
    """★ 防未来泄漏：只留 ts ≤ 给定时刻的条目。"""
    out: List[Dict[str, Any]] = []
    for r in (rows or []):
        try:
            t = float(r.get("ts") or 0.0)
        except (TypeError, ValueError):
            continue
        if t <= ts:
            out.append(r)
    return out


def from_rule(cue: str, rule: Dict[str, Any],
              trial: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """把一条已落地的规则翻译成库条目。缺 lesson 或证据 ⇒ None。"""
    rule = rule if isinstance(rule, dict) else {}
    lesson = str(rule.get("rationale") or "").strip()
    if not lesson:
        return None
    trial = trial if isinstance(trial, dict) else {}
    ev = {
        "in_score": trial.get("in_score"),
        "held_out": trial.get("held_out"),
        "baseline_in": trial.get("baseline_in"),
        "proposal_id": (rule.get("provenance") or {}).get("proposal_id"),
    }
    # ★ 空串/None 都不算证据（"proposal_id": "" 不是依据）
    ev = {k: v for k, v in ev.items() if v not in (None, "", [], {})}
    if not ev:
        return None
    return {"cue": str(cue or "").strip(), "lesson": lesson, "evidence": ev}


def has_cue(cue: str, path: Optional[str] = None) -> bool:
    """该 cue 是否已在库里（防双胞胎）。"""
    c = str(cue or "").strip()
    return any(str(r.get("cue") or "").strip() == c for r in load(path))
