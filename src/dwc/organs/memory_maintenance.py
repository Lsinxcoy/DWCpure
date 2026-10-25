"""memory_maintenance · 可解释维护建议（M3.1）。

定位声明 · **DWC-MEM**（记忆底座）
  ★ 只出建议，不自动删除；`DELETE` 必须显式请求且满足全部条件。
  ★ 未召回 ≠ 该删：可能是检索策略问题（DWC 既有 maintain 的同款判据）。

策略
----
KEEP    保留（SELF / 未召回 / 稀有 / effect 样本不足 / 有正效果）
ARCHIVE 归档候选（召回过、零效果、effect 样本足够）
MERGE   合并候选（同内容多份；只建议，不自动改写）
DELETE  只有 explicit=True 且 access=0、effect=0、非稀有、非 SELF 才允许建议
"""
from __future__ import annotations

from typing import Any


def decide(*, node_id: str, zone: str, access_count: int, effect_count: int,
           rare: bool = False, duplicate_count: int = 1,
           effect_samples: int = 0, explicit_delete: bool = False) -> dict[str, Any]:
    """返回 `{node_id, strategy, reason, delete_allowed}`。"""
    nid = str(node_id)
    if str(zone) == "self":
        return {"node_id": nid, "strategy": "KEEP", "reason": "SELF 保护区",
                "delete_allowed": False}
    if access_count == 0:
        return {"node_id": nid, "strategy": "KEEP",
                "reason": "从未召回：先修检索，不按年龄处置",
                "delete_allowed": False}
    if rare:
        return {"node_id": nid, "strategy": "KEEP", "reason": "稀有保护",
                "delete_allowed": False}
    if effect_samples < 10:
        return {"node_id": nid, "strategy": "KEEP",
                "reason": "effect 样本 %d < 10，判据不可信" % effect_samples,
                "delete_allowed": False}
    if effect_count > 0:
        return {"node_id": nid, "strategy": "KEEP", "reason": "有正效果",
                "delete_allowed": False}
    if duplicate_count > 1:
        return {"node_id": nid, "strategy": "MERGE",
                "reason": "同内容 %d 份，建议合并（不自动改写）" % duplicate_count,
                "delete_allowed": False}
    if explicit_delete:
        return {"node_id": nid, "strategy": "DELETE",
                "reason": "显式删除 + 无 access/effect + 非稀有 + 非 SELF",
                "delete_allowed": True}
    return {"node_id": nid, "strategy": "ARCHIVE",
            "reason": "召回过、零效果、effect 样本足够；归档不删除",
            "delete_allowed": False}


def plan(memory: Any) -> dict[str, Any]:
    """对 eviction_candidates 出建议；不写任何节点。"""
    rows = memory.eviction_candidates()
    n_eff = memory._conn.execute(
        "SELECT COUNT(*) AS n FROM memory_node WHERE effect_count > 0"
    ).fetchone()["n"]
    items = []
    for r in rows:
        memory.get(r["node_id"])
        items.append(decide(
            node_id=r["node_id"], zone=r["zone"],
            access_count=int(r["access_count"] or 0),
            effect_count=int(r["effect_count"] or 0),
            rare=bool(r["rare_protected"]),
            duplicate_count=1, effect_samples=int(n_eff or 0)))
    counts: dict[str, int] = {}
    for item in items:
        counts[item["strategy"]] = counts.get(item["strategy"], 0) + 1
    return {"n_evaluated": len(items), "counts": counts, "items": items}
