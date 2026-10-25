"""DWC-AUTO · W5 has one runtime source of truth: llm.budget + llm.profile."""
from __future__ import annotations

from dataclasses import asdict
import inspect

from dwc.llm import profile as runtime_profile
from dwc.llm import task_exec as te
from dwc.llm import task_profiles as adapter


def test_runtime_task_loop_uses_upstream_budget_and_profile_only():
    module_source = inspect.getsource(te)
    impl_source = inspect.getsource(te._execute_user_task_impl)
    assert "from dwc.llm import budget as _budget" in module_source
    assert "from dwc.llm import profile as _profile" in impl_source
    assert "budget_controller" not in module_source
    assert "budget_controller" not in impl_source


def test_adapter_specs_match_runtime_profile_budgets():
    assert adapter.PROFILE_NAMES == tuple(runtime_profile.PROFILES)
    for name, profile in runtime_profile.PROFILES.items():
        spec = adapter.PROFILE_SPECS[name]
        assert spec["budget"] == asdict(profile.budget)
        assert spec["reasoning_effort"] == profile.reasoning_effort


def test_adapter_delegates_classification_to_runtime_rules(monkeypatch):
    monkeypatch.setattr(runtime_profile, "explain", lambda task: {
        "profile": "deep", "rule": "test_override", "signals": {"len": len(task)},
    })
    selected = adapter.select_profile("anything")
    assert selected["classified_profile"] == "deep"
    assert selected["effective_profile"] == "deep"
    assert selected["rationale"] == "test_override"
    assert selected["selection_source"] == "rules"
