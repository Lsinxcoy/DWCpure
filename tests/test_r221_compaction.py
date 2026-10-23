# -*- coding: utf-8 -*-
"""R221 · 会话 compaction: 滑动窗口 + 前情摘要（长任务的上下文管理）。"""
from __future__ import annotations

import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
from dwc.llm import task_exec as TE                             # noqa: E402


class _Scripted:
    """脚本化 LLM: 按步返回, 捕获 prompt。"""

    def __init__(self, steps):
        self.steps = list(steps)
        self.prompts = []

    def complete(self, prompt, system=None, **kw):
        self.prompts.append(prompt)
        txt = json.dumps(self.steps.pop(0), ensure_ascii=False)
        return type("R", (), {"ok": True, "text": txt, "error": None})()


def test_compaction_injects_summary_after_window(tmp_path, monkeypatch):
    """★★★ 第 4 轮起: 更早轮次压成『前情摘要』注入 prompt — 旧形态只带
    '上一步', 第 3 轮起 LLM 已忘第 1 轮（长任务反复重读同文件的根因）。"""
    monkeypatch.setattr(TE, "SESSIONS", str(tmp_path))
    steps = [
        {"op": "read", "path": "README.md"},
        {"op": "read", "path": "config/dials.yaml"},
        {"op": "read", "path": "README.md"},   # 故意重读 — 摘要应提示已读过
        {"op": "final", "answer": "done", "artifacts": []},
    ]
    llm = _Scripted(steps)
    TE.execute_user_task("多轮压缩测试", llm=llm, max_rounds=5,
                         task_id="T_comp221")
    # 第 4 轮 prompt（index 3）应含前情摘要
    p4 = llm.prompts[3]
    assert "前情摘要" in p4 and "read" in p4, p4[:300]
    # 窗口内最近轮原文仍在（最近 2 轮 JSON）
    assert "最近轮次" in p4


def test_early_rounds_have_no_summary(tmp_path, monkeypatch):
    """★ 前 3 轮无摘要（窗口未满不注入 — 零开销）。"""
    monkeypatch.setattr(TE, "SESSIONS", str(tmp_path))
    steps = [{"op": "final", "answer": "x", "artifacts": []}]
    llm = _Scripted(steps)
    TE.execute_user_task("早轮测试", llm=llm, max_rounds=2)
    assert "前情摘要" not in llm.prompts[0]
