"""DWC-AUTO · Formal budget controller for evaluation; runtime uses dwc.llm.budget.

The production task loop is governed by :mod:`dwc.llm.budget` (R441). This
module provides the stricter evaluation-side state machine and must not be
wired as a second runtime budget source.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

_STAGE_FINALIZE = "finalize"
_STAGE_HARD_EXHAUSTED = "hard_exhausted"


@dataclass(frozen=True)
class BudgetConfig:
    economy_after: int
    converge_after: int
    hard_tool_cap: int
    final_reserved_calls: int = 1
    reminder_every: int = 1
    denial_stop_threshold: int = 2

    def __post_init__(self) -> None:
        values = (self.economy_after, self.converge_after, self.hard_tool_cap,
                  self.final_reserved_calls, self.reminder_every,
                  self.denial_stop_threshold)
        if any(isinstance(v, bool) or not isinstance(v, int) or v < 1 for v in values):
            raise ValueError("budget thresholds must be positive integers")
        if not self.economy_after < self.converge_after < self.hard_tool_cap:
            raise ValueError("economy_after < converge_after < hard_tool_cap required")
        if self.final_reserved_calls >= self.hard_tool_cap - self.converge_after:
            raise ValueError("final reserve must fit inside the finalize budget")


class BudgetController:
    def __init__(self, config: BudgetConfig):
        self.config = config
        self.calls_used = 0
        self.finals_used = 0
        self.deny_count = 0
        self.completion_status = "in_progress"
        self.best_effort = False
        self.events: list[dict[str, Any]] = []

    @property
    def remaining_calls(self) -> int:
        return max(0, self.config.hard_tool_cap - self.calls_used)

    @property
    def stage(self) -> str:
        if self.calls_used >= self.config.hard_tool_cap:
            return "hard_exhausted"
        if self.calls_used >= self.config.hard_tool_cap - self.config.final_reserved_calls:
            return "finalize"
        if self.calls_used >= self.config.converge_after:
            return "converge"
        return "economy"

    def _decision(self, allowed: bool, *, denial_kind: str = "") -> dict[str, Any]:
        hints = {
            "economy": "合并并去重工具调用；这是软提示，不阻止具体修复。",
            "converge": "停止广泛探索；具体失败和变异交付物仍可修复。",
            "finalize": "只保留 final 与必要修复，拒绝新低价值探索。",
            "hard_exhausted": "工具硬预算耗尽；保留 artifacts，best-effort 收尾。",
        }
        return {"stage": self.stage, "allowed": allowed,
                "denial_kind": denial_kind, "hint": hints[self.stage],
                "remaining_calls": self.remaining_calls,
                "best_effort": self.best_effort,
                "completion_status": self.completion_status}

    def before_call(self, *, purpose: str = "explore") -> dict[str, Any]:
        allowed = self.stage in ("economy", "converge") or (
            self.stage == _STAGE_FINALIZE and purpose == "repair")
        return self._decision(allowed, denial_kind="" if allowed else "budget")

    def record_call(self, count: int = 1) -> dict[str, Any]:
        if count < 1 or self.calls_used + count > self.config.hard_tool_cap:
            raise ValueError("tool call would exceed hard cap")
        self.calls_used += count
        if self.calls_used % self.config.reminder_every == 0:
            self.events.append(self._decision(True))
        return self._decision(True)

    def record_denial(self, kind: str) -> dict[str, Any]:
        if kind == "budget":
            self.deny_count += 1
            if self.deny_count >= self.config.denial_stop_threshold:
                self.best_effort = True
                self.completion_status = "incomplete"
        self.events.append({"kind": "denial", "denial_kind": kind,
                            "deny_count": self.deny_count})
        return self._decision(False, denial_kind=kind)

    def final_allowed(self) -> bool:
        return self.finals_used < self.config.final_reserved_calls

    def record_final(self) -> dict[str, Any]:
        if not self.final_allowed():
            raise ValueError("final reserve exhausted")
        self.finals_used += 1
        self.calls_used = self.config.hard_tool_cap
        self.best_effort = self.stage == _STAGE_HARD_EXHAUSTED
        self.completion_status = "incomplete"
        return self._decision(False, denial_kind="budget")
