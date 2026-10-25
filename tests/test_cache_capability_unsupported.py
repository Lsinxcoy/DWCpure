from dwc.llm.cache_capability import CacheCapability, CacheWireDecision, merge_cache_extensions


def test_capability_is_bound_to_endpoint_model_and_runtime():
    capability = CacheCapability(state="active_eligible", wire_schema="akv_drop_rule_v1", endpoint_family="chat", requested_model="m1", runtime_identity="r1")
    decision = CacheWireDecision({"drop_message": [1]})
    body = {"model": "m1"}
    assert "drop_message" in merge_cache_extensions(body, decision, capability, endpoint_family="chat", runtime_identity="r1")
    assert merge_cache_extensions(body, decision, capability, endpoint_family="chat", runtime_identity="r2") == body
    assert merge_cache_extensions({"model": "m2"}, decision, capability, endpoint_family="chat", runtime_identity="r1") == {"model": "m2"}


def test_retry_reuses_same_body_and_history_without_rerunning_policy():
    capability = CacheCapability(state="active_eligible", wire_schema="akv_drop_rule_v1")
    body = {"model": "m", "messages": []}
    decision = CacheWireDecision({"drop_message": [1], "reposition": True})
    first = merge_cache_extensions(body, decision, capability)
    retry = merge_cache_extensions(body, decision, capability)
    assert retry == first
    assert retry is not first
    assert first["drop_message"] == [1]


def test_default_capability_is_unsupported_and_does_not_send_extensions():
    capability = CacheCapability()
    body = {"model": "m", "messages": [{"role": "user", "content": "hello"}]}
    decision = CacheWireDecision(extensions={"drop_message": [1]})
    merged = capability.merge(body, decision)
    assert merged == body
    assert merged is not body
    assert body == {"model": "m", "messages": [{"role": "user", "content": "hello"}]}
    assert capability.state == "unsupported_remote"
    assert decision.request_sent is False
