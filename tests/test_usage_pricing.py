from dwc.observability.usage_pricing import NormalizedUsage, price_usage


def test_cached_uncached_write_output_and_reasoning_are_priced_separately():
    usage = NormalizedUsage(
        input_tokens=100,
        cached_input_tokens=40,
        cache_write_tokens=10,
        output_tokens=20,
        reasoning_tokens=5,
        uncached_input_tokens=50,
        billable_output_tokens=25,
        output_includes_reasoning=False,
    )

    result = price_usage(usage, {
        "input_per_million": 1,
        "cached_input_per_million": 0.1,
        "cache_write_per_million": 2,
        "output_per_million": 3,
        "reasoning_per_million": 4,
    })

    assert result.cost == 0.000169
    assert result.components == {
        "uncached_input": 0.00005,
        "cached_input": 0.000004,
        "cache_write": 0.00002,
        "output": 0.000075,
        "reasoning": 0.00002,
    }
    assert result.status == "priced"


def test_missing_pricing_is_indeterminate_not_zero():
    result = price_usage(NormalizedUsage(input_tokens=10, output_tokens=2, uncached_input_tokens=10, billable_output_tokens=2), None)

    assert result.cost is None
    assert result.status == "not_configured"


def test_normalize_usage_uses_provider_reasoning_semantics_without_double_counting_cached():
    from dwc.observability.usage_pricing import normalize_usage

    usage = normalize_usage(
        {"prompt_tokens": 100, "completion_tokens": 30, "prompt_tokens_details": {"cached_tokens": 40}, "completion_tokens_details": {"reasoning_tokens": 10}},
        {"output_includes_reasoning": True},
    )

    assert usage.uncached_input_tokens == 60
    assert usage.billable_output_tokens == 30
    assert usage.output_includes_reasoning is True


def test_normalize_without_reasoning_semantics_leaves_billable_output_unknown():
    from dwc.observability.usage_pricing import normalize_usage

    usage = normalize_usage({"input_tokens": 1, "output_tokens": 3, "reasoning_tokens": 2}, {})

    assert usage.billable_output_tokens is None
    assert price_usage(usage, {"input_per_million": 1, "output_per_million": 1}).cost is None


def test_late_usage_only_adds_delta_and_conflict_never_subtracts():
    from dwc.observability.usage_pricing import reconcile_usage

    event = NormalizedUsage(input_tokens=80, output_tokens=10, uncached_input_tokens=80, billable_output_tokens=10)
    result = reconcile_usage({"input_tokens": 100, "output_tokens": 10}, [event])
    conflict = reconcile_usage({"input_tokens": 70, "output_tokens": 10}, [event])

    assert result.status == "reconciled"
    assert result.delta == 20
    assert result.event_deltas == {"input_tokens": 20, "output_tokens": 0}
    assert conflict.status == "conflict"
    assert conflict.delta is None
    assert event.input_tokens == 80


def test_summarize_candidate_prices_actual_models_and_uses_task_rollout_denominators():
    from dwc.observability.task_metrics import AttemptRecord
    from dwc.observability.usage_pricing import UsageEvent, summarize_candidate

    attempts = [AttemptRecord(attempt_id=f"a{i}", task_id="t1", candidate_id="c1", rollout_id=f"r{i}", protocol_id="p1", pair_id="expected", selected_formal=True, passed=bool(i)) for i in range(2)]
    events = [UsageEvent(event_id=f"e{i}", attempt_id=f"a{i}", task_id="t1", candidate_id="c1", requested_model="alias", actual_model=f"m{i}", pair_id=f"actual-{i}", input_tokens=1_000_000, output_tokens=0, uncached_input_tokens=1_000_000, billable_output_tokens=0) for i in range(2)]

    result = summarize_candidate(attempts, events, {"m0": {"input_per_million": 1}, "m1": {"input_per_million": 2}}, protocol_allows_mixture=True)

    assert result.execution_mixture_id
    assert result.execution_pair_ids == ["actual-0", "actual-1"]
    assert result.mean_cost_per_task == 1.5
    assert result.cost_of_pass == 3.0
    assert result.requested_formal_units == 2
    assert result.successful_formal_units == 1
    assert result.requested_tasks == 1
    assert result.cost_status == "priced"


