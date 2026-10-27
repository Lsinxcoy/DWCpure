# -*- coding: utf-8 -*-
"""SkillReview · 技能提议/审批（P2/P3）。

★★★ 定位（G1 定位门）: **DWC-AUTO** —— 任务经验到技能的候选层。
★★★ TRUTH_SOURCE（G2）: 只接受 `status=done` 且 actions_log 里有成功
   run/test/check/write 的真实轨迹；模型自述不算证据，不产评分。

流程：
  propose_from_result → var/skill_proposals/<id>.json（status=pending）
  approve(id, apply=False) → 预览；apply=True → skills/<name>/SKILL.md
  reject(id) → status=rejected

没有真实动作 ⇒ 返回 `no_verified_actions`，不生成空技能。
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from typing import Any

from dwc.foundation.atomic_io import write_text_atomic
from dwc.foundation.paths import find_root
from dwc.organs import skill_store as SS

_VERIFY_OPS = {"run", "test", "check", "verify"}
_WRITE_OPS = {"write", "apply_patch", "edit", "patch"}


def _base_dir() -> str:
    var = os.environ.get("DWC_VAR_DIR", "").strip()
    return var or os.path.join(find_root(), "var")


def _dir() -> str:
    return os.path.join(_base_dir(), "skill_proposals")


def _safe(s: str) -> str:
    import re
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", str(s or "")).strip("-")[:64] \
        or "skill"


def _proc(result: dict[str, Any]) -> list[str]:
    lines = []
    for e in result.get("actions_log") or []:
        if not isinstance(e, dict) or not e.get("ok"):
            continue
        op = str(e.get("op") or "")
        tgt = str(e.get("target") or "")[:120]
        if op in _WRITE_OPS:
            lines.append("write `%s`" % tgt if tgt else "write artifact")
        elif op in _VERIFY_OPS:
            lines.append("run/test `%s` and confirm success"
                         % (tgt or "command"))
    return lines


def propose_from_result(result: dict[str, Any], *, task: str,
                        trajectory_ref: str = "") -> dict[str, Any]:
    if not isinstance(result, dict) or result.get("status") != "done":
        return {"ok": False, "why": "not_done"}
    acts = [e for e in (result.get("actions_log") or [])
            if isinstance(e, dict) and e.get("ok")]
    if not any(e.get("op") in (_VERIFY_OPS | _WRITE_OPS) for e in acts):
        return {"ok": False, "why": "no_verified_actions"}
    proc = _proc(result)
    if not proc:
        return {"ok": False, "why": "no_procedure"}
    name = _safe(str(task).strip().splitlines()[0][:48] or "task-procedure")
    pid = hashlib.sha256(
        (name + json.dumps(proc, ensure_ascii=False)).encode("utf-8")
    ).hexdigest()[:12]
    body = "\n".join([
        "# %s" % task.strip()[:120],
        "",
        "## When to use",
        "When a task has the same shape as: %s" % task.strip()[:300],
        "",
        "## Procedure",
        *["%d. %s" % (i + 1, x) for i, x in enumerate(proc[:12])],
        "",
        "## Evidence",
        "- result status: done",
        "- successful actions: %d" % len(acts),
        ("- trajectory: %s" % trajectory_ref) if trajectory_ref else "",
    ]).strip()
    rec = {
        "id": pid, "name": name, "kind": "new",
        "description": task.strip()[:200],
        "trigger": " ".join(str(task).split())[:200],
        "evidence": {"n_actions": len(acts),
                     "trajectory_ref": trajectory_ref},
        "skill_md": body, "status": "pending", "created_at": time.time(),
    }
    os.makedirs(_dir(), exist_ok=True)
    p = os.path.join(_dir(), pid + ".json")
    write_text_atomic(p, json.dumps(rec, ensure_ascii=False, indent=1))
    return {"ok": True, "proposal": rec, "path": p}


def list_proposals(status: str | None = None) -> list[dict[str, Any]]:
    d = _dir()
    out = []
    if not os.path.isdir(d):
        return out
    for f in sorted(os.listdir(d)):
        if not f.endswith(".json"):
            continue
        try:
            with open(os.path.join(d, f), encoding="utf-8") as fh:
                rec = json.load(fh)
        except (OSError, ValueError):
            continue
        if isinstance(rec, dict) and (status is None
                                      or rec.get("status") == status):
            out.append(rec)
    return out


def _load(pid: str) -> tuple[str, dict[str, Any]]:
    p = os.path.join(_dir(), _safe(pid) + ".json")
    with open(p, encoding="utf-8") as fh:
        rec = json.load(fh)
    return p, rec


def approve(pid: str, *, apply: bool = False) -> dict[str, Any]:
    try:
        p, rec = _load(pid)
    except (OSError, ValueError) as exc:
        return {"ok": False, "why": "proposal_not_found: %s" % exc}
    if rec.get("status") != "pending":
        return {"ok": False, "why": "not_pending"}
    if not apply:
        return {"ok": True, "apply": False, "proposal": rec,
                "would_write": SS.path_of(rec["name"])}
    saved = SS.save(rec["name"], description=rec.get("description", ""),
                    content=rec.get("skill_md", ""),
                    trigger=rec.get("trigger", ""), version=1)
    rec["status"] = "approved"
    rec["approved_at"] = time.time()
    rec["skill_path"] = saved.get("path")
    write_text_atomic(p, json.dumps(rec, ensure_ascii=False, indent=1))
    return {"ok": True, "apply": True, "proposal": rec, "skill": saved}


def reject(pid: str, why: str = "") -> dict[str, Any]:
    try:
        p, rec = _load(pid)
    except (OSError, ValueError) as exc:
        return {"ok": False, "why": "proposal_not_found: %s" % exc}
    rec["status"] = "rejected"
    rec["rejected_at"] = time.time()
    rec["reject_why"] = str(why)[:300]
    write_text_atomic(p, json.dumps(rec, ensure_ascii=False, indent=1))
    return {"ok": True, "proposal": rec}
