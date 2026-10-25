"""memory_context · 按 token 预算组装记忆上下文（M2.4）。

定位声明 · **DWC-MEM**（记忆底座）
  ★ 只组装已存在的节点；不生成新事实、不调用 LLM。
  ★ token 是字符近似（中文/英文混合），不是模型 tokenizer；调用方需知道。
  ★ 摘要被裁时保留 `raw_refs`（节点 ID），不丢证据入口。
"""
from __future__ import annotations

from typing import Any

from dwc.organs.memory import MemoryKind, Zone


def estimate_tokens(text: str) -> int:
    """保守近似：3 字符 ≈ 1 token；只用于预算，不冒充 tokenizer。"""
    return max(1, (len(str(text or "")) + 2) // 3)


def _line(node: Any) -> str:
    p = node.payload if isinstance(node.payload, dict) else {}
    if node.kind is MemoryKind.SKILL:
        return "skill: %s -> %s" % (p.get("scene", ""), p.get("method", ""))
    if node.kind is MemoryKind.TRACE:
        return "trace: %s / %s" % (p.get("task", ""), p.get("action", ""))
    if node.kind in (MemoryKind.IDENTITY, MemoryKind.STANDING_RULE):
        return "self: %s" % (p.get("text") or p.get("rule") or "")
    if node.kind is MemoryKind.PREFERENCE:
        return "pref: %s = %s (support=%s contradict=%s)" % (
            p.get("topic", ""), p.get("stance", ""),
            p.get("support_count", 0), p.get("contradict_count", 0))
    if node.kind is MemoryKind.BELIEF:
        return "belief: %s = %s (confidence=%s)" % (
            p.get("topic", ""), p.get("stance", ""), p.get("confidence", ""))
    return "%s: %s" % (node.kind.value, str(p)[:200])


def assemble(memory: Any, task: str, budget_tokens: int = 800, *,
             include_self: bool = True, include_skills: bool = True,
             include_episodes: bool = True) -> dict[str, Any]:
    """返回 `{text, used_ids, tokens, truncated, raw_refs, budget_tokens}`。"""
    budget = max(1, int(budget_tokens))
    head = "task: %s" % str(task or "")[:500]
    lines = [head]
    used: list[str] = []
    raw_refs: list[str] = []
    seen: set[str] = set()
    truncated = False

    def add(node: Any) -> bool:
        nonlocal truncated
        if node.node_id in seen:
            return True
        line = _line(node)[:600]
        candidate = "\n".join(lines + [line])
        if estimate_tokens(candidate) > budget:
            truncated = True
            return False
        lines.append(line)
        used.append(node.node_id)
        raw_refs.append(node.node_id)
        seen.add(node.node_id)
        return True

    if include_self:
        for node in memory.by_zone(Zone.SELF):
            if not add(node):
                break

    candidates = []
    if include_skills or include_episodes:
        try:
            candidates = memory.recall_search(task, k=12)
        except Exception:            # noqa: BLE001 — 组装失败不掀任务
            candidates = []
    if include_skills:
        for node in candidates:
            if node.kind is MemoryKind.SKILL and not add(node):
                break
    if include_episodes:
        for node in candidates:
            if node.kind is MemoryKind.TRACE and not add(node):
                break

    text = "\n".join(lines)
    return {
        "text": text,
        "used_ids": used,
        "tokens": estimate_tokens(text),
        "truncated": truncated,
        "raw_refs": raw_refs,
        "budget_tokens": budget,
    }
