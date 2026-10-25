"""独立审查阻断项回归：成本完整性与重复事件。"""
from dwc.observability.task_metrics import AttemptRecord, summarize_task_metrics
from dwc.observability.usage_pricing import UsageEvent, summarize_candidate


def attempt(aid="a1", task="t1", rollout="r1"):
    return AttemptRecord(attempt_id=aid, task_id=task, rollout_id=rollout,
                         candidate_id="c", protocol_id="p", pair_id="pair",
                         selected_formal=True, passed=True)


def usage(eid="e1", aid="a1"):
    return UsageEvent(event_id=eid, attempt_id=aid, task_id="t1", candidate_id="c",
                      requested_model="m", actual_model="m", input_tokens=1,
                      output_tokens=1, uncached_input_tokens=1,
                      billable_output_tokens=1, idempotency_key=eid)


def test_missing_formal_unit_is_not_priced():
    out = summarize_candidate([attempt()], [usage()], {"m": {
        "input_per_million": 1, "output_per_million": 1}}, requested_formal_units=2)
    assert out.mean_cost_per_task is None
    assert out.pricing_complete is False
    assert out.cost_status == "indeterminate"


def test_empty_formal_summary_has_no_zero_cost():
    out = summarize_task_metrics([], requested_formal_units=1)
    assert out.execution_cost is None
    assert out.cost_status == "indeterminate"


def test_duplicate_usage_is_idempotent_not_double_priced():
    out = summarize_candidate([attempt()], [usage(), usage()], {"m": {
        "input_per_million": 1, "output_per_million": 1}})
    assert out.mean_cost_per_task == 0.000002
    assert out.pricing_complete is True
