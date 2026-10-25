# -*- coding: utf-8 -*-
"""R审计-P2 · P1 记忆强化测试（FTS5 全文索引 + Weibull 排序权重）。

★★ 锁什么:
  1. FTS5 trigger 同步: remember 后立即可全文检索（中文子串也命中）
  2. recall 路1 走 FTS（不是全表扫）—— 命中语义与旧实现一致
  3. 老库 rebuild: 预置行（绕过 trigger 直接插）启动后能被 FTS 查到
  4. Weibull: 新记忆 retention≈1，极旧记忆 retention→0
  5. retention 只做排序权重（不改召回集合、不删任何东西）
"""

from __future__ import annotations

import os
import sqlite3
import sys
import time

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.organs.memory import (  # noqa: E402
    MemoryKernel, MemoryKind, retention_of,
)


@pytest.fixture()
def mem(tmp_path):
    m = MemoryKernel(str(tmp_path / "t.sqlite"))
    yield m
    m.close()


def test_fts_sync_on_insert(mem):
    """★ trigger 同步: 写入即可被 FTS 检索（中文子串）。"""
    nid = mem.remember(MemoryKind.FAILURE_SIGNATURE, {
        "c": "E_VALUE", "q": "wrong_magnitude", "m": "m1",
        "task": "code_fix_001",
        "scene": "修复 sum_first_n 函数中的 off-by-one 错误"})
    rows = mem._conn.execute(
        "SELECT m.node_id FROM memory_fts f JOIN memory_node m"
        " ON m.rowid=f.rowid WHERE memory_fts MATCH ?", ('"函数中"',)).fetchall()
    assert nid in [r["node_id"] for r in rows]


def test_fts_sync_on_update(mem):
    """★ update trigger: 改 payload 后旧词失效、新词可查。"""
    nid = mem.remember(MemoryKind.FAILURE_SIGNATURE, {
        "c": "E_VALUE", "q": "q", "m": "m", "task": "t",
        "scene": "旧场景词汇"})
    mem._conn.execute(
        "UPDATE memory_node SET payload=? WHERE node_id=?",
        ('{"c":"E_VALUE","q":"q","m":"m","task":"t","scene":"新场景词汇"}', nid))
    mem._conn.commit()
    hit_old = mem._conn.execute(
        "SELECT m.node_id FROM memory_fts f JOIN memory_node m"
        " ON m.rowid=f.rowid WHERE memory_fts MATCH ?",
        ('"旧场景"',)).fetchall()
    hit_new = mem._conn.execute(
        "SELECT m.node_id FROM memory_fts f JOIN memory_node m"
        " ON m.rowid=f.rowid WHERE memory_fts MATCH ?",
        ('"新场景"',)).fetchall()
    assert not [r for r in hit_old if r["node_id"] == nid]
    assert [r for r in hit_new if r["node_id"] == nid]


def test_rebuild_picks_up_preexisting_rows(tmp_path):
    """★ 老库 rebuild: 绕过 trigger 直接插的行，重开库后 FTS 能查到。"""
    db = str(tmp_path / "old.sqlite")
    m1 = MemoryKernel(db)
    # 直接 SQL 插入（模拟老版本写入 — trigger 是后来才有的）
    m1._conn.execute(
        "INSERT INTO memory_node(node_id,zone,kind,tube,payload,created_at)"
        " VALUES('legacy1','experience','failure_sig','reflect',?,?)",
        ('{"c":"E_VALUE","q":"q","m":"m","task":"t","scene":"老库遗留场景词"}',
         time.time()))
    # 模拟"老库没有 FTS 内容": 删掉 trigger 自动写入的索引行
    m1._conn.execute("DELETE FROM memory_fts")
    m1._conn.execute("PRAGMA user_version=0")  # 模拟老库：迁移标记归零
    m1._conn.commit()
    m1.close()
    m2 = MemoryKernel(db)          # 重开 ⇒ rebuild
    rows = m2._conn.execute(
        "SELECT m.node_id FROM memory_fts f JOIN memory_node m"
        " ON m.rowid=f.rowid WHERE memory_fts MATCH ?", ('"遗留场景"',)).fetchall()
    assert "legacy1" in [r["node_id"] for r in rows]
    m2.close()


def test_recall_route1_uses_fts(mem):
    """★ recall 路1: 自然语言场景词命中带 scene 的节点。"""
    nid = mem.remember(MemoryKind.FAILURE_SIGNATURE, {
        "c": "E_VALUE", "q": "wrong_magnitude", "m": "m",
        "task": "code_fix_001",
        "scene": "修复 factorial 函数的无限递归，使其正确计算阶乘"})
    hits = mem.recall_search("修复 factorial 函数", None, k=5)
    assert nid in [h.node_id for h in hits]


def test_recall_short_query_no_crash(mem):
    """★ <3 字符查询不炸（trigram 不索引短串）。"""
    mem.remember(MemoryKind.TRACE, {"action": "a", "task": "t"})
    hits = mem.recall_search("修", ["a"], k=3)
    assert isinstance(hits, list)      # 不抛异常即可


