# -*- coding: utf-8 -*-
"""R396 · 卡住时必须**强制** final_answer（tool_choice 硬约束）。

★★★ 现场（2026-10-20 21:35 全池，R394 上线后）：
  cl01/cl02 仍 incomplete，`why` 都是复读熔断，但动作日志显示
  **模型其实已经拿到答案了**：

      nb_..._14: search ok=True → read src/dwc/organs/memory.py ok=True
                 → 又搜 3 次（全被熔断拦）→ incomplete

  即：模型**知道答案却不提交**，反复自证到死。

★ 根因：R385 的收敛机制只靠**提示词**（"现在立即调用 final_answer"）。
  模型可以无视提示词继续调工具 —— 提示词不是约束。

★ 修法：卡住时把 `tool_choice` 从 `"auto"` 换成
  `{"type":"function","function":{"name":"final_answer"}}` ——
  **API 层强制**模型只能调 final_answer。端点不支持就退回 auto。
"""
from __future__ import annotations

import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.llm import task_exec as T  # noqa: E402


class _Recorder:
    """记录每次 complete 的 tool_choice，并按脚本返回 tool_calls。"""

    configured = True

    def __init__(self, script):
        self.script = script
        self.calls = []
        self.n = 0

    def complete(self, prompt, **kw):
        self.calls.append({"tool_choice": kw.get("tool_choice"),
                           "has_tools": bool(kw.get("tools"))})
        i = min(self.n, len(self.script) - 1)
        self.n += 1
        return self.script[i]


def _tc(name, args, cid="c1"):
    return {"id": cid, "type": "function",
            "function": {"name": name, "arguments": json.dumps(args)}}


def _res(tool_calls):
    from types import SimpleNamespace
    return SimpleNamespace(ok=True, error=None, text="",
                           meta={"tool_calls": tool_calls,
                                 "finish_reason": "tool_calls"})


@pytest.fixture(autouse=True)
def _native(monkeypatch):
    monkeypatch.setenv("DWC_LLM_NATIVE_TOOLS", "1")


def test_tool_choice_forced_to_final_when_stuck(monkeypatch):
    """★★★ 同一动作重复到阈值 ⇒ 下一次调用必须 tool_choice=final_answer。"""
    # 同一个搜索动作重复 5 次（触发 REPEAT_LIMIT=4）
    script = [_res([_tc("search_code", {"pattern": "MemoryKernel"})])] * 6
    llm = _Recorder(script)
    T.execute_user_task("MemoryKernel 定义在哪个文件", llm=llm,
                        task_id="T_R396a", max_rounds=8)
    forced = [c for c in llm.calls
              if isinstance(c["tool_choice"], dict)
              and c["tool_choice"].get("function", {}).get("name") == "final_answer"]
    assert forced, "卡住时没有强制 final_answer，tool_choice 一直是: %r" % [
        c["tool_choice"] for c in llm.calls]


def test_tool_choice_auto_at_start(monkeypatch):
    """★★ 第 1 轮必须是 auto（不许一上来就强制 final）。"""
    script = [_res([_tc("final_answer", {"answer": "答案在这里足够长"})])]
    llm = _Recorder(script)
    T.execute_user_task("随便问问", llm=llm, task_id="T_R396b", max_rounds=4)
    assert llm.calls[0]["tool_choice"] == "auto", llm.calls[0]


def test_forced_final_produces_answer(monkeypatch):
    """★★★ 强制 final 后模型真给答案 ⇒ 报告必须是 done（不是 incomplete）。"""
    script = [
        _res([_tc("search_code", {"pattern": "MemoryKernel"})]),
        _res([_tc("search_code", {"pattern": "MemoryKernel"})]),
        _res([_tc("search_code", {"pattern": "MemoryKernel"})]),
        _res([_tc("search_code", {"pattern": "MemoryKernel"})]),
        _res([_tc("search_code", {"pattern": "MemoryKernel"})]),
        _res([_tc("final_answer", {"answer": "定义在 src/dwc/organs/memory.py"})]),
    ]
    llm = _Recorder(script)
    rep = T.execute_user_task("MemoryKernel 定义在哪个文件", llm=llm,
                              task_id="T_R396c", max_rounds=10)
    assert rep["status"] == "done", rep.get("why")
    assert "memory.py" in str(rep.get("answer") or "")


def test_normal_path_not_forced():
    """★★ 正常 2 轮完成的任务不许出现强制 final（零破坏）。"""
    script = [
        _res([_tc("search_code", {"pattern": "MemoryKernel"})]),
        _res([_tc("final_answer", {"answer": "在 src/dwc/organs/memory.py"})]),
    ]
    llm = _Recorder(script)
    rep = T.execute_user_task("MemoryKernel 在哪", llm=llm,
                              task_id="T_R396d", max_rounds=8)
    assert rep["status"] == "done"
    assert all(c["tool_choice"] == "auto" for c in llm.calls), \
        [c["tool_choice"] for c in llm.calls]
