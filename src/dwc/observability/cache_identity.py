"""DWC-AUTO · Canonical, operation-history-aware cache identity (pure data only)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

from .identity import CacheStateIdentity, canonical_hash


_INT64_MAX = 2**63 - 1


def _message_id(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= _INT64_MAX:
        raise ValueError("message ids must be non-negative int64 integers, not bool")
    return value


@dataclass(frozen=True)
class CacheOperation:
    """A client instruction, not evidence that a server executed it."""

    trigger_id: int
    drop_ids: tuple[int, ...] = ()
    reposition: bool = False

    def __post_init__(self) -> None:
        trigger = _message_id(self.trigger_id)
        if not isinstance(self.reposition, bool):
            raise TypeError("reposition must be bool")
        drops = tuple(_message_id(value) for value in self.drop_ids)
        if any(value >= trigger for value in drops):
            raise ValueError("cannot drop a future or trigger message")
        if len(set(drops)) != len(drops):
            raise ValueError("drop ids must be unique within an operation")
        if tuple(sorted(drops)) != drops:
            raise ValueError("drop ids must be sorted")
        object.__setattr__(self, "trigger_id", trigger)
        object.__setattr__(self, "drop_ids", drops)

    def to_dict(self) -> dict[str, Any]:
        return {"trigger_id": self.trigger_id, "drop_ids": list(self.drop_ids), "reposition": self.reposition}


def canonical_operation_history(operations: Iterable[CacheOperation | Mapping[str, Any]]) -> tuple[CacheOperation, ...]:
    result: list[CacheOperation] = []
    dropped: set[int] = set()
    previous_trigger = -1
    for operation in operations:
        if isinstance(operation, Mapping):
            if set(operation) - {"trigger_id", "drop_ids", "reposition"}:
                raise ValueError("unknown cache operation fields")
            operation = CacheOperation(**operation)
        if not isinstance(operation, CacheOperation):
            raise TypeError("operations must be CacheOperation values")
        if operation.trigger_id <= previous_trigger:
            raise ValueError("operation triggers must be strictly increasing")
        if any(value in dropped for value in operation.drop_ids):
            raise ValueError("a message cannot be dropped twice")
        dropped.update(operation.drop_ids)
        previous_trigger = operation.trigger_id
        result.append(operation)
    return tuple(result)


def cache_state_identity(
    messages: Sequence[Mapping[str, Any]],
    operations: Iterable[CacheOperation | Mapping[str, Any]] = (),
    *,
    branch_id: str = "main",
    provider: str = "unknown",
    endpoint_family: str = "unknown",
    model_revision_or_unknown: str = "unknown",
    tokenizer_identity: str = "unknown",
    chat_template_identity: str = "unknown",
    rendering_version: str = "unknown",
    tool_schema_identity: str = "unknown",
    reasoning_template_options: Mapping[str, Any] | None = None,
    rope_config_or_unknown: Any = "unknown",
    normalization_version: str = "cache-operation-history-v1",
) -> CacheStateIdentity:
    history = canonical_operation_history(operations)
    message_list = list(messages)
    if len(message_list) > _INT64_MAX:
        raise ValueError("too many messages")
    for operation in history:
        if operation.trigger_id >= len(message_list):
            raise ValueError("operation trigger is outside the message prefix")
        if any(value >= len(message_list) for value in operation.drop_ids):
            raise ValueError("drop id is outside the message prefix")
    if not branch_id:
        raise ValueError("branch_id is required")
    # The branch is part of the rendering identity, never silently replayed across branches.
    rendering = canonical_hash({"version": rendering_version, "branch_id": branch_id})
    prefix = canonical_hash({"messages": message_list, "branch_id": branch_id})
    history_digest = canonical_hash({
        "normalization": "preserve-all-operations-v1",
        "operations": [operation.to_dict() for operation in history],
    })
    return CacheStateIdentity(
        provider=provider,
        endpoint_family=endpoint_family,
        model_revision_or_unknown=model_revision_or_unknown,
        tokenizer_identity=tokenizer_identity,
        chat_template_identity=chat_template_identity,
        rendering_version=rendering,
        tool_schema_identity=tool_schema_identity,
        reasoning_template_options=reasoning_template_options or {},
        rope_config_or_unknown=rope_config_or_unknown,
        canonical_full_message_prefix_digest=prefix,
        ordered_cache_operation_history_digest=history_digest,
        normalization_version=normalization_version,
    )
