import pytest

from dwc.llm.cache_capability import CacheCapability, CacheUsage, CacheWireDecision, merge_cache_extensions


@pytest.mark.parametrize("capability", [CacheCapability(), CacheCapability(state="declared_unverified"), None, "unknown"])
def test_nonproduction_capabilities_never_send_cache_fields(capability):
    body = {"model": "m", "messages": []}
    result = merge_cache_extensions(body, CacheWireDecision({"drop_message": [1], "reposition": True}), capability)
    assert result == body
    assert "drop_message" not in result and "reposition" not in result and "cache" not in result


def test_http_200_does_not_upgrade_declared_capability():
    capability = CacheCapability(state="declared_unverified")
    observed = capability.observe_http(200)
    assert observed.state == "declared_unverified"
    assert observed.server_accepted == "unknown"


def test_active_schema_mismatch_fails_closed():
    capability = CacheCapability(state="active_eligible", wire_schema="akv_drop_rule_v1")
    body = {"model": "m"}
    result = merge_cache_extensions(body, CacheWireDecision({"drop_message": [1]}, wire_schema="akv_legacy_v1"), capability)
    assert result == body


def test_ordinary_fallback_has_independent_accounting():
    fallback = CacheCapability().ordinary_fallback("request-1")
    assert fallback.cache_mode == "ordinary_fallback"
    assert fallback.parent_request_id == "request-1"
    assert fallback.cost_inclusion == "separate"


def test_nested_usage_keeps_unknown_and_distinct_token_classes():
    usage = CacheUsage.from_response({"usage": {"akv": {"cached_tokens": 8, "repos_tokens": 3, "drop_skipped_tokens": None, "actual_prefill_tokens": 5}, "prompt_tokens_details": {"cached_tokens": 2}}})
    assert usage.akv_cached_tokens == 8
    assert usage.repos_tokens == 3
    assert usage.drop_skipped_tokens is None
    assert usage.actual_prefill_tokens == 5
    assert usage.provider_cached_input_tokens == 2
    assert not hasattr(usage, "saved_tokens")


def test_drop_skipped_and_actual_prefill_can_coexist():
    usage = CacheUsage.from_response({"usage": {"akv": {"drop_skipped_tokens": 12, "actual_prefill_tokens": 7}}})
    assert usage.drop_skipped_tokens == 12
    assert usage.actual_prefill_tokens == 7


@pytest.mark.parametrize("value", ["12", -1, 2**63, True])
def test_invalid_usage_token_counts_are_malformed(value):
    with pytest.raises(ValueError):
        CacheUsage.from_response({"usage": {"akv": {"cached_tokens": value}}})
