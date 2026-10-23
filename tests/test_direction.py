# -*- coding: utf-8 -*-
"""direction（organs/direction.py）的契约测试。

★★★ 为什么这份测试重要
  三方向是**值枚举**（Dedup L254 校正: 只有 3 种, 旧报告 4 种是错的）——
  测试锁的是「恰好 3 + 语义逐字 + 精确匹配」, 防两处漂移:
  枚举悄悄加第 4 个 / 语义表被改字 / ensure 兼容了大小写。
★ 判据族: 值唯一 · 语义表齐 · ensure 拒 None/大小写/未知 · str 兼容
"""
from __future__ import annotations

import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.organs.direction import (  # noqa: E402
    N_DIRECTIONS, SEMANTICS, DirectionError, EvolutionDirection,
    ensure_direction, semantics_of,
)


def test_exactly_three_members_locked():
    """★★ 方向数锁 3（DEDUP L254: 4 是旧报告错误, 3 是校正后口径）。"""
    members = list(EvolutionDirection)
    assert len(members) == N_DIRECTIONS == 3, [d.value for d in members]
    assert {d.value for d in members} == {"FORWARD", "LATERAL", "REVERSE"}


def test_semantics_table_is_complete_and_literal():
    """★ 语义表与设计三句**逐字**一致（语义唯一真源, 防改字漂移）。"""
    assert SEMANTICS == {
        EvolutionDirection.FORWARD: "前进 (在现有基础上改进)",
        EvolutionDirection.LATERAL: "横向 (换一个方向试)",
        EvolutionDirection.REVERSE: "后退 (回退到更简单的方案)",
    }
    # 表键 = 枚举全员（无孤儿语义 / 无缺语义）
    assert set(SEMANTICS) == set(EvolutionDirection)


def test_str_enum_serialization_and_equality():
    """str 混合: 与值直等 + 可 json 序列化（提案/日志携带不炸）。"""
    assert EvolutionDirection.FORWARD == "FORWARD"
    assert json.dumps({"d": EvolutionDirection.LATERAL}) == \
        '{"d": "LATERAL"}'
    # 轮回: 值串 → 枚举 → 值串
    assert EvolutionDirection("REVERSE").value == "REVERSE"


def test_ensure_direction_exact_match():
    """ensure: 合法值往返（含已构造的枚举实例本身）。"""
    for v in ("FORWARD", "LATERAL", "REVERSE"):
        assert ensure_direction(v).value == v
    assert ensure_direction(EvolutionDirection.REVERSE) is \
        EvolutionDirection.REVERSE


def test_ensure_rejects_none_case_variants_unknown():
    """★ ensure 拒三类: None（不是第四方向）/ 大小写变体 / 未知值。"""
    with pytest.raises(DirectionError, match="None"):
        ensure_direction(None)
    with pytest.raises(DirectionError, match="精确匹配"):
        ensure_direction("forward")          # 小写变体必须拒
    with pytest.raises(DirectionError, match="不在"):
        ensure_direction("UPWARD")           # 未知值
    with pytest.raises(DirectionError):
        ensure_direction("")                 # 空串
    with pytest.raises(DirectionError):
        ensure_direction(1)                  # 非字符串


def test_semantics_of_roundtrip():
    """semantics_of 查表往返（非法值走 ensure 的同一道门）。"""
    assert semantics_of("LATERAL") == "横向 (换一个方向试)"
    with pytest.raises(DirectionError):
        semantics_of("sideways")


def test_direction_is_dual_use_in_evolver_boundary():
    """★ 边界文档一致性: ⑥ search/ 四件里 direction 已列、replay 仍标未做
    （防「口头说剩一件」的数错复发 —— 以 EVOLUTION 树为准）。"""
    import inspect
    src = inspect.getsource(sys.modules["dwc.organs.direction"])
    assert "replay.py" in src and "未做" in src
    assert "四件" in src
