# -*- coding: utf-8 -*-
"""R277b · envelope 拆包 + m 填 LLM 断言值（回灌 0 行的根治）。

★ 背景: _build_observations 真执行通道包 envelope
  {observed, ★_executed}，judge 全链无拆包 ⇒ behavior 全误判 False
  （生产 6 False 系赃物）；且 behavior 签名 m 恒 "" ⇒ D6 全拦。
★ 口径冻结: 非 envelope 输入行为逐字节不变；规则时代 m 仍 ""。
★ 测试 fake（手造 observed，不烧 LLM）＋禁碰生产 anchors。
"""
from __future__ import annotations

import os
import sys

import pytest

ROOT = r"E:\Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "src"))
from dwc.organs.judge import Judge, JudgeError                # noqa: E402


def _good_obs():
    return {"sum_first_n": [[3, 6], [5, 15]]}


def test_envelope_unwrap_same_as_inner():
    """★★★ envelope 输入与裸 observed 同判（拆包回归锁）。"""
    j = Judge()
    inner = _good_obs()
    env = {"observed": dict(inner), "★_executed": True}
    a = j.evaluate("code_fix_001", "dev", observed=inner)
    b = j.evaluate("code_fix_001", "dev", observed=env)
    assert a.success is True and b.success is True


def test_envelope_false_carries_m():
    """★★★ envelope 下的 False 签名 m = LLM 断言值（D6 可过）。"""
    j = Judge()
    env = {"observed": {"sum_first_n": [[3, 999], [5, 15]]},
           "★_executed": True}
    v = j.evaluate("code_fix_001", "dev", observed=env)
    assert v.success is False
    assert v.failure_signature.get("m", "").startswith("llm_asserted:")


def test_rule_era_m_stays_empty():
    """★★★ 非 envelope（规则时代）False 的 m 仍空（零破坏锁）。"""
    j = Judge()
    v = j.evaluate("code_fix_001", "dev",
                   observed={"sum_first_n": [[3, 999], [5, 15]]})
    assert v.success is False
    assert v.failure_signature.get("m") == ""


def test_judge_rejects_train_split():
    """★★★ 非法 split 大声 raise（raises 配额）。"""
    j = Judge()
    with pytest.raises(JudgeError):
        j.evaluate("code_fix_001", "train", observed=_good_obs())
