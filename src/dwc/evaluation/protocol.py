"""DWC-AUTO · Frozen evaluation protocols and deterministic result qualification."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping


@dataclass(frozen=True)
class Protocol:
    protocol_id: str = "validation-v1"
    task_manifest_sha256: str = ""
    evaluator_id: str = ""
    evaluator_version: str = ""
    evaluator_artifact_sha256: str = ""
    outcome_kind: str = "binary_pass"
    min_formal_units: int = 1
    baseline_noise_band: float = 0.0
    paired_seeds: tuple[int, ...] = ()
    min_representatives: int = 3
    max_representatives: int = 3

    def __post_init__(self) -> None:
        if self.min_formal_units < 1:
            raise ValueError("min_formal_units must be positive")
        if self.outcome_kind not in {"binary_pass", "macro_test_score"}:
            raise ValueError("unsupported outcome_kind")
        if self.baseline_noise_band < 0:
            raise ValueError("baseline_noise_band must be non-negative")
        if self.min_representatives < 1 or self.max_representatives < self.min_representatives:
            raise ValueError("invalid representative limits")


@dataclass(frozen=True)
class Qualification:
    status: str
    reasons: tuple[str, ...] = ()
    ungraded: int = 0

    @property
    def complete(self) -> bool:
        return self.status == "complete"


def _value(item: Any, key: str, default: Any = None) -> Any:
    return item.get(key, default) if isinstance(item, Mapping) else getattr(item, key, default)


def qualify_run(expected: Iterable[Any], observed: Iterable[Any], protocol: Protocol) -> Qualification:
    """Qualify one frozen run without converting missing results into failures."""
    expected_rows = list(expected)
    observed_rows = list(observed)
    reasons: list[str] = []
    expected_by_id: dict[str, Any] = {}
    for row in expected_rows:
        task_id = str(_value(row, "task_id"))
        if task_id in expected_by_id:
            raise ValueError(f"duplicate expected task: {task_id}")
        expected_by_id[task_id] = row
    observed_by_id: dict[str, Any] = {}
    status = "complete"
    for row in observed_rows:
        task_id = str(_value(row, "task_id"))
        if task_id in observed_by_id:
            reasons.append(f"duplicate_task:{task_id}")
        observed_by_id[task_id] = row
        row_status = _value(row, "status", "complete")
        if row_status == "infrastructure_error":
            status = "infrastructure_error"
        elif row_status == "evaluation_error" and status == "complete":
            status = "evaluation_error"
    unexpected = sorted(set(observed_by_id) - set(expected_by_id))
    missing = sorted(set(expected_by_id) - set(observed_by_id))
    reasons.extend(f"unexpected_task:{item}" for item in unexpected)
    reasons.extend(f"missing_task:{item}" for item in missing)
    if unexpected or len(observed_by_id) != len(observed_rows):
        status = "invalid_candidate"
    elif missing and status == "complete":
        status = "incomplete"
    ungraded = 0
    for task_id, row in observed_by_id.items():
        exp = expected_by_id.get(task_id)
        if exp is None:
            continue
        row_status = _value(row, "status", "complete")
        if row_status in {"not_run", "pending", "incomplete"}:
            reasons.append(f"ungraded:{task_id}")
            ungraded += 1
            if status == "complete":
                status = "incomplete"
            continue
        expected_tests = list(_value(exp, "test_ids", _value(exp, "tests", [])))
        observed_tests = list(_value(row, "test_ids", _value(row, "tests", [])))
        if _value(row, "total_tests", len(observed_tests)) == 0:
            reasons.append(f"zero_tests:{task_id}")
            status = "invalid_candidate"
        if expected_tests and sorted(expected_tests) != sorted(observed_tests):
            reasons.append(f"test_identity_mismatch:{task_id}")
            status = "invalid_candidate"
        expected_hash = _value(exp, "artifact_hash")
        if expected_hash is not None and _value(row, "artifact_hash") != expected_hash:
            reasons.append(f"artifact_hash_mismatch:{task_id}")
            status = "invalid_candidate"
        expected_branches = _value(exp, "branch_ids")
        if expected_branches is not None and sorted(_value(row, "branch_ids", [])) != sorted(expected_branches):
            reasons.append(f"branch_mismatch:{task_id}")
            status = "invalid_candidate"
    return Qualification(status=status, reasons=tuple(reasons), ungraded=ungraded)
