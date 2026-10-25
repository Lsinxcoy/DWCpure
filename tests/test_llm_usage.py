# -*- coding: utf-8 -*-
"""LLM 物理请求的真实 usage / interface 观测契约（无网络）。"""
from __future__ import annotations

import json
import os
import sys
import time

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
from dwc.llm import client as C  # noqa: E402


class Resp:
    def __init__(self, body):
        self.raw = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.headers = {"Content-Type": "application/json"}

    def read(self):
        return self.raw

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def client():
    return C.LLMClient(base_url="http://fake/v1", api_key="secret", model="requested")


def body(text="answer", **kw):
    data = {"model": "reported", "usage": {"prompt_tokens": 3, "completion_tokens": 2},
            "choices": [{"message": {"content": text}, "finish_reason": "stop"}]}
    data.update(kw)
    return data


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    events = []
    monkeypatch.setattr(C, "_OBS_SINK", events.append)
    monkeypatch.setattr(C, "_OBS_SINK_ERRORS", 0)
    monkeypatch.setattr(C, "_load_file_config", lambda: {})
    monkeypatch.setenv("DWC_LLM_RETRIES", "0")
    return events


def test_complete_records_real_usage_and_returned_model(monkeypatch, isolated):
    monkeypatch.setattr(C.urllib.request, "urlopen", lambda *a, **k: Resp(body()))
    result = client().complete("private prompt")
    assert result.ok and result.meta["usage"] == body()["usage"]
    assert result.meta["usage_status"] == "reported"
    assert result.meta["call_id"] == isolated[0]["call_id"]
    assert result.meta["attempt_index"] == 0
    event = isolated[0]
    assert event | {} == event
    assert event["kind"] == "llm_attempt"
    assert event["transport"] == "complete"
    assert event["model_requested"] == "requested"
    assert event["model_reported"] == "reported"
    assert event["usage"] == body()["usage"]
    assert event["interface"] == {"raw_tool_calls": 0, "transport_repaired": False,
                                  "protocol_error": False}
    assert "private prompt" not in repr(event) and "secret" not in repr(event)


@pytest.mark.parametrize("payload,ok,kind,tools", [
    (body(tool_calls=[{"id": "t"}]) | {"choices": [{"message": {"content": "", "tool_calls": [{"id": "t"}]}, "finish_reason": "tool_calls"}]}, True, "", 1),
    (body(""), False, "empty", 0),
    (body("", choices=[{"message": {"content": "", "reasoning_content": "think"}, "finish_reason": "length"}]), False, "reasoning_only", 0),
    (b"not-json", False, "parse", 0),
])
def test_every_complete_outcome_emits_once(monkeypatch, isolated, payload, ok, kind, tools):
    monkeypatch.setattr(C.urllib.request, "urlopen", lambda *a, **k: Resp(payload))
    result = client().complete("x")
    assert result.ok is ok
    assert len(isolated) == 1
    event = isolated[0]
    assert event["error_kind"] == kind
    assert event["interface"]["raw_tool_calls"] == tools
    for key in ("usage", "usage_status", "call_id", "attempt_index"):
        assert key in result.meta


