# -*- coding: utf-8 -*-
"""R380 · 纯文本答案不许判死（修 7/8 失败的真因）。

★★★ 现场取证（2026-10-20 09:40 跑批，修完 R376/R377/R378/R379 之后）:
  真实通过率 2/10，8 单失败中 **7 单的 `why` 内容是答案本身**：
    nb_..._03  why = 'prev_node_id'          ← 正是要的答案
    nb_..._05  why = 'dwc_pairs.jsonl'       ← 正是要的答案
    nb_..._09  why = '一个不存在的内核文件名'      ← 正是要的答案
    nb_..._10  why = 'foundation'            ← 正是要的答案
  ⇒ 模型**答对了**，只是输出纯文本而不是 `{"op":"final","answer":...}`，
    被 `task_exec` 判 `incomplete`。

★★ 为什么会这样: `reasoning_effort="none"`（R377 为修「推理吃光 token」而加）
  压制了推理，模型不再"先想格式再答"，直接给自然语言。
  这是**用格式换正确率**的副作用 —— 格式判死把正确答案一起扔了。

★ 判据（本轮锁的）:
  · 模型返回**非 JSON 纯文本** ⇒ 当作 final 答案收下（status=done），
    不判死（`why` 里保留原文以便审计）
  · 返回**合法 JSON 但没有 op** ⇒ 仍按原逻辑（不能把乱码当答案）
  · 返回空串 ⇒ 仍判 incomplete（不许把"什么都没有"当成功）
  · 已有 `final` op 路径**完全不变**（回归保护）
"""
from __future__ import annotations

import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.llm import task_exec as T  # noqa: E402


class _FakeLLM:
    """按顺序吐出预设响应（不碰网络）。"""

    configured = True

    def __init__(self, texts):
        self._texts = list(texts)
        self.calls = 0

    def complete(self, prompt, system=None, max_tokens=None, json_mode=False,
                 images=None):
        self.calls += 1
        txt = self._texts.pop(0) if self._texts else ""
        return T_Result(txt)


class T_Result:
    def __init__(self, text):
        self.ok = True
        self.text = text
        self.error = ""
        self.meta = {"finish_reason": "stop"}


@pytest.fixture(autouse=True)
def _json_path(monkeypatch):
    """★ R384 · 本文件锁的是 **JSON 回退路径**的语义（原生模式见 test_r384）。

    原生 tool calling 下模型输出散文属协议违反 ⇒ 直接判 incomplete；
    R380 的"纯文本答案收下"只适用于不支持 tools 的端点/provider。
    """
    monkeypatch.setenv("DWC_LLM_NATIVE_TOOLS", "0")


@pytest.fixture()
def work(tmp_path, monkeypatch):
    monkeypatch.setattr(T, "WORK", str(tmp_path))
    monkeypatch.setattr(T, "SESSIONS", str(tmp_path / "sessions"))
    (tmp_path / "sessions").mkdir(exist_ok=True)
    monkeypatch.setattr(T, "SELF_MD", str(tmp_path / "self.md"))
    return tmp_path


# ─────────────────────── ① 纯文本答案要收下


def test_plain_text_answer_is_accepted(work):
    """★★★ 纯文本答案（非 JSON）⇒ status=done，answer 就是那段文本。

    现场：`why = 'prev_node_id'` —— 答对了却被判死。
    """
    llm = _FakeLLM(["prev_node_id"])
    rep = T.execute_user_task("config 里 revision 的字段叫什么？",
                              llm=llm, task_id="t_plain")
    assert rep["status"] == "done", (
        "纯文本答案被判死（why=%r）—— 答案被扔掉了" % rep.get("why"))
    assert "prev_node_id" in str(rep.get("answer") or ""), rep.get("answer")


def test_plain_text_answer_keeps_raw_for_audit(work):
    """★ 原文要留在报告里（可审计：模型到底说了什么）。

    ★ R审计-P1 · 样本文件名换成仓库**真实存在**的 `config/eval_tasks.jsonl`：
      R417 幻觉文件名闸会打回"仓库里不存在的文件名"（dwc_pairs.jsonl 恰好
      不存在 ⇒ 测试锁"纯文本收下"却被幻觉闸正确拦截）。换真实文件保住意图。
    """
    llm = _FakeLLM(["config/eval_tasks.jsonl"])
    rep = T.execute_user_task("文件名？", llm=llm, task_id="t_audit")
    assert rep["status"] == "done"
    blob = json.dumps(rep, ensure_ascii=False)
    assert "config/eval_tasks.jsonl" in blob


def test_plain_text_multiline_answer(work):
    """★ 多行纯文本也要收（模型常给带解释的答案）。"""
    txt = "一个不存在的内核文件名\n\n这是记忆内核的实现文件。"
    llm = _FakeLLM([txt])
    rep = T.execute_user_task("记忆内核在哪个文件？", llm=llm, task_id="t_multi")
    assert rep["status"] == "done"
    assert "一个不存在的内核文件名" in str(rep.get("answer") or "")


# ─────────────────────── ② 不能把垃圾当答案


def test_empty_response_still_incomplete(work):
    """★★ 空响应不许当成功（"什么都没有" ≠ 答案）。"""
    llm = _FakeLLM([""])
    rep = T.execute_user_task("x", llm=llm, task_id="t_empty")
    assert rep["status"] == "incomplete", rep


def test_whitespace_only_still_incomplete(work):
    """★★ 纯空白也不算答案。"""
    llm = _FakeLLM(["   \n\t  "])
    rep = T.execute_user_task("x", llm=llm, task_id="t_ws")
    assert rep["status"] == "incomplete", rep


def test_tool_calls_empty_content_not_answer(work):
    """★★ content 为空（finish=tool_calls）不许当答案。"""
    class _R:
        ok = True
        text = ""
        error = ""
        meta = {"finish_reason": "tool_calls"}

    class _L:
        configured = True

        def complete(self, *a, **k):
            return _R()

    rep = T.execute_user_task("x", llm=_L(), task_id="t_tc")
    assert rep["status"] == "incomplete", rep


# ─────────────────────── ③ 原有 final 路径不变


def test_json_final_op_still_works(work):
    """★★★ 回归保护：合法 JSON + final op 走原路径。"""
    llm = _FakeLLM([json.dumps({"analysis": "答",
                                "op": "final",
                                "answer": "这是答案"},
                               ensure_ascii=False)])
    rep = T.execute_user_task("问", llm=llm, task_id="t_final")
    assert rep["status"] == "done"
    assert rep["answer"] == "这是答案"


def test_json_without_op_not_treated_as_answer(work):
    """★★ 合法 JSON 但没有 op ⇒ 不许当答案（乱码/半截 JSON 的护栏）。"""
    llm = _FakeLLM(['{"foo": "bar"}', '{"foo": "bar"}', '{"foo": "bar"}',
                    '{"foo": "bar"}'])
    rep = T.execute_user_task("问", llm=llm, task_id="t_noop",
                              max_rounds=3)
    assert rep["status"] == "incomplete", (
        "无 op 的 JSON 被当答案了: %r" % rep.get("answer"))
