"""DWC-AUTO · Canonical model/harness identity for measured evaluations."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from hashlib import sha256
import json
from typing import Any, Mapping


def canonical_json(value: Any) -> str:
    """Return deterministic, strict JSON (non-finite numbers are rejected)."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def canonical_hash(value: Any) -> str:
    return sha256(canonical_json(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class PairIdentity:
    model: Mapping[str, Any]
    harness: Mapping[str, Any]
    cache: Mapping[str, Any] = field(default_factory=dict)
    runtime: Mapping[str, Any] = field(default_factory=dict)
    identity_stability: str = field(init=False)
    cache_reuse_allowed: bool = field(init=False)
    pair_id: str = field(init=False)

    def __post_init__(self) -> None:
        stable = self.model.get("revision_status") == "stable" and bool(self.model.get("revision"))
        if not stable and not self.model.get("route_observation_id"):
            raise ValueError("observation-scoped identity requires route_observation_id")
        object.__setattr__(self, "identity_stability", "stable_revision" if stable else "observation_scoped")
        object.__setattr__(self, "cache_reuse_allowed", stable)
        object.__setattr__(self, "pair_id", "")
        object.__setattr__(self, "pair_id", canonical_hash(self.to_dict()))

    def to_dict(self) -> dict[str, Any]:
        return {key: value for key, value in asdict(self).items() if key != "pair_id"}

    @classmethod
    def observation_scoped(cls, *, model: Mapping[str, Any], harness: Mapping[str, Any], route_observation_id: str, cache: Mapping[str, Any] | None = None, runtime: Mapping[str, Any] | None = None) -> "PairIdentity":
        if not route_observation_id:
            raise ValueError("observation-scoped identity requires route_observation_id")
        observed = dict(model)
        observed["route_observation_id"] = route_observation_id
        return cls(model=observed, harness=harness, cache=cache or {}, runtime=runtime or {})

    def can_reuse(self, other: "PairIdentity", *, protocol_id: str, prior_protocol_id: str | None = None) -> bool:
        same_protocol = prior_protocol_id is None or prior_protocol_id == protocol_id
        if self.identity_stability == "observation_scoped" or other.identity_stability == "observation_scoped":
            return same_protocol and self.pair_id == other.pair_id
        return same_protocol and self.cache_reuse_allowed and other.cache_reuse_allowed and self.pair_id == other.pair_id

    @staticmethod
    def execution_mixture_id(execution_pair_ids: list[str] | tuple[str, ...]) -> str:
        return canonical_hash(sorted(set(execution_pair_ids)))


@dataclass(frozen=True)
class _HashedIdentity:
    def to_dict(self) -> dict[str, Any]:
        return {key: value for key, value in asdict(self).items() if not key.endswith("_id") or key in {"evaluator_id", "created_before_candidate_id", "capability_id"}}


@dataclass(frozen=True)
class ProtocolIdentity(_HashedIdentity):
    task_manifest_sha256: str
    train_ids: list[str]
    val_ids: list[str]
    heldout_ids: list[str]
    evaluator_id: str
    evaluator_version: str
    evaluator_artifact_sha256: str
    dependency_manifest_sha256: str
    synth_test_sha256_by_task: Mapping[str, str]
    outcome_kind: str
    rollout_rule: str
    seed_policy: str
    decoding_config_hash: str
    environment_profile: str
    pricing_version: str
    created_before_candidate_id: str
    eval_id: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "eval_id", "")
        object.__setattr__(self, "eval_id", canonical_hash(self.to_dict()))


@dataclass(frozen=True)
class CacheStateIdentity(_HashedIdentity):
    provider: str
    endpoint_family: str
    model_revision_or_unknown: str
    tokenizer_identity: str
    chat_template_identity: str
    rendering_version: str
    tool_schema_identity: str
    reasoning_template_options: Mapping[str, Any]
    rope_config_or_unknown: Any
    canonical_full_message_prefix_digest: str
    ordered_cache_operation_history_digest: str
    normalization_version: str
    cache_state_id: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "cache_state_id", "")
        object.__setattr__(self, "cache_state_id", canonical_hash(self.to_dict()))
