# -*- coding: utf-8 -*-
"""R147 · 泄漏筛查 — 第 0 步（2609.24972 字面子集 + critic 缺口诚实标）。

验收:
  □ 五类词表字面命中 ⇒ 一票否决（非补偿同族）
  □ 命中带上下文（可审计/可复核 — 不是黑箱拒绝）
  □ 空白 diff ⇒ 显式拒（空 diff 不是"干净"）
  □ inert machinery 弱 proxy: 纯注释+字符串 ⇒ 标记（只标记不否决）
  □ 通用 diff（无词表命中）⇒ allowed=True
  □ critic 角色显式 not_instrumented（A4 缺口在档, 不假装语义干净）
"""
from __future__ import annotations

import os
import sys

import pytest

ROOT = r"E:/Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.organs.leakage import (  # noqa: E402
    LEAK_KINDS, LEAKAGE, CRITIC_STATUS, Candidate, LeakError,
    ScreenResult, screen_batch, screen_candidate)


def _c(cid: str, diff: str, **vocab) -> Candidate:
    return Candidate(candidate_id=cid, diff=diff, **vocab)


def test_kinds_enum_and_doc():
    """★ 五类 + 惰机 与原文一致 + 顺序声明在档。"""
    assert LEAK_KINDS == ("task_name", "entity_name",
                          "task_specific_value", "answer", "inert_machinery")
    assert LEAKAGE["order"].startswith("RRSI 第 0 步")
    assert "一票否决" in LEAKAGE["veto"]


def test_task_name_hit_vetoes():
    """★ task name 字面命中 ⇒ 一票否决（非补偿同族）。"""
    r = screen_candidate(_c("c1", "if task == 'code_fix_001': return True",
                            task_names=("code_fix_001",)))
    assert r.allowed is False
    assert r.hits[0].kind == "task_name"
    assert "code_fix_001" in r.hits[0].context


def test_answer_hit_vetoes():
    """answer 串出现在 diff ⇒ 拒（写死答案是最重的泄漏）。"""
    r = screen_candidate(_c("c2", "+ return 42",
                            answers=("42",)))
    assert r.allowed is False and r.hits[0].kind == "answer"


def test_entity_and_specific_value():
    """entity name / task-specific value 各自成类（口径分列可审计）。"""
    r = screen_candidate(_c("c3", "x = 'ACME'  # note: 7",
                            entity_names=("ACME",),
                            task_specific_values=("7",)))
    kinds = sorted(h.kind for h in r.hits)
    assert kinds == ["entity_name", "task_specific_value"]


def test_generic_diff_allowed():
    """★ 通用改动（无词表命中）⇒ allowed=True（原文: generic 保留）。"""
    r = screen_candidate(_c("c4", "if err: retry(backoff=2)",
                            task_names=("t",), entity_names=("E",),
                            answers=("A",)))
    assert r.allowed is True and r.hits == []
    assert r.critic == CRITIC_STATUS          # 但 critic 缺口仍如实标
    d = r.as_dict()
    assert "不等于语义干净" in d["note"]


def test_empty_diff_rejected():
    """空 diff 显式拒（没内容可筛 ≠ 干净 — X2 纪律）。"""
    with pytest.raises(LeakError):
        _c("c5", "   ")


def test_inert_machinery_marked_not_vetoed():
    """★ 惰机 weak proxy: 无任何 ASCII 标识符字符（纯中文注释+字符串）⇒ 标记。

    ★ proxy 的语义（如实标注在实现注释里）: python token 最小面=ASCII
      标识符字符 ⇒ 连一个都没有 = 没有可执行 token（"x = '字符串'"里
      的 x 是标识符 ⇒ 不算 inert — 弱 proxy, 宁漏报不误报）。
    """
    r = screen_candidate(_c("c6", "# 只加注释和说明\n'字符串'"))
    assert r.inert_machinery is True
    assert r.allowed is True                # 只标记, 不进一票否决
    # 有 ASCII 标识符（含单字母变量名）⇒ not inert（宁漏不误）
    r2 = screen_candidate(_c("c7", "+ x = 1"))
    assert r2.inert_machinery is False
    r3 = screen_candidate(_c("c8", "+ if flag: return 1"))
    assert r3.inert_machinery is False


def test_batch_order_and_rejection_list():
    """批量保序 + 被拒清单（原文前置语义: 不进评估）。"""
    out = screen_batch([
        _c("a", "clean = 1"),
        _c("b", "task = 'code_fix_001'", task_names=("code_fix_001",)),
        _c("c", "ok = 2"),
    ])
    assert [x["candidate_id"] for x in out["results"]] == ["a", "b", "c"]
    assert out["n_rejected"] == 1
    assert out["rejected"] == ["b"]
    assert "不进评估" in out["note"]
    assert out["critic_role"] == CRITIC_STATUS
