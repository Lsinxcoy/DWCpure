"""DWC-AUTO · 任务测量上下文与线程本地归属。

TRUTH_SOURCE: client 的物理调用观测 + task_exec 的真实任务/角色上下文。
本模块不生成 token、价格或任务结果；只把真实事件归属到当前任务。
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
import sys
import threading
import time
import uuid

_TASK = ContextVar("dwc_measurement_task", default=None)
_ROLE = ContextVar("dwc_measurement_role", default="solver")
_SINK = None
_STORE = None
_SINK_FAILURES = 0
_LOCK = threading.Lock()


def configure_store(store) -> None:
    """注入进程级证据库；测试传临时库，生产由启动路径显式调用。"""
    global _STORE
    _STORE = store


def configure_sink(sink) -> None:
    global _SINK
    _SINK = sink


@contextmanager
def task_measurement_context(task_id, *, candidate_id=None, rollout_id=None,
                             protocol_id=None, pair_id=None):
    token = _TASK.set({
        "task_id": str(task_id), "candidate_id": candidate_id,
        "rollout_id": rollout_id, "protocol_id": protocol_id, "pair_id": pair_id,
    })
    role_token = _ROLE.set("solver")
    try:
        yield
    finally:
        _ROLE.reset(role_token)
        _TASK.reset(token)


@contextmanager
def measurement_role(role: str):
    token = _ROLE.set(str(role))
    try:
        yield
    finally:
        _ROLE.reset(token)


def current_context() -> dict:
    return dict(_TASK.get() or {})


def _deliver(event: dict) -> str | None:
    """返回真实持久 record_id；失败显式 None，不拿预生成 id 冒充已落库。"""
    global _SINK_FAILURES
    try:
        if _SINK is not None:
            _SINK(event)
        if _STORE is None:
            return None
        return _STORE.append(str(event.get("kind") or "observation"), event,
                             idempotency_key=event.get("event_id"))
    except Exception as exc:  # 测量故障不改变主任务结果，但必须可见
        with _LOCK:
            _SINK_FAILURES += 1
            n = _SINK_FAILURES
        if n <= 5:
            sys.stderr.write("measurement sink 失败×%d: %s: %s\n" %
                             (n, type(exc).__name__, exc))
    return None


def emit_llm_observation(event: dict) -> None:
    enriched = dict(event)
    enriched.update({k: v for k, v in current_context().items()
                     if k not in enriched and v is not None})
    enriched.setdefault("call_role", _ROLE.get())
    enriched.setdefault("cost_scope", "solve_execution")
    enriched.setdefault("event_id", "llm_" + uuid.uuid4().hex)
    enriched.setdefault("observed_at", time.time())
    _deliver(enriched)


def task_usage_summary(task_id: str) -> dict:
    """从已落库的物理 attempt 重算任务 token；不从任务文本估算。"""
    if _STORE is None:
        return {"usage_status": "not_measured", "reason": "store_unconfigured"}
    rows = _STORE.query("llm_attempt", task_id=str(task_id))
    events = [row["payload"] for row in rows]
    normalized = []
    from dwc.observability.usage_pricing import normalize_usage
    for event in events:
        usage = event.get("usage")
        normalized.append(normalize_usage(usage) if isinstance(usage, dict)
                          else normalize_usage(None))
    complete = bool(events) and all(n.status == "reported" for n in normalized)
    return {
        "llm_attempts": len(events),
        "usage_status": "reported" if complete else "partial" if events else "not_reported",
        "input_tokens": sum(n.input_tokens or 0 for n in normalized) if complete else None,
        "cached_input_tokens": sum(n.cached_input_tokens for n in normalized) if complete else None,
        "output_tokens": sum(n.output_tokens or 0 for n in normalized) if complete else None,
        "reasoning_tokens": sum(n.reasoning_tokens for n in normalized) if complete else None,
        "pricing_status": "not_configured",
        "estimated_cost": None,
        "cost_status": "indeterminate",
        "call_event_refs": [row["record_id"] for row in rows],
    }


def emit_task_metrics(report: dict, *, rounds: int | None = None) -> dict:
    event = {
        "kind": "task_metrics", "event_id": "task_" + uuid.uuid4().hex,
        "task_id": report.get("task_id"),
        "status": report.get("status"),
        "measurement_status": "incomplete",
        "rounds": report.get("rounds", rounds),
        "tool_calls": sum(1 for row in report.get("actions_log") or []
                          if isinstance(row, dict) and row.get("phase") == "obs"),
        "usage_status": "aggregated_from_llm_attempts",
        "evidence_ref": report.get("evidence_ref"),
        "observed_at": time.time(),
    }
    summary = task_usage_summary(str(report.get("task_id")))
    event.update(summary)
    usage_ok = (summary.get("usage_status") == "reported"
                and summary.get("llm_attempts", 0) > 0)
    event["measurement_status"] = "measured" if usage_ok else "incomplete"
    event.update({k: v for k, v in current_context().items()
                  if k not in event and v is not None})
    record_id = _deliver(event)
    event["record_id"] = record_id
    event["persistence_status"] = "persisted" if record_id else "not_persisted"
    if not record_id:
        event["measurement_status"] = "incomplete"
    return event
