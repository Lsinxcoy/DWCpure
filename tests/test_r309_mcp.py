# -*- coding: utf-8 -*-
"""R309-② · MCP 探活＋发现缓存：tools 缓存 TTL 过期重探＋probe 永不抛错。"""
import os
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = r"E:/Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "src"))


def _seed_entry(M, name, tools, age_s):
    import threading
    M._POOL[name] = {"proc": None, "lock": threading.Lock(),
                     "tools": tools, "tools_ts": time.time() - age_s}


def test_tools_cache_ttl_refetch(monkeypatch):
    from dwc.llm import mcp_client as M
    name = "t_ttl_srv"
    M._POOL.pop(name, None)
    _seed_entry(M, name, [{"name": "old"}], age_s=9999)
    calls = {"n": 0}

    def _fake_rpc(n, method, params=None, timeout=60.0):
        calls["n"] += 1
        if method == "tools/list":
            return {"tools": [{"name": "new"}]}
        return {}

    monkeypatch.setattr(M, "_rpc", _fake_rpc)
    monkeypatch.setattr(M, "initialize", lambda n: {})
    try:
        tools = M.tools_list(name, ttl_s=60)
        assert tools == [{"name": "new"}], tools
        assert calls["n"] >= 1
    finally:
        M._POOL.pop(name, None)


def test_tools_cache_fresh_no_refetch(monkeypatch):
    from dwc.llm import mcp_client as M
    name = "t_fresh_srv"
    M._POOL.pop(name, None)
    _seed_entry(M, name, [{"name": "old"}], age_s=1)

    def _boom(n, method, params=None, timeout=60.0):
        raise AssertionError("fresh 缓存不应重探")

    monkeypatch.setattr(M, "_rpc", _boom)
    try:
        assert M.tools_list(name, ttl_s=60) == [{"name": "old"}]
    finally:
        M._POOL.pop(name, None)


def test_probe_never_raises(monkeypatch):
    from dwc.llm import mcp_client as M

    def _dead(n, method, params=None, timeout=60.0):
        raise OSError("down")

    monkeypatch.setattr(M, "_rpc", _dead)
    monkeypatch.setattr(M, "initialize", lambda n: (_ for _ in ()).throw(
        OSError("down")))
    assert M.probe("t_dead_srv", timeout=1) is False
