# -*- coding: utf-8 -*-
"""R403 · `search_code` 必须剥掉模型误带的 `def `/`class ` 前缀。

★★★ 现场（2026-10-21 03:40，cl02 连续 3 轮都答错）：
    模型传 `pattern="class MemoryKernel"`，我们的定义正则是
    `^\\s*(def|class)\\s+<pattern>` ⇒ 实际匹配 `class class MemoryKernel`
    ⇒ **DEFINITIONS 0 条**；而"原文包含"匹配到 1 行 ⇒ 全落进 REFERENCES：

        === DEFINITIONS (0) ===
        === REFERENCES (1) ===
        src\\dwc\\organs\\memory.py:223:class MemoryKernel:

    定义明明就在输出里，却不在 DEFINITIONS 段 ⇒ 模型判断"没有定义"
    ⇒ 转头答了不存在的 `一个不存在的内核文件名`。

★ 修法：入口处剥掉 `def `/`class ` 前缀再检索。
"""
from __future__ import annotations

import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.llm import task_exec as T  # noqa: E402


def _search(pat, path="src"):
    tc = [{"id": "c1", "type": "function",
           "function": {"name": "search_code",
                        "arguments": json.dumps({"pattern": pat, "path": path})}}]
    step = T._tool_calls_to_step(tc)
    return T._do_action(step["op"], step)


def test_class_prefix_is_stripped():
    """★★★ `class MemoryKernel` ⇒ 必须命中 DEFINITIONS(1)。"""
    out = _search("class MemoryKernel")
    text = out.get("out", "")
    assert "DEFINITIONS (1)" in text, text[:300]
    assert "organs" in text and "memory.py" in text, text[:300]


def test_def_prefix_is_stripped():
    """★★ `def revise_from_outcome` 同理。"""
    text = _search("def revise_from_outcome").get("out", "")
    assert "DEFINITIONS (1)" in text, text[:300]
    assert "revision.py" in text, text[:300]


def test_plain_pattern_unchanged():
    """★★ 不带前缀的正常 pattern 不受影响（零破坏）。"""
    text = _search("lessons_context").get("out", "")
    assert "DEFINITIONS (1)" in text
    assert "agent_quality.py" in text


def test_multiline_prefix_not_broken():
    """★★ 只有"整串就是 def/class X"才剥；普通含 class 的串不剥。"""
    text = _search("class MemoryKernel:").get("out", "")
    assert "DEFINITIONS (1)" in text, text[:300]
