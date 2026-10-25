"""DWC-AUTO · W1 任务测量上下文（拟实现接口的测试）。"""
import json
from types import SimpleNamespace


def test_task_wrapper_finalizes_early_return_and_assigns_roles(monkeypatch, tmp_path):
    from dwc.llm import task_exec as te
    from dwc.observability import context as mc
    from dwc.observability.evidence_store import EvidenceStore

    events = []
    store = EvidenceStore(tmp_path / "task_metrics.sqlite")
    monkeypatch.setattr(mc, "_SINK", events.append)
    monkeypatch.setattr(mc, "_STORE", store)
    monkeypatch.setattr(te, "_execute_user_task_impl", lambda task, **kw: {
        "task": task, "task_id": kw.get("task_id"), "status": "incomplete",
        "why": "synthetic early return", "actions_log": []})
    monkeypatch.setattr(te, "task_measurement_context", mc.task_measurement_context)

    def fake_impl(task, **kw):
        mc.emit_llm_observation({"kind": "llm_attempt", "call_id": "c1",
                                 "usage": {"prompt_tokens": 10,
                                           "completion_tokens": 2,
                                           "total_tokens": 12}})
        return {"task": task, "task_id": kw.get("task_id"),
                "status": "incomplete", "why": "synthetic early return",
                "actions_log": []}

    monkeypatch.setattr(te, "_execute_user_task_impl", fake_impl)

    result = te.execute_user_task("demo", llm=SimpleNamespace(), task_id="T_measure")
    assert result["measurement_status"] == "measured"
    task_events = [e for e in events if e.get("kind") == "task_metrics"]
    assert len(task_events) == 1
    assert task_events[0]["task_id"] == "T_measure"
    assert task_events[0]["status"] == "incomplete"
    assert result["measurement_ref"] == task_events[0]["record_id"]
    assert store.query("task_metrics", task_id="T_measure")[0]["record_id"] == result["measurement_ref"]
    store.close()


def test_zero_llm_task_is_not_measured_even_when_persisted(monkeypatch, tmp_path):
    from dwc.llm import task_exec as te
    from dwc.observability import context as mc
    from dwc.observability.evidence_store import EvidenceStore

    store = EvidenceStore(tmp_path / "task_metrics.sqlite")
    monkeypatch.setattr(mc, "_SINK", lambda event: None)
    monkeypatch.setattr(mc, "_STORE", store)
    monkeypatch.setattr(te, "task_measurement_context", mc.task_measurement_context)
    monkeypatch.setattr(te, "_execute_user_task_impl", lambda task, **kw: {
        "task": task, "task_id": kw.get("task_id"), "status": "done",
        "actions_log": []})

    result = te.execute_user_task("demo", llm=SimpleNamespace(), task_id="T_zero")

    assert result["measurement_status"] == "incomplete"
    stored = store.query("task_metrics", task_id="T_zero")[0]["payload"]
    assert stored["measurement_status"] == "incomplete"
    assert stored["llm_attempts"] == 0
    assert stored["usage_status"] == "not_reported"
    store.close()


def test_nested_revision_and_retry_roles(monkeypatch):
    from dwc.llm import task_exec as te
    from dwc.observability import context as mc

    events = []
    monkeypatch.setattr(mc, "_SINK", events.append)
    monkeypatch.setattr(te, "task_measurement_context", mc.task_measurement_context)

    def fake_impl(task, **kw):
        mc.emit_llm_observation({"kind": "llm_attempt", "call_id": "outer"})
        if not kw.get("_depth"):
            with mc.measurement_role("revision"):
                mc.emit_llm_observation({"kind": "llm_attempt", "call_id": "plan"})
                te.execute_user_task(task + " retry", llm=kw["llm"], _depth=1)
        return {"task": task, "status": "done", "actions_log": []}

    monkeypatch.setattr(te, "_execute_user_task_impl", fake_impl)
    te.execute_user_task("demo", llm=SimpleNamespace(), task_id="T_roles")
    calls = {e["call_id"]: e["call_role"] for e in events if e.get("kind") == "llm_attempt"}
    assert calls == {"outer": "solver", "plan": "revision"}


def test_concurrent_task_context_does_not_cross(monkeypatch):
    import threading
    from dwc.observability import context as mc
    events = []
    lock = threading.Lock()
    def sink(e):
        with lock:
            events.append(e)
    monkeypatch.setattr(mc, "_SINK", sink)
    barrier = threading.Barrier(2)
    def work(tid):
        with mc.task_measurement_context(tid):
            barrier.wait()
            mc.emit_llm_observation({"kind": "llm_attempt"})
    threads = [threading.Thread(target=work, args=(x,)) for x in ("A", "B")]
    for t in threads: t.start()
    for t in threads: t.join()
    assert {e["task_id"] for e in events} == {"A", "B"}
