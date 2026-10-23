"""arch_queue · 架构类提案的人工审批队列（R438 · #7）。

定位声明 · **DWC-AUTO**（自我强化 · 判据 G1 定位门）

★★★ 存在理由
  `architecture` 在 K_META 里是 `editable=True`，但按设计**必须人工批准**
  （系统层改动会影响判据本身）。改前没有任何队列：
  提案要么被当成普通规则自动落，要么无声消失。

★★★ 形态
  事件流（append-only，可审计）: var/architecture_queue.jsonl
    {"event":"enqueue","id":"A_xxx","ts":...,"component":...,"target":...,
     "patch":...,"rationale":...}
    {"event":"approve","id":"A_xxx","ts":...,"by":"user","note":...}
    {"event":"reject","id":"A_xxx","ts":...,"by":"user","why":...}
  状态 = 该 id 的**最后一条**事件（append-only ⇒ 不改写历史）。

★ 纪律
  · 只有 `approve` 才算"可执行"；pending 永远不自动落。
  · 重复 approve/reject 幂等（返回 already_*，不追加垃圾事件）。
  · 任何写盘失败都抛（不许静默丢提案）。
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from typing import Any

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
QUEUE = os.path.join(ROOT, "var", "architecture_queue.jsonl")


def _path(p: str = "") -> str:
    return p or QUEUE


def _read(p: str) -> list[dict[str, Any]]:
    if not os.path.isfile(p):
        return []
    out = []
    with open(p, encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if not ln:
                continue
            try:
                out.append(json.loads(ln))
            except ValueError:
                continue          # 坏行跳过（事件流容错），但不改文件
    return out


def _append(row: dict[str, Any], p: str) -> None:
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def enqueue(component: str, target: str, patch: str, rationale: str = "",
            p: str = "") -> dict[str, Any]:
    """入队一条架构提案；同 (component,target,patch) 去重。"""
    path = _path(p)
    pid = "A_" + hashlib.sha256(
        ("%s|%s|%s" % (component, target, patch)).encode("utf-8")
    ).hexdigest()[:10]
    for r in _read(path):
        if r.get("id") == pid and r.get("event") == "enqueue":
            return {"outcome": "already_queued", "id": pid}
    row = {"event": "enqueue", "id": pid, "ts": time.time(),
           "component": component, "target": target,
           "patch": patch, "rationale": rationale, "status": "pending"}
    _append(row, path)
    return {"outcome": "queued", "id": pid, "path": path}


def _status(path: str) -> dict[str, dict[str, Any]]:
    st: dict[str, dict[str, Any]] = {}
    for r in _read(path):
        pid = r.get("id")
        if not pid:
            continue
        if r.get("event") == "enqueue":
            st.setdefault(pid, dict(r, status="pending"))
        elif r.get("event") in ("approve", "reject"):
            if pid in st:
                st[pid]["status"] = ("approved" if r["event"] == "approve"
                                     else "rejected")
                st[pid]["decided_by"] = r.get("by", "")
                st[pid]["decided_ts"] = r.get("ts")
    return st


def list_items(status: str | None = None, p: str = "") -> list[dict]:
    rows = list(_status(_path(p)).values())
    if status:
        rows = [r for r in rows if r.get("status") == status]
    rows.sort(key=lambda r: r.get("ts", 0))
    return rows


def decide(pid: str, approve: bool, by: str = "user",
           note: str = "", p: str = "") -> dict[str, Any]:
    """批准/驳回；幂等（已决 ⇒ already_decided，不追加事件）。"""
    path = _path(p)
    st = _status(path).get(pid)
    if st is None:
        return {"outcome": "not_found", "id": pid}
    if st.get("status") != "pending":
        return {"outcome": "already_decided", "id": pid,
                "status": st.get("status")}
    _append({"event": "approve" if approve else "reject", "id": pid,
             "ts": time.time(), "by": by, "note": note, "status": "ok"},
            path)
    return {"outcome": "approved" if approve else "rejected", "id": pid}
