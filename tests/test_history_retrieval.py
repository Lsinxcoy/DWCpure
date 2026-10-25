import json

import pytest

from dwc.harness.history_retrieval import (
    HistoryCard,
    HistoryError,
    freeze_archive_snapshot,
    retrieve_history,
    sanitize_history_card,
)


def _raw(card_id="card:1", **extra):
    return {
        "card_id": card_id,
        "harness_id": "h1",
        "pair_refs": ["pair:1"],
        "protocol_ref": "probe:p1",
        "domain_contract": "python file repair",
        "failure_outcome": "stable_failure",
        "diagnostics_summary": {"problem_type": "correctness", "scope": "domain"},
        "adopted_designs": ["component:1"],
        "rejected_designs": [],
        "dependencies": [],
        "evidence_refs": ["trace:1#4"],
        "created_sequence": 3,
        "question": "private task text",
        "gold": "answer",
        "score": 0.9,
        "selection": {"dominance": True, "validation_verdict": "pass"},
        **extra,
    }


def test_history_projection_drops_score_gold_question_and_validation_payloads():
    card = sanitize_history_card(_raw())
    assert card.historical_reference_only
    encoded = json.dumps(card.to_dict(), sort_keys=True)
    for forbidden in ("private task text", "answer", "0.9", "dominance", "validation_verdict", "gold", "question", "score"):
        assert forbidden not in encoded


def test_frozen_snapshot_does_not_change_with_future_archive_writes():
    first = freeze_archive_snapshot([_raw()], snapshot_id="archive:1")
    second = freeze_archive_snapshot([_raw(), _raw("card:2", created_sequence=4)], snapshot_id="archive:2")
    assert [card.card_id for card in first.cards] == ["card:1"]
    assert [card.card_id for card in second.cards] == ["card:1", "card:2"]


def test_deterministic_failure_similarity_and_recent_with_ties():
    cards = [
        sanitize_history_card(_raw("b", domain_contract="python repair", failure_outcome="flaky", created_sequence=9)),
        sanitize_history_card(_raw("a", domain_contract="python repair", failure_outcome="stable_failure", created_sequence=1)),
        sanitize_history_card(_raw("c", domain_contract="sql query repair", failure_outcome="stable_failure", created_sequence=8)),
    ]
    similar = retrieve_history(cards, {"domain_contract": "python repair", "failure_outcome": "stable_failure"}, mode="failure_similarity")
    assert [item.card_id for item in similar] == ["a", "c", "b"]
    recent = retrieve_history(cards, {}, mode="recent")
    assert [item.card_id for item in recent] == ["b", "c", "a"]


def test_zero_vector_duplicate_ids_and_empty_history_are_explicit():
    assert retrieve_history([], {}, mode="failure_similarity") == ()
    zero = sanitize_history_card(_raw(domain_contract="", failure_outcome="", diagnostics_summary={}))
    assert retrieve_history([zero], {"domain_contract": "unrelated"}, mode="failure_similarity") == ()
    with pytest.raises(HistoryError, match="duplicate"):
        freeze_archive_snapshot([_raw(), _raw()], snapshot_id="archive:x")
    with pytest.raises(HistoryError, match="mode"):
        retrieve_history([], {}, mode="latest")
