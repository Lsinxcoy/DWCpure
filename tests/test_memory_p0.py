# -*- coding: utf-8 -*-
"""R审计-P2 · P0 记忆强化测试（scene/detail 补全 + 召回命中 + maintain 防抖）。

★★ 锁什么:
  1. failure_sig 写入带 scene/detail 后，**自然语言场景词**能召回它
     （改前: payload 只有 c/q/m/task ⇒ 路1 永不命中 ⇒ 6.2% 访问率）
  2. dream 的 candidate_skill.boundary 不再是"未知"（detail 有了）
  3. maintain 三层判据不误伤（未召回 held / 唯一签名 protected）
  4. _maybe_maintain 24h 防抖（不随调用频率刷）
"""

from __future__ import annotations

import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.organs.memory import MemoryKernel, MemoryKind  # noqa: E402


@pytest.fixture()
def mem(tmp_path):
    m = MemoryKernel(str(tmp_path / "t.sqlite"))
    yield m
    m.close()


def test_scene_recall_hits(mem):
    """★★★ 核心: 带 scene 的失败签名能被自然语言场景词召回。"""
    scene = "修复 sum_first_n 函数中的 off-by-one 错误，使其计算 1 到 n 的和"
    nid = mem.remember(MemoryKind.FAILURE_SIGNATURE, {
        "c": "E_VALUE", "q": "wrong_magnitude", "m": "llm_asserted:11",
        "task": "code_fix_001", "scene": scene,
        "detail": "sum_first_n(3) 期望 6 实得 3",
    })
    hits = mem.recall_search("修复 sum_first_n", ["off-by-one"], k=5)
    ids = [h.node_id for h in hits]
    assert nid in ids, "带 scene 的失败签名必须能被场景词召回"


def test_no_scene_still_works(mem):
    """无 scene 的旧形态仍可写入（不破坏兼容）。"""
    nid = mem.remember(MemoryKind.FAILURE_SIGNATURE, {
        "c": "E_NO_RESULT", "q": "abstained_or_missing",
        "m": "llm_asserted:None", "task": "code_fix_002"})
    assert mem.get(nid) is not None


def test_dream_boundary_from_detail(mem):
    """★★ dream 的 boundary 从 detail 取（不再是"未知"）。"""
    for _ in range(2):
        mem.remember(MemoryKind.FAILURE_SIGNATURE, {
            "c": "E_VALUE", "q": "wrong_magnitude", "m": "llm_asserted:11",
            "task": "code_fix_001",
            "scene": "修复求和函数",
            "detail": "期望 6 实得 3（off-by-one）",
        })
    # 让其中一条被使用（dream 一级门槛: access>0）
    hits = mem.recall_many("修复求和函数", ["off-by-one"], k=3)
    assert hits
    rep = mem.dream("E_VALUE", "wrong_magnitude", "llm_asserted:11")
    assert rep["eligible"] is True
    assert rep["candidate_skill"]["boundary"] == "期望 6 实得 3（off-by-one）"


def test_maintain_protects_never_recalled(mem):
    """★ maintain 第 1 层: 从未召回 ⇒ 不处置（held）。

    ★ 前提: 必须**非唯一签名**（唯一签名先被第 3 层稀有保护抓走）。
    """
    nid = None
    for _ in range(2):     # 同签名两条 ⇒ 不唯一 ⇒ 不会被 protected 拦截
        nid = mem.remember(MemoryKind.FAILURE_SIGNATURE, {
            "c": "E_VALUE", "q": "wrong_magnitude", "m": "x", "task": "t"})
    rep = mem.maintain()
    assert nid in rep["held_never_recalled"]
    assert mem.get(nid).archived_at is None


def test_maintain_protects_unique_signature(mem):
    """★ maintain 第 3 层: 唯一签名 ⇒ 硬否决（protected，即使 access=0）。"""
    nid = mem.remember(MemoryKind.FAILURE_SIGNATURE, {
        "c": "E_VALUE", "q": "wrong_magnitude", "m": "unique_m", "task": "t"})
    rep = mem.maintain()
    assert nid in rep["protected_rare"]
    assert mem.get(nid).archived_at is None


def test_maintain_archives_used_no_effect(mem):
    """★ maintain 第 2 层: 召回过但零效果 ⇒ 归档（前提: effect 已喂数）。

    ★ 现场教训: effect_count 全库为 0（record_effect 未接线）时，
      护栏会把所有被召回的节点 held —— 所以本测试必须先喂一条 effect>0
      证明 effect 机制在工作，否则测的是护栏不是第 2 层。
    """
    # 喂一条 effect>0（证明 effect 机制可用）
    other = mem.remember(MemoryKind.TRACE, {"action": "step_1", "task": "t1"})
    mem._conn.execute(
        "UPDATE memory_node SET effect_count=1 WHERE node_id=?", (other,))
    mem._conn.commit()
    nid = mem.remember(MemoryKind.TRACE, {"action": "step_0", "task": "t0"})
    # 召回一次（access+1, effect 仍 0）
    mem.recall_many("t0", ["step_0"], k=3)
    assert mem.get(nid).access_count > 0
    rep = mem.maintain()
    assert rep["effect_unfed"] is False
    assert nid in rep["archived"]
    assert mem.get(nid).archived_at is not None      # 归档 ≠ 删除（行还在）


def test_maintain_guard_when_effect_unfed(mem):
    """★★ 护栏: effect 全库未喂数 ⇒ 不归档（宁可不淘汰，不许误伤）。"""
    nid = mem.remember(MemoryKind.TRACE, {"action": "step_0", "task": "t0"})
    mem.recall_many("t0", ["step_0"], k=3)     # access>0, effect=0
    rep = mem.maintain()
    assert rep["effect_unfed"] is True
    assert rep["n_archived"] == 0
    assert nid in rep["held_never_recalled"]
    assert mem.get(nid).archived_at is None
    assert "effect" in rep["why_no_archive"]


def test_maybe_maintain_empty_does_not_mark(tmp_path, monkeypatch):
    """★ 评估 0 条 ⇒ 不写 marker（否则空跑一次锁死 24h）。"""
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    import importlib
    import dwc_agent as A
    importlib.reload(A)

    class _EmptyMem:
        def maintain(self):
            return {"n_evaluated": 0, "n_held": 0, "n_archived": 0,
                    "n_protected": 0, "hint": "empty"}

    monkeypatch.setattr(A, "ROOT", str(tmp_path))
    os.makedirs(tmp_path / "var", exist_ok=True)
    A._maybe_maintain(_EmptyMem())
    assert not (tmp_path / "var" / "dwc_last_maintain.json").exists()


def test_maybe_maintain_24h_debounce(tmp_path, monkeypatch):
    """★ _maybe_maintain 24h 防抖（第二次调用不重复执行）。"""
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    import importlib
    import dwc_agent as A
    importlib.reload(A)

    calls = {"n": 0}

    class _FakeMem:
        def maintain(self):
            calls["n"] += 1
            return {"n_evaluated": 1, "n_held": 1, "n_archived": 0,
                    "n_protected": 0, "hint": "test"}

    monkeypatch.setattr(A, "ROOT", str(tmp_path))
    os.makedirs(tmp_path / "var", exist_ok=True)
    A._maybe_maintain(_FakeMem())
    A._maybe_maintain(_FakeMem())
    assert calls["n"] == 1, "24h 内第二次调用必须被防抖挡住"
    marker = tmp_path / "var" / "dwc_last_maintain.json"
    assert marker.exists()
    assert json.loads(marker.read_text(encoding="utf-8"))["rep"]["n_evaluated"] == 1