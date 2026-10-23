"""R270-④ · 程序模板库（v10 workflow_memory 两层设计 DWC 版）。
DWC-MEM(记忆底座)-程序性记忆：跨任务可复用的步骤模板。

通用模板（步骤＋条件分支＋证据源）→ 按当前上下文解条件 →
个性化步骤列。条件 `key=value` 对 context 逐条解；无条件步骤恒入；
未知条件保守计入＋标记 unknown。outcome 回写 use_count/success。
"""
from __future__ import annotations

import json
import os
import sys
import time

from dwc.foundation.paths import find_root

ROOT = find_root()
VAR = os.path.join(ROOT, "var")
WORKFLOWS = os.path.join(VAR, "dwc_workflows.jsonl")


def _load(path: str = WORKFLOWS) -> list:
    if not os.path.exists(path):
        return []
    out = []
    for ln in open(path, encoding="utf-8").read().splitlines():
        if ln.strip():
            try:
                out.append(json.loads(ln))
            except ValueError as exc:
                sys.stderr.write("workflow 坏行跳过 [%s] %s\n" % (path, exc))
    return out


def _save(path: str, rows: list) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.writelines(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)
    os.replace(tmp, path)


def store_template(name: str, kind: str, steps: list,
                   conditions: list | None = None,
                   path: str = WORKFLOWS) -> dict:
    """存通用模板。steps 为空抛 ValueError（空模板无意义）。"""
    if not steps:
        raise ValueError("steps 为空（模板至少一步）")
    rows = _load(path)
    tpl = {"template_id": "wftpl_%d" % (len(rows) + 1), "name": name,
           "kind": kind, "steps": steps, "conditions": conditions or [],
           "use_count": 0, "success": 0.5,
           "at": time.strftime("%Y-%m-%dT%H:%M:%S+08:00")}
    rows.append(tpl)
    _save(path, rows)
    return tpl


def _cond_met(cond: str, context: dict) -> bool | None:
    """条件 `key=value` 解值：True/False/None（未知）。"""
    if "=" not in cond:
        return None
    k, v = cond.split("=", 1)
    if k not in context:
        return None
    return str(context[k]) == v


def suggest_workflow(kind: str, context: dict,
                     path: str = WORKFLOWS) -> list | None:
    """按 kind 取最新模板解条件 → 步骤列（含 unknown 标记）；无模板 None。"""
    cands = [r for r in _load(path) if r.get("kind") == kind]
    if not cands:
        return None
    tpl = cands[-1]
    out = []
    for st in tpl.get("steps", []):
        cond = st.get("condition", "")
        if not cond:
            out.append({"desc": st.get("desc", ""),
                        "op": st.get("op", "")})
            continue
        met = _cond_met(cond, context or {})
        if met is True or met is None:
            out.append({"desc": st.get("desc", ""),
                        "op": st.get("op", ""),
                        "unknown_condition": cond if met is None else ""})
    return out or None


def record_workflow_outcome(template_id: str, ok: bool,
                            path: str = WORKFLOWS) -> bool:
    """回写：use_count+1，success 滑动平均。命中返回 True。"""
    rows = _load(path)
    hit = False
    for row in rows:
        if row.get("template_id") == template_id:
            n = int(row.get("use_count", 0) or 0) + 1
            row["use_count"] = n
            prev = float(row.get("success", 0.5) or 0.5)
            row["success"] = round(prev + (float(ok) - prev) / n, 4)
            hit = True
    if hit:
        _save(path, rows)
    return hit
