"""DWC-AUTO · Evidence-gated sparse candidate planning (final specification section 6)."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Iterable, Mapping

INTENTS = ("cost-first", "balanced", "performance-first")
SCOPES = ("invariant", "domain")
_COMPONENTS = {
    "system prompt", "guardrails", "memory", "tool guidance",
    "subagents", "skills", "scripts", "plugin/hooks",
}
_FORBIDDEN_PARTS = {"evaluator", "evaluation", "held-out", "heldout", "validation", "gold", "gates"}


class CandidatePlanError(ValueError):
    pass


@dataclass(frozen=True)
class CandidateEdit:
    edit_id: str
    component: str
    operation: str
    path: str
    content_ref: str
    evidence_refs: tuple[str, ...]


@dataclass(frozen=True)
class CandidatePlan:
    parent_id: str
    intent: str
    scope: str
    diagnosis_refs: tuple[str, ...]
    archive_snapshot_id: str
    hypothesis: str
    reference_ids: tuple[str, ...] = ()
    adopted_designs: tuple[str, ...] = ()
    rejected_designs: tuple[str, ...] = ()
    dependencies: tuple[str, ...] = ()
    evidence_limits: tuple[str, ...] = ()
    avoid: tuple[str, ...] = ()
    edits: tuple[CandidateEdit, ...] = ()
    expected_performance_effect: str = "unknown"
    expected_cost_effect: str = "unknown"
    preserved_behavior: tuple[str, ...] = ()
    regression_risks: tuple[str, ...] = ()
    acceptance_checks: tuple[str, ...] = ()
    validation_protocol: str = "shadow-probe"
    rollback_handle: str = ""
    model_route_change: bool = False
    harness_change: bool = True
    changed_axes: tuple[str, ...] = ("harness",)
    predicted_vs_measured_status: str = "predicted_only"
    plan_status: str = "proposed"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CandidatePlanBatch:
    plans: tuple[CandidatePlan, ...]
    skipped: dict[tuple[str, str], str]


def _get(value: Any, name: str, default: Any = None) -> Any:
    return value.get(name, default) if isinstance(value, Mapping) else getattr(value, name, default)


def _ref(diagnosis: Any) -> str:
    return str(_get(diagnosis, "diagnosis_ref") or _get(diagnosis, "ref") or _get(diagnosis, "id") or "")


def _intent_for(diagnosis: Any) -> str | None:
    explicit = _get(diagnosis, "intent")
    if explicit:
        return str(explicit) if explicit in INTENTS else None
    problem = str(_get(diagnosis, "problem_type", ""))
    if problem in {"waste", "cache"}:
        return "cost-first"
    if problem in {"correctness", "interface_mismatch", "capability_underuse", "harness_restriction"}:
        return "performance-first"
    if problem == "instability":
        return "balanced"
    return None


_HYPOTHESES = {
    ("cost-first", "invariant"): "Remove evidence-linked repeated exploration while preserving behavior.",
    ("cost-first", "domain"): "Remove evidence-linked domain reads and redundant verification.",
    ("balanced", "invariant"): "Balance verification and recovery cost against observed instability.",
    ("balanced", "domain"): "Improve the domain procedure without sacrificing measured cost.",
    ("performance-first", "invariant"): "Repair the observed recovery, verification, or interface failure.",
    ("performance-first", "domain"): "Add a focused check for the observed domain correctness gap.",
}


def build_candidate_plans(
    parent_id: str,
    archive_snapshot_id: str,
    diagnoses: Iterable[Any],
    base_rollouts: Iterable[Any],
) -> CandidatePlanBatch:
    """Build at most one plan per evidenced intent/scope cell, in canonical order."""
    if not parent_id or not archive_snapshot_id:
        raise CandidatePlanError("parent_id and archive_snapshot_id are required")
    base = tuple(base_rollouts)
    cells: dict[tuple[str, str], list[Any]] = {}
    skipped: dict[tuple[str, str], str] = {}
    for intent in INTENTS:
        for scope in SCOPES:
            skipped[(intent, scope)] = "no_evidence"
    for diagnosis in diagnoses:
        scope = str(_get(diagnosis, "scope", ""))
        intent = _intent_for(diagnosis)
        if scope not in SCOPES or intent is None:
            continue
        key = (intent, scope)
        if _get(diagnosis, "evidence_status") != "observed" or not _ref(diagnosis):
            skipped[key] = "unsupported"
            continue
        cells.setdefault(key, []).append(diagnosis)
    plans: list[CandidatePlan] = []
    for intent in INTENTS:
        for scope in SCOPES:
            key = (intent, scope)
            items = cells.get(key, ())
            if not items:
                continue
            refs = tuple(sorted({_ref(item) for item in items}))
            evidence_limits = tuple(sorted({str(value) for item in items for value in (_get(item, "unknowns", ()) or ())}))
            plans.append(CandidatePlan(
                parent_id=parent_id, intent=intent, scope=scope,
                diagnosis_refs=refs, archive_snapshot_id=archive_snapshot_id,
                hypothesis=_HYPOTHESES[key],
                evidence_limits=evidence_limits,
                rollback_handle=parent_id,
                plan_status="proposed" if base else "needs_measurement",
            ))
            skipped.pop(key)
    return CandidatePlanBatch(tuple(plans), skipped)


def static_validate_plan(plan: CandidatePlan, *, edits: Iterable[CandidateEdit] | None = None) -> tuple[str, ...]:
    """Raise with every error; static validation is not behavioral verification."""
    errors: list[str] = []
    selected = tuple(plan.edits if edits is None else edits)
    if plan.parent_id == "" or not plan.diagnosis_refs or not plan.hypothesis:
        errors.append("lineage_or_evidence_missing")
    if not selected:
        errors.append("edits_empty")
    ids: set[str] = set()
    for edit in selected:
        if edit.edit_id in ids:
            errors.append(f"duplicate_edit:{edit.edit_id}")
        ids.add(edit.edit_id)
        if edit.component not in _COMPONENTS:
            errors.append(f"unsupported_component:{edit.edit_id}")
        path_parts = edit.path.replace("\\", "/").lower().split("/")
        if any(part in _FORBIDDEN_PARTS for part in path_parts):
            errors.append(f"evaluation_edit_forbidden:{edit.edit_id}")
        if not edit.evidence_refs:
            errors.append(f"edit_evidence_missing:{edit.edit_id}")
    if plan.model_route_change and "model_route" not in plan.changed_axes:
        errors.append("model_route_axis_missing")
    if errors:
        raise CandidatePlanError("; ".join(errors))
    return ()
