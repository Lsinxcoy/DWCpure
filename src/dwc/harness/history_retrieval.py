"""DWC-AUTO · 脱敏历史卡片与冻结快照检索。

历史只作参考：score / gold / question / selection verdict 永不进入卡片，
也不得回流候选生成。检索只使用 domain、failure、diagnostics 等结构事实。
"""
from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any, Iterable, Mapping

_TOKEN = re.compile(r"[a-z0-9_]+")
_FORBIDDEN_KEYS = {
    "question", "gold", "score", "selection", "validation_verdict",
    "dominance", "answer", "verdict", "reward", "grade",
}
_MODES = {"failure_similarity", "recent"}


class HistoryError(ValueError):
    """历史检索的显式契约错误。"""


@dataclass(frozen=True)
class HistoryCard:
    card_id: str
    harness_id: str
    pair_refs: tuple[str, ...]
    protocol_ref: str
    domain_contract: str
    failure_outcome: str
    diagnostics_summary: dict[str, Any]
    adopted_designs: tuple[str, ...]
    rejected_designs: tuple[str, ...]
    dependencies: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    created_sequence: int
    historical_reference_only: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "card_id": self.card_id,
            "harness_id": self.harness_id,
            "pair_refs": list(self.pair_refs),
            "protocol_ref": self.protocol_ref,
            "domain_contract": self.domain_contract,
            "failure_outcome": self.failure_outcome,
            "diagnostics_summary": dict(self.diagnostics_summary),
            "adopted_designs": list(self.adopted_designs),
            "rejected_designs": list(self.rejected_designs),
            "dependencies": list(self.dependencies),
            "evidence_refs": list(self.evidence_refs),
            "created_sequence": self.created_sequence,
            "historical_reference_only": True,
        }


@dataclass(frozen=True)
class ArchiveSnapshot:
    snapshot_id: str
    cards: tuple[HistoryCard, ...]

    def to_dict(self) -> dict[str, Any]:
        return {"snapshot_id": self.snapshot_id,
                "cards": [card.to_dict() for card in self.cards]}


def _tuple(value: Any, name: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, (list, tuple)):
        raise HistoryError(f"{name} must be a sequence")
    return tuple(str(item) for item in value)


def sanitize_history_card(raw: Mapping[str, Any]) -> HistoryCard:
    if not isinstance(raw, Mapping):
        raise HistoryError("history card must be a mapping")
    card_id = str(raw.get("card_id") or "").strip()
    if not card_id:
        raise HistoryError("history card requires card_id")
    diagnostics = raw.get("diagnostics_summary") or {}
    if not isinstance(diagnostics, Mapping):
        raise HistoryError("diagnostics_summary must be a mapping")
    diagnostics = {str(key): value for key, value in diagnostics.items()
                   if str(key).lower() not in _FORBIDDEN_KEYS}
    sequence = raw.get("created_sequence", 0)
    if not isinstance(sequence, int):
        raise HistoryError("created_sequence must be an integer")
    return HistoryCard(
        card_id=card_id,
        harness_id=str(raw.get("harness_id") or ""),
        pair_refs=_tuple(raw.get("pair_refs"), "pair_refs"),
        protocol_ref=str(raw.get("protocol_ref") or ""),
        domain_contract=str(raw.get("domain_contract") or ""),
        failure_outcome=str(raw.get("failure_outcome") or ""),
        diagnostics_summary=diagnostics,
        adopted_designs=_tuple(raw.get("adopted_designs"), "adopted_designs"),
        rejected_designs=_tuple(raw.get("rejected_designs"), "rejected_designs"),
        dependencies=_tuple(raw.get("dependencies"), "dependencies"),
        evidence_refs=_tuple(raw.get("evidence_refs"), "evidence_refs"),
        created_sequence=sequence,
        historical_reference_only=True,
    )


def freeze_archive_snapshot(raw_cards: Iterable[Mapping[str, Any]], *,
                             snapshot_id: str) -> ArchiveSnapshot:
    cards = [sanitize_history_card(raw) for raw in raw_cards]
    ids = [card.card_id for card in cards]
    if len(ids) != len(set(ids)):
        raise HistoryError("duplicate card_id in archive snapshot")
    ordered = tuple(sorted(cards, key=lambda card: (card.created_sequence, card.card_id)))
    return ArchiveSnapshot(snapshot_id=str(snapshot_id), cards=ordered)


def _tokens(value: str) -> set[str]:
    return set(_TOKEN.findall(value.lower()))


def _domain_similarity(card: HistoryCard, query: Mapping[str, Any]) -> float:
    card_tokens = _tokens(card.domain_contract)
    query_tokens = _tokens(str(query.get("domain_contract") or ""))
    if not card_tokens or not query_tokens:
        return 0.0
    return len(card_tokens & query_tokens) / len(query_tokens)


def _diagnostic_similarity(card: HistoryCard, query: Mapping[str, Any]) -> float:
    wanted = query.get("diagnostics_summary") or {}
    if not isinstance(wanted, Mapping) or not wanted:
        return 0.0
    matches = sum(
        1 for key, value in wanted.items()
        if card.diagnostics_summary.get(key) == value
    )
    return matches / len(wanted)


def _score(card: HistoryCard, query: Mapping[str, Any]) -> float:
    domain = _domain_similarity(card, query)
    wanted_failure = str(query.get("failure_outcome") or "")
    failure = 1.0 if wanted_failure and card.failure_outcome == wanted_failure else 0.0
    diagnostics = _diagnostic_similarity(card, query)
    return 0.6 * domain + 0.4 * failure + 0.2 * diagnostics


def retrieve_history(cards: Iterable[HistoryCard], query: Mapping[str, Any], *,
                     mode: str, limit: int | None = None) -> tuple[HistoryCard, ...]:
    if mode not in _MODES:
        raise HistoryError(f"unsupported history retrieval mode: {mode}")
    if limit is not None and (not isinstance(limit, int) or limit < 0):
        raise HistoryError("limit must be a non-negative integer")
    items = tuple(cards)
    if mode == "recent":
        ordered = sorted(items, key=lambda card: (-card.created_sequence, card.card_id))
    else:
        scored = [(card, _score(card, query)) for card in items]
        scored = [(card, score) for card, score in scored if score > 0.0]
        ordered = [card for card, _ in sorted(
            scored, key=lambda item: (-item[1], -item[0].created_sequence, item[0].card_id)
        )]
    return tuple(ordered[:limit] if limit is not None else ordered)
