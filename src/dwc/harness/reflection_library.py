"""DWC-AUTO · Attribution gates and prefix-visible reflection experience library (section 6.6)."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

NO_ENTRY = "NO_ENTRY"
_VERDICTS = {"helped", "hurt", "no_observed_effect", "confounded"}


@dataclass(frozen=True)
class EditEvidence:
    edit_id: str
    candidate_refs: tuple[str, ...]
    compose_decision: str
    contrast_refs: tuple[str, ...]
    verdict: str
    confounders: tuple[str, ...]
    sample_size: int
    independence: str
    attribution_status: str
    adopted: bool


@dataclass(frozen=True)
class ExperienceEntry:
    cue: str
    applicable_scope: str
    component: str
    operation: str
    supporting_contrasts: tuple[str, ...]
    edit_evidence_refs: tuple[str, ...]
    confidence: str
    confounded: bool
    source_harness_ref: str
    evaluation_version: str
    fact_scope: str
    revalidation_required: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class WriteResult:
    status: str
    reason: str | None = None
    entry_id: str | None = None


def attribute_edit(
    edit_id: str,
    candidate_refs: tuple[str, ...],
    compose_decision: str,
    contrast_refs: tuple[str, ...],
    *,
    proposed_verdict: str,
    adopted: bool,
    components: tuple[str, ...],
    isolated: bool = False,
) -> EditEvidence:
    """Attribute an edit without distributing a candidate-level delta."""
    if proposed_verdict not in _VERDICTS:
        raise ValueError("unknown edit verdict")
    confounders: list[str] = []
    if len(components) != 1 and not isolated:
        confounders.append("multiple_components_without_isolation")
    if len(contrast_refs) < 2:
        confounders.append("single_probe_or_missing_contrast")
    if len(candidate_refs) > 1 and not isolated:
        confounders.append("multiple_candidates_without_isolation")
    verdict = "confounded" if confounders else proposed_verdict
    return EditEvidence(
        edit_id, candidate_refs, compose_decision, contrast_refs, verdict,
        tuple(confounders), len(contrast_refs),
        "independent_contrasts" if len(contrast_refs) >= 2 and isolated else "limited",
        "isolated" if not confounders else "unallocated",
        adopted,
    )


class ReflectionLibrary:
    """Append-only component experience store with a frozen namespace."""

    def __init__(self, root: str | Path, *, namespace: Mapping[str, str]):
        required = ("domain", "protocol", "search_mode", "evaluator_epoch")
        if any(not str(namespace.get(key, "")) for key in required):
            raise ValueError("complete library namespace is required")
        self.root = Path(root)
        self.namespace = {key: str(namespace[key]) for key in required}
        identity = json.dumps(self.namespace, sort_keys=True, separators=(",", ":"))
        suffix = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:20]
        self.path = self.root / f"reflection-{suffix}.jsonl"

    def _rows(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        return [json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def retrieve(self, cue: str, *, sequence: int) -> tuple[ExperienceEntry, ...]:
        terms = {part.casefold() for part in cue.split() if part}
        if not terms:
            return ()
        matches: list[tuple[int, str, ExperienceEntry]] = []
        for row in self._rows():
            if int(row["sequence"]) >= sequence:
                continue
            entry = _entry_from_dict(row["entry"])
            if terms and not terms.issubset(set(entry.cue.casefold().split())):
                continue
            matches.append((int(row["sequence"]), str(row["entry_id"]), entry))
        return tuple(item[2] for item in sorted(matches))


def _entry_from_dict(value: Mapping[str, Any]) -> ExperienceEntry:
    row = dict(value)
    for key in ("supporting_contrasts", "edit_evidence_refs"):
        row[key] = tuple(row[key])
    return ExperienceEntry(**row)


def write_experience(library: ReflectionLibrary, entry: ExperienceEntry, *, sequence: int) -> WriteResult:
    """Write only a complete reusable component lesson; rejection is a success outcome."""
    if sequence < 0:
        raise ValueError("sequence must be non-negative")
    reason = _rejection_reason(entry)
    if reason:
        return WriteResult(NO_ENTRY, reason)
    payload = entry.to_dict()
    entry_id = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
    rows = library._rows()
    if any(row["entry_id"] == entry_id and int(row["sequence"]) == sequence for row in rows):
        return WriteResult("duplicate", entry_id=entry_id)
    library.path.parent.mkdir(parents=True, exist_ok=True)
    with library.path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"sequence": sequence, "entry_id": entry_id, "entry": payload}, sort_keys=True) + "\n")
    return WriteResult("written", entry_id=entry_id)


def _rejection_reason(entry: ExperienceEntry) -> str | None:
    required = {
        "cue": entry.cue, "scope": entry.applicable_scope,
        "component": entry.component, "operation": entry.operation,
        "supporting_contrasts": entry.supporting_contrasts,
        "edit_evidence_refs": entry.edit_evidence_refs,
        "source_harness_ref": entry.source_harness_ref,
        "evaluation_version": entry.evaluation_version,
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        return "missing:" + ",".join(missing)
    if entry.fact_scope not in {"domain", "invariant"}:
        return "workspace_fact_not_reusable"
    if entry.component.strip().casefold() in {"complete harness", "harness", "full harness"}:
        return "complete_harness_forbidden"
    if entry.confounded and entry.confidence == "causal":
        return "confounded_causal_claim"
    if not entry.revalidation_required:
        return "current_probe_revalidation_required"
    return None
