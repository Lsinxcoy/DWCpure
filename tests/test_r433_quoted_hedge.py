# -*- coding: utf-8 -*-
"""R433 · 引号内的措辞不是模型在犹豫（hs01 误杀）。

★★★ 现场（hs01，池 A 19:30）：
    正确答案里有这么一句：

      「2. 收束排序靠信息增益而非置信度：…选「pass-rate 最不确定的分支」
        先探索；该判据只吃布尔观测计数，完全不读 confidence…」

    `不确定` 是**信息增益的术语**（熵最高的分支），不是模型在犹豫。
    R392 已经只看"命中答案的那一句"，但那一句里恰好含这个术语 ⇒
    一条证据充分、结论正确的回答被判 `guess-credit-blocked`。

★ 规则：**引号里的话是引用，不是断言。**
  `「」『』“”""` 包裹的片段在猜测判定前剔除；
  反引号（代码）**不剔除** —— 代码里写"不确定"仍是模型的输出。
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import dwc_bench2 as B  # noqa: E402

CHECK = {"type": "contains_any",
         "target": ["探索", "导航", "世界树", "预测", "模拟", "状态", "环境",
                    "规划", "表征", "因果"]}


def test_quoted_term_does_not_trigger_guess_gate():
    """★★★ 现场原句：术语「最不确定的分支」⇒ 必须判 ✓。"""
    ans = ("世界模型承载进化循环的探索环节：收束排序靠信息增益，"
           "选「pass-rate 最不确定的分支」先探索，该判据只吃布尔观测计数。")
    ok, why = B.verify(CHECK, ans)
    assert ok is True, why


def test_real_hedge_still_blocked():
    """★★ 真犹豫（不在引号里）仍然要拦。"""
    ans = "世界模型的作用可能是探索，但我不确定。"
    ok, why = B.verify(CHECK, ans)
    assert ok is False
    assert "guess-credit-blocked" in why


def test_hedge_outside_quotes_after_quoted_term_still_blocked():
    """★★ 引号剔除不能变成放水：引号外仍有犹豫 ⇒ 拦。"""
    ans = "它负责「最不确定的分支」的探索，不过这个结论大概是推测。"
    ok, why = B.verify(CHECK, ans)
    assert ok is False, why


def test_backticks_are_not_stripped():
    """★★ 反引号是代码，不是引用 —— 里面的犹豫仍然算。"""
    ans = "世界模型负责探索，`无法确定` 具体实现。"
    ok, why = B.verify(CHECK, ans)
    assert ok is False, why


def test_strip_quoted_basic():
    assert "不确定" not in B._strip_quoted("选「最不确定的分支」")
    assert "不确定" in B._strip_quoted("我不确定")
