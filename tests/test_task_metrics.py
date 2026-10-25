from dataclasses import asdict

from dwc.observability.task_metrics import AttemptRecord, select_formal_attempts


def attempt(attempt_id, *, index=0, selected=True, passed=False, rollout="r0",
            execution_cost=1.0, execution_cost_status="priced"):
    return AttemptRecord(
        attempt_id=attempt_id,
        task_id="task-1",
        candidate_id="candidate-1",
        rollout_id=rollout,
        protocol_id="protocol-1",
        pair_id="pair-1",
        attempt_index=index,
        selected_formal=selected,
        passed=passed,
        execution_cost=execution_cost,
        execution_cost_status=execution_cost_status,
    )


def test_formal_attempts_are_one_per_task_rollout_and_never_best_of_retries():
    first = attempt("a0", index=0, selected=True, passed=False)
    retry = attempt("a1", index=1, selected=False, passed=True)
    retry.formal_exclusion_reason = "infrastructure_retry"

    selected = select_formal_attempts([retry, first])

    assert selected == [first]
    assert retry.formal_exclusion_reason == "infrastructure_retry"


def test_selection_does_not_mutate_excluded_attempt_to_add_reason():
    retry = attempt("a1", selected=False)

    select_formal_attempts([retry])

    assert retry.formal_exclusion_reason is None


def test_missing_formal_attempt_does_not_promote_retry():
    retry = attempt("a1", index=1, selected=False, passed=True)

    assert select_formal_attempts([retry]) == []


def test_selected_retry_or_duplicate_formal_unit_is_rejected_not_best_of():
    import pytest

    with pytest.raises(ValueError, match="formal attempt must be initial"):
        select_formal_attempts([attempt("a1", index=1, selected=True, passed=True)])
    with pytest.raises(ValueError, match="multiple formal attempts"):
        select_formal_attempts([attempt("a0"), attempt("a0-copy")])


def test_attempt_record_can_be_dict():
    assert asdict(attempt("a0"))["protocol_id"] == "protocol-1"


def test_c_and_cop_use_requested_units_and_zero_success_is_not_zero_cost():
    from dwc.observability.task_metrics import summarize_task_metrics

    failing = attempt("a0", passed=False)
    failing.execution_cost_status = "priced"
    missing = attempt("a1", rollout="r1", passed=True, execution_cost=None, execution_cost_status="not_reported")
    priced = summarize_task_metrics([failing, attempt("a2", rollout="r2", passed=False, execution_cost=0.0, execution_cost_status="priced")], requested_formal_units=2)
    incomplete = summarize_task_metrics([failing, missing], requested_formal_units=2)

    assert priced.mean_cost_per_unit == 0.5
    assert priced.cost_of_pass is None
    assert priced.cost_status == "zero_successes"
    assert incomplete.mean_cost_per_unit is None
    assert incomplete.cost_status == "indeterminate"


def test_usage_event_and_candidate_evaluation_can_be_dict():
    from dwc.observability.usage_pricing import UsageEvent
    from dwc.observability.task_metrics import CandidateEvaluation

    event = UsageEvent(event_id="e", attempt_id="a", task_id="t", candidate_id="c", requested_model="m", actual_model="m")
    assert event.to_dict()["actual_model"] == "m"
    evaluation = CandidateEvaluation(candidate_id="c", protocol_id="p", pair_id="pair", execution_pair_ids=["pair"], execution_mixture_id="mix", requested_tasks=0, completed_tasks=0, successful_tasks=0, requested_formal_units=0, completed_formal_units=0, successful_formal_units=0, n_rollouts=0, mean_cost_per_task=None, cost_of_pass=None, cost_status="indeterminate", usage_complete=False, pricing_complete=False, measurement_status="incomplete", result_set_complete=False)
    assert evaluation.to_dict()["execution_mixture_id"] == "mix"


def test_missing_formal_unit_stays_in_requested_denominator():
    from dwc.observability.usage_pricing import UsageEvent, summarize_candidate

    formal = attempt("a0", passed=True)
    formal.execution_cost_status = "priced"
    retry_only = attempt("a1", selected=False, passed=True, rollout="r1")
    event = UsageEvent(event_id="e0", attempt_id="a0", task_id="task-1", candidate_id="candidate-1", requested_model="m", actual_model="m", input_tokens=0, output_tokens=0, uncached_input_tokens=0, billable_output_tokens=0)

    result = summarize_candidate([formal, retry_only], [event], {"m": {}}, requested_formal_units=2)

    assert result.requested_formal_units == 2
    assert result.completed_formal_units == 1
    assert result.infra_failed_ids == ["task-1:r1"]
    assert result.result_set_complete is False
    assert result.mean_cost_per_task is None
    assert result.cost_status == "indeterminate"
    assert result.observed_cost_lower_bound == 0.0
