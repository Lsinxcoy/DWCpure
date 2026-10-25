import pytest

from dwc.llm.task_profiles import select_profile


def test_short_task_uses_runtime_compact_profile_and_keeps_four_layers():
    selected = select_profile("请修复这个函数")

    assert selected["profile_requested"] is None
    assert selected["classified_profile"] == "compact"
    assert selected["effective_profile"] == "compact"
    assert selected["actual_profile"] == "standard"
    assert selected["selection_source"] == "rules"
    assert selected["fallback_reason"] == ""
    assert selected["spec"]["max_rounds"] == 15
    assert selected["spec"]["repeat_limit"] == 4
    assert selected["spec"]["budget"]["economy_after"] == 3


def test_neutral_long_task_falls_back_to_standard():
    task = "请完成这项工作。" + ("这是一段中性描述。" * 20)
    selected = select_profile(task)
    assert selected["effective_profile"] == "standard"
    assert selected["selection_source"] == "rules"


def test_requested_profile_is_distinct_from_classification_and_shadow_actual():
    selected = select_profile(
        "research the literature", requested_profile="lean",
        classifier=lambda _: {"profile": "deep", "confidence": 0.8},
    )

    assert (selected["profile_requested"], selected["classified_profile"],
            selected["effective_profile"], selected["actual_profile"]) == (
                "lean", "deep", "lean", "standard")
    assert selected["execution_adjustment"] == "shadow"
    assert selected["actual_reasoning_effort"] is None
    assert len(selected["profile_effective_hash"]) == 64


def test_classifier_failure_uses_standard_and_records_failure():
    def broken_classifier(_):
        raise TimeoutError("classifier timed out")

    selected = select_profile("research task", classifier=broken_classifier)

    assert selected["classified_profile"] == "unknown"
    assert selected["effective_profile"] == "standard"
    assert selected["fallback_reason"] == "classification_failed:TimeoutError"


@pytest.mark.parametrize("task,expected", [
    ("修复一个错字", "compact"),
    ("请审计这个架构并重构", "deep"),
    ("调研这些论文并对比多个来源", "research"),
])
def test_rule_profiles_cover_all_explicit_modes(task, expected):
    assert select_profile(task)["effective_profile"] == expected
