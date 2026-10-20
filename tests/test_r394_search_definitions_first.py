# -*- coding: utf-8 -*-
"""R394 · search_code 必须**定义置顶**（grep 会把定义埋在几十行引用里）。

★★★ 现场（2026-10-20 20:19 全池）：
  cl01「execute_user_task 定义在哪个文件」被判 incomplete，`why`：

      复读熔断: 连续 3 轮同动作同结果
      （run / ['grep','-rn','--include=*.py','--exclude-dir=.git',…]）

  动作日志：**第 1 轮 grep ok=True，之后 3 轮全 ok=False**。

★ 根因：`grep -rn <symbol> src` 返回的是**所有引用**（几十行）——
  定义行 `def execute_user_task` 被埋在几十个调用点中间，
  模型读不出"哪个是定义"，只好换个词再搜，越搜越窄 ⇒ 最后搜不到 ⇒ 熔断。

★ 修法：`search_code` 改 Python 实现，输出分两段：

      === DEFINITIONS (n) ===      ← def/class <pattern>，**置顶**，最多 20 行
      src/dwc/llm/task_exec.py:914:def execute_user_task(...)
      === REFERENCES (m) ===       ← 其它命中，最多 30 行

  模型第一眼就能看到答案 ⇒ 不用反复重搜。
"""
from __future__ import annotations

import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.llm import task_exec as T  # noqa: E402


def _tc(name, args):
    return [{"id": "c1", "type": "function",
             "function": {"name": name, "arguments": json.dumps(args)}}]


def _run_search(pat, path="src"):
    step = T._tool_calls_to_step(_tc("search_code", {"pattern": pat, "path": path}))
    assert step is not None
    obs = T._do_action(step["op"], step)
    return obs, str(obs.get("out") or "")


# ───────────────────── ① 定义必须置顶且带文件路径


def test_definition_is_at_top_with_path():
    """★★★ 核心：`execute_user_task` 的定义必须在 DEFINITIONS 段，
    且带 `src/dwc/llm/task_exec.py` 路径。"""
    obs, out = _run_search("execute_user_task")
    assert obs.get("ok") is True, obs
    assert "=== DEFINITIONS" in out, out[:300]
    head = out.split("=== REFERENCES")[0]
    assert "task_exec.py" in head, "定义没置顶:\n" + head[:400]
    assert "def execute_user_task" in head, head[:400]


def test_class_definition_detected():
    """★★ `class MemoryKernel` 也要被识别为定义。"""
    obs, out = _run_search("MemoryKernel")
    head = out.split("=== REFERENCES")[0]
    assert "memory.py" in head, head[:400]
    assert "class MemoryKernel" in head, head[:400]


def test_definition_before_references_in_text_order():
    """★★ 文本顺序上 DEFINITIONS 必须在 REFERENCES 之前。"""
    obs, out = _run_search("execute_user_task")
    assert out.index("=== DEFINITIONS") < out.index("=== REFERENCES")


# ───────────────────── ② 输出必须限流（不许几十行淹没上下文）


def test_output_is_capped():
    """★★★ 高频词（如 `self`）必须被限流，不能返回几百行。"""
    obs, out = _run_search("self")
    assert obs.get("ok") is True, obs
    lines = [l for l in out.splitlines() if l.strip()]
    assert len(lines) <= 60, "输出未限流: %d 行" % len(lines)


# ───────────────────── ③ 搜不到时也要有明确信号


def test_no_match_is_explicit():
    """★★ 搜不到时输出 `DEFINITIONS (0)` / `REFERENCES (0)`（不是空字符串）。"""
    obs, out = _run_search("__definitely_not_a_symbol_zzz__")
    assert "DEFINITIONS (0)" in out, out[:200]
    assert "REFERENCES (0)" in out, out[:200]


# ───────────────────── ④ 仍然只读 + 仍走工具层


def test_search_step_marked_readonly():
    """★★ R393 的 readonly 标记不能丢（否则 qa_mode 又 R5 拦）。"""
    step = T._tool_calls_to_step(_tc("search_code", {"pattern": "x"}))
    assert step.get("readonly") is True


def test_search_uses_python_not_grep():
    """★★ 实现必须换成 Python（grep 会埋定义）。"""
    step = T._tool_calls_to_step(_tc("search_code", {"pattern": "x"}))
    assert step["cmd"][0].lower().endswith(("python.exe", "python", "python3")), step
    assert "-c" in step["cmd"]
