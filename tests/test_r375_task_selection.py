# -*- coding: utf-8 -*-
"""R375 · 任务选择逃逸阀 + 任务池覆盖（修「1120 term 只跑 12 个任务」）。

★★★ 病根（实测取证，不是猜）：
  · `select_task` 取上轮 advice 的**第一个** `world_tree_action` node
    ⇒ 一旦收敛到某任务就永久卡住（生产日志 1120 term / 12 task，
      单个 `reproduce_003` 占 949 次 = 85%）。
  · `DEV_POOL` 只有 11 个任务，而 anchors 有 15 个真任务
    ⇒ `code_fix_007/008/009`（behavior，LLM 可接管）从未被跑过。
  · 后果：`Evolver._seen` 按 key 去重 ⇒ 同一失败重复 N 次产 0 个新提案
    ⇒ 提高执行频率只是放大重复，不是加速进化。

★★ 本轮判据（用户拍板「执行你的推荐」）：
  ① 同一任务连续被选中 3 次 ⇒ 强制换（保留「同一失败重复 3 次」的频次信号）
  ② 换的时候取池里**最久没用过**的（从未用过优先），并让卡住的任务冷却一整圈
  ③ 池扩到全部 16 个真 anchors（含 3 个从未跑过的 behavior 任务）
"""
from __future__ import annotations

import os
import sys
from types import SimpleNamespace

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.path.insert(0, os.path.join(ROOT, "src"))

import dwc_agent as A  # noqa: E402


@pytest.fixture(autouse=True)
def _clean_selection():
    """★ 进程内全局选择态必须每个测试复位。

    用 monkeypatch(raising=False)：实现落地前属性不存在也能装上，
    落地后 patch 的就是真对象（函数里是全局名查找，patch 生效）。
    """
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(A, "_sel",
                        {"last": None, "streak": 0, "used": [], "cooldown": {}},
                        raising=False)
    yield
    monkeypatch.undo()


def _rep(task: str) -> SimpleNamespace:
    """造一个「上轮建议下一轮做 task」的 TermReport 替身。"""
    return SimpleNamespace(next_task_source={
        "tasks": [{"kind": "world_tree_action", "node": task}]})


# ────────────────────────────────── ① 逃逸阀


def test_escape_after_three_consecutive_same():
    """★★★ 连续 3 次同一任务后必须换 —— 这是打破固定点的核心判据。"""
    picks = [A.select_task(_rep("reproduce_003")) for _ in range(5)]
    assert picks[:3] == ["reproduce_003"] * 3, (
        "前 3 次应保持同一任务（保留失败频次信号），实得 %r" % (picks[:3],))
    assert picks[3] != "reproduce_003", (
        "第 4 次必须逃逸，实得仍为 reproduce_003 ⇒ 固定点未破")


def test_streak_resets_when_task_changes():
    """★ 中间换了任务 ⇒ 连续计数清零（不是「累计 3 次」）。"""
    seq = ["reproduce_003", "reproduce_003", "reproduce_003",
           "code_fix_001", "reproduce_003", "reproduce_003"]
    picks = [A.select_task(_rep(t)) for t in seq]
    assert picks == seq, (
        "计数应按「连续」而非「累计」：被 code_fix_001 打断后不应逃逸，"
        "实得 %r" % (picks,))


def test_escape_picks_least_recently_used():
    """★ 逃逸目标 = 池里最久没用过的（从未用过优先），不是随便换一个。"""
    A.select_task(_rep("code_fix_001"))
    A.select_task(_rep("code_fix_002"))
    picks = [A.select_task(_rep("reproduce_003")) for _ in range(4)]
    esc = picks[3]
    assert esc not in ("reproduce_003", "code_fix_001", "code_fix_002"), (
        "应选最久未用的任务，实得 %r（刚用过的三个之一）" % (esc,))


def test_escape_result_is_always_in_pool():
    """★ 逃逸不能跑到池外（池外任务 execute_task 会 ActorError）。"""
    picks = [A.select_task(_rep("reproduce_003")) for _ in range(6)]
    assert all(p in A.DEV_POOL for p in picks), picks


def test_after_escape_pool_is_swept_before_stuck_task_returns():
    """★★★ 逃逸后卡住的任务必须**让位一整圈** —— 否则下轮 advice 又把它
    拽回去，逃逸形同虚设（只给 25% 探索率，实测）。"""
    seq = [A.select_task(_rep("reproduce_003")) for _ in range(10)]
    assert "reproduce_003" not in seq[3:], (
        "冷却期内不得回到卡住的任务，实得 %r" % (seq,))
    assert len(set(seq[3:])) == len(seq[3:]), (
        "冷却期内应逐个覆盖不同任务（不得重复），实得 %r" % (seq[3:],))


def test_seed_fallback_still_rotates_pool():
    """★ 无 advice ⇒ 仍走池轮询（旧行为不破）。"""
    got = A.select_task(SimpleNamespace(next_task_source={"tasks": []}))
    assert got in A.DEV_POOL


# ────────────────────────────────── ② 池覆盖


def _real_anchors():
    from dwc.llm.executor import load_anchors
    return {k: v for k, v in load_anchors().items()
            if not k.startswith("_") and isinstance(v, dict)}


def test_dev_pool_covers_all_anchor_tasks():
    """★★★ 池必须覆盖全部真 anchors —— 漏一个就有一整片能力面永不执行。"""
    real = set(_real_anchors())
    pool = set(A.DEV_POOL)
    assert pool == real, (
        "池与 anchors 不一致\n  漏: %s\n  多: %s"
        % (sorted(real - pool), sorted(pool - real)))


def test_dev_pool_contains_every_behavior_task():
    """★★ behavior 是 LLM 唯一能接管的一类 ⇒ 一个都不许漏在池外。"""
    beh = {k for k, v in _real_anchors().items()
           if v.get("verifier_kind") == "behavior"}
    missing = beh - set(A.DEV_POOL)
    assert not missing, "LLM 可接管但不在池里: %s" % sorted(missing)
    assert len(beh) == 9, "behavior 任务数变了（%d）—— 池扩展需同轮复核" % len(beh)


def test_select_task_after_monitor_skip():
    """★★★ 被 monitor 跳过的 tick 不得消耗任务选择态（源码序锁）。

    生产实测（interval=90）：5 分钟里 2 次 skip + 2 个 term ⇒ 选择态空转
    2 格，冷却会在池子扫完前到期。select_task 必须排在 skip 判定之后。
    """
    src = open(A.__file__, encoding="utf-8").read()
    i_skip = src.index("_maybe_skip(prev is not None")
    i_sel = src.index("task = select_task(prev)")
    assert i_sel > i_skip, (
        "select_task 必须在 monitor 跳过判定之后调用（当前 %d < %d）"
        % (i_sel, i_skip))
