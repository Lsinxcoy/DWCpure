"""SEC-03 · SSRF policy tests."""
from __future__ import annotations

import pytest

from dwc.llm import net_policy as N


def _fake(ip, port=80):
    return [(2, 1, 6, "", (ip, port))]


@pytest.mark.parametrize("ip", [
    "127.0.0.1", "::1", "10.0.0.1", "192.168.1.1",
    "169.254.169.254", "0.0.0.0", "224.0.0.1",
])
def test_private_and_loopback_denied(monkeypatch, ip):
    monkeypatch.setattr(N.socket, "getaddrinfo",
                        lambda *a, **k: _fake(ip))
    with pytest.raises(N.EgressDenied):
        N.check_url("http://example.com/x")


def test_public_allowed(monkeypatch):
    monkeypatch.setattr(N.socket, "getaddrinfo",
                        lambda *a, **k: _fake("93.184.216.34"))
    assert N.check_url("https://example.com") == "https://example.com"


@pytest.mark.parametrize("url", [
    "file:///etc/passwd", "ftp://x", "http://user:pass@example.com",
])
def test_bad_scheme_or_userinfo(monkeypatch, url):
    monkeypatch.setattr(N.socket, "getaddrinfo",
                        lambda *a, **k: _fake("93.184.216.34"))
    with pytest.raises(N.EgressDenied):
        N.check_url(url)


def test_web_read_loopback_denied(monkeypatch):
    from dwc.llm.task_exec import _do_action
    monkeypatch.setattr(N.socket, "getaddrinfo",
                        lambda *a, **k: _fake("127.0.0.1"))
    r = _do_action("web_read", {"url": "http://example.com"})
    assert r["ok"] is False
    assert r["error"] == "egress_denied"
