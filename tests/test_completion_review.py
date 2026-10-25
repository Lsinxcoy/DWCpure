from dwc.llm.completion_review import ReviewConfig, run_conditional_review


def test_review_is_conditional_and_keeps_usage_separate_and_actual_artifact():
    calls = []

    def reviewer(budget):
        calls.append(budget)
        return {"ok": True, "artifact_ref": "artifact/reviewed",
                "usage": {"total_tokens": 7}, "call_ids": ["review-1"],
                "budget_spent": 2}

    config = ReviewConfig(short_execution_calls=2, min_remaining_budget=2,
                          review_profiles=("deep", "research"))
    report = run_conditional_review(
        initial_artifact_ref="artifact/initial", reviewer=reviewer,
        config=config, initial_usage={"total_tokens": 11},
        initial_call_ids=["initial-1"], remaining_budget=5,
        execution_calls=1, risk_flags=(), profile="standard",
    )

    assert report["triggered"] is True
    assert report["trigger_reason"] == "short_execution"
    assert report["initial_call_ids"] == ["initial-1"]
    assert report["review_call_ids"] == ["review-1"]
    assert report["initial_usage"] == {"total_tokens": 11}
    assert report["review_usage"] == {"total_tokens": 7}
    assert report["review_budget"] == 5
    assert report["remaining_budget"] == 3
    assert report["review_outcome"] == "success"
    assert report["final_artifact_ref"] == "artifact/reviewed"
    assert calls == [5]


def test_no_condition_means_no_second_call():
    def unexpected_review(_):
        raise AssertionError("unconditional review")

    report = run_conditional_review(
        initial_artifact_ref="initial", reviewer=unexpected_review,
        config=ReviewConfig(short_execution_calls=2, min_remaining_budget=2),
        initial_usage={"total_tokens": 4}, initial_call_ids=["i"],
        remaining_budget=5, execution_calls=3, risk_flags=(), profile="standard",
    )

    assert report["triggered"] is False
    assert report["review_outcome"] == "not_run"
    assert report["remaining_budget"] == 5
    assert report["final_artifact_ref"] == "initial"


def test_failed_review_is_not_initial_success_or_artifact_replacement():
    def failed_review(_):
        return {"ok": False, "error": "timeout",
                "usage": {"total_tokens": 3}, "call_ids": ["r"],
                "artifact_ref": "unverified", "budget_spent": 1}

    report = run_conditional_review(
        initial_artifact_ref="initial", reviewer=failed_review,
        config=ReviewConfig(short_execution_calls=2, min_remaining_budget=1),
        initial_usage={"total_tokens": 4}, initial_call_ids=["i"],
        remaining_budget=2, execution_calls=1, risk_flags=("unverified_write",),
    )

    assert report["triggered"] is True
    assert report["review_outcome"] == "failed:timeout"
    assert report["review_usage"] == {"total_tokens": 3}
    assert report["remaining_budget"] == 1
    assert report["final_artifact_ref"] == "initial"


def test_review_does_not_start_below_remaining_budget_floor():
    def unexpected_review(_):
        raise AssertionError("review exceeded remaining budget")

    report = run_conditional_review(
        initial_artifact_ref="initial", reviewer=unexpected_review,
        config=ReviewConfig(short_execution_calls=3, min_remaining_budget=2),
        initial_usage=None, initial_call_ids=[], remaining_budget=1,
        execution_calls=1, risk_flags=("risk",),
    )

    assert report["triggered"] is False
    assert report["trigger_reason"] == "insufficient_budget"
