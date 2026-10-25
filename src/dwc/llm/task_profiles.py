"""DWC-AUTO · Public-feature task profiles with an explicit four-layer identity."""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Callable

from dwc.llm.task_exec import NATIVE_TOOLS_MAX_ROUNDS, NATIVE_TOOLS_REPEAT_LIMIT

PROFILE_NAMES = ("lean", "standard", "deep", "research")
BASE_SPEC = {
    "max_rounds": NATIVE_TOOLS_MAX_ROUNDS,
    "repeat_limit": NATIVE_TOOLS_REPEAT_LIMIT,
    "reasoning_effort": "medium",
    "final_reserved_calls": 1,
    "output_recovery": True,
}
PROFILE_SPECS = {
    "standard": BASE_SPEC,
    "lean": {**BASE_SPEC, "reasoning_effort": "low"},
    "deep": {**BASE_SPEC, "reasoning_effort": "high"},
    "research": {**BASE_SPEC, "reasoning_effort": "high"},
}


def _rule_classify(task: str) -> tuple[str, str]:
    text = str(task or "")
    if re.search(r"research|survey|literature|sources|研究|调研|文献|检索", text, re.I):
        return "research", "public_research_keywords"
    if re.search(r"architecture|debug|refactor|analy[sz]e|设计|调试|重构|分析", text, re.I):
        return "deep", "public_complexity_keywords"
    if re.search(r"typo|rename|one[- ]line|small change|错字|重命名|一行|小改", text, re.I):
        return "lean", "public_small_change_keywords"
    return "unknown", "no_specialized_public_features"


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
