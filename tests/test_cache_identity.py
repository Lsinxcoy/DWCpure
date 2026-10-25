import pytest

from dwc.observability.cache_identity import CacheOperation, cache_state_identity, canonical_operation_history


def _identity(history, branch="main"):
    return cache_state_identity(
        [{"role": "assistant", "content": value} for value in ("A", "B", "C")],
        history,
        branch_id=branch,
    )


def test_cache_identity_depends_on_ordered_history_and_branch():
    after_c = [CacheOperation(2, (0,))]
    before_c = [CacheOperation(1, (0,))]
    assert _identity(after_c).cache_state_id != _identity(before_c).cache_state_id
    assert _identity([]).cache_state_id != _identity(after_c).cache_state_id
    assert _identity(after_c, "other").cache_state_id != _identity(after_c).cache_state_id


def test_operation_ids_must_be_ordinary_bounded_integers():
    with pytest.raises((TypeError, ValueError)):
        CacheOperation(True)


def test_identity_normalizes_message_key_order_but_preserves_operation_order():
    left = cache_state_identity([{"role": "tool", "content": "x", "name": "n"}], [])
    right = cache_state_identity([{"name": "n", "content": "x", "role": "tool"}], [])
    assert left.cache_state_id == right.cache_state_id
    assert left.cache_state_id != cache_state_identity([{"role": "tool", "content": "y", "name": "n"}], []).cache_state_id


def test_no_ops_are_not_silently_erased_from_history():
    messages = [{"role": "assistant", "content": "x"}]
    with_noop = cache_state_identity(messages, [CacheOperation(0)])
    without_noop = cache_state_identity(messages, [])
    assert with_noop.cache_state_id != without_noop.cache_state_id


@pytest.mark.parametrize("kwargs", [
    {"trigger_id": -1}, {"trigger_id": 2**63}, {"trigger_id": 1.0},
    {"trigger_id": 2, "drop_ids": (2,)}, {"trigger_id": 2, "drop_ids": (1, 1)},
    {"trigger_id": 2, "drop_ids": (2, 1)},
])
def test_invalid_operations_fail_closed(kwargs):
    with pytest.raises((TypeError, ValueError)):
        CacheOperation(**kwargs)


def test_duplicate_triggers_and_cross_branch_replay_are_rejected():
    operation = CacheOperation(1)
    with pytest.raises(ValueError):
        canonical_operation_history([operation, operation])
