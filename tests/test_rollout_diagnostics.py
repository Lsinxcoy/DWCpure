from dwc.harness.rollout_diagnostics import diagnose_cache, diagnose_rollouts


def _rollout(rollout_id, passed, **extra):
    return {
        "task_id": "task-1",
        "candidate_id": "candidate-1",
        "pair_id": "pair-1",
        "protocol_id": "protocol-1",
        "effective_profile_hash": "profile-1",
        "rollout_id": rollout_id,
        "passed": passed,
        "trajectory_ref": f"trajectory-{rollout_id}",
        **extra,
    }


def test_rollout_diagnostics_separate_stable_flaky_waste_and_infra():
    stable = diagnose_rollouts([_rollout("a", False), _rollout("b", False)])
    flaky = diagnose_rollouts([_rollout("a", False), _rollout("b", True)])
    wasteful = diagnose_rollouts([
        _rollout("a", True, events=[{
            "event_index": 1,
            "action_key": "read:README",
            "candidate_waste": True,
            "state_digest": "same",
            "evidence_digest": "same",
            "new_information": False,
        }]),
    ])
    infra = diagnose_rollouts([
        _rollout("a", None, infrastructure_failed=True, event_refs=["infra-event"]),
        _rollout("b", None, infrastructure_failed=True),
    ])

    assert stable[0].problem_type == "correctness"
    assert stable[0].pass_pattern == "stable_failure"
    assert flaky[0].problem_type == "instability"
    assert flaky[0].pass_pattern == "flaky"
    assert wasteful[0].problem_type == "waste"
    assert wasteful[0].pass_pattern == "successful_but_wasteful"
    assert wasteful[0].redundant_event_ranges == [{"trajectory_ref": "trajectory-a", "start": 1, "end": 1}]
    assert wasteful[0].event_refs == ["trajectory-a#1"]
    assert infra[0].problem_type == "infrastructure"
    assert infra[0].pass_pattern == "infra_only"
    assert infra[0].event_refs == ["infra-event"]


def test_rollout_group_keeps_execution_identity_and_changed_state_not_waste():
    changed = _rollout("a", True, candidate_id="other", events=[
        {"event_index": 1, "action_key": "read:x", "candidate_waste": True,
         "state_changed": True},
    ])
    result = diagnose_rollouts([_rollout("a", True), changed])
    assert len(result) == 2
    assert {item.group_key["candidate_id"] for item in result} == {"candidate-1", "other"}
    assert all(item.problem_type == "stable_success" for item in result)


def test_cache_diagnosis_projects_only_reported_observations():
    result = diagnose_cache({
        "logical_tokens": 2000,
        "active_cache_reported": True,
        "physical_residency_reported": None,
        "drop_skipped": 2,
        "actual_prefill": 100,
        "evidence_refs": ["cache-event"],
        "secret_unreported_field": "do-not-project",
        "provider_claimed_hit_rate": 0.99,
    })
    assert result.to_dict() == {
        "problem_type": "cache",
        "logical_tokens": 2000,
        "active_cache_reported": True,
        "physical_residency_reported": None,
        "drop_skipped": 2,
        "actual_prefill": 100,
        "unknowns": ["physical_residency"],
        "evidence_refs": ["cache-event"],
        "evidence_status": "partial",
    }


def test_waste_requires_repeated_action_unchanged_evidence_and_no_new_information():
    events = [
        {"event_index": 1, "action_key": "read:x", "state_digest": "s0", "evidence_digest": "e0"},
        {"event_index": 2, "action_key": "read:x", "state_digest": "s0", "evidence_digest": "e0",
         "new_information": False},
        {"event_index": 3, "action_key": "read:x", "state_digest": "s0", "evidence_digest": "e0",
         "new_information": True},
        {"event_index": 4, "action_key": "verify", "effective": True},
    ]
    diagnosis = diagnose_rollouts([_rollout("a", True, events=events)])[0]
    assert diagnosis.problem_type == "waste"
    assert diagnosis.redundant_event_ranges == [{"trajectory_ref": "trajectory-a", "start": 2, "end": 2}]
    assert diagnosis.event_refs == ["trajectory-a#2"]
    assert diagnosis.repeated_action_keys == ["read:x"]
    assert diagnosis.first_effective_event_ref == "trajectory-a#4"
    assert diagnosis.cost_impact_or_unknown is None
    assert "waste_cost" in diagnosis.unknowns


def test_cache_projection_uses_cache_observation_field_names():
    result = diagnose_cache({
        "capability_id": "capability-1", "cache_mode": "akv",
        "policy_decided": True, "request_sent": True, "extension_fields_sent": True,
        "server_accepted": "unknown", "server_acceptance_basis": "not_reported",
        "usage_status": "partial", "akv_cached_tokens": 200, "repos_tokens": 50,
        "drop_skipped_tokens": 10, "actual_prefill_tokens": 300,
        "actual_decode_tokens": 20, "provider_cached_input_tokens": 80,
        "residency_or_recovery_status": "unknown", "unsupported_reason": None,
        "evidence_ref": "cache-1", "invented_hit": True,
    })
    assert result.akv_cached_tokens == 200
    assert result.drop_skipped_tokens == 10
    assert result.actual_prefill_tokens == 300
    assert result.server_accepted == "unknown"
    assert result.evidence_refs == ["cache-1"]
    assert "invented_hit" not in result.to_dict()
