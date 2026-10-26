"""H6 · knowledge page 投影：可重建、带来源、可拉取、不推送。"""
from __future__ import annotations

import json
import time

from dwc.llm.executor import memory_text
from dwc.organs import knowledge_page as KP
from dwc.organs.memory import MemoryKernel, MemoryKind


def _mem(tmp_path):
    m = MemoryKernel(str(tmp_path / "m.db"))
    r = m.remember(MemoryKind.REFERENCE, {
        "claim": "本项目测试命令是 uv run pytest -q",
        "topic": "测试命令",
        "source_ids": ["task:T1"],
        "observed_at": time.time(),
    })
    s = m.remember(MemoryKind.SKILL, {
        "scene": "定位代码符号", "method": "先搜索定义，再读取文件",
        "boundary": "success_pattern:code",
        "invalid_conditions": "非代码定位不适用",
        "recovery_strategies": "失败后重新诊断",
        "source_ids": ["task:T2"],
        "observed_at": time.time(),
    })
    return m, r, s


def test_build_creates_page_with_sources(tmp_path):
    m, r, s = _mem(tmp_path)
    out = tmp_path / "knowledge"
    rep = KP.build(m, out_dir=str(out))
    assert rep["n_pages"] == 2
    files = list(out.glob("*.md"))
    assert len(files) == 2
    text = "".join(p.read_text(encoding="utf-8") for p in files)
    assert "uv run pytest -q" in text
    assert "先搜索定义" in text
    assert r in text and s in text
    assert "sources:" in text


def test_build_is_projection_not_push(tmp_path):
    m, r, s = _mem(tmp_path)
    KP.build(m, out_dir=str(tmp_path / "knowledge"))
    # factual 不回到 skill prompt；procedural 仍可召回
    assert "uv run pytest" not in memory_text(m, "测试命令")
    assert "先搜索定义" in memory_text(m, "定位代码符号")


def test_check_flags_expired_source(tmp_path):
    m, r, s = _mem(tmp_path)
    out = tmp_path / "knowledge"
    KP.build(m, out_dir=str(out))
    assert KP.check(m, out_dir=str(out))["ok"] is True
    m.supersede(r, s, at=time.time())
    rep = KP.check(m, out_dir=str(out))
    assert rep["ok"] is False
    assert any("expired" in x or "status" in x
               for item in rep["stale"] for x in item["reasons"])


def test_search_records_knowledge_page_route(tmp_path):
    m, r, s = _mem(tmp_path)
    out = tmp_path / "knowledge"
    KP.build(m, out_dir=str(out))
    rep = KP.search(m, "uv run pytest", out_dir=str(out))
    assert rep["ok"] is True
    assert rep["n"] >= 1
    st = m.retrieval_stats("knowledge_page")
    assert st["n_retrievals"] == 1
    assert st["n_with_hits"] == 1


def test_list_pages_reads_frontmatter(tmp_path):
    m, r, s = _mem(tmp_path)
    out = tmp_path / "knowledge"
    KP.build(m, out_dir=str(out))
    pages = KP.list_pages(out_dir=str(out))
    assert len(pages) == 2
    assert all(p["page_id"] for p in pages)
    assert all(not p["stale"] for p in pages)


def test_knowledge_search_is_a_native_tool():
    from dwc.llm.task_exec import _tool_calls_to_step
    step = _tool_calls_to_step([{
        "function": {"name": "knowledge_search",
                     "arguments": '{"query":"测试命令"}'}}])
    assert step is not None
    assert step["op"] == "knowledge_search"
    assert step["query"] == "测试命令"
