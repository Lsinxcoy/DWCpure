import pytest

from dwc.llm.cache_policy import CachePolicySpec, CacheTool, decide_cache_policy


def test_false_trigger_never_selects_and_reposition_is_independent():
    spec = CachePolicySpec(status="shadow", trigger={"kind": "turn", "after": 99}, reposition={"kind": "turn", "after": 0, "every": 1})
    decision = decide_cache_policy(spec, [{"id": 0, "role": "tool", "turn": 1}], turn=1)
    assert all(not operation.drop_ids for operation in decision.new_operations)
    assert decision.reposition is True
    assert decision.selected_message_ids == ()


def messages():
    return [
        {"id": 0, "role": "system", "content": "rules", "turn": 1},
        {"id": 1, "role": "tool", "turn": 1, "atomic_batch_id": "b1", "content": "a", "original_artifact_ref": "raw:a"},
        {"id": 2, "role": "tool", "turn": 1, "atomic_batch_id": "b1", "content": "b", "original_artifact_ref": "raw:b"},
        {"id": 3, "role": "tool", "turn": 2, "referenced_by_unresolved_failure": True},
        {"id": 4, "role": "tool", "turn": 2, "contains_final_verification": True},
        {"id": 5, "role": "tool", "turn": 2, "content": "ordinary", "original_artifact_ref": "raw:ordinary"},
    ]


def test_selector_keeps_protected_evidence_and_whole_batches():
    spec = CachePolicySpec(status="shadow")
    decision = decide_cache_policy(spec, messages(), turn=3)
    assert decision.selected_message_ids == (1, 2, 5)
    assert decision.protected_message_ids == (0, 3, 4)


def test_batch_with_protected_member_is_not_partially_dropped():
    data = messages()
    data[2]["contains_task_constraint"] = True
    decision = decide_cache_policy(CachePolicySpec(status="shadow"), data, turn=3)
    assert 1 not in decision.selected_message_ids
    assert 2 not in decision.selected_message_ids


def test_token_counter_mismatch_disables_token_rules_with_base_decision():
    spec = CachePolicySpec(status="shadow", trigger={"kind": "token", "threshold": 1}, reposition={"kind": "token", "threshold": 1})
    decision = decide_cache_policy(spec, messages(), turn=3, prompt_tokens=100, hidden_tokens=0, counter_status="mismatch")
    assert decision.policy_status == "base"
    assert decision.counter_status == "mismatch"
    assert decision.new_operations == () and decision.reposition is False


def test_token_threshold_is_strict():
    spec = CachePolicySpec(status="shadow", trigger={"kind": "token", "threshold": 100})
    decision = decide_cache_policy(spec, messages(), turn=3, prompt_tokens=100, hidden_tokens=0, counter_status="matched")
    assert decision.new_operations == ()


def test_max_selected_overflow_keeps_base_instead_of_truncating():
    spec = CachePolicySpec(status="shadow", max_selected_per_turn=1)
    decision = decide_cache_policy(spec, messages(), turn=3)
    assert decision.policy_status == "budget_exhausted"
    assert decision.selected_message_ids == () and decision.new_operations == ()


def test_previous_operations_are_preserved():
    spec = CachePolicySpec(status="shadow")
    first = decide_cache_policy(spec, messages(), turn=3)
    second = decide_cache_policy(spec, messages(), turn=4, previous_operations=first.cumulative_operations)
    assert second.cumulative_operations[:len(first.cumulative_operations)] == first.cumulative_operations


def test_invalid_tool_id_rejects_entire_batch_and_receipt_is_only_scheduled():
    tool = CacheTool()
    receipt = tool.schedule([1, 2], valid_ids={1, 2}, protected_ids=set())
    assert receipt.status == "scheduled"
    with pytest.raises(ValueError):
        CacheTool().schedule([1, 999], valid_ids={1, 2}, protected_ids=set())
    assert CacheTool().pending_operations == ()


def test_turn_selector_retains_recent_complete_turn():
    spec = CachePolicySpec(status="shadow", selector={"kind": "turn", "target": "tool", "retain_turns": 1})
    decision = decide_cache_policy(spec, messages(), turn=3)
    assert decision.selected_message_ids == (1, 2)


def test_tool_evidence_without_recoverable_original_is_protected():
    data = [{"id": 0, "role": "tool", "turn": 1, "content": "irreplaceable"}]
    decision = decide_cache_policy(CachePolicySpec(status="shadow"), data, turn=2)
    assert decision.selected_message_ids == ()
    assert decision.protected_message_ids == (0,)


def test_no_new_messages_do_not_duplicate_operations_or_reposition():
    spec = CachePolicySpec(status="shadow", reposition={"kind": "turn", "after": 0})
    first = decide_cache_policy(spec, messages(), turn=3)
    second = decide_cache_policy(spec, messages(), turn=4, previous_operations=first.cumulative_operations)
    assert second.new_operations == ()
    assert second.cumulative_operations == first.cumulative_operations


def test_model_tool_rules_do_not_run_as_automatic_turn_rules():
    spec = CachePolicySpec(status="shadow", trigger={"kind": "model_tool"}, selector={"kind": "model_tool", "target": "tool"}, reposition={"kind": "model_tool"})
    decision = decide_cache_policy(spec, messages(), turn=3)
    assert decision.new_operations == () and decision.reposition is False


def test_token_selector_uses_verified_token_counts_and_retains_recent_budget():
    data = [
        {"id": 0, "role": "tool", "turn": 1, "verified_tokens": 10},
        {"id": 1, "role": "tool", "turn": 2, "verified_tokens": 7},
        {"id": 2, "role": "tool", "turn": 3, "verified_tokens": 5},
    ]
    spec = CachePolicySpec(status="shadow", selector={"kind": "token", "target": "tool", "retain_tokens": 5})
    decision = decide_cache_policy(spec, data, turn=4, counter_status="matched")
    assert decision.selected_message_ids == (0, 1)
