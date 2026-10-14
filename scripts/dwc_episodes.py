# -*- coding: utf-8 -*-
"""R270-⑥ · Episode 链（Nexus graph_memory＋HORMA 路径思想 DWC 版）。

同 kind 按时间成链（prev＝上一个同 kind 的 ep），"失败→加练→通过"
天然连成因果链。related(task_id, depth) BFS 前后各 depth 步。
"""
from __future__ import annotations

import io
import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "src"))

from dwc.foundation.paths import find_root  # noqa: E402
ROOT = find_root()
VAR = os.path.join(ROOT, "var")
EPISODES = os.path.join(VAR, "dwc_episodes.jsonl")


def _load(path: str = EPISODES) -> list:
    if not os.path.exists(path):
        return []
    out = []
    for ln in io.open(path, encoding="utf-8").read().splitlines():
        if ln.strip():
            try:
                out.append(json.loads(ln))
            except ValueError:
                pass
    return out


def append_episode(task_id: str, kind: str, ok: bool,
                   path: str = EPISODES) -> dict:
    """追加一集，prev 自动链上一个同 kind。失败不阻断调用方。"""
    rows = _load(path)
    prev = ""
    for row in reversed(rows):
        if row.get("kind") == kind:
            prev = row.get("ep", "")
            break
    ep = {"ep": "ep_%05d" % (len(rows) + 1), "task_id": task_id,
          "kind": kind, "ok": bool(ok), "prev": prev}
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with io.open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(ep, ensure_ascii=False) + "\n")
    except OSError:
        pass
    return ep


def related(task_id: str, depth: int = 2, path: str = EPISODES) -> list:
    """BFS：以前后链为边，前后各 depth 步（纯函数）。"""
    rows = _load(path)
    by_ep = {r["ep"]: r for r in rows if r.get("ep")}
    start = [r["ep"] for r in rows if r.get("task_id") == task_id]
    if not start:
        return []
    seen = set(start)
    frontier = set(start)
    for _ in range(depth):
        nxt = set()
        for ep in frontier:
            row = by_ep.get(ep, {})
            prev = row.get("prev", "")
            if prev and prev not in seen:
                seen.add(prev)
                nxt.add(prev)
            for cand, crow in by_ep.items():
                if crow.get("prev") == ep and cand not in seen:
                    seen.add(cand)
                    nxt.add(cand)
        frontier = nxt
    order = [r for r in rows if r.get("ep") in seen]
    return order
