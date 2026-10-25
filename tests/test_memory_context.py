"""DWC-AUTO · M2.4 context assembler: budget, order, raw refs."""
from __future__ import annotations

from dwc.organs.memory import MemoryKernel, MemoryKind
from dwc.organs.memory_context import assemble, estimate_tokens


def _mem(tmp_path):
    mem = MemoryKernel(str(tmp_path / "m.db"))
    sid = mem.remember(MemoryKind.IDENTITY, {"text": "我是 DWC"},
                       source_channel="user_message")
    kid = mem.remember(MemoryKind.SKILL, {
        "scene": "定位代码符号", "method": "先搜索定义，再读取文件",
        "boundary": "success_pattern:code",
        "invalid_conditions": "非代码不适用",
        "recovery_strategies": "重新诊断",
    })
    tid = mem.remember(MemoryKind.TRACE,
                       {"task": "定位代码符号", "action": "search_code"})
    return mem, sid, kid, tid


def test_assemble_orders_self_before_skills_and_traces(tmp_path):
    mem, sid, kid, tid = _mem(tmp_path)
    out = assemble(mem, "定位代码符号", budget_tokens=800)
    lines = out["text"].splitlines()
    assert lines[0].startswith("task:")
    assert lines[1].startswith("self:")
    assert any(x.startswith("skill:") for x in lines)
    assert any(x.startswith("trace:") for x in lines)
    assert out["used_ids"][0] == sid
    assert out["raw_refs"] == out["used_ids"]
    assert out["truncated"] is False


def test_assemble_respects_budget_and_marks_truncation(tmp_path):
    mem, *_ = _mem(tmp_path)
    out = assemble(mem, "定位代码符号", budget_tokens=5)
    assert out["truncated"] is True
    assert out["tokens"] >= 1


def test_estimate_tokens_is_stable():
    assert estimate_tokens("") == 1
    assert estimate_tokens("abc") == 1
    assert estimate_tokens("abcdef") == 2
