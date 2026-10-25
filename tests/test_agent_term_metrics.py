"""DWC-AUTO · agent term 级任务账必须按本轮时间窗聚合 llm_attempt。"""
from __future__ import annotations

from pathlib import Path

from dwc.observability import context as ctx
from dwc.observability.evidence_store import EvidenceStore


def _attempt(task_id: str, observed_at: float, prompt_tokens: int) -> None:
    ctx.emit_llm_observation({
        "kind": "llm_attempt",
        "task_id": task_id,
        "usage": {"prompt_tokens": prompt_tokens,
                  "completion_tokens": 2,
                  "total_tokens": prompt_tokens + 2},
        "usage_status": "reported",
        "observed_at": observed_at,
    })


def test_term_metrics_only_aggregate_current_window(tmp_path):
    old = ctx._STORE
    store = EvidenceStore(str(tmp_path / "metrics.sqlite"))
    ctx.configure_store(store)
    try:
        _attempt("T", 100.0, 11)
        _attempt("T", 200.0, 22)
        event = ctx.emit_task_metrics(
            {"task_id": "T", "status": "done"}, rounds=1,
            since=150.0, until=250.0,
        )
        assert event["llm_attempts"] == 1
        assert event["input_tokens"] == 22
        assert event["measurement_status"] == "measured"
        assert event["persistence_status"] == "persisted"
        assert event["record_id"]
    finally:
        ctx.configure_store(old)
        store.close()


def test_term_metrics_without_attempts_in_window_is_incomplete(tmp_path):
    old = ctx._STORE
    store = EvidenceStore(str(tmp_path / "metrics.sqlite"))
    ctx.configure_store(store)
    try:
        _attempt("T", 100.0, 11)
        event = ctx.emit_task_metrics(
            {"task_id": "T", "status": "done"}, rounds=1,
            since=300.0, until=400.0,
        )
        assert event["llm_attempts"] == 0
        assert event["input_tokens"] is None
        assert event["measurement_status"] == "incomplete"
    finally:
        ctx.configure_store(old)
        store.close()


def test_agent_loop_emits_term_metrics_with_term_window():
    source = (Path(__file__).resolve().parents[1] / "scripts" / "dwc_agent.py").read_text(
        encoding="utf-8", errors="replace")
    assert "emit_task_metrics(" in source
    assert "since=rep.started_at" in source
    assert "until=rep.closed_at or time.time()" in source
