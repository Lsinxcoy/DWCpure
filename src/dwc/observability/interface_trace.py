"""DWC-AUTO · Interface mismatch rate and coverage projections from observed model turns."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

VIOLATION_CATEGORIES = ("unknown_tool", "invalid_json", "argument_schema", "response_protocol", "final_format")


@dataclass(frozen=True)
class InterfaceTrace:
    task_id: str
    turn_id: str
    request_index: int
    response_stage: str
    offered_tools: list[str]
    raw_response_ref: str | None
    effective_response_ref: str | None
    transport_repaired: bool
    termination: str | None
    parse_status: str | None
    evidence_ref: str | None
    violations: list[str] = field(default_factory=list)
    interface_recovered: bool = False
    observed: bool = True

    def __post_init__(self) -> None:
        if self.response_stage not in {"provider", "client"}:
            raise ValueError("response_stage must be provider or client")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TIMR:
    metric_version: str
    task_set: list[str]
    observed_model_turns: int
    violating_model_turns: int
    rate: float | None
    counts: dict[str, int]
    by_task: dict[str, "TIMR"]
    transport_repaired_turns: int
    interface_recovered_turns: int
    event_refs: list[str]
    coverage_complete: bool
    coverage: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        return result


@dataclass(frozen=True)
class Coverage:
    checked: int | None
    total: int | None
    rate: float | None
    reason: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TIMRComparison:
    comparable: bool
    reasons: list[str]
    left_rate: float | None
    right_rate: float | None
    delta: float | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _value(item: Any, name: str, default: Any = None) -> Any:
    return item.get(name, default) if isinstance(item, dict) else getattr(item, name, default)


def _turn_id(turn: Any) -> tuple[str, str]:
    task = _value(turn, "task_id")
    turn_id = _value(turn, "turn_id")
    if task is None or turn_id is None:
        raise ValueError("task_id and turn_id are required")
    return str(task), str(turn_id)


def _categories(turn: Any) -> list[str]:
    categories = list(_value(turn, "violations", []) or [])
    aliases = {"schema": "argument_schema", "schema_violation": "argument_schema",
               "protocol": "response_protocol", "response_format": "final_format"}
    categories = [aliases.get(category, category) for category in categories]
    for field_name, category in (("unknown_tool", "unknown_tool"), ("invalid_json", "invalid_json"),
                                  ("schema_violation", "argument_schema"),
                                  ("protocol_violation", "response_protocol"),
                                  ("final_format_violation", "final_format")):
        if _value(turn, field_name, False):
            categories.append(category)
    unknown = set(categories).difference(VIOLATION_CATEGORIES)
    if unknown:
        raise ValueError(f"unknown interface violation categories: {sorted(unknown)!r}")
    return sorted(set(categories))


def _summary(turns: list[Any], *, task_set: list[str], metric_version: str,
             coverage_complete: bool, coverage: dict[str, Any], nested: bool = True) -> TIMR:
    observed: dict[tuple[str, str], dict[str, Any]] = {}
    for turn in turns:
        if not _value(turn, "observed", True):
            continue
        key = _turn_id(turn)
        if key not in observed:
            observed[key] = {"categories": set(), "transport": False, "recovery": False, "refs": []}
        target = observed[key]
        target["categories"].update(_categories(turn))
        target["transport"] |= bool(_value(turn, "transport_repaired", False))
        target["recovery"] |= bool(_value(turn, "interface_recovered", False))
        ref = _value(turn, "event_ref") or _value(turn, "evidence_ref")
        if ref and target["categories"]:
            target["refs"].append(ref)
    counts = {category: sum(category in turn["categories"] for turn in observed.values()) for category in VIOLATION_CATEGORIES}
    violating = sum(bool(turn["categories"]) for turn in observed.values())
    by_task = {}
    if nested:
        for task in sorted({key[0] for key in observed}):
            subset = [turn for turn in turns if _turn_id(turn)[0] == task]
            by_task[task] = _summary(subset, task_set=[task], metric_version=metric_version,
                                      coverage_complete=coverage_complete, coverage={}, nested=False)
    return TIMR(metric_version=metric_version, task_set=sorted(task_set),
                observed_model_turns=len(observed), violating_model_turns=violating,
                rate=violating / len(observed) if observed else None, counts=counts,
                by_task=by_task,
                transport_repaired_turns=sum(turn["transport"] for turn in observed.values()),
                interface_recovered_turns=sum(turn["recovery"] for turn in observed.values()),
                event_refs=list(dict.fromkeys(ref for turn in observed.values() for ref in turn["refs"])),
                coverage_complete=coverage_complete, coverage=coverage)


def summarize_timr(turns: list[Any], *, task_set: list[str] | None = None,
                   metric_version: str = "timr.v1", coverage_complete: bool = True,
                   coverage: dict[str, Any] | None = None) -> TIMR:
    """Count each (task, model turn) once even with multiple violation types."""
    tasks = sorted(task_set) if task_set is not None else sorted({_turn_id(turn)[0] for turn in turns})
    coverage = coverage or {}
    if coverage:
        coverage_complete = all(item.rate == 1 and item.reason is None for item in coverage.values())
    return _summary(turns, task_set=tasks, metric_version=metric_version,
                    coverage_complete=coverage_complete, coverage=coverage)


def _unresolved_schema(value: Any) -> bool:
    if isinstance(value, dict):
        if "$ref" in value:
            reference = value["$ref"]
            if not isinstance(reference, str) or not reference.startswith("#/"):
                return True
        return any(_unresolved_schema(child) for child in value.values())
    if isinstance(value, list):
        return any(_unresolved_schema(child) for child in value)
    return False


def summarize_interface_coverage(observations: list[Any]) -> dict[str, Coverage]:
    """Project coverage without interpreting absent evidence as a zero numerator."""
    result = {}
    simple = (("raw_trace_tasks", "raw_trace_ref", "raw_trace_not_reported"),
              ("tool_names", "tool_names", "tool_names_not_reported"),
              ("argument_schemas", "argument_schemas", "schema_not_reported"),
              ("tool_returns", "tool_returns", "tool_return_contract_unknown"))
    for name, field_name, missing_reason in simple:
        reported = [_value(observation, field_name) for observation in observations]
        if all(value is None for value in reported):
            result[name] = Coverage(checked=None, total=None, rate=None, reason=missing_reason)
            continue
        if any(value is not None and (
                (name == "argument_schemas" and _unresolved_schema(value)) or
                (name == "tool_returns" and any(_value(item, "contract") == "unknown" or _value(item, "status") == "unknown" for item in value)))
               for value in reported):
            result[name] = Coverage(checked=None, total=None, rate=None, reason=missing_reason if name == "tool_returns" else "unresolved_schema_ref")
            continue
        checked = sum(value is not None for value in reported)
        total = len(observations)
        result[name] = Coverage(checked=checked, total=total,
                                rate=checked / total if total else None,
                                reason=None if checked == total and total else missing_reason)
    complete = [_value(observation, "complete_interface_turns") for observation in observations]
    turns = [_value(observation, "observed_model_turns") for observation in observations]
    if any(value is None for value in complete + turns):
        result["complete_interface_turns"] = Coverage(checked=None, total=None, rate=None,
            reason=next((_value(observation, "reason") for observation in observations if _value(observation, "reason")), "interface_turns_not_reported"))
    else:
        checked, total = sum(complete), sum(turns)
        result["complete_interface_turns"] = Coverage(checked=checked, total=total,
            rate=checked / total if total else None,
            reason=None if total else "no_observed_model_turns")
    return result


def compare_timr(left: TIMR, right: TIMR) -> TIMRComparison:
    reasons = []
    if left.task_set != right.task_set:
        reasons.append("task_set_mismatch")
    if left.metric_version != right.metric_version:
        reasons.append("metric_version_mismatch")
    if not left.coverage_complete or not right.coverage_complete:
        reasons.append("incomplete_coverage")
    if left.rate is None or right.rate is None:
        reasons.append("undefined_rate")
    return TIMRComparison(comparable=not reasons, reasons=reasons,
                          left_rate=left.rate, right_rate=right.rate,
                          delta=left.rate - right.rate if not reasons else None)
