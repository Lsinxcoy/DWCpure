# -*- coding: utf-8 -*-
"""P1 · plan mode：enter 后写/改/跑被拦，exit 后解锁。"""
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
            raise AssertionError("plan mode 测试步数不够")
        return type("R", (), {
            "ok": True, "error": None,
            "text": json.dumps(self.steps.pop(0), ensure_ascii=False)})()


def _env(tmp_path, monkeypatch):
    monkeypatch.setenv("DWC_LLM_NATIVE_TOOLS", "0")
    monkeypatch.setenv("DWC_WORKING_STATE_GATE", "0")
    monkeypatch.setattr(TE, "ROOT", str(tmp_path))
    monkeypatch.setattr(TE, "WORK", str(tmp_path / "var" / "inbox_work"))
    monkeypatch.setattr(TE, "SESSIONS", str(tmp_path / "sessions"))
    monkeypatch.setattr(TE, "SELF_MD", str(tmp_path / "self.md"))
    (tmp_path / "sessions").mkdir()
    (tmp_path / "var" / "inbox_work").mkdir(parents=True)


def test_plan_mode_blocks_write_until_exit(tmp_path, monkeypatch):
    _env(tmp_path, monkeypatch)
    llm = _LLM([
        {"analysis": "先计划", "op": "enter_plan"},
        {"analysis": "想写", "op": "write",
         "path": "var/inbox_work/plan.md", "content": "too early\n"},
        {"analysis": "退出", "op": "exit_plan"},
        {"analysis": "写", "op": "write",
         "path": "var/inbox_work/plan.md", "content": "# ok\n"},
        {"analysis": "done", "op": "final", "answer": "完成"},
    ])
    rep = TE.execute_user_task(
        "写一个报告并保存到 var/inbox_work/plan.md",
        llm=llm, max_rounds=6, retry_on_fail=False)
    assert rep["status"] == "done", rep
    p = tmp_path / "var" / "inbox_work" / "plan.md"
    assert p.read_text(encoding="utf-8") == "# ok\n"
    blocked = [e for e in rep["actions_log"]
               if e.get("target") == "plan_mode"]
    assert blocked and blocked[0]["ok"] is False
    assert llm.n == 5


def test_plan_tools_are_registered_and_valid():
    names = [t["function"]["name"] for t in TE.TASK_TOOLS]
    assert "enter_plan" in names and "exit_plan" in names
    assert TE._TOOL_TO_OP["enter_plan"][0] == "enter_plan"
    from dwc.llm.step_judge import judge_step, validate_step
    for op in ("enter_plan", "exit_plan"):
        verdict, why, rule = judge_step({"op": op}, [])
        assert verdict != "noisy", (op, verdict, why, rule)
        assert validate_step({"op": op}) is None
