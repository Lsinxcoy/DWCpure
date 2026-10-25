from dwc.observability.identity import PairIdentity


def test_stable_revision_allows_reuse_and_has_deterministic_pair_id():
    model = {
        "provider": "p",
        "route": "r",
        "requested_model": "alias",
        "reported_model": "model-a",
        "revision": "rev-1",
        "revision_status": "stable",
    }
    pair = PairIdentity(
        model=model,
        harness={"bundle_hash": "h1"},
        cache={"policy_version": "c1"},
        runtime={"profile_effective_hash": "r1"},
    )

    assert pair.identity_stability == "stable_revision"
    assert pair.cache_reuse_allowed is True
    assert pair.pair_id == PairIdentity(model=model, harness={"bundle_hash": "h1"}, cache={"policy_version": "c1"}, runtime={"profile_effective_hash": "r1"}).pair_id
    assert pair.to_dict()["model"]["revision"] == "rev-1"


def test_unknown_revision_is_scoped_to_a_fresh_observation_and_cannot_cross_periods():
    pair = PairIdentity.observation_scoped(
        model={"provider": "p", "route": "r", "requested_model": "alias", "reported_model": "model-a", "revision": None, "revision_status": "unknown"},
        harness={"bundle_hash": "h1"},
        route_observation_id="period-1",
    )
    later = PairIdentity.observation_scoped(
        model=pair.model,
        harness=pair.harness,
        route_observation_id="period-2",
    )

    assert pair.identity_stability == "observation_scoped"
    assert pair.cache_reuse_allowed is False
    assert pair.model["route_observation_id"] == "period-1"
    assert pair.pair_id != later.pair_id
    assert not pair.can_reuse(later, protocol_id="proto")
    assert pair.can_reuse(pair, protocol_id="proto")


def test_unknown_revision_requires_an_observation_id():
    import pytest

    with pytest.raises(ValueError, match="route_observation_id"):
        PairIdentity(model={"revision": None, "revision_status": "unknown"}, harness={})


def test_execution_mixture_identity_distinguishes_routes():
    first = PairIdentity.observation_scoped(model={"provider": "p", "route": "a", "requested_model": "m", "reported_model": "a", "revision": None, "revision_status": "unknown"}, harness={}, route_observation_id="run-a")
    second = PairIdentity.observation_scoped(model={"provider": "p", "route": "b", "requested_model": "m", "reported_model": "b", "revision": None, "revision_status": "unknown"}, harness={}, route_observation_id="run-b")

    assert PairIdentity.execution_mixture_id([first.pair_id, second.pair_id]) == PairIdentity.execution_mixture_id([second.pair_id, first.pair_id])
    assert PairIdentity.execution_mixture_id([first.pair_id]) != PairIdentity.execution_mixture_id([second.pair_id])


def test_protocol_and_cache_state_have_separate_deterministic_identities():
    from dwc.observability.identity import CacheStateIdentity, ProtocolIdentity

    protocol = ProtocolIdentity(task_manifest_sha256="tasks", train_ids=["a"], val_ids=["b"], heldout_ids=["c"], evaluator_id="e", evaluator_version="1", evaluator_artifact_sha256="eval", dependency_manifest_sha256="deps", synth_test_sha256_by_task={}, outcome_kind="binary_pass", rollout_rule="G=1", seed_policy="fixed", decoding_config_hash="decode", environment_profile="env", pricing_version="v1", created_before_candidate_id="base")
    cache = CacheStateIdentity(provider="p", endpoint_family="chat", model_revision_or_unknown="unknown", tokenizer_identity="tok", chat_template_identity="chat", rendering_version="render", tool_schema_identity="tools", reasoning_template_options={}, rope_config_or_unknown=None, canonical_full_message_prefix_digest="prefix", ordered_cache_operation_history_digest="ops", normalization_version="1")

    assert protocol.eval_id != protocol.to_dict()
    assert protocol.eval_id == ProtocolIdentity(**{key: value for key, value in protocol.to_dict().items() if key != "eval_id"}).eval_id
    assert cache.cache_state_id != protocol.eval_id
