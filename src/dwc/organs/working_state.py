"""working_state · 工作态更新前的环境证据门（M1.7）。

定位声明 · **DWC-MEM**（记忆底座）
  ★ 只做确定性检查：`done` 是否有非空环境证据、`blocked` 是否有 blocker。
  ★ 不判断证据真假、不调用 LLM、不替调用方改任务状态。

为什么需要
----------
ARSI 的 `WorkingState` checker 反复抓到一个问题：agent 说“已完成”，但没有任何
环境证据（文件/测试/观察）。DWC 的 `WORKING_STATE` 节点此前可以直接写，
没有“claim-only done”这一道门。M1.7 只补这道门，不复制 ARSI 的类结构。

边界
----
- `check_update()` 是纯函数；`propose_update()` 才写记忆。
- 证据是字符串列表；空串不算证据。
- `claimed=True` 表示“这是自我声称的完成”，没有证据必须打回。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from dwc.organs.memory import MemoryKind

VALID_STATUS = ("active", "blocked", "done")


@dataclass
class WorkingStateUpdate:
    goal_id: str
    status: str
    evidence: list[str] = field(default_factory=list)
    blocker: str = ""
    claimed: bool = False


def _clean_evidence(evidence: Any) -> list[str]:
    if isinstance(evidence, str):
        evidence = [evidence]
    out: list[str] = []
    for item in evidence or []:
        text = str(item or "").strip()
        if text:
            out.append(text[:500])
    return out


def check_update(goal_id: str, status: str,
                 evidence: Any = None, blocker: str = "",
                 claimed: bool = False) -> dict[str, Any]:
    """返回 `{passed, code, reason, goal_id, status, evidence, blocker}`。"""
    ev = _clean_evidence(evidence)
    st = str(status or "").strip().lower()
    base = {
        "goal_id": str(goal_id or ""),
        "status": st,
        "evidence": ev,
        "blocker": str(blocker or "")[:500],
    }
    if not base["goal_id"]:
        return {**base, "passed": False, "code": "missing_goal_id",
                "reason": "工作态更新必须有 goal_id"}
    if st not in VALID_STATUS:
        return {**base, "passed": False, "code": "invalid_status",
                "reason": "status 必须是 active/blocked/done"}
    if st == "done" and not ev:
        return {**base, "passed": False,
                "code": "truth_bounce_no_env_evidence",
                "reason": "done 必须带环境证据；claim-only 完成不算完成"}
    if st == "blocked" and not base["blocker"]:
        return {**base, "passed": False, "code": "blocked_without_blocker",
                "reason": "blocked 必须说明 blocker"}
    if claimed and not ev:
        return {**base, "passed": False,
                "code": "claim_without_evidence",
                "reason": "自我声称的完成必须带证据"}
    return {**base, "passed": True, "code": "ok", "reason": ""}


def propose_update(memory: Any, goal_id: str, status: str,
                   evidence: Any = None, blocker: str = "",
                   claimed: bool = False) -> dict[str, Any]:
    """检查后写入 WORKING_STATE；检查失败不写，返回 verdict。"""
    verdict = check_update(goal_id, status, evidence, blocker, claimed)
    if not verdict["passed"]:
        return {**verdict, "written": None}
    payload = {
        "goal_id": verdict["goal_id"],
        "status": verdict["status"],
        "evidence": verdict["evidence"],
        "blocker": verdict["blocker"],
        "claimed": bool(claimed),
    }
    nid = memory.remember(MemoryKind.WORKING_STATE, payload,
                          source_channel="system_summary")
    return {**verdict, "written": nid}
