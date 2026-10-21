# -*- coding: utf-8 -*-
"""R408 · 有证据却拒答 ⇒ 打回（rf12 型失败）。

★★★ 现场（2026-10-21 08:45，rf12「DWC 的 TUI 主题名叫什么」）：
    这一轮的 obs **全都指向正确答案**：
      · search_code('theme') → `scripts/dwc_theme.py:12:    "deep": {`
      · read scripts/dwc_theme.py → 正文「两套主题：deep（Deep Space 现…）」
      · 甚至 read 到一个内容就是 `deep` 的文件
    模型最后仍答：
      「无法确定…在 DWC 仓库中未检索到任何 TUI 主题相关的代码或配置证据，
        因此不给出猜测」

    **证据在手还拒答**，比猜错更冤。

★ 修法：qa_mode 下，答案命中"拒答话术"且**已经有成功取证** ⇒ 打回一次，
  要求它逐条回看 obs、摘出最短答案。
  零取证时的拒答是诚实行为，**不拦**（否则会逼模型瞎编）。
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


def test_refusal_with_evidence_is_rejected():
    """★★★ rf12 复现：读到证据还拒答 ⇒ 打回，之后给出答案。"""
    llm = _Script([
        {"analysis": "读", "op": "read", "path": "scripts/dwc_theme.py"},
        {"analysis": "拒答", "op": "final",
         "answer": "无法确定：未检索到任何与 TUI 主题相关的证据。"},
        {"analysis": "再看一眼", "op": "final", "answer": "deep"},
    ])
    rep = T.execute_user_task("DWC 的 TUI 主题名（theme）叫什么？只答主题名。",
                              llm=llm, task_id="T_R408_a", max_rounds=8)
    assert any("却仍然拒答" in p for p in llm.prompts), \
        "有证据的拒答未被拦下"
    assert "deep" in str(rep.get("answer"))


def test_refusal_without_evidence_is_allowed():
    """★★ 零取证时拒答是**诚实**，不许逼它瞎编（旧行为保护）。"""
    llm = _Script([
        {"analysis": "答", "op": "final",
         "answer": "无法确定：仓库里没有找到相关证据。"},
    ])
    rep = T.execute_user_task("DWC 的 TUI 主题名（theme）叫什么？只答主题名。",
                              llm=llm, task_id="T_R408_b", max_rounds=4)
    assert rep["status"] == "done"
    assert len(llm.prompts) == 1, "零取证的诚实拒答被多余打回"


def test_normal_answer_not_touched():
    """★★ 正常答案不受影响。"""
    llm = _Script([
        {"analysis": "读", "op": "read", "path": "scripts/dwc_theme.py"},
        {"analysis": "答", "op": "final", "answer": "deep"},
    ])
    rep = T.execute_user_task("DWC 的 TUI 主题名（theme）叫什么？只答主题名。",
                              llm=llm, task_id="T_R408_c", max_rounds=6)
    assert rep["status"] == "done"
    assert len(llm.prompts) == 2


def test_gate_helper_boundaries():
    """★★ 纯函数边界。"""
    assert T._refusal_gate("q", "无法确定，未检索到证据", True)
    assert T._refusal_gate("q", "无法确定，未检索到证据", False) is None
    assert T._refusal_gate("q", "deep", True) is None
    assert T._refusal_gate("q", "答案就是 memory.py", True) is None
