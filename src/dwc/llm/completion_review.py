"""DWC-AUTO · Conditional completion review with separate usage and actual artifact accounting."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class ReviewConfig:
    short_execution_calls: int
    min_remaining_budget: int
    review_profiles: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if any(isinstance(v, bool) or not isinstance(v, int) or v < 1
               for v in (self.short_execution_calls, self.min_remaining_budget)):
            raise ValueError("review thresholds must be positive integers")


def _base_report(reason: str, artifact_ref: str, initial_usage: Any,
                 initial_call_ids: list[str], remaining_budget: int,
                 review_budget: int = 0) -> dict[str, Any]:
    return {
        "triggered": False, "trigger_reason": reason,
        "initial_call_ids": list(initial_call_ids), "review_call_ids": [],
        "initial_usage": initial_usage, "review_usage": None,
        "review_budget": review_budget, "remaining_budget": remaining_budget,
        "review_outcome": "not_run", "final_artifact_ref": artifact_ref,
    }


def run_conditional_review(*, initial_artifact_ref: str,
                           reviewer: Callable[[int], dict[str, Any]],
                           config: ReviewConfig, initial_usage: Any,
                           initial_call_ids: list[str], remaining_budget: int,
                           execution_calls: int, risk_flags: tuple[str, ...] = (),
                           profile: str = "standard") -> dict[str, Any]:
    """Run at most one fresh review, only for configured public trigger conditions."""
    if remaining_budget < config.min_remaining_budget:
        return _base_report("insufficient_budget", initial_artifact_ref,
                            initial_usage, initial_call_ids, remaining_budget)
    reasons = []
    if execution_calls <= config.short_execution_calls:
        reasons.append("short_execution")
    if risk_flags:
        reasons.append("explicit_risk")
    if profile in config.review_profiles:
        reasons.append("profile")
    if not reasons:
        return _base_report("not_triggered", initial_artifact_ref,
                            initial_usage, initial_call_ids, remaining_budget)
    report = _base_report("+".join(reasons), initial_artifact_ref, initial_usage,
                          initial_call_ids, remaining_budget, remaining_budget)
    report["triggered"] = True
    try:
        reviewed = reviewer(remaining_budget)
    except Exception as exc:
        report["review_outcome"] = "failed:" + type(exc).__name__
        return report
    if not isinstance(reviewed, dict):
        report["review_outcome"] = "failed:invalid_result"
        return report
    report["review_usage"] = reviewed.get("usage")
    report["review_call_ids"] = list(reviewed.get("call_ids") or [])
    spent = reviewed.get("budget_spent", 0)
    if isinstance(spent, bool) or not isinstance(spent, int) or not 0 <= spent <= remaining_budget:
        report["review_outcome"] = "failed:invalid_budget"
        return report
    report["remaining_budget"] = remaining_budget - spent
    if not reviewed.get("ok"):
        report["review_outcome"] = "failed:" + str(reviewed.get("error") or "review_failed")
        return report
    artifact = reviewed.get("artifact_ref")
    if not artifact:
        report["review_outcome"] = "failed:missing_artifact"
        return report
    report["review_outcome"] = "success"
    report["final_artifact_ref"] = artifact
    return report
