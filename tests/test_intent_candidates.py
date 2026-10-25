import pytest

from dwc.harness.intent_candidates import (
    CandidateEdit,
    CandidatePlanError,
    build_candidate_plans,
    static_validate_plan,
)


def _diagnosis(ref="diag:1", **extra):
    return {
        "diagnosis_ref": ref,
        "scope": "invariant",
        "problem_type": "waste",
        "evidence_status": "observed",
        "evidence_refs": ["trace:1#2"],
        **extra,
    }


def test_sparse_plan_only_emits_diagnosed_cells_and_distinct_hypotheses():
    result = build_candidate_plans(
        parent_id="base-a",
        archive_snapshot_id="archive:4",
        diagnoses=[_diagnosis()],
        base_rollouts=[{"rollout_ref": "base:1"}],
    )
    assert len(result.plans) == 1
    assert result.plans[0].intent == "cost-first"
    assert result.skipped == {
        ("balanced", "domain"): "no_evidence",
        ("balanced", "invariant"): "no_evidence",
        ("cost-first", "domain"): "no_evidence",
        ("performance-first", "domain"): "no_evidence",
        ("performance-first", "invariant"): "no_evidence",
    }
    assert result.plans[0].diagnosis_refs == ("diag:1",)
    assert result.plans[0].predicted_vs_measured_status == "predicted_only"


def test_missing_base_and_unsupported_cell_are_explicit_not_promoted():
    no_base = build_candidate_plans("base-a", "archive:4", [_diagnosis()], [])
    assert no_base.plans[0].plan_status == "needs_measurement"
    unsupported = build_candidate_plans(
        "base-a", "archive:4",
        [_diagnosis(scope="domain", problem_type="waste", evidence_status="unsupported")],
        [{"rollout_ref": "base:1"}],
    )
    assert unsupported.plans == ()
    assert unsupported.skipped[("cost-first", "domain")] == "unsupported"


def test_plan_rejects_missing_evidence_and_evaluation_or_generic_edits():
    plan = build_candidate_plans(
        "base-a", "archive:4", [_diagnosis()], [{"rollout_ref": "base:1"}]
    ).plans[0]
    broken = CandidatePlanError
    with pytest.raises(broken) as exc:
        static_validate_plan(plan)
    assert "edits" in str(exc.value)
    with pytest.raises(CandidatePlanError):
        static_validate_plan(plan, edits=[CandidateEdit(
            "edit:1", "memory", "replace", "evaluator/gold.py", "content:1", ("diag:1",)
        )])
