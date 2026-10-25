"""DWC-AUTO · Standard-library usage normalization, pricing, and reconciliation."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from decimal import Decimal
from typing import Any, Mapping


@dataclass(frozen=True)
class NormalizedUsage:
    input_tokens: int | None = None
    cached_input_tokens: int = 0
    cache_write_tokens: int = 0
    output_tokens: int | None = None
    reasoning_tokens: int = 0
    uncached_input_tokens: int | None = None
    billable_output_tokens: int | None = None
    output_includes_reasoning: bool | None = None
    status: str = "reported"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PriceResult:
    cost: float | None
    status: str
    components: dict[str, float | None] = field(default_factory=dict)
    pricing_version: str | None = None
    repriced_from: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ReconcileResult:
    status: str
    delta: int | None
    provider_total: int | None
    observed_total: int
    event_deltas: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_RATES = {
    "uncached_input": "input_per_million",
    "cached_input": "cached_input_per_million",
    "cache_write": "cache_write_per_million",
    "output": "output_per_million",
    "reasoning": "reasoning_per_million",
}


def price_usage(normalized: NormalizedUsage, pricing_entry: Mapping[str, Any] | None, *, repriced_from: str | None = None) -> PriceResult:
    if pricing_entry is None:
        return PriceResult(None, "not_configured", repriced_from=repriced_from)
    if normalized.status != "reported":
        return PriceResult(None, "indeterminate", pricing_version=pricing_entry.get("version"), repriced_from=repriced_from)
    if normalized.reasoning_tokens and normalized.output_includes_reasoning is None:
        return PriceResult(None, "indeterminate", pricing_version=pricing_entry.get("version"), repriced_from=repriced_from)
    if normalized.uncached_input_tokens is None or normalized.billable_output_tokens is None:
        return PriceResult(None, "indeterminate", pricing_version=pricing_entry.get("version"), repriced_from=repriced_from)
    tokens = {
        "uncached_input": normalized.uncached_input_tokens,
        "cached_input": normalized.cached_input_tokens,
        "cache_write": normalized.cache_write_tokens,
        "output": normalized.billable_output_tokens,
        "reasoning": normalized.reasoning_tokens if not normalized.output_includes_reasoning else 0,
    }
    components: dict[str, float | None] = {}
    total = Decimal(0)
    missing = []
    for component, count in tokens.items():
        if not count:
            components[component] = 0.0
            continue
        rate = pricing_entry.get(_RATES[component])
        if rate is None:
            components[component] = None
            missing.append(component)
        else:
            amount = Decimal(count) * Decimal(str(rate)) / Decimal(1_000_000)
            components[component] = float(amount)
            total += amount
    if missing:
        return PriceResult(None, "partial", components, pricing_entry.get("version"), repriced_from)
    return PriceResult(float(total), "priced", components, pricing_entry.get("version"), repriced_from)


@dataclass
class UsageEvent:
    event_id: str
    attempt_id: str
    task_id: str
    candidate_id: str
    requested_model: str
    actual_model: str | None
    schema_version: str = "1"
    call_id: str | None = None
    parent_call_id: str | None = None
    term_id: str | None = None
    parent_candidate_id: str | None = None
    rollout_id: str | None = None
    attempt_index: int | None = None
    idempotency_key: str | None = None
    call_role: str = "unassigned"
    cost_scope: str = "solve_execution"
    cost_stage: str | None = None
    parent_stage_id: str | None = None
    model_revision_status: str = "unknown"
    endpoint_class: str | None = None
    pair_id: str | None = None
    provider_trace_id: str | None = None
    started_at: str | None = None
    observed_at: str | None = None
    wall_time_ms: float | None = None
    transport_status: str | None = None
    finish_reason: str | None = None
    usage_raw_ref: str | None = None
    usage_status: str = "reported"
    usage_coverage: str = "full"
    input_tokens: int | None = None
    cached_input_tokens: int = 0
    cache_write_tokens: int = 0
    output_tokens: int | None = None
    reasoning_tokens: int = 0
    uncached_input_tokens: int | None = None
    billable_output_tokens: int | None = None
    pricing_version: str | None = None
    pricing_status: str = "not_configured"
    estimated_cost: float | None = None
    cache_hit: bool | None = None
    original_execution_ref: str | None = None
    evidence_ref: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _pick(raw: Mapping[str, Any], *names: str, default: Any = None) -> Any:
    for name in names:
        if name in raw:
            return raw[name]
    return default


def _integer(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field_name} must be a non-negative integer")
    return value


def normalize_usage(raw: Mapping[str, Any], provider_adapter: Mapping[str, Any] | None = None) -> NormalizedUsage:
    adapter = provider_adapter or {}
    if raw is None:
        return NormalizedUsage(status="not_reported")
    input_tokens = _pick(raw, "input_tokens", "prompt_tokens")
    output_tokens = _pick(raw, "output_tokens", "completion_tokens")
    prompt_details = raw.get("prompt_tokens_details") or raw.get("input_token_details") or {}
    completion_details = raw.get("completion_tokens_details") or raw.get("output_token_details") or {}
    cached = _pick(raw, "cached_input_tokens", default=_pick(prompt_details, "cached_tokens", default=0))
    cache_write = _pick(raw, "cache_write_tokens", "cache_creation_input_tokens", default=0)
    reasoning = _pick(raw, "reasoning_tokens", default=_pick(completion_details, "reasoning_tokens", default=0))
    values = {"input_tokens": input_tokens, "output_tokens": output_tokens, "cached_input_tokens": cached, "cache_write_tokens": cache_write, "reasoning_tokens": reasoning}
    for name, value in values.items():
        if value is not None:
            values[name] = _integer(value, name)
    if values["input_tokens"] is None or values["output_tokens"] is None:
        return NormalizedUsage(status="partial", **values)
    uncached = values["input_tokens"] - values["cached_input_tokens"] - values["cache_write_tokens"]
    if uncached < 0:
        return NormalizedUsage(status="malformed")
    includes_reasoning = adapter.get("output_includes_reasoning")
    billable_output = None if includes_reasoning is None else (values["output_tokens"] if includes_reasoning else values["output_tokens"] + values["reasoning_tokens"])
    return NormalizedUsage(**values, uncached_input_tokens=uncached, billable_output_tokens=billable_output, output_includes_reasoning=includes_reasoning)


def reconcile_usage(provider_total: Mapping[str, int], observed_events: list[NormalizedUsage]) -> ReconcileResult:
    if any(getattr(event, "status", getattr(event, "usage_status", "not_reported")) != "reported" for event in observed_events):
        return ReconcileResult("indeterminate", None, None, 0)
    observed = {
        "input_tokens": sum(event.input_tokens or 0 for event in observed_events),
        "cached_input_tokens": sum(event.cached_input_tokens for event in observed_events),
        "cache_write_tokens": sum(event.cache_write_tokens for event in observed_events),
        "output_tokens": sum(event.output_tokens or 0 for event in observed_events),
        "reasoning_tokens": sum(event.reasoning_tokens for event in observed_events),
    }
    total = sum(observed.values())
    deltas = {}
    for name, count in observed.items():
        if count == 0 and name not in provider_total:
            continue
        supplied = provider_total.get(name, count)
        if supplied < count:
            return ReconcileResult("conflict", None, None, total)
        deltas[name] = supplied - count
    return ReconcileResult("reconciled", sum(deltas.values()), sum(provider_total.get(name, observed[name]) for name in deltas), total, deltas)


def summarize_candidate(attempts: list[Any], usage_events: list[UsageEvent], price_book: Mapping[str, Mapping[str, Any]], *, requested_formal_units: int | None = None, protocol_allows_mixture: bool = False) -> Any:
    from .identity import PairIdentity
    from .task_metrics import CandidateEvaluation, select_formal_attempts

    formal = select_formal_attempts(attempts)
    if not formal:
        raise ValueError("no formal attempts")
    first = formal[0]
    if any(a.candidate_id != first.candidate_id or a.protocol_id != first.protocol_id for a in formal):
        raise ValueError("attempts must belong to one candidate and protocol")
    by_attempt = {a.attempt_id: a for a in attempts}
    formal_ids = {a.attempt_id for a in formal}
    relevant = []
    seen_events = {}
    for event in usage_events:
        if event.attempt_id not in by_attempt:
            continue
        key = event.idempotency_key or event.event_id
        signature = (event.attempt_id, event.call_id, event.attempt_index,
                     event.input_tokens, event.output_tokens, event.actual_model)
        if key in seen_events:
            if seen_events[key] != signature:
                raise ValueError("conflicting duplicate usage event: %s" % key)
            continue
        seen_events[key] = signature
        relevant.append(event)
    covered_attempts = {event.attempt_id for event in relevant if event.cost_scope != "excluded_infra"}
    usage_complete = covered_attempts >= formal_ids and all(event.usage_status == "reported" and event.usage_coverage == "full" and event.input_tokens is not None and event.output_tokens is not None and event.uncached_input_tokens is not None and event.billable_output_tokens is not None and not (event.cache_hit and not event.original_execution_ref) for event in relevant)
    total = Decimal(0)
    observed = Decimal(0)
    pricing_complete = usage_complete
    priced_results: dict[str, PriceResult] = {}
    for event in relevant:
        if not usage_complete:
            break
        result = price_usage(NormalizedUsage(**{name: getattr(event, name) for name in NormalizedUsage.__dataclass_fields__ if hasattr(event, name)}), price_book.get(event.actual_model or ""))
        if result.cost is None:
            pricing_complete = False
            break
        priced_results[event.event_id] = result
        if event.attempt_id in formal_ids and event.cost_scope != "excluded_infra":
            total += Decimal(str(result.cost))
        observed += Decimal(str(result.cost))
    requested = len(formal) if requested_formal_units is None else requested_formal_units
    result_set_complete = len(formal) == requested and all(a.passed is not None for a in formal)
    usage_complete = result_set_complete and usage_complete
    completed = sum(a.passed is not None for a in formal)
    successful = sum(a.passed is True for a in formal)
    task_ids = sorted({a.task_id for a in formal})
    pairs = sorted({a.pair_id for a in formal})
    pairs = sorted({event.pair_id for event in relevant if event.pair_id is not None} or set(pairs))
    route_deviation = any(event.pair_id is not None and event.pair_id != by_attempt[event.attempt_id].pair_id for event in relevant)
    mixture = PairIdentity.execution_mixture_id(pairs)
    if route_deviation and not protocol_allows_mixture:
        pricing_complete = False
    cost = float(total) if pricing_complete and result_set_complete else None
    status = "priced" if pricing_complete and result_set_complete else "indeterminate"
    scope_breakdown: dict[str, float | None] = {}
    if pricing_complete:
        for scope in sorted({event.cost_scope for event in relevant}):
            scope_total = sum((Decimal(str(priced_results[event.event_id].cost)) for event in relevant if event.cost_scope == scope), Decimal(0))
            scope_breakdown[scope] = float(scope_total)
    return CandidateEvaluation(
        candidate_id=first.candidate_id,
        baseline_id=first.baseline_id,
        protocol_id=first.protocol_id,
        pair_id=first.pair_id,
        execution_pair_ids=pairs,
        execution_mixture_id=mixture,
        requested_tasks=len(task_ids),
        completed_tasks=len({a.task_id for a in formal if a.passed is not None}),
        successful_tasks=len({a.task_id for a in formal if a.passed is True}),
        requested_formal_units=requested,
        completed_formal_units=completed,
        successful_formal_units=successful,
        n_rollouts=len({a.rollout_id for a in formal}),
        performance=successful / completed if completed else None,
        mean_cost_per_task=cost / requested if cost is not None and requested else None,
        cost_of_pass=cost / successful if cost is not None and successful else None,
        cost_of_pass_status=status if successful else ("zero_successes" if cost is not None else status),
        cost_status=status,
        cost_scope_breakdown=scope_breakdown,
        observed_cost_lower_bound=float(observed) if not (pricing_complete and result_set_complete) else cost,
        usage_complete=usage_complete,
        pricing_complete=pricing_complete and result_set_complete,
        measurement_status="indeterminate" if route_deviation and not protocol_allows_mixture else ("measured" if completed == requested and pricing_complete else "incomplete"),
        result_set_complete=completed == requested,
        infra_failed_ids=sorted({f"{a.task_id}:{a.rollout_id}" for a in attempts if not a.selected_formal} - {f"{a.task_id}:{a.rollout_id}" for a in formal}),
        expected_task_ids=task_ids,
        completed_task_ids=sorted({a.task_id for a in formal if a.passed is not None}),
        pending_task_ids=sorted({a.task_id for a in formal if a.passed is None}),
        route_coverage_by_model={model: sum(event.actual_model == model for event in relevant) for model in sorted({event.actual_model for event in relevant if event.actual_model})},
    )
