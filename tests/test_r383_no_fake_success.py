# -*- coding: utf-8 -*-
"""R383 · 「声称已执行但零动作」必须判 incomplete（修 R380 的假成功）。

★★★ 现场取证（2026-10-20 14:14–15:10 全池 52 单跑批）:
  报告里 **51/54 = 94% 的 `actions_log` 为空**，而模型在 `answer` 里写：
    wr03  "已写入 `var/inbox_work/list.md`,内容: ..."   ← 文件根本没写
    wr05  "已在 `var/inbox_work/note.txt` 写入,内容为..." ← 根本没写
    wr07  "已写入 `var/inbox_work/two.txt`：..."        ← 根本没写
    wr01  "`flag.txt` 已写入,内容为 `EVAL_E2E_COMPLETE`" ← 根本没写
    an04  "我无法执行文件写入（**没有可用的文件/终端工具**）"

  ⇒ R380 把"非 JSON 纯文本"收下当答案（status=done），结果模型**说**
    它写了文件就被当成完成 —— 这是**假成功**，正是本项目一直反对的
    「降级与成功不可区分」。

★ 判据（本轮锁的）:
  · 纯文本 + 零动作 + 文本里**声称**执行过动作（已写入/已创建/已执行/
    已运行/写入成功…）⇒ `status=incomplete`，`why` 说明是幻觉
  · 纯文本 + 零动作 + 文本是**明确的拒绝**（我无法/没有可用工具…）
    ⇒ `status=incomplete`
  · 纯文本 + 零动作 + 只是**陈述性答案**（纯知识题，如"世界模型的作用是…"）
    ⇒ 仍然收下（这类任务本来不需要工具）
  · 有动作的路径**完全不变**（回归保护）
"""
from __future__ import annotations

import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.llm import task_exec as T  # noqa: E402


class _Res:
    def __init__(self, text, finish="stop"):
        self.ok = True
        self.text = text
        self.error = ""
        self.meta = {"finish_reason": finish}


class _LLM:
    configured = True

    def __init__(self, texts):
        self._t = list(texts)

    def complete(self, *a, **k):
        return _Res(self._t.pop(0) if self._t else "")


@pytest.fixture()
def work(tmp_path, monkeypatch):
    monkeypatch.setattr(T, "WORK", str(tmp_path))
    monkeypatch.setattr(T, "SESSIONS", str(tmp_path / "sessions"))
    (tmp_path / "sessions").mkdir(exist_ok=True)
    monkeypatch.setattr(T, "SELF_MD", str(tmp_path / "self.md"))
    return tmp_path


# ─────────────────────── ① 幻觉动作必须判死


@pytest.mark.parametrize("claim", [
    "已写入 `var/inbox_work/list.md`,内容: 检查输入源文件",
    "已在 `var/inbox_work/note.txt` 写入,内容为: DWC 999",
    "已写入 `var/inbox_work/two.txt`：A B",
    "`var/inbox_work/flag.txt` 已写入,内容为 EVAL_E2E_COMPLETE",
    "文件创建成功。",
    "已执行命令,退出码 0。",
    "已运行测试,全部通过。",
    "写入成功。",
])
def test_claimed_action_without_action_is_incomplete(work, claim):
    """★★★ 声称执行了动作但零动作 ⇒ 必须 incomplete（假成功）。

    现场：wr01/wr03/wr05/wr07 全部这样被判 done，文件实际没写。
    """
    llm = _LLM([claim])
    rep = T.execute_user_task("在 var/inbox_work/list.md 写一个清单",
                              llm=llm, task_id="t_claim")
    assert rep["status"] == "incomplete", (
        "零动作却声称已执行，被判 done —— 假成功（answer=%r）"
        % rep.get("answer"))
    why = str(rep.get("why") or "")
    assert why.strip(), "incomplete 但 why 空着（无法审计）"
    assert ("声称" in why) or ("幻觉" in why), (
        "why 没说明是「声称动作但零动作」: %r" % why)


# ─────────────────────── ② 拒绝也必须判死


@pytest.mark.parametrize("refusal", [
    "我无法执行文件写入（没有可用的文件/终端工具）。",
    "我无法直接访问文件系统,因此不能列出目录。",
    "抱歉,我没有访问你项目文件系统的能力。",
    "我无法完成这个任务:我没有终端工具。",
])
def test_refusal_is_incomplete(work, refusal):
    """★★★ 明确拒绝 ⇒ incomplete（不许当答案）。"""
    llm = _LLM([refusal])
    rep = T.execute_user_task("列出 src/dwc/organs 下的文件",
                              llm=llm, task_id="t_refuse")
    assert rep["status"] == "incomplete", (
        "拒绝被当成答案（answer=%r）" % rep.get("answer"))


# ─────────────────────── ③ 纯知识答案仍要收下（不许修过头）


@pytest.mark.parametrize("answer", [
    "世界模型的核心作用是让智能体在内部模拟环境,从而预测与规划。",
    "上轮没执行的原因是复读熔断触发了。",
    "0xFEFF",
    "Ctrl+P",
])
def test_knowledge_answer_still_accepted(work, answer):
    """★★★ 纯陈述性答案（不需要工具的知识题）必须仍然收下。

    修过头的后果：hs01/hs02/rf01/rf02 这些本来能过的会全挂。
    """
    llm = _LLM([answer])
    rep = T.execute_user_task("世界模型的作用是什么？", llm=llm,
                              task_id="t_know")
    assert rep["status"] == "done", (
        "知识题答案被判死（why=%r）—— 修过头了" % rep.get("why"))
    assert answer[:20] in str(rep.get("answer") or "")


# ─────────────────────── ④ 回归保护


def test_json_final_op_unchanged(work):
    """★★ JSON + final op 路径完全不变。"""
    llm = _LLM([json.dumps({"analysis": "答", "op": "final",
                            "answer": "这是答案"}, ensure_ascii=False)])
    rep = T.execute_user_task("问", llm=llm, task_id="t_final")
    assert rep["status"] == "done"
    assert rep["answer"] == "这是答案"


def test_empty_still_incomplete(work):
    """★★ 空响应仍判 incomplete。"""
    rep = T.execute_user_task("x", llm=_LLM([""]), task_id="t_empty")
    assert rep["status"] == "incomplete"