def test_summarize_candidate_missing_usage_or_one_model_price_is_indeterminate():
    from dwc.observability.task_metrics import AttemptRecord
    from dwc.observability.usage_pricing import UsageEvent, summarize_candidate

    attempt = AttemptRecord(attempt_id="a0", task_id="t1", candidate_id="c1", rollout_id="r0", protocol_id="p1", pair_id="expected", selected_formal=True, passed=False)
    event = UsageEvent(event_id="e0", attempt_id="a0", task_id="t1", candidate_id="c1", requested_model="alias", actual_model="unknown", input_tokens=100, output_tokens=0, uncached_input_tokens=100, billable_output_tokens=0)
    result = summarize_candidate([attempt], [event], {})
    no_usage = summarize_candidate([attempt], [], {})

    assert result.mean_cost_per_task is None and result.cost_of_pass is None
    assert result.cost_status == "indeterminate"
    assert result.observed_cost_lower_bound == 0.0
    assert no_usage.usage_complete is False
    assert no_usage.cost_status == "indeterminate"


def test_unplanned_actual_pair_makes_single_pair_evaluation_indeterminate():
    from dwc.observability.task_metrics import AttemptRecord
    from dwc.observability.usage_pricing import UsageEvent, summarize_candidate

    attempt = AttemptRecord(attempt_id="a0", task_id="t1", candidate_id="c1", rollout_id="r0", protocol_id="p1", pair_id="expected", selected_formal=True, passed=True)
    event = UsageEvent(event_id="e0", attempt_id="a0", task_id="t1", candidate_id="c1", requested_model="alias", actual_model="m0", pair_id="fallback", input_tokens=0, output_tokens=0, uncached_input_tokens=0, billable_output_tokens=0)
    result = summarize_candidate([attempt], [event], {"m0": {}})

    assert result.execution_pair_ids == ["fallback"]
    assert result.measurement_status == "indeterminate"
    assert result.cost_status == "indeterminate"
    assert result.mean_cost_per_task is None


def test_reasoning_included_in_output_is_not_charged_twice():
    usage = NormalizedUsage(output_tokens=10, reasoning_tokens=4, uncached_input_tokens=0, billable_output_tokens=10, output_includes_reasoning=True)

    result = price_usage(usage, {"output_per_million": 1, "reasoning_per_million": 100})

    assert result.components["reasoning"] == 0.0
    assert result.cost == 0.00001


def test_repricing_keeps_provenance_and_zero_priced_cache_hit_is_explicit():
    usage = NormalizedUsage(input_tokens=0, output_tokens=0, uncached_input_tokens=0, billable_output_tokens=0)

    result = price_usage(usage, {"version": "v2"}, repriced_from="v1")

    assert result.cost == 0.0
    assert result.pricing_version == "v2"
    assert result.repriced_from == "v1"


def test_excluded_retry_and_cache_hit_have_separate_cost_scopes():
    from dwc.observability.task_metrics import AttemptRecord
    from dwc.observability.usage_pricing import UsageEvent, summarize_candidate

    formal = AttemptRecord(attempt_id="formal", task_id="t", candidate_id="c", rollout_id="r", protocol_id="p", pair_id="pair", selected_formal=True, passed=True, call_event_refs=["formal-event"])
    retry = AttemptRecord(attempt_id="retry", task_id="t", candidate_id="c", rollout_id="r", protocol_id="p", pair_id="pair", selected_formal=False, passed=True, call_event_refs=["retry-event"])
    events = [
        UsageEvent(event_id="formal-event", attempt_id="formal", task_id="t", candidate_id="c", requested_model="m", actual_model="m", input_tokens=1_000_000, output_tokens=0, uncached_input_tokens=1_000_000, billable_output_tokens=0),
        UsageEvent(event_id="retry-event", attempt_id="retry", task_id="t", candidate_id="c", requested_model="m", actual_model="m", cost_scope="excluded_infra", input_tokens=2_000_000, output_tokens=0, uncached_input_tokens=2_000_000, billable_output_tokens=0),
        UsageEvent(event_id="cached-event", attempt_id="formal", task_id="t", candidate_id="c", requested_model="m", actual_model="m", cost_scope="cache_hit", cache_hit=True, original_execution_ref="formal-event", input_tokens=0, output_tokens=0, uncached_input_tokens=0, billable_output_tokens=0),
    ]

    result = summarize_candidate([formal, retry], events, {"m": {"input_per_million": 1}})

    assert result.cost_scope_breakdown == {"solve_execution": 1.0, "excluded_infra": 2.0, "cache_hit": 0.0}
    assert result.mean_cost_per_task == 1.0


