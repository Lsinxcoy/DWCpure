import pytest

from dwc.evaluation.protocol import Protocol, qualify_run


def protocol():
    return Protocol(
        protocol_id="p1",
        task_manifest_sha256="a" * 64,
        evaluator_id="tests",
        evaluator_version="1",
        evaluator_artifact_sha256="b" * 64,
        outcome_kind="binary_pass",
        min_formal_units=3,
        baseline_noise_band=0.05,
    )


def test_protocol_is_frozen_and_validates_statistical_policy():
    p = protocol()
    with pytest.raises(AttributeError):
        p.min_formal_units = 1
    with pytest.raises(ValueError, match="min_formal_units"):
        Protocol(min_formal_units=0)
    with pytest.raises(ValueError, match="outcome_kind"):
        Protocol(outcome_kind="other")


def test_qualification_distinguishes_missing_duplicate_and_unexpected_results():
    p = protocol()
    expected = [{"task_id": "a", "test_ids": ["t1"], "artifact_hash": "h"}]
    valid = [{"task_id": "a", "test_ids": ["t1"], "artifact_hash": "h", "total_tests": 1, "status": "complete"}]
    assert qualify_run(expected, valid, p).status == "complete"
    assert qualify_run(expected, [], p).status == "incomplete"
    assert qualify_run(expected, valid + valid, p).status == "invalid_candidate"
    assert qualify_run(expected, [{**valid[0], "task_id": "b"}], p).status == "invalid_candidate"


def test_qualification_checks_tests_identity_artifact_and_execution_errors():
    p = protocol()
    expected = [{"task_id": "a", "test_ids": ["t1"], "artifact_hash": "h"}]
    base = {"task_id": "a", "artifact_hash": "h", "total_tests": 1, "status": "complete"}
    cases = [
        ({**base, "test_ids": ["t1"], "total_tests": 0}, "invalid_candidate"),
        ({**base, "test_ids": ["different"]}, "invalid_candidate"),
        ({**base, "test_ids": ["t1"], "artifact_hash": "changed"}, "invalid_candidate"),
        ({**base, "test_ids": ["t1"], "status": "not_run"}, "incomplete"),
        ({**base, "test_ids": ["t1"], "status": "infrastructure_error"}, "infrastructure_error"),
        ({**base, "test_ids": ["t1"], "status": "evaluation_error"}, "evaluation_error"),
    ]
    for observed, status in cases:
        result = qualify_run(expected, [observed], p)
        assert result.status == status
        assert result.complete is False


def test_formal_attempt_selection_reuses_observability_rules():
    from dwc.evaluation import select_formal_attempts
    from dwc.observability.task_metrics import select_formal_attempts as original
    assert select_formal_attempts is original
