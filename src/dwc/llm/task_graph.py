# -*- coding: utf-8 -*-
"""TaskGraph · 持久任务图（P1）。

★★★ 定位（G1 定位门）: **DWC-AUTO** —— 任务执行层的计划对象，不是记忆底座。
★★★ TRUTH_SOURCE（G2）: 节点状态来自模型显式 `task_update` 调用；
   本模块只校验状态枚举与依赖引用，不判定任务是否真的完成；
   完成真值仍由 TaskContract / verifier / 工具回执给出。

存储：`var/task_graphs/<task_id>.json`，原子写；一个任务一个文件。
节点：id / subject / description / activeForm / status / owner /
      blocks / blockedBy / metadata。
状态：pending / in_progress / completed / deleted。
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from typing import Any

from dwc.foundation.atomic_io import write_text_atomic
from dwc.foundation.paths import find_root

_STATUS = ("pending", "in_progress", "completed", "deleted")
_LOAD_FAIL = 0


def _base_dir() -> str:
    var = os.environ.get("DWC_VAR_DIR", "").strip()
    return var or os.path.join(find_root(), "var")


def _safe_id(task_id: str) -> str:
    s = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(task_id or "default"))
    return (s or "default")[:80]


def graph_path(task_id: str, base_dir: str | None = None) -> str:
    d = os.path.join(base_dir or _base_dir(), "task_graphs")
    return os.path.join(d, _safe_id(task_id) + ".json")


class TaskGraph:
    def __init__(self, task_id: str, base_dir: str | None = None):
        self.task_id = str(task_id or "default")
        self.path = graph_path(self.task_id, base_dir)
        self.data: dict[str, Any] = {"task_id": self.task_id, "nodes": []}
        self.load()

    def load(self) -> None:
        try:
            with open(self.path, encoding="utf-8") as fh:
                raw = json.load(fh)
            if isinstance(raw, dict) and isinstance(raw.get("nodes"), list):
                self.data = raw
        except (OSError, ValueError) as exc:
            global _LOAD_FAIL
            _LOAD_FAIL += 1
            if _LOAD_FAIL <= 3:
                sys.stderr.write("task_graph 读取失败×%d: %s\n"
                                 % (_LOAD_FAIL, exc))

    def save(self) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self.data["updated_at"] = time.time()
        write_text_atomic(self.path, json.dumps(
            self.data, ensure_ascii=False, indent=1))

    def _nodes(self) -> list[dict[str, Any]]:
        return [n for n in self.data.get("nodes", []) if isinstance(n, dict)]

    def _find(self, node_id: str) -> dict[str, Any] | None:
        for n in self._nodes():
            if str(n.get("id")) == str(node_id):
                return n
        return None

    def create(self, subject: str, *, description: str = "",
               active_form: str = "", owner: str = "") -> dict[str, Any]:
        subject = str(subject or "").strip()
        if not subject:
            raise ValueError("task_create 需要 subject")
        nodes = self._nodes()
        nid = "T%d" % (len(nodes) + 1)
        node = {
            "id": nid, "subject": subject[:300],
            "description": str(description or "")[:2000],
            "activeForm": str(active_form or subject)[:200],
            "status": "pending", "owner": str(owner or "")[:80],
            "blocks": [], "blockedBy": [], "metadata": {},
            "created_at": time.time(), "updated_at": time.time(),
        }
        nodes.append(node)
        self.data["nodes"] = nodes
        self.save()
        return node

    def update(self, node_id: str, *, status: str | None = None,
               owner: str | None = None,
               add_blocks: list[str] | None = None,
               add_blocked_by: list[str] | None = None,
               metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        node = self._find(node_id)
        if node is None:
            raise ValueError("task_update 未知 id: %s" % node_id)
        if status is not None:
            if status not in _STATUS:
                raise ValueError("task_update status 非法: %s" % status)
            node["status"] = status
        if owner is not None:
            node["owner"] = str(owner)[:80]
        for key, add in (("blocks", add_blocks),
                         ("blockedBy", add_blocked_by)):
            if add:
                cur = list(node.get(key) or [])
                for x in add:
                    x = str(x)
                    if x and x not in cur:
                        cur.append(x)
                node[key] = cur
        if isinstance(metadata, dict):
            node.setdefault("metadata", {}).update(metadata)
        node["updated_at"] = time.time()
        self.save()
        return node

    def list(self, *, include_deleted: bool = False) -> dict[str, Any]:
        nodes = self._nodes()
        if not include_deleted:
            nodes = [n for n in nodes if n.get("status") != "deleted"]
        return {"task_id": self.task_id, "nodes": nodes,
                "path": self.path}

    def summary(self, *, limit: int = 1200) -> str:
        nodes = self._nodes()
        if not nodes:
            return "任务图: (空)"
        lines = []
        for n in nodes:
            if n.get("status") == "deleted":
                continue
            bits = ["%s [%s] %s" % (n.get("id"), n.get("status"),
                                    n.get("subject"))]
            if n.get("owner"):
                bits.append("owner=%s" % n["owner"])
            if n.get("blockedBy"):
                bits.append("blockedBy=%s" % ",".join(n["blockedBy"]))
            if n.get("blocks"):
                bits.append("blocks=%s" % ",".join(n["blocks"]))
            lines.append(" · ".join(bits))
        out = "任务图:\n" + "\n".join(lines)
        return out[:limit]
