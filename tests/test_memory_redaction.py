"""H7 · 记忆写入脱敏：密钥/PII 不落库，所有通道生效。"""
from __future__ import annotations

import json

from dwc.llm.executor import memory_text
from dwc.organs.memory import MemoryKernel, MemoryKind
from dwc.organs.memory_guard import redact, redact_obj


def test_redact_known_patterns():
    s, hits = redact(
        "key sk-abcdefghijklmnopqrstuvwxyz123456 "
        "auth Bearer abcdefghijklmnopqrstuvwxyz "
        "password=hunter2 "
        "postgres://user:pass@db.local/app")
    assert "sk-abcdefghijklmnopqrstuvwxyz123456" not in s
    assert "hunter2" not in s
    assert "user:pass@" not in s
    assert "api_key" in hits
    assert "bearer" in hits
    assert "password" in hits
    assert "connection" in hits


def test_redact_private_key_block():
    s, hits = redact(
        "-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBg\n"
        "-----END PRIVATE KEY-----")
    assert "MIIEvQIBADANBg" not in s
    assert "private_key" in hits


def test_remember_redacts_even_without_channel(tmp_path):
    mem = MemoryKernel(str(tmp_path / "m.db"))
    nid = mem.remember(MemoryKind.TRACE, {
        "task": "run tests",
        "action": "curl -H 'Authorization: Bearer abcdefghijklmnopqrstuvwxyz'",
        "obs": "api_key=sk-abcdefghijklmnopqrstuvwxyz123456",
    })
    raw = mem._conn.execute(
        "SELECT payload FROM memory_node WHERE node_id=?", (nid,)).fetchone()[0]
    assert "abcdefghijklmnopqrstuvwxyz" not in raw
    assert "sk-abcdefghijklmnopqrstuvwxyz123456" not in raw
    p = json.loads(raw)
    assert "api_key" in p["_redactions"]
    assert "bearer" in p["_redactions"]


def test_redacted_skill_does_not_leak_into_prompt(tmp_path):
    mem = MemoryKernel(str(tmp_path / "m.db"))
    mem.remember(MemoryKind.SKILL, {
        "scene": "定位代码符号",
        "method": "先搜索定义，再读取文件；token=sk-abcdefghijklmnopqrstuvwxyz123456",
        "boundary": "success_pattern:code",
        "invalid_conditions": "非代码不适用",
        "recovery_strategies": "重新诊断",
    })
    txt = memory_text(mem, "定位代码符号")
    assert "先搜索定义" in txt
    assert "sk-abcdefghijklmnopqrstuvwxyz123456" not in txt


def test_redact_obj_is_recursive_and_does_not_mutate():
    src = {"a": ["Bearer abcdefghijklmnopqrstuvwxyz"],
           "b": {"password": "hunter2"}}
    out, hits = redact_obj(src)
    assert "abcdefghijklmnopqrstuvwxyz" not in json.dumps(out)
    assert "hunter2" not in json.dumps(out)
    assert "bearer" in hits and "password" in hits
    assert src["b"]["password"] == "hunter2"
