# -*- coding: utf-8 -*-
"""R392 · 猜测检测必须是**句子级**，不是全文级。

★★★ R389 的问题（自查发现）：
  `_hedge_block` 按**全文**扫描 —— 一个长答案里只要出现一次"不确定"，
  即使主体是确证结论也会被判 ✗：

      "我读了 README。定义在 src/dwc/llm/task_exec.py。
       另外配置项我不确定是否已启用。"
      ⇒ R389 判 ✗（误杀）

  而正确答案常常带一句免责声明 ⇒ 系统性压低通过率。

★ 正确语义：**只判"答案所在的那句话"是不是猜测**。
  · "可能是 task_exec.py"            ⇒ 该句有猜测 ⇒ ✗
  · "定义在 task_exec.py。别的不确定" ⇒ 命中句是确证 ⇒ ✓
  · "无法确认。不过可能是 task_exec.py" ⇒ 命中句有猜测 ⇒ ✗

★ 兜底：定位不到命中句时（例如 target 根本不在答案里），
  不做猜测判定（让正常的"未命中"逻辑判 ✗）。
"""
from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import dwc_bench2 as B2  # noqa: E402


# ───────────────────── ① 长答案里的无关猜测不该杀


def test_unrelated_hedge_in_other_sentence_passes():
    """★★★ 核心：命中句是确证，别的句子有"不确定" ⇒ 必须 ✓。"""
    ans = ("我读了 README。定义在 src/dwc/llm/task_exec.py。"
           "另外配置项我不确定是否已启用。")
    ok, how = B2.verify({"type": "contains", "target": "task_exec.py"}, ans)
    assert ok is True, "无关句子的猜测把确证答案误杀了: %s" % how


def test_hedge_before_but_not_in_match_sentence_passes():
    """★★ "无法确认…" 在前句，命中句是确证 ⇒ ✓。"""
    ans = "一开始无法确认。但 grep 之后：定义在 task_exec.py:914。"
    ok, how = B2.verify({"type": "contains", "target": "task_exec.py"}, ans)
    assert ok is True, how


# ───────────────────── ② 命中句是猜测 ⇒ 必须杀


@pytest.mark.parametrize("ans", [
    "可能是 task_exec.py",
    "无法确认，但可能是 task_exec.py",
    "推测定义在 task_exec.py",
    "我猜测是 task_exec.py",
    "应该是 task_exec.py 吧",
    "没有取证信息。例如可能是 task_exec.py。",
])
def test_hedge_in_match_sentence_fails(ans):
    """★★★ 命中句本身是猜测 ⇒ 判 ✗（rf05 的假通过）。"""
    ok, how = B2.verify({"type": "contains", "target": "task_exec.py"}, ans)
    assert ok is False, "猜测仍被判通过: %r (%s)" % (ans, how)
    assert "猜测" in how or "guess" in how.lower(), how


def test_multi_sentence_answer_with_hedged_match_fails():
    """★★ 长答案里，命中的那句是猜测 ⇒ 仍要 ✗。"""
    ans = ("我查看了仓库结构，目录很多。"
           "不过没有找到确切的定义，**可能是** task_exec.py。"
           "建议你再用 grep 确认一下。")
    ok, how = B2.verify({"type": "contains", "target": "task_exec.py"}, ans)
    assert ok is False, how


# ───────────────────── ③ regex / equiv 也要按句


def test_regex_hedge_sentence():
    """★★ regex：命中片段所在句有猜测 ⇒ ✗；别的句有 ⇒ ✓。"""
    bad = "我不太确定，可能是 65279"
    ok, _ = B2.verify({"type": "regex", "pattern": r"65279"}, bad)
    assert ok is False
    good = "PowerShell 脚本里是 65279。其余部分我不确定。"
    ok2, how2 = B2.verify({"type": "regex", "pattern": r"65279"}, good)
    assert ok2 is True, how2


def test_equiv_hedge_sentence():
    """★★ contains_equiv 同样按句判。"""
    ok, _ = B2.verify({"type": "contains_equiv", "target": ["0xfeff", "65279"]},
                      "我猜可能是 65279")
    assert ok is False
    ok2, how2 = B2.verify({"type": "contains_equiv",
                           "target": ["0xfeff", "65279"]},
                          "字符码是 65279。其他细节不确定。")
    assert ok2 is True, how2


# ───────────────────── ④ 豁免与回归


def test_allow_guess_still_works():
    """★ `allow_guess: true` 仍然豁免（句子级不影响豁免）。"""
    ok, how = B2.verify({"type": "contains", "target": "MemoryKernel",
                         "allow_guess": True}, "可能是 MemoryKernel")
    assert ok is True, how


def test_confident_answers_unaffected():
    """★★ 正常确证答案不受影响。"""
    for ans in ("src/dwc/llm/task_exec.py",
                "定义在 src/dwc/llm/task_exec.py（第 914 行）",
                "根据 grep 结果，定义在 task_exec.py:914"):
        ok, how = B2.verify({"type": "contains", "target": "task_exec.py"}, ans)
        assert ok is True, (ans, how)
