"""DWC-AUTO · W5 profile metadata is wired as shadow, not behavior change."""
from __future__ import annotations

from types import SimpleNamespace


def test_task_exec_attaches_shadow_profile_without_changing_execution(monkeypatch):
    from dwc.llm import task_exec as te
    from dwc.observability import context as mc

    captured = {}
    monkeypatch.setattr(mc, "_SINK", lambda event: None)
    monkeypatch.setattr(mc, "_STORE", None)
    monkeypatch.setattr(te, "task_measurement_context", mc.task_measurement_context)

    def fake_impl(task, **kwargs):
        captured.update(kwargs)
        return {"task": task, "task_id": kwargs.get("task_id"),
                "status": "done", "actions_log": []}

    monkeypatch.setattr(te, "_execute_user_task_impl", fake_impl)
    result = te.execute_user_task("研究一下缓存论文", llm=SimpleNamespace(),
                                  task_id="T_profile", max_rounds=7)
    profile = result["runtime_profile"]
    assert captured["max_rounds"] == 7
    assert profile["effective_profile"] == "research"
    assert profile["actual_profile"] == "standard"
    assert profile["execution_adjustment"] == "shadow"
    assert profile["selection_source"] == "rules"
    assert len(result["profile_effective_hash"]) == 64
    assert "spec" not in profile
