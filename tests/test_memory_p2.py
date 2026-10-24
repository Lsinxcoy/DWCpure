# -*- coding: utf-8 -*-
"""R审计-P2 · P2 记忆强化测试（learn 管 + importance + MMR + 4-tier）。

★★ 锁什么:
  1. learn 乘法门控: utility<τ ⇒ gated（importance 回基线 0.5）
  2. learn 巩固: utility≥τ ⇒ importance>0.5 且真写进 DB
  3. importance 影响召回排序（不是死字段）
  4. MMR 多样性: 同任务的多条 trace 不再占满 top-k
  5. tier_of: kind → 4-tier 语义名（与 WEIBULL 同源）
  6. 老库迁移: 无 importance 列的表打开后自动 ALTER
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
    MemoryKernel, MemoryKind, tier_of,
)


@pytest.fixture()
def mem(tmp_path):
    m = MemoryKernel(str(tmp_path / "t.sqlite"))
    yield m
    m.close()


def test_learn_gates_zero_utility(mem):
    """★ 乘法门控: 零效用 ⇒ gated，importance 保持基线 0.5。"""
    nid = mem.remember(MemoryKind.TRACE, {"action": "a", "task": "t"})
    rep = mem.learn([nid])
    assert rep["n_gated"] == 1
    assert rep["n_updated"] == 0
    assert mem.get(nid).importance == 0.5


def test_learn_consolidates_used_memory(mem):
    """★★ 巩固: 被真正用过的记忆 importance 上升且落库。"""
    nid = mem.remember(MemoryKind.TRACE, {"action": "a", "task": "t"})
    # 制造实测效用: access×2 + effect×1
    mem._conn.execute(
        "UPDATE memory_node SET access_count=2, effect_count=1"
        " WHERE node_id=?", (nid,))
    mem._conn.commit()
    rep = mem.learn([nid])
    assert rep["n_updated"] == 1
    imp = mem.get(nid).importance
    assert imp > 0.5, imp
    # DB 真写（不是只改内存对象）
    row = mem._conn.execute(
        "SELECT importance FROM memory_node WHERE node_id=?",
        (nid,)).fetchone()
    assert abs(float(row["importance"]) - imp) < 1e-9


def test_learn_surprise_rarity(mem):
    """★ surprise: 同签名簇越小，巩固分越高（稀有=意外=值得记）。"""
    a = mem.remember(MemoryKind.FAILURE_SIGNATURE,
                     {"c": "E_VALUE", "q": "q", "m": "rare_m", "task": "t1"})
    b = mem.remember(MemoryKind.FAILURE_SIGNATURE,
                     {"c": "E_VALUE", "q": "q", "m": "common_m", "task": "t2"})
    for _ in range(4):      # common_m 簇 5 条
        mem.remember(MemoryKind.FAILURE_SIGNATURE,
                     {"c": "E_VALUE", "q": "q", "m": "common_m", "task": "t2"})
    mem._conn.execute("UPDATE memory_node SET access_count=1")
    mem._conn.commit()
    rep = mem.learn([a, b])
    it = {i["node_id"]: i for i in rep["items"]}
    assert it[a]["surprise"] > it[b]["surprise"]
    assert it[a]["importance"] > it[b]["importance"]


def test_importance_affects_ranking(mem):
    """★ importance 不是死字段: 同等 RRF 下高 importance 排前。"""
    n1 = mem.remember(MemoryKind.TRACE, {"action": "step_0", "task": "t"})
    n2 = mem.remember(MemoryKind.TRACE, {"action": "step_0", "task": "t"})
    mem._conn.execute(
        "UPDATE memory_node SET importance=1.0 WHERE node_id=?", (n2,))
    mem._conn.execute(
        "UPDATE memory_node SET importance=0.5 WHERE node_id=?", (n1,))
    mem._conn.commit()
    hits = mem.recall_search("t", ["step_0"], k=2)
    ids = [h.node_id for h in hits]
    assert ids.index(n2) < ids.index(n1)


def test_mmr_diversity(mem):
    """★★ MMR: 同任务的高相似 trace 不再占满 top-k。"""
    # 3 条高度相似（同 task/action）+ 1 条不同的
    for _ in range(3):
        mem.remember(MemoryKind.TRACE, {"action": "step_0", "task": "t"})
    diff = mem.remember(MemoryKind.TRACE, {"action": "step_9", "task": "t"})
    hits = mem.recall_search("t", ["step_0", "step_9"], k=2)
    ids = [h.node_id for h in hits]
    # 前 2 条里必须包含那条"不同的"（否则 MMR 没生效）
    assert diff in ids, ids


def test_tier_of_mapping():
    """★ 4-tier 映射与 Weibull 档位同源。"""
    assert tier_of(MemoryKind.TRACE) == "working"
    assert tier_of(MemoryKind.FAILURE_SIGNATURE) == "episodic"
    assert tier_of(MemoryKind.SKILL) == "procedural"
    assert tier_of(MemoryKind.PROPOSAL) == "semantic"


def test_legacy_db_gets_importance_column(tmp_path):
    """★ 老库迁移: 无 importance 列的表打开后自动 ALTER。"""
    db = str(tmp_path / "legacy.sqlite")
    con = sqlite3.connect(db)
    con.execute(
        "CREATE TABLE memory_node (node_id TEXT PRIMARY KEY, zone TEXT,"
        " kind TEXT, tube TEXT, payload TEXT, chain_id TEXT,"
        " created_at REAL, last_access REAL, access_count INTEGER,"
        " effect_count INTEGER, archived_at REAL)")
    con.execute(
        "INSERT INTO memory_node VALUES('old1','proxy','trace','remember',"
        "'{\"a\":1}',NULL,?,NULL,0,0,NULL)", (time.time(),))
    con.commit()
    con.close()
    m = MemoryKernel(db)          # 打开 ⇒ ALTER + FTS rebuild
    cols = [r[1] for r in m._conn.execute(
        "PRAGMA table_info(memory_node)").fetchall()]
    assert "importance" in cols
    assert m.get("old1").importance == 0.5
    m.close()