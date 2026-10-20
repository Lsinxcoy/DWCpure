# -*- coding: utf-8 -*-
"""R389 · 判据必须区分「确证」与「猜测」。

★★★ 现场（2026-10-20 全池 52 单）：
  `rf05` 问「DWC 记忆系统内核类名」，agent 答：

      抱歉，我目前没有关于 DWC 记忆系统内核类名的可用取证信息，
      无法给出确切的类名（例如可能是 MemoryKernel…）

  判据 `contains: "MemoryKernel"` ⇒ **判 ✓**。
  但这不是"找到了"，是"猜对了" —— 模型自己都说没有取证。

★ 根因：`contains` 只看字符串命中，不看**这句答案是在断言还是在猜**。

★ 修法（保守，避免误伤）：
  答案里出现**明确的猜测/弃权标记**时，`contains` / `regex` /
  `contains_equiv` / `contains_any` 的命中**不算确证** ⇒ 判 ✗，
  并在 how 里写明"猜测措辞"。

  只在**整句层面**判（不是见到"可能"就杀）：
    · "可能是 X" / "大概是 X" / "推测 X" / "猜测 X" / "应该是 X"
    · "无法确认" / "没有取证" / "无法读取" / "未能找到" / "不确定"
    · "若…则…" 这种假设句不算（太常见，会误伤）

★ 显式豁免：`allow_guess: true`（用于"开放题，允许推测"的场景）。
"""
from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import dwc_bench2 as B2  # noqa: E402


# ───────────────────── ① 猜测必须判 ✗


def test_hedged_answer_with_keyword_fails():
    """★★★ 核心：说"可能是 MemoryKernel"命中关键词 ⇒ 仍判 ✗。

    这就是 rf05 的假通过（模型自述没有取证，判据却给分）。
    """
    ans = ("抱歉，我目前没有关于 DWC 记忆系统内核类名的可用取证信息，"
           "无法给出确切的类名（例如可能是 MemoryKernel）")
    ok, how = B2.verify({"type": "contains", "target": "MemoryKernel"}, ans)
    assert ok is False, "猜测命中被判通过 —— 判据把'猜对了'当成'找到了'"
    assert "猜测" in how or "guess" in how.lower(), how


@pytest.mark.parametrize("ans", [
    "大概是 src/dwc/llm/task_exec.py",
    "推测定义在 task_exec.py",
    "我猜测是 task_exec.py",
    "应该是 task_exec.py 吧",
    "无法确认，但可能是 task_exec.py",
    "没有取证信息，可能是 task_exec.py",
    "不确定，估计是 task_exec.py",
    "未能找到确切的定义文件，也许是 task_exec.py",
])
def test_various_hedge_phrases_fail(ans):
    """★★ 各种猜测措辞都要抓（不许只认一种写法）。"""
    ok, how = B2.verify({"type": "contains", "target": "task_exec.py"}, ans)
    assert ok is False, "猜测措辞未拦截: %r (%s)" % (ans, how)


def test_hedge_applies_to_regex_and_equiv():
    """★★ regex / contains_equiv / contains_any 同样要拦猜测。"""
    ok, _ = B2.verify({"type": "regex", "pattern": r"task_exec\.py"},
                      "可能是 task_exec.py")
    assert ok is False
    ok, _ = B2.verify({"type": "contains_equiv",
                       "target": ["0xfeff", "65279"]},
                      "我猜可能是 65279")
    assert ok is False
    ok, _ = B2.verify({"type": "contains_any", "target": ["task_exec.py"]},
                      "无法确认，估计是 task_exec.py")
    assert ok is False


# ───────────────────── ② 确证答案不受影响（防误伤）


@pytest.mark.parametrize("ans", [
    "src/dwc/llm/task_exec.py",                       # 光秃秃的文件名
    "定义在 src/dwc/llm/task_exec.py（第 914 行）",     # 带证据
    "根据 grep 结果，execute_user_task 定义在 "
    "src/dwc/llm/task_exec.py:914",                   # 带取证过程
    "不是 task_exec.py，而是 memory.py",               # 否定句，无猜测
    "如果按模块划分，task_exec.py 属于 llm 层",          # 假设句，不算猜测
])
def test_confident_answers_still_pass(ans):
    """★★ 正常确证答案不许被误杀（尤其假设句/否定句）。"""
    ok, how = B2.verify({"type": "contains", "target": "task_exec.py"}, ans)
    assert ok is True, "误杀了确证答案: %r (%s)" % (ans, how)


# ───────────────────── ③ 显式豁免


def test_allow_guess_opt_out():
    """★ `allow_guess: true` ⇒ 开放题允许推测（显式豁免）。"""
    ok, how = B2.verify({"type": "contains", "target": "MemoryKernel",
                         "allow_guess": True},
                        "可能是 MemoryKernel")
    assert ok is True, how


# ───────────────────── ④ 不影响其它判据


def test_file_checks_unaffected():
    """★★ 文件类判据不看措辞（有文件就是有文件）。"""
    # 不实际建文件：只验证 hedge 逻辑没有错误地套到 file_* 上
    ok, how = B2.verify({"type": "file_contains",
                         "path": "var/__r389_not_exist__.txt",
                         "target": "x"}, "可能是 x")
    assert ok is False and "missing" in how.lower(), how
