"""H5 · 离线 consolidation：把近重复的 fact/procedure/observation 合成一张卡。

定位声明 · **DWC-MEM**（记忆底座）

原则（借鉴 Hindsight，但不照抄 prompt）：
  · 一个节点一个 facet；只在同 kind + 同 topic 内聚类
  · 近重复用 token Jaccard（确定性，无 LLM）
  · 至少 2 条独立证据才合并；不足 ⇒ skip（fail-closed）
  · 原节点保留：只写 valid_to/status，新增节点用 supersedes 指回
  · dry-run 只出计划；apply 才写
"""
from __future__ import annotations

import json
import re
import time
from typing import Any

from dwc.organs.memory import MemoryKind

_THRESHOLD = 0.85
_KINDS = ("reference", "belief", "skill")


def _norm(text: Any) -> str:
    s = str(text or "").strip().lower()
    return re.sub(r"\s+", " ", s)


def _topic(node: Any) -> str:
    p = node.payload or {}
    for key in ("topic", "scene", "claim", "text", "task"):
        v = str(p.get(key) or "").strip()
        if v:
            return _norm(v)[:200]
    return node.kind.value


def _tokens(node: Any) -> set[str]:
    text = _norm(json.dumps(node.payload or {}, ensure_ascii=False,
                            sort_keys=True))
    if len(text) <= 1:
        return {text} if text else set()
    return {text[i:i + 2] for i in range(len(text) - 1)}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / float(len(a | b))


def _eligible(memory: Any) -> list[Any]:
    rows = memory._conn.execute(
        "SELECT node_id FROM memory_node WHERE archived_at IS NULL"
        " AND kind IN ('reference','belief','skill')"
        " ORDER BY created_at").fetchall()
    out = []
    now = time.time()
    for r in rows:
        n = memory.get(r["node_id"])
        if n.status != "active":
            continue
        if n.valid_to is not None and float(n.valid_to) <= now:
            continue
        out.append(n)
    return out


def plan(memory: Any, scope: str | None = None,
         threshold: float = _THRESHOLD) -> dict[str, Any]:
    """返回合并计划；不写任何节点。"""
    nodes = _eligible(memory)
    if scope:
        nodes = [n for n in nodes if scope in json.dumps(
            n.payload, ensure_ascii=False)]
    groups: dict[tuple[str, str], list[Any]] = {}
    for n in nodes:
        groups.setdefault((n.kind.value, _topic(n)), []).append(n)
    actions = []
    for (kind, topic), items in groups.items():
        if len(items) < 2:
            continue
        # greedy 近重复聚类
        clusters: list[list[Any]] = []
        for n in items:
            tok = _tokens(n)
            placed = False
            for c in clusters:
                if any(_jaccard(tok, _tokens(x)) >= threshold for x in c):
                    c.append(n)
                    placed = True
                    break
            if not placed:
                clusters.append([n])
        for c in clusters:
            if len(c) < 2:
                continue
            sources: list[str] = []
            seen: set[str] = set()
            for n in c:
                for sid in (n.source_ids or (n.node_id,)):
                    s = str(sid)
                    if s and s not in seen:
                        seen.add(s)
                        sources.append(s)
            canonical = max(c, key=lambda n: (n.proof_count, n.created_at))
            actions.append({
                "kind": kind,
                "topic": topic,
                "node_ids": [n.node_id for n in c],
                "canonical": canonical.node_id,
                "source_ids": sources,
                "proof_count": len(sources),
                "action": ("merge" if len(sources) >= 2 else "skip"),
                "why": ("near_duplicate" if len(sources) >= 2
                        else "insufficient_evidence"),
            })
    return {
        "threshold": float(threshold),
        "n_candidates": len(nodes),
        "n_actions": len(actions),
        "actions": actions,
    }


def _payload_for(kind: str, canonical: Any, sources: list[str],
                 old_ids: list[str]) -> dict[str, Any]:
    p = dict(canonical.payload or {})
    p["source_ids"] = list(sources)
    p["proof_count"] = len(sources)
    p["derived_kind"] = canonical.derived_kind
    p["status"] = "active"
    p["consolidated_from"] = list(old_ids)
    if kind == "reference":
        p["claim"] = str(p.get("claim") or p.get("text") or "").strip()
        p["topic"] = str(p.get("topic") or "").strip()
    elif kind == "skill":
        p["skill_kind"] = "procedural"
    elif kind == "belief":
        # BELIEF 的 D6 字段保持原样；只补来源
        p.setdefault("topic", str(p.get("topic") or ""))
        p.setdefault("stance", str(p.get("stance") or p.get("text") or ""))
        p.setdefault("confidence", p.get("confidence", 0.5))
        p.setdefault("evidence_refs", list(sources))
    return p


def apply(memory: Any, scope: str | None = None,
          threshold: float = _THRESHOLD) -> dict[str, Any]:
    """执行 plan：新建合并节点，旧节点写 valid_to；不删除。"""
    rep = plan(memory, scope=scope, threshold=threshold)
    written = []
    skipped = []
    for a in rep["actions"]:
        if a["action"] != "merge":
            skipped.append(a)
            continue
        kind = MemoryKind(a["kind"])
        canonical = memory.get(a["canonical"])
        payload = _payload_for(a["kind"], canonical, a["source_ids"],
                               a["node_ids"])
        new_id = memory.remember(
            kind, payload, source_ids=a["source_ids"],
            proof_count=a["proof_count"], supersedes=a["node_ids"],
            dedupe=False)
        for old in a["node_ids"]:
            if old == new_id:
                continue
            try:
                memory.supersede(old, new_id)
            except Exception as exc:          # noqa: BLE001 — 单个失败留痕
                import sys as _sys
                _sys.stderr.write("consolidate supersede 失败 %s: %r\n"
                                  % (old, exc))
        written.append({"new_id": new_id, "from": a["node_ids"],
                        "proof_count": a["proof_count"]})
    return {"plan": rep, "written": written, "skipped": skipped}