def test_retry_attempts_share_call_id_and_emit_failures(monkeypatch, isolated):
    monkeypatch.setenv("DWC_LLM_RETRIES", "1")
    replies = iter([OSError("down"), Resp(body())])
    def urlopen(*a, **k):
        item = next(replies)
        if isinstance(item, Exception):
            raise item
        return item
    monkeypatch.setattr(C.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(time, "sleep", lambda _: None)
    result = client().complete("x")
    assert result.ok and len(isolated) == 2
    assert [e["attempt_index"] for e in isolated] == [0, 1]
    assert len({e["call_id"] for e in isolated}) == 1
    assert isolated[0]["ok"] is False and isolated[0]["error_kind"] == "transport"
    assert result.meta["attempt_index"] == 1


def test_sink_failure_does_not_change_result(monkeypatch, isolated, capsys):
    monkeypatch.setattr(C.urllib.request, "urlopen", lambda *a, **k: Resp(body()))
    def broken(_):
        raise RuntimeError("observer secret prompt")
    monkeypatch.setattr(C, "_OBS_SINK", broken)
    result = client().complete("x")
    assert result.ok and result.text == "answer"
    assert C._OBS_SINK_ERRORS == 1
    assert "RuntimeError" in capsys.readouterr().err


class SSE:
    headers = {"Content-Type": "text/event-stream"}

    def __init__(self, frames):
        self.frames = frames

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def __iter__(self):
        for frame in self.frames:
            payload = frame if isinstance(frame, str) else (frame.decode() if isinstance(frame, bytes) else json.dumps(frame))
            yield ("data: " + payload + "\n").encode()
        yield b"data: [DONE]\n"


def test_sse_usage_only_final_frame_and_reported_model(monkeypatch, isolated):
    frames = [
        {"model": "stream-model", "choices": [{"delta": {"content": "hello"}}]},
        {"model": "stream-model", "choices": [{"delta": {}, "finish_reason": "stop"}]},
        {"model": "stream-model", "usage": {"total_tokens": 9}},
    ]
    monkeypatch.setattr(C.urllib.request, "urlopen", lambda *a, **k: SSE(frames))
    result = client().complete_stream("x")
    assert result.ok and result.meta["usage"] == {"total_tokens": 9}
    assert result.meta["streamed"] is True
    assert isolated[0]["model_reported"] == "stream-model"
    assert isolated[0]["transport"] == "stream"
    assert isolated[0]["usage_status"] == "reported"


def test_sse_tool_call_fragments_are_real_interface_result(monkeypatch, isolated):
    frames = [
        {"choices": [{"delta": {"tool_calls": [{"index": 0, "id": "call-1", "function": {"name": "lookup", "arguments": "{\""}}]}}]},
        {"choices": [{"delta": {"tool_calls": [{"index": 0, "function": {"arguments": "x\":1}"}}]}}]},
        {"choices": [{"delta": {}, "finish_reason": "tool_calls"}], "usage": {"total_tokens": 4}},
    ]
    monkeypatch.setattr(C.urllib.request, "urlopen", lambda *a, **k: SSE(frames))
    result = client().complete_stream("x")
    assert result.ok and result.text == ""
    assert result.meta["tool_calls"] == [{"index": 0, "id": "call-1", "function": {"name": "lookup", "arguments": "{\"x\":1}"}}]
    assert isolated[0]["interface"]["raw_tool_calls"] == 1
    assert isolated[0]["finish_reason"] == "tool_calls"


def test_sse_keeps_text_when_tool_call_is_present(monkeypatch, isolated):
    frames = [
        {"choices": [{"delta": {"content": "I will "}}]},
        {"choices": [{"delta": {"content": "call"}}]},
        {"choices": [{"delta": {"tool_calls": [{"index": 0, "id": "call-1", "function": {"name": "lookup", "arguments": "{\"x\":1}"}}]}, "finish_reason": "tool_calls"}]},
    ]
    monkeypatch.setattr(C.urllib.request, "urlopen", lambda *a, **k: SSE(frames))
    result = client().complete_stream("x")
    assert result.ok and result.text == "I will call"
    assert result.meta["tool_calls"][0]["function"]["name"] == "lookup"
    assert result.meta["content_chars"] == len("I will call")


def test_sse_malformed_tool_arguments_are_protocol_error(monkeypatch, isolated):
    frames = [
        {"choices": [{"delta": {"tool_calls": [{"index": 0, "id": "call-1", "function": {"name": "lookup", "arguments": "{"}}]}, "finish_reason": "tool_calls"}]},
    ]
    monkeypatch.setattr(C.urllib.request, "urlopen", lambda *a, **k: SSE(frames))
    result = client().complete_stream("x")
    assert result.ok is False
    assert "协议" in result.error
    assert isolated[0]["error_kind"] == "tool_protocol"
    assert isolated[0]["interface"]["protocol_error"] is True


def test_stream_fallback_retry_keeps_original_parent_chain(monkeypatch, isolated):
    monkeypatch.setenv("DWC_LLM_RETRIES", "1")
    monkeypatch.setattr(time, "sleep", lambda _: None)
    replies = iter([OSError("no stream"), OSError("fallback retry"),
                    Resp(body("whole", usage={"total_tokens": 12}))])
    def urlopen(*a, **k):
        item = next(replies)
        if isinstance(item, Exception):
            raise item
        return item
    monkeypatch.setattr(C.urllib.request, "urlopen", urlopen)

    result = client().complete_stream("x")

    assert result.ok and result.text == "whole"
    assert len(isolated) == 3
    stream, first_fallback, retried_fallback = isolated
    assert stream["transport"] == "stream" and stream["parent_call_id"] is None
    assert first_fallback["parent_call_id"] == stream["call_id"]
    assert retried_fallback["parent_call_id"] == stream["call_id"]
    assert first_fallback["transport"] == "fallback"
    assert retried_fallback["transport"] == "fallback"
    assert retried_fallback["attempt_index"] == 1


def test_stream_fallback_emits_both_attempts_and_preserves_fallback_meta(monkeypatch, isolated):
    replies = iter([OSError("no stream"), Resp(body("whole", usage={"total_tokens": 12}))])
    def urlopen(*a, **k):
        item = next(replies)
        if isinstance(item, Exception):
            raise item
        return item
    monkeypatch.setattr(C.urllib.request, "urlopen", urlopen)
    result = client().complete_stream("x")
    assert result.ok and result.text == "whole"
    assert result.meta["stream_fallback"] is True
    assert result.meta["fallback_reason"] == "OSError: no stream"
    assert result.meta["usage"] == {"total_tokens": 12}
    assert result.meta["model"] == "reported"
    assert len(isolated) == 2
    stream, fallback = isolated
    assert stream["transport"] == "stream" and not stream["ok"]
    assert fallback["transport"] == "fallback" and fallback["ok"]
    assert fallback["parent_call_id"] == stream["call_id"]
    assert fallback["interface"]["transport_repaired"] is True
    assert result.meta["call_id"] == fallback["call_id"]


def test_sse_empty_and_bad_frame_expose_interface_error(monkeypatch, isolated):
    frames = [b"not-json"]
    sse = SSE([{"choices": [{"delta": {"content": ""}}]}])
    sse.frames = frames + list(sse.frames)
    monkeypatch.setattr(C.urllib.request, "urlopen", lambda *a, **k: sse)
    result = client().complete_stream("x")
    assert not result.ok and result.meta["kind"] == "empty"
    assert result.meta["usage_status"] == "not_reported"
    assert isolated[0]["error_kind"] == "empty"
    assert isolated[0]["interface"]["protocol_error"] is True


def test_failed_fallback_keeps_both_physical_attempt_facts(monkeypatch, isolated):
    monkeypatch.setenv("DWC_LLM_RETRIES", "0")
    replies = iter([OSError("stream down"), Resp(body("", usage={"total_tokens": 7}))])
    def urlopen(*a, **k):
        item = next(replies)
        if isinstance(item, Exception):
            raise item
        return item
    monkeypatch.setattr(C.urllib.request, "urlopen", urlopen)
    result = client().complete_stream("x")
    assert not result.ok and result.meta["kind"] == "empty"
    assert result.meta["stream_fallback"] is True
    assert result.meta["stream_error"] == "stream down"
    assert result.meta["usage"] == {"total_tokens": 7}
    assert len(isolated) == 2
    assert isolated[1]["parent_call_id"] == isolated[0]["call_id"]
    assert result.meta["call_id"] == isolated[1]["call_id"]
    assert isolated[1]["error_kind"] == "empty"


def test_http_attempt_has_code_and_not_reported_usage(monkeypatch, isolated):
    import urllib.error
    def deny(*a, **k):
        raise urllib.error.HTTPError("http://fake", 401, "denied", {}, None)
    monkeypatch.setattr(C.urllib.request, "urlopen", deny)
    result = client().complete("x")
    assert not result.ok and result.meta["http_code"] == 401
    assert result.meta["n_retry_used"] == 0
    assert isolated[0]["http_code"] == 401
    assert isolated[0]["usage"] is None
    assert isolated[0]["usage_status"] == "not_reported"
    assert isolated[0]["error_kind"] == "http"


def test_no_sink_is_optional_and_legacy_stats_remain(monkeypatch):
    monkeypatch.setattr(C, "_OBS_SINK", None)
    monkeypatch.setattr(C.urllib.request, "urlopen", lambda *a, **k: Resp(body()))
    llm = client()
    result = llm.complete("x")
    assert result.ok and result.text == "answer"
    assert llm.stats()["n_calls"] == 1 and llm.stats()["n_ok"] == 1
    assert llm.stats()["n_fail"] == 0 and llm.stats()["n_retries"] == 0


def test_next_top_level_call_gets_new_call_id(monkeypatch, isolated):
    monkeypatch.setattr(C.urllib.request, "urlopen", lambda *a, **k: Resp(body()))
    llm = client()
    first = llm.complete("x")
    second = llm.complete("x")
    assert first.meta["call_id"] != second.meta["call_id"]
    assert [e["attempt_index"] for e in isolated] == [0, 0]
    assert all(e["parent_call_id"] is None for e in isolated)


def test_concurrent_retries_do_not_share_call_id(monkeypatch, isolated):
    import threading
    monkeypatch.setenv("DWC_LLM_RETRIES", "1")
    monkeypatch.setattr(time, "sleep", lambda _: None)
    def urlopen(req, timeout=None):
        payload = json.loads(req.data)
        marker = payload["messages"][0]["content"]
        key = marker + "-seen"
        if not urlopen.seen.get(key):
            urlopen.seen[key] = True
            raise OSError("retry " + marker)
        return Resp(body(marker))
    urlopen.seen = {}
    monkeypatch.setattr(C.urllib.request, "urlopen", urlopen)
    llm = client()
    results = {}
    def run(name):
        results[name] = llm.complete(name)
    threads = [threading.Thread(target=run, args=(name,)) for name in ("first", "second")]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert all(result.ok for result in results.values())
    groups = {}
    for event in isolated:
        groups.setdefault(event["call_id"], []).append(event)
    assert len(groups) == 2
    assert all([e["attempt_index"] for e in events] == [0, 1] for events in groups.values())
    assert results["first"].meta["call_id"] != results["second"].meta["call_id"]
