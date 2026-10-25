"""DWC-AUTO · Deterministic, offline dual-baseline Pareto selection."""
from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Any, Iterable, Mapping

from dwc.evaluation.protocol import Protocol


@dataclass(frozen=True)
class SelectionReport:
    status: str
    retained_ids: tuple[str, ...]
    pareto_front_ids: tuple[str, ...]
    unique_parent_pool: tuple[str, ...]
    baseline_floor: float | None
    selection_eligibility: bool
    evidence_status: str
    dominated_by: dict[str, str] = field(default_factory=dict)
    reasons: dict[str, str] = field(default_factory=dict)
    sample_sizes: dict[str, int] = field(default_factory=dict)
    mode_selections: dict[str, tuple[str, ...]] = field(default_factory=dict)
    degenerate_dimensions: dict[str, tuple[str, ...]] = field(default_factory=dict)
    independent_rollback_id: str = ""


def _get(row: Any, key: str, default: Any = None) -> Any:
    return row.get(key, default) if isinstance(row, Mapping) else getattr(row, key, default)


def _finite(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _dominates(left: Any, right: Any) -> bool:
    lp, rp = _get(left, "performance"), _get(right, "performance")
    lc, rc = _get(left, "mean_cost_per_task"), _get(right, "mean_cost_per_task")
    return lp >= rp and lc <= rc and (lp > rp or lc < rc)


def select_candidate_pool(
    evaluations: Iterable[Any], *, incumbent_baseline_id: str, original_base_id: str,
    protocol: Protocol, mode_weights: Mapping[str, tuple[float, float]],
) -> SelectionReport:
    """Select from frozen records. Missing/invalid evidence is never zero."""
    rows = list(evaluations)
    ids = [str(_get(row, "candidate_id")) for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate candidate_id")
    if incumbent_baseline_id not in ids:
        raise ValueError("missing current baseline")
    if original_base_id not in ids:
        raise ValueError("missing original base")
    by_id = dict(zip(ids, rows))
    retained = tuple(ids)
    reasons: dict[str, str] = {}
    sample_sizes = {cid: int(_get(row, "completed_formal_units", 0) or 0) for cid, row in by_id.items()}
    for cid, row in by_id.items():
        if _get(row, "protocol_id") != protocol.protocol_id:
            reasons[cid] = "protocol_mismatch"
        elif _get(row, "performance_kind") != protocol.outcome_kind:
            reasons[cid] = "metric_mismatch"
        elif not _get(row, "result_set_complete", False):
            reasons[cid] = "incomplete_results"
        elif _get(row, "measurement_status") != "measured":
            reasons[cid] = "unmeasured"
        elif not _finite(_get(row, "performance")):
            reasons[cid] = "indeterminate_performance"
        elif not _get(row, "usage_complete", False) or not _get(row, "pricing_complete", False) or not _finite(_get(row, "mean_cost_per_task")):
            reasons[cid] = "indeterminate_cost"
    current = by_id[incumbent_baseline_id]
    if incumbent_baseline_id in reasons or original_base_id in reasons and reasons[original_base_id] in {"protocol_mismatch", "metric_mismatch"}:
        return SelectionReport("indeterminate", retained, (), (), None, False, "exploratory", reasons=reasons, sample_sizes=sample_sizes, independent_rollback_id=original_base_id)
    floor = float(_get(current, "performance"))
    comparable = [cid for cid in ids if cid not in reasons and _get(by_id[cid], "performance") >= floor]
    # H0 is always retained independently but cannot weaken the current floor.
    front = [cid for cid in comparable if not any(_dominates(by_id[other], by_id[cid]) for other in comparable if other != cid)]
    dominated_by = {
        cid: sorted(other for other in comparable if other != cid and _dominates(by_id[other], by_id[cid]))[0]
        for cid in comparable if cid not in front
    }
    eligible = all(sample_sizes[cid] >= protocol.min_formal_units for cid in comparable)
    if eligible:
        for cid in comparable:
            delta = float(_get(by_id[cid], "performance")) - floor
            if cid != incumbent_baseline_id and -protocol.baseline_noise_band <= delta < protocol.baseline_noise_band:
                eligible = False
                reasons[cid] = "within_baseline_noise"
    mode_selections: dict[str, tuple[str, ...]] = {}
    degenerate: dict[str, tuple[str, ...]] = {}
    for mode, weights in sorted(mode_weights.items()):
        if len(weights) != 2 or not all(_finite(w) and w >= 0 for w in weights) or sum(weights) <= 0:
            raise ValueError(f"invalid weights for {mode}")
        performances = [float(_get(by_id[cid], "performance")) for cid in front]
        costs = [float(_get(by_id[cid], "mean_cost_per_task")) for cid in front]
        dims: list[str] = []
        p_range = max(performances) - min(performances)
        c_range = max(costs) - min(costs)
        if p_range == 0:
            dims.append("performance")
        if c_range == 0:
            dims.append("cost")
        degenerate[mode] = tuple(dims)
        ranked = sorted(front, key=lambda cid: (
            weights[0] * (0.0 if p_range == 0 else (max(performances) - float(_get(by_id[cid], "performance"))) / p_range) ** 2
            + weights[1] * (0.0 if c_range == 0 else (float(_get(by_id[cid], "mean_cost_per_task")) - min(costs)) / c_range) ** 2,
            cid,
        ))
        mode_selections[mode] = tuple(ranked[:protocol.max_representatives])
    unique = tuple(sorted({cid for chosen in mode_selections.values() for cid in chosen}))
    if not eligible:
        status = "no_update"
        evidence = "exploratory"
        unique = ()
    else:
        status = "selected" if unique else "no_update"
        evidence = "independent_ready" if unique else "exploratory"
    return SelectionReport(
        status, retained, tuple(sorted(front)), unique, floor, eligible, evidence,
        dominated_by=dominated_by, reasons=reasons, sample_sizes=sample_sizes,
        mode_selections=mode_selections, degenerate_dimensions=degenerate,
        independent_rollback_id=original_base_id,
    )
