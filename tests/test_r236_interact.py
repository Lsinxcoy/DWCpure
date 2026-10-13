# -*- coding: utf-8 -*-
"""R236 · 同步直驱交互：progress 事件流 / chat 路由 / 渲染。"""
from __future__ import annotations

import os
import sys

ROOT = r"E:\Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from dwc.llm import task_exec as TE                             # noqa: E402
import dwc_chat as CH                                           # noqa: E402


class _FakeLLM:
    """两轮假 LLM: 第一轮 read, 第二轮 final — 只测事件流不触网。"""
    configured = True

    def __init__(self):
        self.n = 0

    def complete(self, *a, **k):
        # ★ task_exec 期望对象形态（res.ok / res.text 属性 — client 同款）
        from types import SimpleNamespace
        self.n += 1
        if self.n == 1:
            return SimpleNamespace(ok=True, error=None,
                text='{"analysis": "先读", "op": "read",'
                     ' "path": "README.md"}')
        return SimpleNamespace(ok=True, error=None,
            text='{"analysis": "收尾", "op": "final",'
                 ' "answer": "第一行\\n\\n## 标题\\n**要点**"}')


def test_progress_event_stream():
    """★★★ 事件流锁: progress 收到 round→action→final 全链事件
    （Claude Code 式实时可视化的数据源 — 事件缺一即体验塌）。"""
    events = []
    rep = TE.execute_user_task("测试任务", llm=_FakeLLM(), progress=events.append)
    kinds = [e["ev"] for e in events]
    assert "round" in kinds and "action" in kinds and "final" in kinds, kinds
    acts = [e for e in events if e["ev"] == "action"]
    assert acts[0]["op"] == "read" and acts[0]["ok"] is True, acts
    fin = [e for e in events if e["ev"] == "final"][0]
    assert "第一行" in fin["answer"]
    assert rep["status"] == "done"
    # 零破坏: 不传 progress 照常工作
    rep2 = TE.execute_user_task("测试任务", llm=_FakeLLM())
    assert rep2["status"] == "done"


def test_chat_sync_routing(capsys, monkeypatch):
    """★★ 路由锁: 默认(非 BG)走同步直驱; /bg 切异步投单; /fg 切回。"""
    called = {}
    monkeypatch.setattr(CH, "_run_sync", lambda t: called.setdefault("sync", t))
    monkeypatch.setattr(CH, "BG_MODE", False)
    CH.handle("随便什么任务")
    assert called.get("sync") == "随便什么任务"
    called.clear()
    CH.handle("/bg")
    assert CH.BG_MODE is True
    CH.handle("/fg")
    assert CH.BG_MODE is False


def test_md_renderer(capsys):
    """★ 渲染锁: 代码块保原缩进 + 标题去#上粗 + **粗体**标记去除。"""
    out = CH._md("前言\n\n```py\ncode()\n```\n\n## 标题\n**要点**文字")
    assert "  code()" in out              # 代码块保原（缩进两格）
    assert "标题" in out and "##" not in out.split("标题")[0][-3:]
    assert "**" not in out
