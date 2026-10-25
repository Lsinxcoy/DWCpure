import pytest

from dwc.evaluation.protocol import Protocol
from dwc.harness.pareto_select import select_candidate_pool


P = Protocol(protocol_id="p", outcome_kind="binary_pass", min_formal_units=2)


def ev(cid, performance, cost, **kw):
    row = {
        "candidate_id": cid,
        "protocol_id": "p",
        "pair_id": "pair",
        "execution_pair_ids": ["pair"],
        "performance_kind": "binary_pass",
        "performance": performance,
        "mean_cost_per_task": cost,
        "cost_of_pass": cost / max(performance, 0.01) if cost is not None else None,
        "cost_status": "priced" if cost is not None else "indeterminate",
        "usage_complete": cost is not None,
        "pricing_complete": cost is not None,
        "measurement_status": "measured",
        "result_set_complete": True,
        "completed_formal_units": 2,
        "requested_formal_units": 2,
        "role": "final",
    }
    row.update(kw)
    return row


def test_floor_frontier_representatives_and_deterministic_ties():
    evaluations = [
        ev("current", 0.6, 4, role="current"),
        ev("base", 0.5, 2, role="original_base"),
        ev("cheap", 0.7, 2),
        ev("strong", 0.8, 4),
        ev("worse", 0.55, 1),
        ev("dominated", 0.7, 3),
    ]
    report = select_candidate_pool(evaluations, incumbent_baseline_id="current", original_base_id="base", protocol=P, mode_weights={"quality": (2, 1), "economy": (1, 2)})
    assert report.baseline_floor == 0.6
    assert report.pareto_front_ids == ("cheap", "strong")
    assert report.unique_parent_pool == ("cheap", "strong")
    assert report.status == "selected"
    assert report.retained_ids == ("current", "base", "cheap", "strong", "worse", "dominated")
    assert report.mode_selections["quality"] == ("strong", "cheap")


def test_invalid_current_makes_whole_pool_indeterminate_without_h0_fallback():
    report = select_candidate_pool(
        [ev("current", 0.5, 1, result_set_complete=False), ev("base", 0.9, 1), ev("child", 0.95, 0.1)],
        incumbent_baseline_id="current", original_base_id="base", protocol=P, mode_weights={"m": (1, 1)},
    )
    assert report.status == "indeterminate"
    assert report.selection_eligibility is False
    assert report.unique_parent_pool == ()
    assert report.retained_ids == ("current", "base", "child")


def test_insufficient_statistics_forces_exploratory_no_update_even_on_pareto():
    evaluations = [
        ev("current", 0.6, 3), ev("base", 0.5, 2),
        ev("child", 0.65, 2, completed_formal_units=1),
        ev("other", 0.7, 4, measurement_status="insufficient"),
    ]
    report = select_candidate_pool(evaluations, incumbent_baseline_id="current", original_base_id="base", protocol=P, mode_weights={"m": (1, 1)})
    assert report.status == "no_update"
    assert report.evidence_status == "exploratory"
    assert report.selection_eligibility is False
    assert report.unique_parent_pool == ()
    assert report.pareto_front_ids


def test_missing_cost_cannot_be_selected_and_does_not_dominate():
    evaluations = [ev("current", 0.5, 2), ev("base", 0.4, 1), ev("unknown", 0.9, None), ev("known", 0.6, 3)]
    report = select_candidate_pool(evaluations, incumbent_baseline_id="current", original_base_id="base", protocol=P, mode_weights={"m": (1, 1)})
    assert "unknown" not in report.pareto_front_ids
    assert "unknown" not in report.unique_parent_pool
    assert report.reasons["unknown"] == "indeterminate_cost"


def test_all_lineage_roles_retained_even_when_dominated_or_filtered():
    evaluations = [
        ev("current", 0.9, 5, role="current"), ev("base", 0.1, 9, role="original_base"),
        ev("parent", 0.2, 8, role="parent"), ev("final", 0.3, 7, role="final"),
        ev("checkpoint", 0.4, 6, role="checkpoint"),
    ]
    report = select_candidate_pool(evaluations, incumbent_baseline_id="current", original_base_id="base", protocol=P, mode_weights={"m": (1, 1)})
    assert set(report.retained_ids) == {"current", "base", "parent", "final", "checkpoint"}
    assert report.unique_parent_pool == ("current",)


def test_degenerate_dimensions_and_candidate_id_tie_break():
    evaluations = [ev("current", 0.5, 1), ev("base", 0.4, 2), ev("b", 0.6, 1), ev("a", 0.6, 1)]
    report = select_candidate_pool(evaluations, incumbent_baseline_id="current", original_base_id="base", protocol=Protocol(protocol_id="p", min_formal_units=2, min_representatives=1, max_representatives=1), mode_weights={"m": (1, 1), "n": (1, 1)})
    assert "cost" in report.degenerate_dimensions["m"]
    assert report.unique_parent_pool == ("a",)
    assert report.mode_selections == {"m": ("a",), "n": ("a",)}


def test_missing_baselines_duplicate_ids_and_protocol_mismatch_fail_closed():
    with pytest.raises(ValueError, match="current"):
        select_candidate_pool([ev("base", 0.4, 1)], incumbent_baseline_id="current", original_base_id="base", protocol=P, mode_weights={})
    with pytest.raises(ValueError, match="original"):
        select_candidate_pool([ev("current", 0.4, 1)], incumbent_baseline_id="current", original_base_id="base", protocol=P, mode_weights={})
    with pytest.raises(ValueError, match="duplicate"):
        select_candidate_pool([ev("current", 0.4, 1), ev("current", 0.5, 1), ev("base", 0.4, 1)], incumbent_baseline_id="current", original_base_id="base", protocol=P, mode_weights={})
    report = select_candidate_pool([ev("current", 0.5, 1), ev("base", 0.4, 1), ev("bad", 0.9, 0.1, protocol_id="other")], incumbent_baseline_id="current", original_base_id="base", protocol=P, mode_weights={"m": (1, 1)})
    assert report.reasons["bad"] == "protocol_mismatch"
