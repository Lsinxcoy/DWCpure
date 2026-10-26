"""H6 · Knowledge page：把记忆投影成可重建的 markdown，供 agent 主动拉取。

定位声明 · **DWC-MEM**（记忆底座）

定位：**只读投影**，不是 source of truth。
  · 输入：REFERENCE（事实）、BELIEF（观察）、active SKILL（过程）
  · 输出：`var/knowledge/<slug>.md`，带 sources/frontmatter
  · 消费：`knowledge_search()` / `read`，不进入 `memory_text` 的每轮推送

边界：
  · 不写记忆节点（除 record_retrieval 的 access 记账）
  · 不删除页面；重建覆盖同名页面
  · 没有 sources 的句子不生成；事实必须有来源
"""
from __future__ import annotations

import json
import os
import re
import time
from typing import Any

from dwc.foundation.paths import find_root

ROOT = find_root()
DEFAULT_OUT = os.path.join(
    os.environ.get("DWC_VAR_DIR") or os.path.join(ROOT, "var"), "knowledge")

_SLUG_BAD = re.compile(r"[^0-9A-Za-z\u4e00-\u9fff._-]+")


def _slug(text: str, fallback: str = "page") -> str:
    s = _SLUG_BAD.sub("-", str(text or "").strip()).strip("-._")
    return (s[:80] or fallback)


def _topic_of(node: Any) -> str:
    p = node.payload or {}
    for key in ("topic", "scene", "claim", "text", "task"):
        v = str(p.get(key) or "").strip()
        if v:
            return v[:120]
    return node.kind.value


def _source_ref(node: Any) -> dict[str, Any]:
    return {
        "node_id": node.node_id,
        "kind": node.kind.value,
        "derived_kind": node.derived_kind,
        "observed_at": node.observed_at,
        "valid_to": node.valid_to,
        "source_ids": list(node.source_ids),
    }


def _yaml_list(items: list[dict[str, Any]]) -> str:
    # 只输出本模块自己生成的结构；不引入 PyYAML 依赖
    lines = []
    for it in items:
        lines.append("  - node_id: %s" % json.dumps(it["node_id"], ensure_ascii=False))
        for key in ("kind", "derived_kind", "observed_at", "valid_to"):
            if it.get(key) is not None:
                lines.append("    %s: %s" % (key, json.dumps(it[key], ensure_ascii=False)))
        if it.get("source_ids"):
            lines.append("    source_ids: %s" % json.dumps(it["source_ids"], ensure_ascii=False))
    return "\n".join(lines)


def _eligible(memory: Any) -> list[Any]:
    rows = memory._conn.execute(
        "SELECT node_id FROM memory_node"
        " WHERE archived_at IS NULL"
        " AND kind IN ('reference','belief','skill')"
        " ORDER BY created_at").fetchall()
    out = []
    now = time.time()
    for r in rows:
        n = memory.get(r["node_id"])
        if n.status in ("invalid", "superseded"):
            continue
        if n.valid_to is not None and float(n.valid_to) <= now:
            continue
        if n.kind.value == "skill":
            if n.status != "active":
                continue
            p = n.payload or {}
            sk = str(p.get("skill_kind") or "")
            if not sk:
                from dwc.organs.skill_writer import classify_skill_kind
                sk = classify_skill_kind(p.get("scene") or "",
                                         p.get("method") or "")
            if sk != "procedural":
                continue
        out.append(n)
    return out


def build(memory: Any, out_dir: str | None = None,
          scope: str | None = None) -> dict[str, Any]:
    """从记忆投影页面；返回 `{n_pages, pages, out_dir}`。"""
    out = out_dir or DEFAULT_OUT
    os.makedirs(out, exist_ok=True)
    groups: dict[str, list[Any]] = {}
    for n in _eligible(memory):
        topic = _topic_of(n)
        if scope and scope not in topic and scope not in json.dumps(
                n.payload, ensure_ascii=False):
            continue
        groups.setdefault(topic, []).append(n)
    pages = []
    for topic, nodes in groups.items():
        slug = _slug(topic)
        path = os.path.join(out, slug + ".md")
        refs = [_source_ref(n) for n in nodes]
        lines = [
            "---",
            "page_id: %s" % json.dumps(slug, ensure_ascii=False),
            "title: %s" % json.dumps(topic, ensure_ascii=False),
            "scope: %s" % json.dumps(scope or "all", ensure_ascii=False),
            "refreshed_at: %s" % json.dumps(time.time()),
            "stale: false",
            "sources:",
            _yaml_list(refs),
            "---",
            "",
            "# %s" % topic,
            "",
        ]
        facts = [n for n in nodes if n.kind.value == "reference"]
        beliefs = [n for n in nodes if n.kind.value == "belief"]
        skills = [n for n in nodes if n.kind.value == "skill"]
        if facts:
            lines.append("## 事实")
            for n in facts:
                claim = str(n.payload.get("claim") or n.payload.get("text") or "").strip()
                if claim:
                    lines.append("- %s" % claim)
            lines.append("")
        if beliefs:
            lines.append("## 观察")
            for n in beliefs:
                stance = str(n.payload.get("stance") or n.payload.get("text") or "").strip()
                if stance:
                    lines.append("- %s" % stance)
            lines.append("")
        if skills:
            lines.append("## 过程")
            for n in skills:
                p = n.payload
                scene = str(p.get("scene") or "").strip()
                method = str(p.get("method") or "").strip()
                if scene or method:
                    lines.append("- **%s**：%s" % (scene or "过程", method))
                steps = p.get("steps") or []
                if isinstance(steps, list) and steps:
                    lines.append("  - 步骤：%s" % " → ".join(
                        str(s.get("op") or s) for s in steps if s))
                invalid = str(p.get("invalid_conditions") or "").strip()
                if invalid:
                    lines.append("  - 失效条件：%s" % invalid)
            lines.append("")
        lines.append("## 来源")
        for n in nodes:
            lines.append("- `%s` (%s, %s)" % (
                n.node_id, n.kind.value, n.derived_kind))
        lines.append("")
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("\n".join(lines))
        pages.append({"page_id": slug, "title": topic, "path": path,
                      "n_sources": len(nodes)})
    return {"n_pages": len(pages), "pages": pages, "out_dir": out}


