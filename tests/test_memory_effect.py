# -*- coding: utf-8 -*-
"""R审计-P2 · 边界3 测试（effect 保守接线 + 对照台账）。

★★ 锁什么:
  1. term 成功 + 召回历史记忆 ⇒ effect+1，且 source 标注 inferred（可审计）
  2. term 失败 ⇒ **不**记 effect（推断必须依附成功证据）
  3. 召回自己刚写的节点 ⇒ 不算历史（不记 effect）
  4. 对照台账 effect_ablation.jsonl 每 term 一行（召回数/成功/effect 数）
"""

from __future__ import annotations

import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.harness.run_term import TermRunner  # noqa: E402
from dwc.organs.memory import MemoryKernel, MemoryKind  # noqa: E402


class _PassJudge:
    anchors: dict = {}

    def self_check(self):
        return {"truth_source": {"verified": []}}

    def score(self, split, obs):
        return {"pass_rate": 1.0, "details": []}


class _FailJudge:
    anchors: dict = {}

    def self_check(self):
        return {"truth_source": {"verified": []}}

    def score(self, split, obs):
        return {"pass_rate": 0.0, "details": []}


@pytest.fixture()
def env(tmp_path):
    db = str(tmp_path / "t.sqlite")
    mem = MemoryKernel(db)
    yield db, mem
    mem.close()


def test_effect_backfill_on_success(env):
    """★★ term 成功 + 历史召回 ⇒ effect+1，来源标注 inferred。"""
    db, mem = env
    hist = mem.remember(MemoryKind.TRACE,
                        {"action": "step_0", "task": "hist_task"})
    tr = TermRunner(db_path=db, memory=mem, judge=_PassJudge())
    tr.run_term("hist_task", n_steps=1)
    node = mem.get(hist)
    assert node.effect_count >= 1
    assert "inferred_by_step_success" in (node.payload.get("_effect_sources") or [])


def test_effect_not_recorded_on_failure(env):
    """★ term 失败 ⇒ 不记 effect（推断依附成功证据）。"""
    db, mem = env
    hist = mem.remember(MemoryKind.TRACE,
                        {"action": "step_0", "task": "hist_task"})
    tr = TermRunner(db_path=db, memory=mem, judge=_FailJudge())
    tr.run_term("hist_task", n_steps=1)
    assert mem.get(hist).effect_count == 0


def test_self_written_not_counted(env):
    """★ 召回自己刚写的节点不算历史 ⇒ 不记 effect。"""
    db, mem = env
    tr = TermRunner(db_path=db, memory=mem, judge=_PassJudge())
    rep = tr.run_term("brand_new_task", n_steps=1)
    # 本步新写的 trace 自己召回自己 ⇒ effect 必须仍为 0
    for nid in rep.self_written:
        assert mem.get(nid).effect_count == 0


def test_ablation_ledger_written(env, tmp_path):
    """★ 对照台账: 每 term 一行（召回数/成功/effect 数）。"""
    db, mem = env
    mem.remember(MemoryKind.TRACE, {"action": "step_0", "task": "hist_task"})
    tr = TermRunner(db_path=db, memory=mem, judge=_PassJudge())
    tr.run_term("hist_task", n_steps=1)
    p = tmp_path / "effect_ablation.jsonl"
    assert p.exists()
    rec = json.loads(p.read_text(encoding="utf-8").strip().splitlines()[-1])
    assert rec["success"] is True
    assert rec["n_hist"] >= 1
    assert rec["n_effect"] >= 1


def test_record_effect_source_trace(env):
    """★ record_effect 的 source 落进 payload 且只留最近 5 条。"""
    _db, mem = env
    nid = mem.remember(MemoryKind.TRACE, {"action": "a", "task": "t"})
    for i in range(7):
        mem.record_effect(nid, source="s%d" % i)
    node = mem.get(nid)
    assert node.effect_count == 7
    srcs = node.payload.get("_effect_sources") or []
    assert srcs == ["s2", "s3", "s4", "s5", "s6"]