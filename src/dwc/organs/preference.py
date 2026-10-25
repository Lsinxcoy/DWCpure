"""preference · 偏好/信念的版本化写入（M2.3）。

定位声明 · **DWC-MEM**（记忆底座）
  ★ 偏好/信念不覆盖旧节点：每次观察写新节点 + `supersedes` 边。
  ★ 只接受显式证据；模型自评不算证据。
  ★ 不调用 LLM、不做真假判断；矛盾计数是证据计数，不是“谁对”。

为什么需要
----------
Omega 的 FourNetworkMemory 把 world facts / experiences / summaries / beliefs
分开；DWC 之前只有事实/经验/技能，没有“用户偏好”和“可修订信念”。M2.3
只补最小结构：topic / stance / evidence_refs / support / contradict / confidence。
"""
from __future__ import annotations

import json
import time
from typing import Any

from dwc.organs.memory import MemoryError, MemoryKind


def _latest(memory: Any, kind: MemoryKind, topic: str) -> dict[str, Any] | None:
    rows = memory._conn.execute(
        "SELECT node_id, payload FROM memory_node"
        " WHERE kind=? AND archived_at IS NULL ORDER BY created_at DESC",
        (kind.value,)).fetchall()
    for row in rows:
        try:
            p = json.loads(row["payload"])
        except (TypeError, ValueError):
            continue
        if str(p.get("topic") or "") == str(topic):
            return {"node_id": row["node_id"], "payload": p}
    return None


def latest_preference(memory: Any, topic: str) -> dict[str, Any] | None:
    return _latest(memory, MemoryKind.PREFERENCE, topic)


def observe_preference(memory: Any, topic: str, stance: str,
                       evidence_ref: str, *,
                       source_channel: str = "user_message") -> dict[str, Any]:
    """写一条偏好观察；同立场 support+1，不同立场 contradict+1。"""
    topic = str(topic or "").strip()
    stance = str(stance or "").strip()
    ref = str(evidence_ref or "").strip()
    if not topic or not stance or not ref:
        raise MemoryError("偏好必须有 topic/stance/evidence_ref")
    old = latest_preference(memory, topic)
    support, contradict = 1, 0
    prev = ""
    if old:
        prev = old["node_id"]
        op = old["payload"]
        support = int(op.get("support_count") or 0)
        contradict = int(op.get("contradict_count") or 0)
        if str(op.get("stance") or "") == stance:
            support += 1
        else:
            contradict += 1
    payload = {
        "topic": topic,
        "stance": stance,
        "evidence_refs": [ref],
        "support_count": support,
        "contradict_count": contradict,
        "last_confirmed": time.time(),
    }
    if prev:
        payload["_prev"] = prev
    nid = memory.remember(MemoryKind.PREFERENCE, payload,
                          source_channel=source_channel)
    if prev:
        memory.link(nid, prev, "supersedes", evidence_ref=ref)
    return {"node_id": nid, "topic": topic, "stance": stance,
            "support_count": support, "contradict_count": contradict,
            "supersedes": prev or None}


def revise_belief(memory: Any, node_id: str, new_stance: str,
                  evidence_ref: str, *,
                  confidence: float | None = None) -> dict[str, Any]:
    """修订信念：旧节点保留，新节点 `_rev_prev`，并写 `revises` 边。"""
    old = memory.get(node_id)
    if old.kind is not MemoryKind.BELIEF:
        raise MemoryError("revise_belief 只接受 BELIEF 节点")
    ref = str(evidence_ref or "").strip()
    if not ref:
        raise MemoryError("信念修订必须有 evidence_ref")
    op = dict(old.payload)
    refs = list(op.get("evidence_refs") or [])
    if ref not in refs:
        refs.append(ref)
    payload = {
        "topic": op.get("topic") or "",
        "stance": str(new_stance or "").strip(),
        "confidence": (float(confidence) if confidence is not None
                       else float(op.get("confidence") or 0.5)),
        "evidence_refs": refs,
        "support_count": int(op.get("support_count") or 0),
        "contradict_count": int(op.get("contradict_count") or 0) + 1,
        "_rev_prev": node_id,
        "_rev_why": "belief_revision",
        "_rev_src": ref,
    }
    if not payload["stance"]:
        raise MemoryError("信念修订必须有 new_stance")
    new_id = memory.remember(MemoryKind.BELIEF, payload,
                             source_channel="user_message")
    old_p = dict(old.payload)
    old_p["_revised_to"] = new_id
    memory._conn.execute(
        "UPDATE memory_node SET payload=? WHERE node_id=?",
        (json.dumps(old_p, ensure_ascii=False), node_id))
    memory._conn.commit()
    memory.link(new_id, node_id, "revises", evidence_ref=ref)
    return {"node_id": new_id, "old_node_id": node_id,
            "stance": payload["stance"], "confidence": payload["confidence"],
            "contradict_count": payload["contradict_count"]}
