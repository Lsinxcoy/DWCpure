# -*- coding: utf-8 -*-
"""R407 · 标识符类问题必须取证（read-fact 79% 的根因）。

★★★ 现场（2026-10-21 06:0x 全池，read-fact 掉到 11/14）：
    rf05「DWC 的记忆系统内核类名叫什么？只答类名。」
      → 「无法确证…**最可能是** MemoryKernel」← 没搜，靠推断
      → 被 R389 猜测惩罚正确拦下 ⇒ 0 分（其实答案就是 MemoryKernel）
    rf09「DWC 事前判别的 env 开关变量名是什么？」
      → 一个**全仓 0 命中**的开关名（真实是另一个，见下）
        task_exec.py:1643）

  共同点：问题在问**一个标识符**，模型不取证、凭"看起来像"直接答。
  R400-f 只拦「答案含 `.py` 文件名」，而类名/变量名没有后缀 ⇒ 全漏。

★ 修法：
  R407  问题在问标识符（类名/变量名/主题名/哪个文件…）+ 答案含代码
        标识符（UPPER_SNAKE / CamelCase）+ 零取证 ⇒ 打回并要求 search_code。
  R407-b 答案里的 `DWC_*` 必须在仓库里真实存在，否则打回。
        （只查 DWC_ 前缀：项目自有名字，HTTP/JSON 这类外部概念不误伤）
"""
from __future__ import annotations

import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.llm import task_exec as T  # noqa: E402

#: 拼接构造：不写成连续字面量，避免被 search_code 检索到（污染）
FAKE_ENV = "DWC_" + "ZZZFAKE"


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


def test_identifier_guess_without_evidence_is_rejected():
    """★★★ rf05 复现：问类名 + 零取证 + 答 CamelCase ⇒ 打回，之后搜到才放行。"""
    llm = _Script([
        {"analysis": "推断", "op": "final",
         "answer": "无法确证，最可能是 MemoryKernel"},
        {"analysis": "读", "op": "read", "path": "src/dwc/organs/memory.py"},
        {"analysis": "答", "op": "final", "answer": "MemoryKernel"},
    ])
    rep = T.execute_user_task("DWC 的记忆系统内核类名叫什么？只答类名。",
                              llm=llm, task_id="T_R407_a", max_rounds=8)
    assert any("没有做任何取证" in p for p in llm.prompts), \
        "标识符类零取证未被拦下"
    assert "MemoryKernel" in str(rep.get("answer"))


def test_fake_dwc_env_var_is_rejected():
    """★★★ rf09 复现：`DWC_*` 变量名在仓库不存在 ⇒ 打回。"""
    llm = _Script([
        {"analysis": "读", "op": "read", "path": "src/dwc/llm/task_exec.py"},
        {"analysis": "答", "op": "final", "answer": FAKE_ENV},
        {"analysis": "改", "op": "final", "answer": "DWC_STEP_JUDGE"},
    ])
    rep = T.execute_user_task(
        "DWC 事前判别的 env 开关变量名是什么（可关判别的那个）？只答变量名。",
        llm=llm, task_id="T_R407_b", max_rounds=8)
    assert any("没有任何使用点" in p and FAKE_ENV in p
               for p in llm.prompts), "不存在的 DWC_* 未被拦下"
    assert "DWC_STEP_JUDGE" in str(rep.get("answer"))


def test_real_dwc_var_passes_without_extra_round():
    """★★ 真实存在的 DWC_* 不许被打回（零破坏）。"""
    llm = _Script([
        {"analysis": "读", "op": "read", "path": "src/dwc/llm/task_exec.py"},
        {"analysis": "答", "op": "final", "answer": "DWC_STEP_JUDGE"},
    ])
    rep = T.execute_user_task(
        "DWC 事前判别的 env 开关变量名是什么？只答变量名。",
        llm=llm, task_id="T_R407_c", max_rounds=6)
    assert rep["status"] == "done"
    assert len(llm.prompts) == 2, "真实变量名被多余打回: %r" % llm.prompts


def test_pure_knowledge_question_still_not_forced():
    """★★ 非标识符问题 ⇒ 不强制取证（旧行为保护）。"""
    llm = _Script([
        {"analysis": "答", "op": "final",
         "answer": "闭包是函数与其捕获的自由变量的组合。"},
    ])
    rep = T.execute_user_task("什么是闭包？", llm=llm,
                              task_id="T_R407_d", max_rounds=4)
    assert rep["status"] == "done"
    assert len(llm.prompts) == 1


def test_gate_helpers_direct():
    """★★ 纯函数级：判据边界。"""
    # 问标识符 + 零取证 + CamelCase ⇒ 拦
    assert T._ident_gate("内核类名叫什么？", "最可能是 MemoryKernel", False)
    # 有取证 ⇒ 不拦
    assert T._ident_gate("内核类名叫什么？", "MemoryKernel", True) is None
    # 不问标识符 ⇒ 不拦
    assert T._ident_gate("什么是闭包？", "闭包是 MemoryKernel 之外的…",
                         False) is None
    # 不存在的 DWC_* ⇒ 拦
    assert T._fake_ident_gate(FAKE_ENV)
    # 存在的 ⇒ 不拦
    assert T._fake_ident_gate("DWC_STEP_JUDGE") is None
    # 非 DWC_ 前缀不受影响
    assert T._fake_ident_gate("HTTP_TIMEOUT") is None
    # ★ 只在文档里提过、代码里没用过 ⇒ 仍判不存在（防自证预言）
    assert T._ident_used_in_code("DWC_STEP_JUDGE") is True
    assert T._ident_used_in_code("DWC_THIS_NAME_IS_ONLY_IN_MY_DOCSTRING") is False
