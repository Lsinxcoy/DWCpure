from dwc.observability.interface_trace import InterfaceTrace, compare_timr, summarize_interface_coverage, summarize_timr


def _turn(turn_id, task_id="task-1", **extra):
    return {"turn_id": turn_id, "task_id": task_id, "observed": True, **extra}


def test_timr_deduplicates_turn_and_unions_task_and_separates_recovery():
    result = summarize_timr([
        _turn("turn-1", violations=["unknown_tool", "invalid_json"],
              transport_repaired=True, interface_recovered=True, event_ref="event-1"),
        _turn("turn-1", violations=["invalid_json"], event_ref="duplicate-event"),
        _turn("turn-2", violations=[]),
        _turn("turn-3", task_id="task-2", violations=["invalid_json"]),
    ])
    assert result.observed_model_turns == 3
    assert result.violating_model_turns == 2
    assert result.rate == 2 / 3
    assert result.counts == {"unknown_tool": 1, "invalid_json": 2,
                             "argument_schema": 0, "response_protocol": 0, "final_format": 0}
    assert result.by_task["task-1"].rate == 0.5
    assert result.by_task["task-2"].rate == 1
    assert result.transport_repaired_turns == 1
    assert result.interface_recovered_turns == 1
    assert result.event_refs == ["event-1", "duplicate-event"]


def test_timr_zero_turns_is_not_zero_violations():
    empty = summarize_timr([])
    clean = summarize_timr([_turn("turn-1")])
    assert empty.rate is None
    assert empty.observed_model_turns == 0
    assert clean.rate == 0
    assert clean.violating_model_turns == 0


def test_timr_rejects_incomplete_or_mismatched_comparison():
    left = summarize_timr([_turn("1", violations=["invalid_json"])])
    right = summarize_timr([_turn("1")], task_set=["other"])
    assert compare_timr(left, right).comparable is False
    incomplete = summarize_timr([_turn("1")], coverage_complete=False)
    assert compare_timr(left, incomplete).comparable is False
    different_metric = summarize_timr([_turn("1")], metric_version="other")
    assert compare_timr(left, different_metric).comparable is False


def test_interface_coverage_is_per_dimension_and_missing_is_not_zero():
    coverage = summarize_interface_coverage([
        {"task_id": "task-1", "raw_trace_ref": "raw-1", "tool_names": ["read"],
         "argument_schemas": {"read": {"type": "object"}},
         "tool_returns": [{"status": "unknown"}], "complete_interface_turns": 2,
         "observed_model_turns": 3},
        {"task_id": "task-2", "raw_trace_ref": None, "tool_names": None,
         "argument_schemas": None, "tool_returns": None,
         "complete_interface_turns": None, "observed_model_turns": None,
         "reason": "trace_not_collected"},
    ])
    assert set(coverage) == {"raw_trace_tasks", "tool_names", "argument_schemas",
                             "tool_returns", "complete_interface_turns"}
    assert coverage["raw_trace_tasks"].to_dict() == {"checked": 1, "total": 2,
                                                      "rate": 0.5, "reason": "raw_trace_not_reported"}
    assert coverage["tool_names"].rate == 0.5
    assert coverage["tool_names"].checked == 1
    assert coverage["argument_schemas"].reason == "schema_not_reported"
    assert coverage["tool_returns"].reason == "tool_return_contract_unknown"
    assert coverage["complete_interface_turns"].reason == "trace_not_collected"
    result = summarize_timr([_turn("1")], coverage=coverage)
    assert result.coverage_complete is False
    assert compare_timr(result, result).comparable is False


def test_interface_coverage_unknown_totals_never_become_zero():
    coverage = summarize_interface_coverage([
        {"task_id": "task-1", "raw_trace_ref": None, "tool_names": None,
         "argument_schemas": None, "tool_returns": None,
         "complete_interface_turns": None, "observed_model_turns": None},
    ])
    assert all(item.rate is None for item in coverage.values())
    assert coverage["raw_trace_tasks"].checked is None
    assert coverage["raw_trace_tasks"].total is None


def test_schema_unknowns_are_not_return_contract_success():
    coverage = summarize_interface_coverage([
        {"task_id": "task-1", "raw_trace_ref": "raw", "tool_names": ["remote"],
         "argument_schemas": {"remote": {"$ref": "https://example/schema"}},
         "tool_returns": [{"contract": "unknown", "success": True}],
         "complete_interface_turns": 1, "observed_model_turns": 1},
    ])
    assert coverage["argument_schemas"].rate is None
    assert coverage["argument_schemas"].reason == "unresolved_schema_ref"
    assert coverage["tool_returns"].rate is None
    assert coverage["tool_returns"].reason == "tool_return_contract_unknown"


def test_interface_trace_preserves_provider_and_client_response_refs():
    trace = InterfaceTrace(task_id="task-1", turn_id="turn-1", request_index=2,
        response_stage="provider", offered_tools=["read"], raw_response_ref="raw-2",
        effective_response_ref="effective-2", transport_repaired=True,
        termination="stop", parse_status="invalid_json", evidence_ref="evidence-2",
        violations=["invalid_json"], interface_recovered=True)
    assert trace.observed is True
    assert trace.to_dict()["raw_response_ref"] == "raw-2"
    result = summarize_timr([trace])
    assert result.rate == 1
    assert result.transport_repaired_turns == 1
    assert result.interface_recovered_turns == 1
    assert result.event_refs == ["evidence-2"]
