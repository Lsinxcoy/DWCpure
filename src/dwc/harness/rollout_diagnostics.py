"""DWC-AUTO · Pure multi-rollout diagnostics; observations are never promoted to causes."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class Diagnosis:
    problem_type: str
    scope: str
    frequency: float
    observed_rollouts: int
    pass_pattern: str
    outcome_pattern: list[str]
    performance_impact: str | None
    cost_impact_or_unknown: str | None
    trajectory_refs: list[str]
    event_ranges: list[dict[str, Any]]
    first_effective_event_ref: str | None
    redundant_event_ranges: list[dict[str, Any]]
    repeated_action_keys: list[str]
    state_change_refs: list[str]
    confidence: str
    unknowns: list[str]
    independence_limits: list[str]
    confounders: list[str]
    evidence_status: str
    group_key: dict[str, str]
    event_refs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _value(item: Any, name: str, default: Any = None) -> Any:
    return item.get(name, default) if isinstance(item, dict) else getattr(item, name, default)


def _group_key(rollout: Any) -> tuple[str, ...]:
    names = ("task_id", "candidate_id", "pair_id", "protocol_id", "effective_profile_hash")
    values = tuple(_value(rollout, name) for name in names)
    if any(value is None for value in values):
        raise ValueError("complete rollout group identity is required")
    return values


def _trajectory(rollout: Any) -> str | None:
    return _value(rollout, "trajectory_ref") or _value(rollout, "trace_ref")


def _events(rollout: Any) -> list[dict[str, Any]]:
    events = list(_value(rollout, "events", []) or [])
    return [asdict(event) if hasattr(event, "__dataclass_fields__") else dict(event) for event in events]


def _waste(rollouts: list[Any]) -> tuple[list[dict[str, Any]], list[str], list[str], list[str], list[str]]:
    ranges, action_keys, event_refs, state_refs, unknowns = [], [], [], [], []
    for rollout in rollouts:
        trajectory = _trajectory(rollout)
        previous_by_action = {}
        for event in _events(rollout):
            index = event.get("event_index", event.get("index"))
            action = event.get("action_key")
            previous = previous_by_action.get(action)
            event_ref = event.get("event_ref") or (f"{trajectory}#{index}" if trajectory and index is not None else None)
            if event.get("state_change_ref"):
                state_refs.append(event["state_change_ref"])
            duplicate = bool(event.get("candidate_waste", False)) and not event.get("state_changed", False)
            if previous and event.get("new_information") is False:
                duplicate = (event.get("state_digest") == previous.get("state_digest")
                             and event.get("evidence_digest") == previous.get("evidence_digest")
                             and not event.get("state_changed", False))
            previous_by_action[action] = event
            if not duplicate:
                continue
            if event.get("origin") == "renderer":
                continue
            if not trajectory or index is None:
                unknowns.append("waste_event_reference")
                continue
            ranges.append({"trajectory_ref": trajectory, "start": index, "end": index})
            if event_ref:
                event_refs.append(event_ref)
            key = event.get("action_key")
            if key and key not in action_keys:
                action_keys.append(key)
    return ranges, action_keys, event_refs, state_refs, unknowns


def diagnose_rollouts(rollouts: list[Any]) -> list[Diagnosis]:
    """Return one evidence-linked diagnosis per exact rollout group."""
    groups: dict[tuple[str, ...], list[Any]] = {}
    for rollout in rollouts:
        groups.setdefault(_group_key(rollout), []).append(rollout)
    diagnoses = []
    for key in sorted(groups):
        items = groups[key]
        total = len(items)
        outcomes = [_value(item, "outcome") for item in items]
        if any(outcome is not None for outcome in outcomes):
            if any(outcome is None for outcome in outcomes):
                outcomes = ["unknown" if outcome is None else str(outcome) for outcome in outcomes]
        else:
            outcomes = ["pass" if _value(item, "passed") is True else "fail" if _value(item, "passed") is False else "unknown" for item in items]
        infrastructure = [_value(item, "infrastructure_failed", False) or _value(item, "infra_failed", False) or _value(item, "outcome") == "infra_failed" for item in items]
        if all(infrastructure):
            problem_type, pattern = "infrastructure", "infra_only"
        elif any(infrastructure):
            problem_type, pattern = "infrastructure", "mixed_infrastructure"
        elif all(_value(item, "passed") is False for item in items):
            problem_type, pattern = "correctness", "stable_failure"
        elif all(_value(item, "passed") is True for item in items):
            problem_type, pattern = "stable_success", "stable_success"
        else:
            problem_type, pattern = "instability", "flaky"
        ranges, keys, waste_refs, state_refs, unknowns = _waste(items)
        if ranges:
            problem_type, pattern = "waste", "successful_but_wasteful" if all(_value(item, "passed") is True for item in items) else pattern
        trajectories = [_trajectory(item) for item in items]
        trajectories = [ref for ref in trajectories if ref]
        event_refs = [ref for item in items for ref in (_value(item, "event_refs", []) or [])]
        event_refs.extend(waste_refs)
        first_effective = next((_value(item, "first_effective_event_ref") for item in items if _value(item, "first_effective_event_ref")), None)
        if first_effective is None:
            first_effective = next((event.get("event_ref") or f"{_trajectory(item)}#{event.get('event_index', event.get('index'))}"
                for item in items for event in _events(item) if event.get("effective")), None)
        costs = [_value(item, "waste_cost") for item in items]
        cost_impact = str(sum(costs)) if ranges and costs and all(cost is not None for cost in costs) else None
        if ranges and cost_impact is None:
            unknowns.append("waste_cost")
        performance_impact = "failed_all_rollouts" if pattern == "stable_failure" else "unstable_pass_rate" if pattern == "flaky" else None
        diagnoses.append(Diagnosis(
            problem_type=problem_type, scope="invariant", frequency=1.0,
            observed_rollouts=total, pass_pattern=pattern, outcome_pattern=outcomes,
            performance_impact=performance_impact, cost_impact_or_unknown=cost_impact,
            trajectory_refs=trajectories, event_ranges=ranges,
            first_effective_event_ref=first_effective, redundant_event_ranges=ranges,
            repeated_action_keys=keys, state_change_refs=state_refs,
            confidence="observed", unknowns=sorted(set(unknowns)),
            independence_limits=["same_distribution_rollouts_not_independent_evidence"],
            confounders=[], evidence_status="observed" if total else "unknown",
            group_key=dict(zip(("task_id", "candidate_id", "pair_id", "protocol_id", "effective_profile_hash"), key)),
            event_refs=event_refs,
        ))
    return diagnoses


@dataclass(frozen=True)
class CacheDiagnosis:
    problem_type: str
    reported: dict[str, Any]
    unknowns: list[str]
    evidence_refs: list[str]
    evidence_status: str

    def __getattr__(self, name: str) -> Any:
        try:
            return self.reported[name]
        except KeyError as error:
            raise AttributeError(name) from error

    def to_dict(self) -> dict[str, Any]:
        return {"problem_type": self.problem_type, **self.reported,
                "unknowns": self.unknowns, "evidence_refs": self.evidence_refs,
                "evidence_status": self.evidence_status}


CACHE_FIELDS = ("capability_id", "cache_mode", "policy_decided", "request_sent",
    "extension_fields_sent", "server_accepted", "server_acceptance_basis", "usage_status",
    "akv_cached_tokens", "repos_tokens", "drop_skipped_tokens", "actual_prefill_tokens",
    "actual_decode_tokens", "provider_cached_input_tokens", "residency_or_recovery_status",
    "unsupported_reason", "logical_tokens", "active_cache_reported",
    "physical_residency_reported", "drop_skipped", "actual_prefill")


def diagnose_cache(observation: Any) -> CacheDiagnosis:
    """Expose only reported cache fields; never infer provider-side behavior."""
    values = {name: _value(observation, name) for name in CACHE_FIELDS
              if isinstance(observation, dict) and name in observation or hasattr(observation, name)}
    unknowns = [name.removesuffix("_reported") for name, value in values.items() if value is None]
    if not values:
        unknowns = ["cache_observation"]
    evidence_refs = list(_value(observation, "evidence_refs", []) or [])
    evidence_ref = _value(observation, "evidence_ref")
    if evidence_ref:
        evidence_refs.append(evidence_ref)
    return CacheDiagnosis(problem_type="cache", reported=values, unknowns=unknowns,
                          evidence_refs=evidence_refs,
                          evidence_status="partial" if unknowns and evidence_refs else "unknown" if unknowns else "observed")