def test_usage_is_required_per_formal_attempt_and_cache_hit_requires_origin():
    from dwc.observability.task_metrics import AttemptRecord
    from dwc.observability.usage_pricing import UsageEvent, summarize_candidate

    attempts = [AttemptRecord(attempt_id=f"a{i}", task_id=f"t{i}", candidate_id="c", rollout_id="r", protocol_id="p", pair_id="pair", selected_formal=True, passed=True) for i in range(2)]
    event = UsageEvent(event_id="e0", attempt_id="a0", task_id="t0", candidate_id="c", requested_model="m", actual_model="m", input_tokens=0, output_tokens=0, uncached_input_tokens=0, billable_output_tokens=0)
    result = summarize_candidate(attempts, [event], {"m": {}})
    invalid_cache = UsageEvent(event_id="cache", attempt_id="a1", task_id="t1", candidate_id="c", requested_model="m", actual_model="m", cache_hit=True, original_execution_ref=None, input_tokens=0, output_tokens=0, uncached_input_tokens=0, billable_output_tokens=0)
    cache_result = summarize_candidate(attempts, [event, invalid_cache], {"m": {}})

    assert result.usage_complete is False
    assert result.cost_status == "indeterminate"
    assert cache_result.cost_status == "indeterminate"


def test_unknown_reasoning_billing_semantics_cannot_produce_a_price():
    usage = NormalizedUsage(output_tokens=5, reasoning_tokens=2, uncached_input_tokens=0, billable_output_tokens=7, output_includes_reasoning=None)

    assert price_usage(usage, {"output_per_million": 1, "reasoning_per_million": 1}).cost is None


def test_package_exports_parent_integration_api():
    from dwc.observability import AttemptRecord, CandidateEvaluation, PairIdentity, UsageEvent, normalize_usage, price_usage, reconcile_usage, select_formal_attempts, summarize_candidate

    assert all((AttemptRecord, CandidateEvaluation, PairIdentity, UsageEvent, normalize_usage, price_usage, reconcile_usage, select_formal_attempts, summarize_candidate))


def test_reconcile_covers_cached_write_and_reasoning_and_missing_usage_is_indeterminate():
    from dwc.observability.usage_pricing import UsageEvent, reconcile_usage

    event = UsageEvent(event_id="e", attempt_id="a", task_id="t", candidate_id="c", requested_model="m", actual_model="m", input_tokens=100, cached_input_tokens=20, cache_write_tokens=10, output_tokens=30, reasoning_tokens=5)
    result = reconcile_usage({"input_tokens": 110, "cached_input_tokens": 20, "cache_write_tokens": 15, "output_tokens": 30, "reasoning_tokens": 8}, [event])
    conflict = reconcile_usage({"input_tokens": 100, "cached_input_tokens": 20, "cache_write_tokens": 10, "output_tokens": 30, "reasoning_tokens": 4}, [event])
    incomplete = reconcile_usage({"input_tokens": 100}, [NormalizedUsage(status="not_reported")])

    assert result.delta == 18
    assert result.event_deltas == {"input_tokens": 10, "cached_input_tokens": 0, "cache_write_tokens": 5, "output_tokens": 0, "reasoning_tokens": 3}
    assert conflict.status == "conflict"
    assert incomplete.status == "indeterminate"
