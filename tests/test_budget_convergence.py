import pytest

from dwc.llm.budget_controller import BudgetConfig, BudgetController


def test_soft_stages_and_hard_cap_with_reserved_final():
    controller = BudgetController(BudgetConfig(
        economy_after=2, converge_after=4, hard_tool_cap=6,
        final_reserved_calls=1,
    ))

    assert controller.before_call()["stage"] == "economy"
    assert controller.before_call()["allowed"] is True
    assert controller.record_call()["stage"] == "economy"
    controller.record_call()
    assert "合并" in controller.before_call()["hint"]
    controller.record_call()
    controller.record_call()
    decision = controller.before_call()
    assert decision["stage"] == "converge"
    assert "探索" in decision["hint"]
    controller.record_call()
    decision = controller.before_call()
    assert decision["stage"] == "finalize"
    assert decision["allowed"] is False
    assert decision["denial_kind"] == "budget"
    repair = controller.before_call(purpose="repair")
    assert repair["allowed"] is True
    assert repair["stage"] == "finalize"
    assert controller.final_allowed() is True
    assert controller.record_final()["stage"] == "hard_exhausted"
    assert controller.before_call()["allowed"] is False
    assert controller.completion_status == "incomplete"


def test_only_repeated_budget_denials_trigger_best_effort_incomplete():
    controller = BudgetController(BudgetConfig(
        economy_after=1, converge_after=2, hard_tool_cap=4,
        final_reserved_calls=1, denial_stop_threshold=2,
    ))

    controller.record_denial("permission")
    assert controller.best_effort is False
    assert controller.completion_status == "in_progress"
    controller.record_denial("budget")
    assert controller.best_effort is False
    decision = controller.record_denial("budget")
    assert decision["best_effort"] is True
    assert decision["completion_status"] == "incomplete"


@pytest.mark.parametrize("kwargs", [
    {"economy_after": 2, "converge_after": 2, "hard_tool_cap": 4},
    {"economy_after": 2, "converge_after": 4, "hard_tool_cap": 4},
    {"economy_after": 1, "converge_after": 2, "hard_tool_cap": 4,
     "final_reserved_calls": 2},
])
def test_budget_thresholds_must_be_explicitly_ordered(kwargs):
    with pytest.raises(ValueError):
        BudgetConfig(**kwargs)