def _read_frontmatter(path: str) -> tuple[dict[str, Any], str]:
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        return {}, ""
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end < 0:
        return {}, text
    head = text[3:end]
    body = text[end + 4:]
    meta: dict[str, Any] = {}
    for line in head.splitlines():
        if ":" in line and not line.startswith((" ", "-")):
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip().strip('"')
    return meta, body


def check(memory: Any, out_dir: str | None = None) -> dict[str, Any]:
    """检查页面来源是否仍有效；返回 `{n_pages, stale, ok}`（不重写页面）。"""
    out = out_dir or DEFAULT_OUT
    if not os.path.isdir(out):
        return {"n_pages": 0, "stale": [], "ok": True, "out_dir": out}
    stale = []
    pages = [os.path.join(out, f) for f in sorted(os.listdir(out))
             if f.endswith(".md")]
    for path in pages:
        meta, _ = _read_frontmatter(path)
        page_id = meta.get("page_id") or os.path.basename(path)
        reasons = []
        # 逐行解析 sources 的 node_id（本模块自己的格式）
        try:
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
        except OSError:
            continue
        ids = re.findall(r"^\s+- node_id:\s*\"?([^\"\n]+)\"?", text, re.M)
        for nid in ids:
            try:
                n = memory.get(nid)
            except Exception:                 # noqa: BLE001
                reasons.append("missing:%s" % nid)
                continue
            if n.archived_at is not None:
                reasons.append("archived:%s" % nid)
            elif n.valid_to is not None and float(n.valid_to) <= time.time():
                reasons.append("expired:%s" % nid)
            elif n.status in ("invalid", "superseded"):
                reasons.append("status:%s" % nid)
        if reasons:
            stale.append({"page_id": page_id, "path": path,
                          "reasons": reasons})
    return {"n_pages": len(pages), "stale": stale,
            "ok": not stale, "out_dir": out}


def list_pages(out_dir: str | None = None) -> list[dict[str, Any]]:
    out = out_dir or DEFAULT_OUT
    if not os.path.isdir(out):
        return []
    items = []
    for f in sorted(os.listdir(out)):
        if not f.endswith(".md"):
            continue
        path = os.path.join(out, f)
        meta, _ = _read_frontmatter(path)
        items.append({"page_id": meta.get("page_id") or f[:-3],
                      "title": meta.get("title") or f[:-3],
                      "path": path,
                      "stale": str(meta.get("stale", "false")).lower() == "true"})
    return items


def search(memory: Any, query: str, out_dir: str | None = None,
           k: int = 5) -> dict[str, Any]:
    """页面级检索；命中后记 route=knowledge_page（不碰 skill_prompt）。"""
    q = str(query or "").strip()
    if not q:
        return {"ok": False, "error": "query 为空", "results": []}
    out = out_dir or DEFAULT_OUT
    terms = [t for t in re.split(r"\s+", q) if t]
    results = []
    for item in list_pages(out):
        try:
            with open(item["path"], encoding="utf-8") as fh:
                raw = fh.read()
        except OSError:
            continue
        # 跳过 YAML frontmatter，避免摘要变成转义的 page_id
        _meta, text = _read_frontmatter(item["path"])
        if not text:
            text = raw
        hit = sum(1 for t in terms if t in text)
        if hit <= 0:
            continue
        snippet = ""
        for line in text.splitlines():
            if any(t in line for t in terms):
                snippet = line.strip()[:300]
                break
        results.append({"page_id": item["page_id"], "title": item["title"],
                        "path": item["path"], "score": hit,
                        "snippet": snippet})
    results.sort(key=lambda x: (-x["score"], x["page_id"]))
    results = results[:max(1, int(k))]
    ids = []
    for r in results:
        meta, _ = _read_frontmatter(r["path"])
        try:
            with open(r["path"], encoding="utf-8") as fh:
                text = fh.read()
            ids.extend(re.findall(
                r"^\s+- node_id:\s*\"?([^\"\n]+)\"?", text, re.M))
        except OSError as exc:
            import sys as _sys
            _sys.stderr.write("knowledge_search 读页面失败 %s: %s\n"
                              % (r.get("path"), exc))
    try:
        memory.record_retrieval(q, "knowledge_page", ids[:50],
                                source="knowledge_search", touch=True)
    except Exception as exc:                  # noqa: BLE001 — 记账坏不掀检索
        import sys as _sys
        _sys.stderr.write("knowledge_search 记账失败: %r\n" % (exc,))
    return {"ok": True, "query": q, "n": len(results), "results": results}
