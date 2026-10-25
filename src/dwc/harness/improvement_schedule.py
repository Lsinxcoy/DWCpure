"""DWC-AUTO · Deterministic parallel/sequential search accounting (final specification 6.5)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable, Mapping


class ScheduleError(ValueError):
    pass


@dataclass(frozen=True)
class ScheduleResult:
    mode: str
    original_base: str
    current_checkpoint: str
    checkpoints: tuple[str, ...]
    final_pool: tuple[str, ...]
    ledger: tuple[dict[str, Any], ...]


def run_improvement_schedule(
    mode: str,
    original_base: str,
    steps: Iterable[Mapping[str, Any]],
    execute: Callable[[str, Mapping[str, Any]], Mapping[str, Any]],
    *,
    execution_order: Iterable[int] | None = None,
    completed: Iterable[Mapping[str, Any]] = (),
) -> ScheduleResult:
    """Execute against explicit parents, then sort the ledger by canonical label.

    ``execution_order`` can represent already-completed concurrent work; labels,
    not completion timing, determine accounting order and sequential lineage.
    """
    if mode not in {"parallel", "sequential"}:
        raise ScheduleError("mode must be parallel or sequential")
    if not original_base:
        raise ScheduleError("original base is required")
    rows = list(steps)
    labels = [str(row.get("label", "")) for row in rows]
    if any(not label for label in labels) or len(labels) != len(set(labels)):
        raise ScheduleError("duplicate or empty schedule label")
    previous = {str(row.get("label")): dict(row) for row in completed}
    if any(label not in labels for label in previous):
        raise ScheduleError("resume label is absent from frozen schedule")
    order = list(range(len(rows))) if execution_order is None else list(execution_order)
    if sorted(order) != list(range(len(rows))):
        raise ScheduleError("execution_order must be a permutation")
    outcomes: dict[str, dict[str, Any]] = dict(previous)
    for index in order:
        row = rows[index]
        label = labels[index]
        if label in outcomes:
            continue
        parent = original_base if mode == "parallel" else _current_before(rows, index, original_base, outcomes)
        outcome = dict(execute(parent, row))
        outcome.update({"label": label, "parent_checkpoint": parent})
        outcomes[label] = outcome
    ledger: list[dict[str, Any]] = []
    current = original_base
    pool = [original_base]
    checkpoints: list[str] = []
    for sequence, label in enumerate(sorted(labels)):
        if label not in outcomes:
            raise ScheduleError(f"missing execution result: {label}")
        source = rows[labels.index(label)]
        outcome = dict(outcomes[label])
        checkpoint = str(outcome.get("checkpoint") or outcome.get("id") or "")
        if not checkpoint:
            raise ScheduleError(f"missing checkpoint: {label}")
        parent = original_base if mode == "parallel" else current
        recorded_parent = outcome.get("parent_checkpoint", parent)
        if recorded_parent != parent:
            raise ScheduleError(f"checkpoint lineage mismatch: {label}")
        restore = source.get("restore")
        if restore is not None:
            if restore != original_base and restore not in pool:
                raise ScheduleError(f"unknown restore checkpoint: {restore}")
            checkpoint = str(restore)
        entry = {
            "label": label,
            "sequence": sequence,
            "parent_checkpoint": parent,
            "checkpoint": checkpoint,
            "cost": outcome.get("cost", 0),
            "status": str(outcome.get("status", "recorded")),
        }
        ledger.append(entry)
        if mode == "sequential" or outcome.get("adopted", True):
            pool.append(checkpoint)
        if mode == "sequential":
            current = checkpoint
            if checkpoint not in checkpoints:
                checkpoints.append(checkpoint)
    return ScheduleResult(
        mode, original_base, current, tuple(checkpoints),
        tuple(dict.fromkeys(pool)), tuple(ledger),
    )


def _current_before(
    rows: list[Mapping[str, Any]], index: int, original: str,
    outcomes: Mapping[str, Mapping[str, Any]],
) -> str:
    """Sequential execution follows canonical labels, independent of completion order."""
    current = original
    for row in sorted(rows[:index], key=lambda item: str(item["label"])):
        label = str(row["label"])
        outcome = outcomes.get(label)
        if outcome is None:
            # Execute prerequisites lazily is unsafe without their executor here.
            raise ScheduleError(f"sequential prerequisite not executed: {label}")
        current = str(row.get("restore") or outcome.get("checkpoint") or outcome.get("id") or "")
    return current
