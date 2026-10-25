"""trajectory_stitch · 两段真实轨迹的拼接（M3.3）。

定位声明 · **DWC-AUTO**（自我强化）
  ★ 只拼已有步骤；不生成、不补全、不推断缺失动作。
  ★ 单边/空轨迹 ⇒ `stitched=False`，不制造“完整轨迹”。

为什么需要
----------
MSTAR 的 ExperienceRecall 会做 trajectory stitching；DWC 先只做最小机械面：
两段轨迹有真实步骤时按顺序拼接，并保留每段的来源索引，供后续对比/检索。
"""
from __future__ import annotations

from typing import Any


def _norm(traj: Any, source: str) -> list[dict[str, Any]]:
    if isinstance(traj, dict):
        traj = traj.get("steps") or traj.get("actions_log") or []
    out = []
    for i, step in enumerate(traj or []):
        if not isinstance(step, dict):
            continue
        out.append({
            "source": source,
            "source_index": i,
            "op": str(step.get("op") or ""),
            "target": str(step.get("target") or "")[:200],
            "ok": step.get("ok"),
            "evidence_ref": str(step.get("evidence_ref")
                                or step.get("obs_ref") or ""),
        })
    return out


def stitch(primary: Any, secondary: Any, *,
           relation: str = "follows") -> dict[str, Any]:
    """返回 `{stitched, steps, link, n_steps, evidence_refs}`。"""
    a = _norm(primary, "primary")
    b = _norm(secondary, "secondary")
    if not a or not b:
        return {"stitched": False, "steps": [], "link": None,
                "n_steps": 0, "evidence_refs": [],
                "why": "单边或空轨迹：不拼接"}
    steps = a + b
    refs = [s["evidence_ref"] for s in steps if s["evidence_ref"]]
    return {
        "stitched": True,
        "steps": steps,
        "link": {"from_source_index": a[-1]["source_index"],
                 "to_source_index": b[0]["source_index"],
                 "relation": str(relation or "follows")},
        "n_steps": len(steps),
        "evidence_refs": refs[:40],
        "why": "",
    }
