# -*- coding: utf-8 -*-
"""R400-f · 零取证的"文件名断言"必须打回。

★★★ 现场（2026-10-21 02:40~02:50，同一任务 cl02 三次结果不同）：
    第 1 次 ✓（memory.py）
    第 2 次 ✗（猜了一个不存在的文件名 —— zzz_no_such_file_a.py）
    第 3 次 ✗（先答那个假文件名，被引用校验打回后**撤回并拒答**）

cl08 同款：直接答 `zzz_no_such_file_b.py`（不存在）。

★ 根因：模型**跳过取证**，凭"看起来像"的印象先给一个文件名；
  引用校验（R302）发现路径不存在 ⇒ 打回；模型不重试取证，而是撤回拒答。

★ 修法：qa_mode 下，答案里出现**文件名**却零取证（没有一次 obs ok）
  ⇒ 直接打回，并明确要求先 search_code 再答。
  纯知识问答（答案不含文件名）不受影响。
"""
from __future__ import annotations

import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.llm import task_exec as T  # noqa: E402


class _Script:
    configured = True

    def __init__(self, steps):
        self.steps = steps
        self.n = 0
        self.prompts = []

    def complete(self, prompt, **kw):
        from types import SimpleNamespace
        self.prompts.append(prompt)
        i = min(self.n, len(self.steps) - 1)
        self.n += 1
        return SimpleNamespace(ok=True, error="", meta={},
                               text=json.dumps(self.steps[i],
                                               ensure_ascii=False))

    def complete_stream(self, prompt, **kw):
        return self.complete(prompt, **kw)


@pytest.fixture(autouse=True)
def _json_path(monkeypatch):
    monkeypatch.setenv("DWC_LLM_NATIVE_TOOLS", "0")


def test_guess_without_evidence_is_rejected():
    """★★★ 零取证 + 给文件名 ⇒ 打回（prompt 要求先 search_code）。"""
    llm = _Script([
        {"analysis": "我记得", "op": "final",
         "answer": "MemoryKernel 定义在 src/dwc/foundation/zzz_no_such_file_a.py"},
        {"analysis": "查", "op": "read", "path": "src/dwc/organs/memory.py"},
        {"analysis": "答", "op": "final",
         "answer": "MemoryKernel 定义在 src/dwc/organs/memory.py 第 223 行"},
    ])
    rep = T.execute_user_task("MemoryKernel 定义在哪个文件？只答文件名。",
                              llm=llm, task_id="T_R400F_a", max_rounds=8)
    assert "memory.py" in str(rep.get("answer") or "")
    assert any("没有做任何取证" in p for p in llm.prompts), \
        "第一次 final 未被零取证规则打回"


def test_answer_with_evidence_passes():
    """★★ 有取证 ⇒ 正常放行（零破坏）。"""
    llm = _Script([
        {"analysis": "查", "op": "read", "path": "src/dwc/organs/memory.py"},
        {"analysis": "答", "op": "final",
         "answer": "定义在 src/dwc/organs/memory.py 第 223 行"},
    ])
    rep = T.execute_user_task("MemoryKernel 定义在哪个文件？只答文件名。",
                              llm=llm, task_id="T_R400F_b", max_rounds=6)
    assert rep["status"] == "done"
    assert "memory.py" in str(rep.get("answer"))


def test_pure_knowledge_answer_not_forced_to_search():
    """★★ 纯知识问答（答案不含文件名）不许被强制取证。"""
    llm = _Script([
        {"analysis": "答", "op": "final",
         "answer": "闭包是指函数与其捕获的自由变量的组合，是一种语言特性。"},
    ])
    rep = T.execute_user_task("什么是闭包？", llm=llm,
                              task_id="T_R400F_c", max_rounds=4)
    assert rep["status"] == "done"
    assert len(llm.prompts) == 1, "纯知识问答被多余打回: %r" % llm.prompts
