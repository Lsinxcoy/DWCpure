"""DWC-AUTO · Fail-closed cache capability declarations; no transport or serving logic."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field, replace
from typing import Any, Mapping

_CACHE_KEYS = frozenset({"drop_message", "drop_rule", "reposition", "cache"})
_ACTIVE_ELIGIBLE = "active_eligible"
_TOKEN_KEYS = (
    "akv_cached_tokens", "repos_tokens", "drop_skipped_tokens",
    "actual_prefill_tokens", "actual_decode_tokens", "provider_cached_input_tokens",
)


@dataclass(frozen=True)
class OrdinaryFallback:
    parent_request_id: str
    cache_mode: str = "ordinary_fallback"
    cost_inclusion: str = "separate"


@dataclass(frozen=True)
class CacheUsage:
    """Observed counts; None means unknown, never zero. No savings arithmetic."""

    akv_cached_tokens: int | None = None
    repos_tokens: int | None = None
    drop_skipped_tokens: int | None = None
    actual_prefill_tokens: int | None = None
    actual_decode_tokens: int | None = None
    provider_cached_input_tokens: int | None = None

    @classmethod
    def from_response(cls, response: Mapping[str, Any]) -> "CacheUsage":
        usage = response.get("usage") or {}
        if not isinstance(usage, Mapping):
            raise ValueError("usage must be an object")
        akv = usage.get("akv") or usage.get("cache") or {}
        if not isinstance(akv, Mapping):
            raise ValueError("AKV usage must be an object")
        provider = usage.get("prompt_tokens_details") or {}
        if not isinstance(provider, Mapping):
            raise ValueError("provider usage details must be an object")
        raw = {
            "akv_cached_tokens": akv.get("cached_tokens"),
            "repos_tokens": akv.get("repos_tokens"),
            "drop_skipped_tokens": akv.get("drop_skipped_tokens"),
            "actual_prefill_tokens": akv.get("actual_prefill_tokens"),
            "actual_decode_tokens": akv.get("actual_decode_tokens"),
            "provider_cached_input_tokens": provider.get("cached_tokens"),
        }
        for key, value in raw.items():
            if value is not None and (isinstance(value, bool) or not isinstance(value, int) or not 0 <= value < 2**63):
                raise ValueError(f"{key} must be a non-negative int64 or null")
        return cls(**raw)


@dataclass(frozen=True)
class CacheWireDecision:
    """A local cache decision, deliberately distinct from a server acknowledgement."""

    extensions: Mapping[str, Any] = field(default_factory=dict)
    request_sent: bool = False
    wire_schema: str = "akv_drop_rule_v1"


@dataclass(frozen=True)
class CacheCapability:
    state: str = "unsupported_remote"
    wire_schema: str = "none"
    server_accepted: str = "not_applicable"
    endpoint_family: str | None = None
    requested_model: str | None = None
    runtime_identity: str | None = None

    def merge(self, body: Mapping[str, Any], decision: CacheWireDecision) -> dict[str, Any]:
        return merge_cache_extensions(body, decision, self)

    def observe_http(self, status: int) -> "CacheCapability":
        # A successful transport is not explicit protocol acceptance evidence.
        return replace(self, server_accepted="unknown")

    def ordinary_fallback(self, parent_request_id: str) -> OrdinaryFallback:
        return OrdinaryFallback(parent_request_id)


def merge_cache_extensions(
    body: Mapping[str, Any],
    decision: CacheWireDecision | Mapping[str, Any] | None,
    capability: CacheCapability | None | str = None,
    *,
    endpoint_family: str | None = None,
    runtime_identity: str | None = None,
) -> dict[str, Any]:
    """Return a fresh body, omitting cache fields unless all production gates match."""
    result = deepcopy(dict(body))
    for key in _CACHE_KEYS:
        result.pop(key, None)
    if not isinstance(capability, CacheCapability) or decision is None:
        return result
    if isinstance(decision, Mapping):
        decision = CacheWireDecision(extensions=decision)
    if capability.state != _ACTIVE_ELIGIBLE or capability.wire_schema != decision.wire_schema:
        return result
    if capability.requested_model is not None and body.get("model") != capability.requested_model:
        return result
    if capability.endpoint_family is not None and endpoint_family != capability.endpoint_family:
        return result
    if capability.runtime_identity is not None and runtime_identity != capability.runtime_identity:
        return result
    extensions = deepcopy(dict(decision.extensions))
    if not extensions or set(extensions) - _CACHE_KEYS:
        return result
    result.update(extensions)
    return result
