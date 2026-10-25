"""DWC-AUTO · Evaluation adapter for runtime task profiles.

Canonical runtime selection lives in :mod:`dwc.llm.profile` and
:mod:`dwc.llm.budget`. This module only projects the runtime choice into the
four-layer identity required by formal evaluation; it must not keep a second
classification or budget table.
"""
from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
from typing import Any, Callable

from dwc.llm import profile as _runtime_profile
from dwc.llm.task_exec import NATIVE_TOOLS_MAX_ROUNDS, NATIVE_TOOLS_REPEAT_LIMIT

PROFILE_NAMES = tuple(_runtime_profile.PROFILES)
BASE_SPEC = {
    "max_rounds": NATIVE_TOOLS_MAX_ROUNDS,
    "repeat_limit": NATIVE_TOOLS_REPEAT_LIMIT,
    "final_reserved_calls": 1,
    "output_recovery": True,
}
PROFILE_SPECS = {
    name: {
        **BASE_SPEC,
        "reasoning_effort": profile.reasoning_effort,
        "budget": asdict(profile.budget),
    }
    for name, profile in _runtime_profile.PROFILES.items()
}


def _rule_classify(task: str) -> tuple[str, str]:
    """Use the runtime rule engine; do not duplicate its thresholds."""
    info = _runtime_profile.explain(task)
    return str(info["profile"]), str(info["rule"])


def _normalize_classification(value: Any) -> tuple[str, dict[str, Any]]:
    if isinstance(value, str):
        value = {"profile": value}
    if not isinstance(value, dict):
        raise ValueError("classifier must return a profile or mapping")
    profile = value.get("profile", value.get("classified_profile", "unknown"))
    if profile not in PROFILE_NAMES:
        raise ValueError("unknown classified profile")
    return profile, value


def select_profile(task: str, *, requested_profile: str | None = None,
                   classifier: Callable[[str], Any] | None = None,
                   overrides: dict[str, Any] | None = None,
                   applied: bool = False) -> dict[str, Any]:
    """Resolve requested, classified, effective, and actually applied identity."""
    fallback_reason = ""
    classification: dict[str, Any] = {}
    if classifier is None:
        try:
            classified, rationale = _rule_classify(task)
            selection_source = "rules"
            classification = {"rationale": rationale}
        except Exception as exc:  # classifier failures must not alter execution
            classified, selection_source = "unknown", "fallback"
            fallback_reason = "classification_failed:" + type(exc).__name__
    else:
        try:
            classified, classification = _normalize_classification(classifier(task))
            selection_source = "classifier"
        except Exception as exc:
            classified, selection_source = "unknown", "fallback"
            fallback_reason = "classification_failed:" + type(exc).__name__
    if requested_profile is not None:
        if requested_profile not in PROFILE_NAMES:
            raise ValueError("unknown requested profile")
        effective, selection_source = requested_profile, "requested"
    elif classified in PROFILE_NAMES:
        effective = classified
    else:
        effective = "standard"
        selection_source = "fallback"
        fallback_reason = fallback_reason or "classification_unavailable"
    spec = dict(PROFILE_SPECS[effective])
    spec.update(overrides or {})
    actual = effective if applied else "standard"
    identity = {
        "profile_requested": requested_profile,
        "classified_profile": classified,
        "effective_profile": effective,
        "actual_profile": actual,
        "selection_source": selection_source,
        "confidence": classification.get("confidence"),
        "rationale": classification.get("rationale", "public task features"),
        "fallback_reason": fallback_reason,
        "classifier_call_id": classification.get("classifier_call_id"),
        "vote_counts": classification.get("vote_counts", {}),
        "consensus_status": classification.get("consensus_status"),
        "execution_adjustment": "applied" if applied else "shadow",
        "actual_model": None,
        "actual_reasoning_effort": spec["reasoning_effort"] if applied else None,
    }
    encoded = json.dumps({"profile": effective, "spec": spec}, sort_keys=True,
                         ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    identity["profile_effective_hash"] = hashlib.sha256(encoded).hexdigest()
    return {**identity, "spec": spec}
