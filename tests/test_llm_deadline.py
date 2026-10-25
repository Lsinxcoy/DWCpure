"""DWC-AUTO · A-class boundary: LLM total deadline bounds the retry chain."""
from __future__ import annotations

import time

from dwc.llm.client import LLMClient


class _Resp:
    def __init__(self, body: bytes):
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return self._body


def _client():
    return LLMClient(base_url="http://unit.test/v1", api_key="k",
                     model="m", timeout=10)


def test_deadline_exceeded_returns_without_network(monkeypatch):
    c = _client()
    c.deadline = 0.0
    called = {"n": 0}

    def _boom(*a, **k):
        called["n"] += 1
        raise AssertionError("network must not be called")

    monkeypatch.setattr("urllib.request.urlopen", _boom)
    r = c.complete("hi")
    assert r.ok is False and r.error == "deadline_exceeded"
    assert called["n"] == 0


def test_retry_chain_is_bounded_by_deadline(monkeypatch):
    c = _client()
    c.timeout = 10
    c.deadline = 0.2
    c.retries = 5

    def _timeout(*a, **k):
        raise TimeoutError("simulated")

    monkeypatch.setattr("urllib.request.urlopen", _timeout)
    t0 = time.monotonic()
    r = c.complete("hi")
    elapsed = time.monotonic() - t0
    assert r.ok is False
    assert elapsed < 2.0
    assert c.n_retries <= 1


def test_urlopen_timeout_uses_remaining_deadline(monkeypatch):
    c = _client()
    c.timeout = 10
    c.deadline = 1.0
    seen = {}

    def _ok(req, timeout=None):
        seen["timeout"] = timeout
        return _Resp(b'{"choices":[{"message":{"content":"ok"}}]}')

    monkeypatch.setattr("urllib.request.urlopen", _ok)
    r = c.complete("hi")
    assert r.ok is True
    assert 0 < seen["timeout"] <= 1.0
