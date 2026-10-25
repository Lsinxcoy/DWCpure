"""DWC-AUTO · Formal attempt selection; no best-of retry semantics."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class AttemptRecord:
    attempt_id: str
    task_id: str
    candidate_id: str
    rollout_id: str
    protocol_id: str
    pair_id: str
    attempt_index: int = 0
    selected_formal: bool = False
    formal_exclusion_reason: str | None = None
    passed: bool | None = None
    score: float | None = None
    execution_cost: float | None = None
    execution_cost_status: str = "not_reported"
    execution_mixture_id: str | None = None
    call_event_refs: list[str] = field(default_factory=list)
    parent_attempt_id: str | None = None
    baseline_id: str | None = None
    artifact_hash: str | None = None
    attempt_class: str = "formal"
    cost_inclusion: str = "formal"
    outcome_kind: str = "binary_pass"
    resolved_tests: int | None = None
    total_tests: int | None = None
    evaluator_id: str | None = None
    evaluator_version: str | None = None
    solver_wall_ms: float | None = None
    grader_wall_ms: float | None = None
    environment_setup_ms: float | None = None
    transport_wait_ms: float | None = None
    retry_backoff_ms: float | None = None
    excluded_infra_cost: float | None = None
    tool_events_ref: str | None = None
    trajectory_ref: str | None = None
    deliverable_refs: list[str] = field(default_factory=list)
    profile_effective_hash: str | None = None
    complete_marker_ref: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CandidateEvaluation:
    candidate_id: str
    protocol_id: str
    pair_id: str
    execution_pair_ids: list[str]
    execution_mixture_id: str
    requested_tasks: int
    completed_tasks: int
    successful_tasks: int
    requested_formal_units: int
    completed_formal_units: int
    successful_formal_units: int
    n_rollouts: int
    mean_cost_per_task: float | None
    cost_of_pass: float | None
    cost_status: str
    usage_complete: bool
    pricing_complete: bool
    measurement_status: str
    result_set_complete: bool
    performance: float | None = None
    performance_kind: str = "binary_pass"
    cost_scope_breakdown: dict[str, float | None] = field(default_factory=dict)
    observed_cost_lower_bound: float | None = None
    cost_of_pass_status: str | None = None
    route_coverage_by_model: dict[str, Any] = field(default_factory=dict)
    expected_task_ids: list[str] = field(default_factory=list)
    completed_task_ids: list[str] = field(default_factory=list)
    pending_task_ids: list[str] = field(default_factory=list)
    infra_failed_ids: list[str] = field(default_factory=list)
    invalid_ids: list[str] = field(default_factory=list)
    unexpected_task_ids: list[str] = field(default_factory=list)
    sample_variance: float | None = None
    confidence_interval_or_unknown: Any = None
    evidence_refs: list[str] = field(default_factory=list)
    baseline_id: str | None = None
    epoch_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TaskMetrics:
    requested_formal_units: int
    completed_formal_units: int
    successful_formal_units: int
    execution_cost: float | None
    mean_cost_per_unit: float | None
    cost_of_pass: float | None
    cost_status: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _unit_key(attempt: AttemptRecord) -> tuple[str, str, str, str, str]:
    return (attempt.candidate_id, attempt.execution_mixture_id or attempt.pair_id, attempt.protocol_id, attempt.task_id, attempt.rollout_id)


def select_formal_attempts(attempts: list[AttemptRecord]) -> list[AttemptRecord]:
    selected: dict[tuple[str, str, str, str, str], AttemptRecord] = {}
    for attempt in attempts:
        if not attempt.selected_formal:
            continue
        if attempt.attempt_index != 0:
            raise ValueError("formal attempt must be initial, not a selected retry")
        key = _unit_key(attempt)
        if key in selected:
            raise ValueError(f"multiple formal attempts for {key!r}")
        selected[key] = attempt
    return [selected[key] for key in sorted(selected)]


def summarize_task_metrics(attempts: list[AttemptRecord], *, requested_formal_units: int | None = None) -> TaskMetrics:
    formal = select_formal_attempts(attempts)
    requested = len(formal) if requested_formal_units is None else requested_formal_units
    completed = sum(item.passed is not None for item in formal)
    successful = sum(item.passed is True for item in formal)
    complete_costs = bool(formal) and len(formal) == requested and all(item.execution_cost is not None and item.execution_cost_status == "priced" for item in formal)
    cost = sum(item.execution_cost or 0.0 for item in formal) if complete_costs else None
    status = "priced" if complete_costs else "indeterminate"
    return TaskMetrics(
        requested_formal_units=requested,
        completed_formal_units=completed,
        successful_formal_units=successful,
        execution_cost=cost,
        mean_cost_per_unit=cost / requested if cost is not None and requested else None,
        cost_of_pass=cost / successful if cost is not None and successful else None,
        cost_status=status if successful else ("zero_successes" if cost is not None else status),
    )
