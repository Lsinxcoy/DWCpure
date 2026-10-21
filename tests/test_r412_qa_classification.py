# -*- coding: utf-8 -*-
"""R412 · 「运行脚本…是否通过」不许被判成 qa_mode。

★★★ 现场（2026-10-21 R411 全池，rv07）：
    任务：`运行门禁脚本 scripts/gate.py, 报告是否全部通过。`
    `_QA_Q` 命中 `"是否"`；`_QA_X` 里有 `"执行"/"跑"` 但**没有 `"运行"`**
    ⇒ `is_qa_task=True` ⇒ 进 qa_mode ⇒ `_READONLY_BREAKERS` 含 `"python"`
    ⇒ `run(['python','scripts/gate.py'])` 被判非只读 ⇒ **R5_blocked ×3**
    ⇒ agent 只能答"无法核实"，判据判 ✗。

    这是**产品 bug**：只读闸把任务本身要求的执行拦掉了。

★ 保护旧行为：真问答句（叫什么/是什么/为什么）仍必须 True；
  原有执行动词（执行/跑/修/写）仍必须 False。
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.llm.step_judge import is_qa_task  # noqa: E402


def test_run_script_is_not_qa():
    """★★★ 新行为：'运行…是否…' 是执行任务，不是问答。"""
    assert is_qa_task("运行门禁脚本 scripts/gate.py, 报告是否全部通过。") is False


def test_start_is_not_qa():
    """★ '启动…是否…' 同样是执行任务。"""
    assert is_qa_task("启动服务后检查是否监听 8765。") is False


def test_real_question_still_qa():
    """★ 旧行为保护：真问答句仍走 qa 直答通道。"""
    for q in ("DWC 的 TUI 主题名（theme）叫什么？只答主题名。",
              "为什么这一步会失败？",
              "PowerShell 需要 TrimStart 的字符码是多少？"):
        assert is_qa_task(q) is True, q


def test_old_exec_verbs_unchanged():
    """★ 旧行为保护：原有执行动词仍然 False（不能因为加词而翻转）。"""
    for q in ("执行 pytest tests/", "跑一遍全量测试", "修一下这个 bug",
              "写一个报告到 docs/"):
        assert is_qa_task(q) is False, q
