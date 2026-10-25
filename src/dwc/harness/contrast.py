"""contrast · 成功/失败轨迹的成对差异（M1.5）。

定位声明 · **DWC-AUTO**（自我强化）
  ★ 只比较**两边都真实存在**的步骤；单边样本不写因果、不生成技能。
  ★ 不判分、不调用 LLM；输出是证据，不是结论。

为什么需要
----------
DWC 的 dream 只聚失败签名，成功路径没有形成“差异步骤”。但差异不能靠
模型自述编：必须把失败轨迹与成功轨迹按动作对齐，找到第一个分叉点。
"""
from __future__ import annotations

from typing import Any


def _steps(traj: Any) -> list[dict[str, Any]]:
    if isinstance(traj, dict):
        traj = traj.get("steps") or traj.get("actions_log") or []
    out: list[dict[str, Any]] = []
    for i, step in enumerate(traj or []):
        if not isinstance(step, dict):
            continue
        out.append({
            "index": i,
            "op": str(step.get("op") or ""),
            "target": str(step.get("target") or "")[:200],
            "ok": step.get("ok"),
            "evidence_ref": str(step.get("evidence_ref")
                                or step.get("obs_ref") or ""),
        })
    return out


def compare(failure_traj: Any, success_traj: Any) -> dict[str, Any]:
    """返回第一个分叉点、变化动作、成功侧验证步骤与置信度。

    ★ 只有两边都有步骤才给 `comparable=True`；否则 `confidence=0.0`。
    ★ 同一位置 op/target/ok 任一不同即视为分叉；找不到分叉时
      `divergence_index=None`（不编“差异”）。
    """
    f = _steps(failure_traj)
    s = _steps(success_traj)
    if not f or not s:
        return {
            "comparable": False,
            "divergence_index": None,
            "changed_action": None,
            "verification": [],
            "evidence_refs": [],
            "confidence": 0.0,
            "why": "单边或空轨迹：不比较，不写因果",
        }
    idx = None
    for i in range(min(len(f), len(s))):
        if (f[i]["op"], f[i]["target"], f[i]["ok"]) != \
                (s[i]["op"], s[i]["target"], s[i]["ok"]):
            idx = i
            break
    if idx is None and len(f) != len(s):
        idx = min(len(f), len(s))
    changed = None
    if idx is not None and idx < len(f) and idx < len(s):
        changed = {"failure": f[idx], "success": s[idx]}
    verification = [step for step in s
                    if step["op"] in ("run", "test", "check")
                    and step["ok"] is True]
    refs = [step["evidence_ref"] for step in f + s
            if step["evidence_ref"]]
    return {
        "comparable": True,
        "divergence_index": idx,
        "changed_action": changed,
        "verification": verification,
        "evidence_refs": refs[:20],
        "confidence": 0.8 if idx is not None else 0.2,
        "why": ("找到第一个分叉" if idx is not None
                else "两边步骤一致；不编差异"),
    }
