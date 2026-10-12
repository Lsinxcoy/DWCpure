# -*- coding: utf-8 -*-
"""R223 · delegate 子代理: 独立上下文隔离 + 深度限 1 防递归。"""
from __future__ import annotations

import json
import os
import sys

ROOT = r"E:\Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "src"))
from dwc.llm import task_exec as TE                             # noqa: E402


class _Delegating:
    """第一轮 delegate, 之后 final。"""

    def __init__(self, sub_steps):
        self.calls = 0
        self.sub_steps = sub_steps

    def complete(self, prompt, system=None, **kw):
        self.calls += 1
        if self.calls == 1:
            txt = json.dumps({"op": "delegate", "task": "子研究"})
        elif self.calls == 2:
            # 子代理的脚本化 LLM — 同实例: 子代理第 1 轮 final
            txt = json.dumps({"op": "final", "answer": "子结论",
                              "artifacts": []})
        else:
            txt = json.dumps({"op": "final", "answer": "汇总", "artifacts": []})
        return type("R", (), {"ok": True, "text": txt, "error": None})()


def test_delegate_runs_subagent_and_feeds_summary(tmp_path, monkeypatch):
    """★★★ delegate: 子代理真跑（独立轮次）, 报告摘要回喂主任务 —
    主上下文只收摘要不收子代理的全部 read 输出（隔离价值）。"""
    monkeypatch.setattr(TE, "SESSIONS", str(tmp_path))
    llm = _Delegating([])
    rep = TE.execute_user_task("主任务", llm=llm, max_rounds=4,
                               task_id="T_del223")
    assert rep["status"] == "done"
    ops = [x["op"] for x in rep["actions_log"]]
    assert "delegate" in ops, ops


def test_depth_limit_blocks_recursive_delegate(tmp_path, monkeypatch):
    """★★★ 深度限 1: 子代理内 delegate 被拒（防递归爆炸 — 错误信息明确）。"""
    monkeypatch.setattr(TE, "SESSIONS", str(tmp_path))

    class _SubDelegating:
        def __init__(self):
            self.n = 0

        def complete(self, prompt, system=None, **kw):
            self.n += 1
            if "子代理内不可再 delegate" in prompt:
                # 子代理收到深度拒绝后 → final 收场
                txt = json.dumps({"op": "final", "answer": "子代理收场",
                                  "artifacts": []})
            elif self.n == 1:
                txt = json.dumps({"op": "delegate", "task": "父任务的委派"})
            elif self.n == 2:
                txt = json.dumps({"op": "delegate", "task": "子代理想再委派"})
            else:
                txt = json.dumps({"op": "final", "answer": "父收场",
                                  "artifacts": []})
            return type("R", (), {"ok": True, "text": txt, "error": None})()
    rep = TE.execute_user_task("深度测试", llm=_SubDelegating(),
                               max_rounds=5, task_id="T_depth223")
    assert rep["status"] == "done", rep