def test_retention_values():
    """★ Weibull 数值: 新≈1，7 天后 trace 明显衰减。"""
    class N:
        kind = MemoryKind.TRACE
        created_at = 0.0

    now = 100.0 * 86400
    n = N()
    n.created_at = now                       # 刚写
    assert retention_of(n, now) > 0.99
    n.created_at = now - 7 * 86400           # 7 天前
    r7 = retention_of(n, now)
    assert 0.3 < r7 < 0.4                    # exp(-(7/7)^1.5)=exp(-1)=0.368
    n.created_at = now - 60 * 86400          # 60 天前
    assert retention_of(n, now) < 0.01


def test_retention_only_weights_not_filters(mem):
    """★ retention 只影响排序，不改变召回集合（旧节点仍可被召回）。"""
    old = mem.remember(MemoryKind.TRACE, {"action": "step_0", "task": "t0"})
    mem._conn.execute(
        "UPDATE memory_node SET created_at=? WHERE node_id=?",
        (time.time() - 90 * 86400, old))     # 90 天前
    mem._conn.commit()
    hits = mem.recall_search("t0", ["step_0"], k=5)
    assert old in [h.node_id for h in hits]   # 仍在召回集合里

def test_cjk_2gram_fallback(mem):
    """★★ 边界1A · 中文 2-gram 兜底: 概括词召回不连续的原文。

    "修复求和函数" 与 "修复 sum_first_n 函数对超大入参的处理" 不连续
    ⇒ LIKE/trigram 都命中不了 ⇒ 2-gram 计分（命中"修复"+"函数"）兜底。
    """
    nid = mem.remember(MemoryKind.FAILURE_SIGNATURE, {
        "c": "E_VALUE", "q": "wrong_magnitude", "m": "m",
        "task": "code_fix_001",
        "scene": "修复 sum_first_n 函数对超大入参的处理"})
    hits = mem.recall_search("修复求和函数", None, k=5)
    assert nid in [h.node_id for h in hits], "2-gram 兜底必须命中不连续的原文"


def test_cjk_2gram_no_false_positive(mem):
    """★ 2-gram 兜底不误报: 完全无关的查询仍返回空。"""
    mem.remember(MemoryKind.FAILURE_SIGNATURE, {
        "c": "E_VALUE", "q": "q", "m": "m", "task": "t",
        "scene": "修复 sum_first_n 函数对超大入参的处理"})
    hits = mem.recall_search("天气预报明天降雨概率", None, k=5)
    assert hits == [], hits


class _FakeLLM:
    """假 LLMClient（configured + 返回固定扩展词）。"""

    configured = True

    def __init__(self, *a, **kw):
        pass

    def complete(self, prompt, **kw):
        class _R:
            ok = True
            text = '["sum", "求和", "sum_first_n"]'
        return _R()


def test_llm_expand_fallback_hits(mem, monkeypatch):
    """★★ 边界1B · LLM 扩展兜底: 同义不同词（"计算总和" → sum）能召回。"""
    import dwc.llm.client as C
    import dwc.organs.memory as M
    monkeypatch.setattr(M, "_EXPAND_CACHE", {})
    monkeypatch.setattr(C, "LLMClient", _FakeLLM)
    nid = mem.remember(MemoryKind.FAILURE_SIGNATURE, {
        "c": "E_VALUE", "q": "wrong_magnitude", "m": "m",
        "task": "code_fix_001",
        "scene": "修复 sum_first_n 函数对超大入参的处理"})
    # "计算总和" 的 2-gram 在库里不存在 ⇒ 走到 LLM 扩展 ⇒ sum 命中
    hits = mem.recall_search("计算总和", None, k=5)
    assert nid in [h.node_id for h in hits], hits


def test_llm_expand_cache(monkeypatch):
    """★ 扩展结果缓存: 同查询 24h 内只调一次 LLM。"""
    import dwc.llm.client as C
    import dwc.organs.memory as M
    calls = {"n": 0}

    class _Counting(_FakeLLM):
        def complete(self, prompt, **kw):
            calls["n"] += 1
            return super().complete(prompt, **kw)

    monkeypatch.setattr(M, "_EXPAND_CACHE", {})
    monkeypatch.setattr(C, "LLMClient", _Counting)
    a = M._llm_expand("某个查询")
    b = M._llm_expand("某个查询")
    assert a == b and a
    assert calls["n"] == 1


def test_llm_expand_unconfigured_returns_empty(monkeypatch):
    """★ 未配置 LLM ⇒ 返回空（不抛异常）。"""
    import dwc.llm.client as C
    import dwc.organs.memory as M

    class _NoCfg(_FakeLLM):
        configured = False

    monkeypatch.setattr(M, "_EXPAND_CACHE", {})
    monkeypatch.setattr(C, "LLMClient", _NoCfg)
    assert M._llm_expand("x") == []
