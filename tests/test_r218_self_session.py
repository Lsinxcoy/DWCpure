# -*- coding: utf-8 -*-
"""R218 · 自我认知注入 + 会话留痕（独立 agent 的持久自我）。"""
from __future__ import annotations

import io
import json
import os
import sys

ROOT = r"E:\Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "src"))
from dwc.llm import task_exec as TE                             # noqa: E402


class _FakeLLM:
    """最小 LLM 打桩: 一轮 final。"""

    def __init__(self, steps):
        self.steps = list(steps)
        self.systems = []

    def complete(self, prompt, system=None, **kw):
        self.systems.append(system or "")
        txt = json.dumps(self.steps.pop(0), ensure_ascii=False)
        return type("R", (), {"ok": True, "text": txt, "error": None})()


def test_self_md_injected_into_system():
    """★★★ 自我认知注入: dwc_self.md 内容进 system prompt（每次接单加载 —
    CLAUDE.md 同款; 注入≤4000 字符防爆上下文）。"""
    llm = _FakeLLM([{"op": "final", "answer": "ok", "artifacts": []}])
    TE.execute_user_task("测试注入", llm=llm, max_rounds=2)
    sys_prompt = llm.systems[0]
    assert "自我认知" in sys_prompt and "DWC" in sys_prompt, "自我文件没注入"
    assert len(sys_prompt) < 6000, "注入失控膨胀"


def test_session_jsonl_written(tmp_path, monkeypatch):
    """★★★ 会话留痕: 每任务一个 var/dwc_sessions/<id>.jsonl, 逐轮 op 落痕
    （session 概念最小形态 — 异步期间可查进度, 事后可审计）。"""
    monkeypatch.setattr(TE, "SESSIONS", str(tmp_path))
    llm = _FakeLLM([{"op": "final", "answer": "done", "artifacts": []}])
    rep = TE.execute_user_task("会话测试", llm=llm, task_id="T_sess218",
                               max_rounds=2)
    p = tmp_path / "T_sess218.jsonl"
    assert p.exists(), "会话文件没生成"
    evs = [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines()]
    assert any(e.get("op") == "final" for e in evs), evs
    assert rep["task_id"] == "T_sess218", "task_id 未回填进报告"


def test_self_md_absent_does_not_break(tmp_path, monkeypatch):
    """★ 自我文件缺席=空串不装有, 不炸单（诚实缺席）。"""
    monkeypatch.setattr(TE, "SELF_MD", str(tmp_path / "nonexist.md"))
    llm = _FakeLLM([{"op": "final", "answer": "ok", "artifacts": []}])
    rep = TE.execute_user_task("缺席测试", llm=llm, max_rounds=2)
    assert rep["status"] == "done"
    assert "自我认知" not in llm.systems[0]
