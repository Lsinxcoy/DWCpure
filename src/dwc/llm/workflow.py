# -*- coding: utf-8 -*-
"""Workflow · 可恢复的步骤编排（P2）。

★★★ 定位（G1 定位门）: **DWC-AUTO** —— 任务执行编排层，不是记忆底座。
★★★ TRUTH_SOURCE（G2）: 步骤成功与否来自 runner 返回的 `status`；
   本模块只做缓存/恢复/状态落盘，不判定任务语义，不产评分。

规格（JSON）：
  {"name": "...", "steps": [
      {"id": "s1", "task": "...", "max_rounds": 6, "opts": {}},
      ...
  ]}

恢复：
  - 每个步骤 key = sha256(task + opts)；
  - 同一 run_id 下，key 未变且 status=done ⇒ 直接复用；
  - 改了 task/opts ⇒ key 变 ⇒ 只重跑该步骤；
  - 每步完成后原子写 state.json，失败保留错误。
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from typing import Any, Callable

from dwc.foundation.atomic_io import write_text_atomic
from dwc.foundation.paths import find_root


def _base_dir() -> str:
    var = os.environ.get("DWC_VAR_DIR", "").strip()
    return var or os.path.join(find_root(), "var")


def _safe(s: str, limit: int = 80) -> str:
    keep = "".join(c for c in str(s or "") if c.isalnum() or c in "._-")
    return (keep or "run")[:limit]


def _key(task: str, opts: dict[str, Any]) -> str:
    raw = json.dumps({"task": str(task), "opts": opts or {}},
                     ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def _summary(result: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(result, dict):
        return {"status": "error", "why": "runner 返回非 dict"}
    return {
        "status": result.get("status"),
        "answer": str(result.get("answer") or "")[:500],
        "rounds": result.get("rounds"),
        "terminal_reason": result.get("terminal_reason"),
        "why": str(result.get("why") or "")[:300],
    }


def load_state(run_id: str, base_dir: str | None = None) -> dict[str, Any]:
    p = os.path.join(base_dir or _base_dir(), "workflows",
                     _safe(run_id), "state.json")
    try:
        with open(p, encoding="utf-8") as fh:
            raw = json.load(fh)
        return raw if isinstance(raw, dict) else {}
    except (OSError, ValueError):
        return {}


def run_workflow(spec: dict[str, Any], *,
                 runner: Callable[[str, dict[str, Any]], dict[str, Any]],
                 run_id: str | None = None,
                 resume: bool = False,
                 base_dir: str | None = None) -> dict[str, Any]:
    steps = spec.get("steps") if isinstance(spec, dict) else None
    if not isinstance(steps, list) or not steps:
        raise ValueError("workflow 需要非空 steps 列表")
    rid = _safe(run_id or ("W_" + time.strftime("%m%d_%H%M%S")))
    state = load_state(rid, base_dir) if resume else {}
    if not state:
        state = {"run_id": rid, "name": str(spec.get("name") or ""),
                 "created_at": time.time(), "steps": {}}
    state.setdefault("steps", {})
    out_steps = []
    n_run = n_cached = 0
    status = "done"
    for i, raw in enumerate(steps):
        if not isinstance(raw, dict):
            raise ValueError("workflow step 必须是 dict")
        sid = str(raw.get("id") or ("s%d" % (i + 1)))
        task = str(raw.get("task") or "")
        opts = raw.get("opts") if isinstance(raw.get("opts"), dict) else {}
        if raw.get("max_rounds") is not None:
            opts = dict(opts)
            opts.setdefault("max_rounds", raw.get("max_rounds"))
        if not task.strip():
            raise ValueError("workflow step %s 缺 task" % sid)
        key = _key(task, opts)
        prev = state["steps"].get(sid) or {}
        if (resume and prev.get("key") == key
                and prev.get("status") == "done"):
            out_steps.append({"id": sid, "cached": True,
                              "status": "done",
                              "result": prev.get("result") or {}})
            n_cached += 1
            continue
        try:
            res = runner(task, opts)
            summ = _summary(res)
            st = "done" if summ.get("status") == "done" else "incomplete"
        except Exception as exc:            # noqa: BLE001 — 失败必须可见
            summ = {"status": "error", "why": "%s: %s"
                    % (type(exc).__name__, exc)}
            st = "failed"
        state["steps"][sid] = {"key": key, "status": st, "result": summ,
                               "task": task[:500], "opts": opts,
                               "updated_at": time.time()}
        state["updated_at"] = time.time()
        _save(rid, state, base_dir)
        out_steps.append({"id": sid, "cached": False, "status": st,
                          "result": summ})
        n_run += 1
        if st == "failed":
            status = "failed"
            break
        if st == "incomplete":
            status = "incomplete"
    state["status"] = status
    _save(rid, state, base_dir)
    return {"run_id": rid, "status": status, "steps": out_steps,
            "n_run": n_run, "n_cached": n_cached,
            "path": os.path.join(base_dir or _base_dir(), "workflows",
                                 rid, "state.json")}


def _save(run_id: str, state: dict[str, Any],
          base_dir: str | None = None) -> None:
    d = os.path.join(base_dir or _base_dir(), "workflows", _safe(run_id))
    os.makedirs(d, exist_ok=True)
    write_text_atomic(os.path.join(d, "state.json"),
                      json.dumps(state, ensure_ascii=False, indent=1))
