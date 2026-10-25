import pytest

from dwc.harness.artifact_selector import AnonymousArtifactSelector, assign_ids, select_shadow_artifact


def test_assign_ids_canonical_sort_then_seeded_shuffle_is_reproducible():
    artifacts = [
        {"candidate_id": "c2", "delivered": True, "content": "two"},
        {"candidate_id": "base", "delivered": True, "content": "base"},
        {"candidate_id": "c1", "delivered": True, "content": "one"},
    ]
    first = assign_ids(artifacts, seed=17)
    second = assign_ids(list(reversed(artifacts)), seed=17)
    assert [a.anonymous_id for a in first] == [a.anonymous_id for a in second]
    assert first[0].content == second[0].content
    assert {a.candidate_id for a in first} == {"base", "c1", "c2"}


def test_selector_sees_only_deliverables_and_can_only_choose_existing_id():
    artifacts = [
        {"candidate_id": "base", "delivered": True, "content": "base", "cost": 100, "intent": "secret"},
        {"candidate_id": "c1", "delivered": True, "content": "candidate"},
        {"candidate_id": "empty", "delivered": True, "content": ""},
    ]
    seen = []
    def selector(pool):
        seen.append(pool)
        return next(row["anonymous_id"] for row in pool if row["deliverable"] == "candidate")
    result = select_shadow_artifact(artifacts, selector=selector, seed=4)
    assert result.status == "adopted"
    assert result.selected_candidate_id == "c1"
    assert result.dropped_candidate_ids == ("empty",)
    assert all(set(row) == {"anonymous_id", "deliverable"} for row in seen[0])


def test_invalid_or_synthesized_selector_output_falls_back_without_verification():
    artifacts = [{"candidate_id": "base", "delivered": True, "content": "base"}]
    result = select_shadow_artifact(artifacts, selector=lambda pool: "invented answer", seed=1)
    assert result.status == "selector_fallback"
    assert result.selected_candidate_id == "base"
    assert result.adopted is False
    assert result.verified is False


def test_selector_cannot_override_fixed_evaluation():
    selector = AnonymousArtifactSelector(seed=1)
    with pytest.raises(ValueError, match="shadow"):
        selector.select([], lambda pool: None, mode="production")
