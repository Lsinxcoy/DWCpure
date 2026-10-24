# -*- coding: utf-8 -*-
"""R454 · 难度阶梯 —— 饱和就升、太难就降，但必须"先试过"才许升。

★ 为什么要 min_terms + cooldown：
  饱和判据看的是**整窗**通过率，刚升到 L2 时窗里还是 L1 的成绩，
  立刻再升就会一路窜到 L3 —— 那不是难度阶梯，是电梯。
"""
import io
import json
import os

import pytest

from dwc.organs import task_supply as S


def _p(tmp_path, name="level.json"):
    return str(tmp_path / name)


SAT = {"n": 30, "mean": 1.0, "saturated": True}
HARD = {"n": 30, "mean": 0.3, "saturated": False}
MID = {"n": 30, "mean": 0.8, "saturated": False}


def test_default_level_is_1(tmp_path):
    st = S.load_level(_p(tmp_path))
    assert st["level"] == 1 and st["terms"] == 0


def test_step_level_holds_before_min_terms(tmp_path):
    p = _p(tmp_path)
    for _ in range(S.MIN_TERMS_PER_LEVEL - 1):
        st = S.step_level(SAT, now=1000.0, path=p, cooldown=0)
        assert st["level"] == 1 and st["changed"] is False


def test_step_level_escalates_after_min_terms(tmp_path):
    p = _p(tmp_path)
    st = None
    for _ in range(S.MIN_TERMS_PER_LEVEL):
        st = S.step_level(SAT, now=1000.0, path=p, cooldown=0)
    assert st["level"] == 2 and st["changed"] is True


def test_step_level_respects_cooldown(tmp_path):
    p = _p(tmp_path)
    S.save_level(1, why="seed", path=p, since=0.0)
    for _ in range(S.MIN_TERMS_PER_LEVEL):
        S.step_level(SAT, now=10000.0, path=p, cooldown=7200)
    # 冷却未过：再刷 5 次也不许升
    for _ in range(5):
        st = S.step_level(SAT, now=10001.0, path=p, cooldown=7200)
    assert st["level"] == 2
    # 冷却过了才升
    for _ in range(S.MIN_TERMS_PER_LEVEL):
        st = S.step_level(SAT, now=10000.0 + 7201, path=p, cooldown=7200)
    assert st["level"] == 3


def test_level_caps_at_3(tmp_path):
    p = _p(tmp_path)
    for _ in range(S.MIN_TERMS_PER_LEVEL * 8):
        st = S.step_level(SAT, now=float(_) * 9999, path=p, cooldown=0)
    assert st["level"] == 3


def test_step_level_relaxes_when_too_hard(tmp_path):
    p = _p(tmp_path)
    S.save_level(3, why="seed", path=p, since=0.0)
    st = None
    for i in range(S.MIN_TERMS_PER_LEVEL):
        st = S.step_level(HARD, now=1000.0 + i, path=p, cooldown=0)
    assert st["level"] == 2 and st["changed"] is True


def test_mid_range_holds(tmp_path):
    p = _p(tmp_path)
    S.save_level(2, why="seed", path=p, since=0.0)
    for i in range(S.MIN_TERMS_PER_LEVEL * 2):
        st = S.step_level(MID, now=1000.0 + i, path=p, cooldown=0)
    assert st["level"] == 2


def test_state_persists(tmp_path):
    p = _p(tmp_path)
    S.step_level(SAT, now=1000.0, path=p, cooldown=0)
    raw = json.loads(io.open(p, encoding="utf-8").read())
    assert raw["terms"] == 1
    assert S.load_level(p)["terms"] == 1


def test_corrupt_state_falls_back(tmp_path):
    """坏文件不许把 agent 掀翻：退回默认 level=1。"""
    p = _p(tmp_path)
    io.open(p, "w", encoding="utf-8").write("{not json")
    st = S.load_level(p)
    assert st["level"] == 1 and st["terms"] == 0


def test_escalation_request_and_take(tmp_path):
    p = _p(tmp_path, "esc.json")
    assert S.take_escalation(p) is None
    S.request_escalation(2, why="saturated_at_L3", path=p, now=1000.0)
    got = S.take_escalation(p)
    assert got["n"] == 2 and got["why"] == "saturated_at_L3"
    # ★ 取过就没了：否则每 tick 都会重复触发 L3 起草（烧钱）
    assert S.take_escalation(p) is None
    assert not os.path.exists(p)


# ── plan_batch（纯决策）────────────────────────────────────────

def test_plan_not_saturated_does_nothing():
    assert S.plan_batch(2, MID, 0)["action"] == "none"


def test_plan_L1_generates_without_fresh():
    p = S.plan_batch(1, SAT, 0)
    assert p["action"] == "generate" and p["with_fresh"] is False


def test_plan_L2_generates_with_fresh():
    p = S.plan_batch(2, SAT, 0)
    assert p["action"] == "generate" and p["with_fresh"] is True


def test_plan_L3_escalates_instead_of_drafting():
    """★ L3 要 LLM ⇒ tick 里只写请求，绝不自己起草。"""
    p = S.plan_batch(3, SAT, 0)
    assert p["action"] == "escalate" and p["why"] == "saturated_at_L3"


def test_plan_queue_full_holds():
    assert S.plan_batch(2, SAT, 8)["action"] == "none"


def test_plan_queue_full_also_holds_L3():
    """★ 队列里还有一堆没跑的题 ⇒ 先跑完，L3 也不许继续堆。"""
    p = S.plan_batch(3, SAT, 8)
    assert p["action"] == "none" and p["why"] == "queue_full"
