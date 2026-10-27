# -*- coding: utf-8 -*-
"""P0.5 · 契约补齐：有动作但缺产物时给一次明确修复机会。"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
from dwc.llm import task_exec as TE                             # noqa: E402


class _LLM:
    configured = True

    def __init__(self, steps):
        self.steps = list(steps)
        self.n = 0

    def complete(self, prompt, system=None, **kw):
        self.n += 1
        if not self.steps:
            raise AssertionError("契约补齐后又多调了一次 LLM")
        return type("R", (), {
            "ok": True, "error": None,
            "text": json.dumps(self.steps.pop(0), ensure_ascii=False)})()


def test_contract_repair_writes_missing_artifact(tmp_path, monkeypatch):
    monkeypatch.setenv("DWC_LLM_NATIVE_TOOLS", "0")
    monkeypatch.setenv("DWC_WORKING_STATE_GATE", "0")
    monkeypatch.setattr(TE, "ROOT", str(tmp_path))
    monkeypatch.setattr(TE, "WORK", str(tmp_path / "var" / "inbox_work"))
    monkeypatch.setattr(TE, "SESSIONS", str(tmp_path / "sessions"))
    monkeypatch.setattr(TE, "SELF_MD", str(tmp_path / "self.md"))
    (tmp_path / "sessions").mkdir()
    (tmp_path / "var" / "inbox_work").mkdir(parents=True)
    (tmp_path / "README.md").write_text("x\n", encoding="utf-8")

    llm = _LLM([
        {"analysis": "先看文件", "op": "read", "path": "README.md"},
        {"analysis": "done", "op": "final", "answer": "好了"},
        {"analysis": "补产物", "op": "write",
         "path": "var/inbox_work/repair_test.md", "content": "# ok\n"},
        {"analysis": "done", "op": "final", "answer": "已补齐"},
    ])
    rep = TE.execute_user_task(
        "写一个报告并保存到 var/inbox_work/repair_test.md",
        llm=llm, max_rounds=5, retry_on_fail=False)
    assert rep["status"] == "done", rep
    assert rep["contract"]["ok"] is True
    assert (tmp_path / "var" / "inbox_work" / "repair_test.md").exists()
    assert llm.n == 4, "应只补一次：read → final → 修复 → final"


def test_contract_repair_does_not_run_without_actions(tmp_path, monkeypatch):
    monkeypatch.setenv("DWC_LLM_NATIVE_TOOLS", "0")
    monkeypatch.setattr(TE, "ROOT", str(tmp_path))
    monkeypatch.setattr(TE, "SESSIONS", str(tmp_path / "sessions"))
    monkeypatch.setattr(TE, "SELF_MD", str(tmp_path / "self.md"))
    (tmp_path / "sessions").mkdir()

    class _One(_LLM):
        def complete(self, prompt, system=None, **kw):
            self.n += 1
            return type("R", (), {
                "ok": True, "error": None,
                "text": '{"analysis":"done","op":"final","answer":"好了"}'})()

    llm = _One([])
    rep = TE.execute_user_task(
        "写一个报告并保存到 var/inbox_work/x.md",
        llm=llm, max_rounds=2, retry_on_fail=False)
    assert rep["status"] == "incomplete"
    assert llm.n == 1, "零动作不应触发补齐（直接判死）"
