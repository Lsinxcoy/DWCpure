"""DWC-AUTO · Declarative, side-effect-free cache policy decisions."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from dwc.observability.cache_identity import CacheOperation

_EVIDENCE_FLAGS = (
    "referenced_by_open_hypothesis", "referenced_by_unresolved_failure",
    "contains_task_constraint", "contains_final_verification",
    "contains_source_identity", "contains_final_delivery_contract",
)


@dataclass(frozen=True)
class CachePolicySpec:
    status: str = "disabled"
    trigger: Mapping[str, Any] = field(default_factory=lambda: {"kind": "turn", "after": 0, "every": 1})
    selector: Mapping[str, Any] = field(default_factory=lambda: {"kind": "turn", "target": "tool"})
    reposition: Mapping[str, Any] = field(default_factory=lambda: {"kind": "off"})
    protected_roles: tuple[str, ...] = ("system", "user")
    max_selected_per_turn: int | None = None
    max_operations: int | None = None


@dataclass(frozen=True)
class CachePolicyDecision:
    selected_message_ids: tuple[int, ...] = ()
    new_operations: tuple[CacheOperation, ...] = ()
    reposition: bool = False
    protected_message_ids: tuple[int, ...] = ()
    cumulative_operations: tuple[CacheOperation, ...] = ()
    policy_status: str = "decided"
    counter_status: str = "not_applicable"


@dataclass(frozen=True)
class CacheToolReceipt:
    selected_message_ids: tuple[int, ...]
    status: str = "scheduled"


class CacheTool:
    """Validates/schedules locally; a receipt is not a server acceptance."""

    def __init__(self) -> None:
        self.pending_operations: tuple[int, ...] = ()

    def schedule(self, message_ids: Sequence[int], *, valid_ids: set[int], protected_ids: set[int]) -> CacheToolReceipt:
        if not isinstance(message_ids, Sequence) or isinstance(message_ids, (str, bytes)) or len(message_ids) > 64:
            raise ValueError("message_ids must be a bounded sequence")
        ids = tuple(message_ids)
        if any(isinstance(value, bool) or not isinstance(value, int) for value in ids):
            raise ValueError("message ids must be integers")
        if len(set(ids)) != len(ids) or any(value not in valid_ids or value in protected_ids for value in ids):
            raise ValueError("invalid, duplicate, or protected message id; entire call rejected")
        self.pending_operations = ids
        return CacheToolReceipt(ids)

    def read_result(self, receipt: CacheToolReceipt) -> CacheToolReceipt:
        if not isinstance(receipt, CacheToolReceipt) or receipt.selected_message_ids != self.pending_operations:
            raise ValueError("receipt does not match the scheduled operation")
        return receipt


def _scheduled(rule: Mapping[str, Any], turn: int, prompt_tokens: int, hidden_tokens: int) -> bool:
    kind = rule.get("kind", "turn")
    if kind == "token":
        return prompt_tokens - hidden_tokens > int(rule["threshold"])
    if kind != "turn":
        # model_tool 等规则只能由模型显式调用触发，绝不当作自动 turn 规则。
        return False
    after = int(rule.get("after", 0))
    every = int(rule.get("every", 1))
    if every <= 0:
        raise ValueError("every must be positive")
    return turn > after and (turn - after - 1) % every == 0


def _protected(message: Mapping[str, Any], roles: tuple[str, ...]) -> bool:
    if message.get("role") in roles or any(message.get(flag) for flag in _EVIDENCE_FLAGS):
        return True
    return bool(message.get("content")) and not (message.get("original_artifact_ref") or message.get("artifact_recovery_status") == "recoverable")


def decide_cache_policy(
    spec: CachePolicySpec,
    messages: Sequence[Mapping[str, Any]],
    *,
    turn: int,
    previous_operations: Sequence[CacheOperation] = (),
    prompt_tokens: int = 0,
    hidden_tokens: int = 0,
    counter_status: str = "not_applicable",
) -> CachePolicyDecision:
    previous = tuple(previous_operations)
    protected = tuple(message["id"] for message in messages if _protected(message, spec.protected_roles))
    token_rule = any(rule.get("kind") == "token" for rule in (spec.trigger, spec.selector, spec.reposition))
    if spec.status == "disabled":
        return CachePolicyDecision(protected_message_ids=protected, cumulative_operations=previous, policy_status="disabled", counter_status=counter_status)
    if token_rule and counter_status != "matched":
        return CachePolicyDecision(protected_message_ids=protected, cumulative_operations=previous, policy_status="base", counter_status="mismatch")
    if previous and messages and max(message["id"] for message in messages) <= previous[-1].trigger_id:
        return CachePolicyDecision(protected_message_ids=protected, cumulative_operations=previous, counter_status=counter_status)
    triggered = _scheduled(spec.trigger, turn, prompt_tokens, hidden_tokens)
    selected: tuple[int, ...] = ()
    if triggered and spec.selector.get("target", "tool") == "tool":
        already_dropped = {value for operation in previous for value in operation.drop_ids}
        if spec.selector.get("kind") == "token":
            tools = [message for message in messages if message.get("role") == "tool"]
            verified = [message.get("verified_tokens") for message in tools]
            if any(isinstance(value, bool) or not isinstance(value, int) or value < 0
                   for value in verified):
                return CachePolicyDecision(protected_message_ids=protected,
                                           cumulative_operations=previous,
                                           policy_status="base",
                                           counter_status="unverified")
            retain = int(spec.selector.get("retain_tokens", 0))
            kept_total = 0
            boundary = len(tools)
            for index in range(len(tools) - 1, -1, -1):
                if kept_total >= retain:
                    break
                kept_total += int(tools[index]["verified_tokens"])
                boundary = index
            candidates = tools[:boundary]
        else:
            retain_turns = spec.selector.get("retain_turns")
            latest_turn = max((message.get("turn", 0) for message in messages), default=0)
            cutoff = latest_turn - int(retain_turns) if retain_turns is not None else latest_turn
            candidates = [message for message in messages if message.get("role") == "tool" and message.get("turn", 0) <= cutoff]
        selected = tuple(message["id"] for message in candidates if message["id"] not in protected and message["id"] not in already_dropped)
        batches = {message.get("atomic_batch_id") for message in messages if message["id"] in selected and message.get("atomic_batch_id") is not None}
        selected = tuple(value for value in selected if all(message["id"] in selected for message in messages if message.get("atomic_batch_id") in batches))
    if spec.max_selected_per_turn is not None and len(selected) > spec.max_selected_per_turn:
        return CachePolicyDecision(protected_message_ids=protected, cumulative_operations=previous, policy_status="budget_exhausted", counter_status=counter_status)
    reposition = spec.reposition.get("kind") != "off" and _scheduled(spec.reposition, turn, prompt_tokens, hidden_tokens)
    operation_count = int(bool(selected)) + int(reposition)
    if spec.max_operations is not None and operation_count > spec.max_operations:
        return CachePolicyDecision(protected_message_ids=protected, cumulative_operations=previous, policy_status="budget_exhausted", counter_status=counter_status)
    operations: tuple[CacheOperation, ...] = ()
    if selected or reposition:
        trigger_id = max(message["id"] for message in messages) + 1
        operations = (CacheOperation(trigger_id, tuple(sorted(selected)), reposition),)
    return CachePolicyDecision(selected, operations, reposition, protected, previous + operations, counter_status=counter_status)
