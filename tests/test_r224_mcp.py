# -*- coding: utf-8 -*-
"""R224 · MCP client: 协议全链（假 server 真 JSON-RPC 应答）+ 配置校验。"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
from dwc.llm import mcp_client as M                             # noqa: E402
import pytest                                                   # noqa: E402

#: 最小 MCP stdio server（头分帧 JSON-RPC; bytes([13,10]) 构造 CRLF —
#: 彻底避开 raw-string 转义坑）
_FAKE_CODE = "\n".join([
    "import sys, json",
    "CRLF = bytes([13,10])",
    "def read_msg():",
    "    head = b''",
    "    while not head.endswith(CRLF + CRLF):",
    "        ch = sys.stdin.buffer.read(1)",
    "        if not ch:",
    "            return None",
    "        head += ch",
    "    n = int(head.split(b'Content-Length:')[1].split(CRLF)[0])",
    "    return json.loads(sys.stdin.buffer.read(n).decode())",
    "def send(obj):",
    "    raw = json.dumps(obj).encode()",
    "    sys.stdout.buffer.write(b'Content-Length: %d' % len(raw) + CRLF + CRLF + raw)",
    "    sys.stdout.buffer.flush()",
    "while True:",
    "    m = read_msg()",
    "    if m is None:",
    "        break",
    "    meth = m.get('method', '')",
    "    if meth == 'initialize':",
    "        send({'jsonrpc': '2.0', 'id': m['id'], 'result': {'protocolVersion': '2024-11-05'}})",
    "    elif meth == 'tools/list':",
    "        send({'jsonrpc': '2.0', 'id': m['id'], 'result': {'tools': [{'name': 'echo'}]}})",
    "    elif meth == 'tools/call':",
    "        a = (m.get('params') or {}).get('arguments', {})",
    "        send({'jsonrpc': '2.0', 'id': m['id'], 'result': {'content': [{'type': 'text', 'text': 'echo:' + str(a.get('x', ''))}]}})",
    "    else:",
    "        send({'jsonrpc': '2.0', 'id': m.get('id'), 'result': {}})",
])


def _with_fake(tmp_path, monkeypatch):
    srv = tmp_path / "fake_mcp_server.py"
    srv.write_text(_FAKE_CODE, encoding="utf-8")
    conf = tmp_path / "mcp.json"
    conf.write_text(json.dumps({"servers": {"fake": {
        "command": [sys.executable, str(srv)]}}}), encoding="utf-8")
    monkeypatch.setattr(M, "MCP_CONF", str(conf))
    M._POOL.clear()


def test_full_protocol_roundtrip(tmp_path, monkeypatch):
    """★★★ 协议全链: initialize → tools/list → tools/call 真 JSON-RPC
    （头分帧; 假 server 真应答 — 不是 mock 内部函数）。"""
    _with_fake(tmp_path, monkeypatch)
    try:
        tools = M.tools_list("fake")
        assert [t["name"] for t in tools] == ["echo"]
        out = M.tools_call("fake", "echo", {"x": "hi"})
        assert out["ok"] and out["text"] == "echo:hi", out
    finally:
        M.shutdown_all()
        M._POOL.clear()


def test_unconfigured_server_raises():
    """★ 未配置 server 明确报错（不静默空转）。"""
    M._POOL.clear()
    with pytest.raises(M.McpError, match="未配置"):
        M.tools_call("nope", "t")


def test_broken_config_raises(tmp_path):
    """★ 坏 mcp.json 大声报错（"没有校验器的 yaml 只是文本"同族）。"""
    bad = tmp_path / "bad.json"
    bad.write_text("{broken", encoding="utf-8")
    with pytest.raises(M.McpError, match="坏了"):
        M.load_config(str(bad))


def test_command_argv_required(tmp_path):
    """★ 配置校验: command 必须非空 argv 列表。"""
    conf = tmp_path / "c.json"
    conf.write_text(json.dumps({"servers": {"x": {"command": []}}}),
                    encoding="utf-8")
    with pytest.raises(M.McpError, match="command"):
        M.load_config(str(conf))
