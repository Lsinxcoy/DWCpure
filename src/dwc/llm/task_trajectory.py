"""task_trajectory · 任务执行轨迹的机械面（M1.4）。

定位声明 · **DWC-MEM**（记忆底座）
  ★ 只投影 `execute_user_task()` 已有的 `actions_log`；不判分、不推断步骤。
★ 定位：只把 `execute_user_task()` 已经产生的 `actions_log` 投影成
  「可回读、可对账、可被过程技能引用」的 jsonl；不判分、不推断步骤、
  不补模型没做过的动作。

★ 为什么不是从 `run_term._step` 取：
  `run_term` 的 step 是进化周期回执（decision/turn/trace），不是工具执行；
  真实工具调用在 `task_exec._do_action()`，其观察已进 `actions_log`。
  从 run_term 编轨迹 = 假数据。

★ 隐私/体积边界：
  - 只存 `args`/`obs` 的 sha256 与字符数，不内联原文；
  - `answer`/`why` 同理只存 hash 与长度；
  - 原始大对象继续由既有 session/tool_raw 负责，轨迹只做引用。

★ 失败语义：
  - 轨迹写失败不掀任务；调用方把 `trajectory_status=error` 写进结果，
    并保留 `trajectory_error`（G7：不静默）。
  - 空 actions_log 是合法一等输出：`n_steps=0`，不编步骤。
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
import uuid
from typing import Any

SCHEMA_VERSION = 1


def _root() -> str:
    # src/dwc/llm/task_trajectory.py -> src/dwc/llm -> src/dwc -> src -> repo
    return os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))))


def _var_dir(var_dir: str | None = None) -> str:
    if var_dir:
        return var_dir
    env = (os.environ.get("DWC_VAR_DIR") or "").strip()
    return env or os.path.join(_root(), "var")


def _canonical(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True,
                          default=str)
    except (TypeError, ValueError):
        return str(value)


def _digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(
        _canonical(value).encode("utf-8", "replace")).hexdigest()


def _safe_name(task_id: str) -> str:
    name = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(task_id or "unknown"))
    name = name.strip("._")[:80]
    return name or "unknown"


def record_task_trajectory(result: dict[str, Any],
                           *, var_dir: str | None = None) -> dict[str, Any]:
    """把一次任务的 `actions_log` 落成一条轨迹记录。

    返回可并入任务结果的元数据：
      trajectory_ref / trajectory_path / trajectory_id /
      trajectory_steps / trajectory_sha256 / trajectory_status
    """
    if not isinstance(result, dict):
        raise TypeError("task result must be dict")
    if result.get("trajectory_ref"):
        return {
            "trajectory_ref": result.get("trajectory_ref"),
            "trajectory_path": result.get("trajectory_path"),
            "trajectory_id": result.get("trajectory_id"),
            "trajectory_steps": result.get("trajectory_steps"),
            "trajectory_sha256": result.get("trajectory_sha256"),
            "trajectory_status": result.get("trajectory_status") or "recorded",
        }
    task_id = str(result.get("task_id") or "unknown")
    log = result.get("actions_log") or []
    steps: list[dict[str, Any]] = []
    bad = 0
    for i, entry in enumerate(log if isinstance(log, list) else []):
        if not isinstance(entry, dict):
            bad += 1
            steps.append({"index": i, "bad": "not_a_dict"})
            continue
        args = entry.get("args", "")
        obs = entry.get("obs", "")
        steps.append({
            "index": i,
            "round": entry.get("round"),
            "phase": entry.get("phase"),
            "op": entry.get("op"),
            "target": str(entry.get("target") or "")[:200],
            "ok": entry.get("ok"),
            "args_ref": _digest(args),
            "obs_ref": _digest(obs),
            "args_chars": len(str(args or "")),
            "obs_chars": len(str(obs or "")),
        })
    now = time.time()
    rec = {
        "schema": SCHEMA_VERSION,
        "trajectory_id": "TRJ_" + uuid.uuid4().hex[:12],
        "task_id": task_id,
        "status": result.get("status"),
        "rounds": result.get("rounds"),
        "n_steps": len(log) if isinstance(log, list) else 0,
        "n_bad_steps": bad,
        "steps": steps,
        "answer_ref": _digest(result.get("answer", "")),
        "answer_chars": len(str(result.get("answer") or "")),
        "why_ref": _digest(result.get("why", "")),
        "created_at": now,
    }
    path = os.path.join(_var_dir(var_dir), "trajectories",
                        _safe_name(task_id) + ".jsonl")
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        fh.flush()
        os.fsync(fh.fileno())
    return {
        "trajectory_ref": path + "#" + rec["trajectory_id"],
        "trajectory_path": path,
        "trajectory_id": rec["trajectory_id"],
        "trajectory_steps": rec["n_steps"],
        "trajectory_sha256": _digest(rec),
        "trajectory_status": "recorded",
    }
