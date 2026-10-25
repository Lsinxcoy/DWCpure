"""DWC-AUTO · Anonymous, deterministic shadow triage over existing deliverables only."""
from __future__ import annotations

from dataclasses import dataclass
import random
from typing import Any, Callable, Iterable, Mapping


@dataclass(frozen=True)
class AnonymousArtifact:
    anonymous_id: str
    candidate_id: str
    content: Any


@dataclass(frozen=True)
class ShadowSelection:
    status: str
    selected_candidate_id: str | None
    selected_anonymous_id: str | None
    dropped_candidate_ids: tuple[str, ...]
    adopted: bool
    verified: bool = False


def assign_ids(artifacts: Iterable[Mapping[str, Any]], *, seed: int) -> list[AnonymousArtifact]:
    ordered = sorted(artifacts, key=lambda row: str(row["candidate_id"]))
    rng = random.Random(seed)
    rng.shuffle(ordered)
    return [AnonymousArtifact(f"artifact-{index + 1}", str(row["candidate_id"]), row.get("content"))
            for index, row in enumerate(ordered)]


class AnonymousArtifactSelector:
    def __init__(self, *, seed: int, protocol_version: str = "1"):
        self.seed = seed
        self.protocol_version = protocol_version

    def select(self, artifacts: Iterable[Mapping[str, Any]],
               selector: Callable[[list[dict[str, Any]]], Any], *, mode: str = "shadow") -> ShadowSelection:
        if mode != "shadow":
            raise ValueError("anonymous artifact selection is shadow-only")
        rows = list(artifacts)
        dropped = tuple(sorted(str(row["candidate_id"]) for row in rows
                               if not row.get("delivered") or row.get("content") in (None, "", b"")))
        delivered = [row for row in rows if str(row["candidate_id"]) not in dropped]
        assigned = assign_ids(delivered, seed=self.seed)
        public = [{"anonymous_id": row.anonymous_id, "deliverable": row.content} for row in assigned]
        by_anon = {row.anonymous_id: row.candidate_id for row in assigned}
        base = next((row.candidate_id for row in assigned if row.candidate_id == "base"), None)
        try:
            choice = selector(public)
            if not isinstance(choice, str) or choice not in by_anon:
                raise ValueError("selector must return an existing anonymous id")
            return ShadowSelection("adopted", by_anon[choice], choice, dropped, True)
        except Exception:
            fallback = next((row for row in assigned if row.candidate_id == base), assigned[0] if assigned else None)
            return ShadowSelection("selector_fallback", fallback.candidate_id if fallback else None,
                                   fallback.anonymous_id if fallback else None, dropped, False)


def select_shadow_artifact(artifacts: Iterable[Mapping[str, Any]], *,
                           selector: Callable[[list[dict[str, Any]]], Any], seed: int) -> ShadowSelection:
    return AnonymousArtifactSelector(seed=seed).select(artifacts, selector)
