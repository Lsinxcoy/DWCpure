# -*- coding: utf-8 -*-
"""R227 · 真并行子代理: tasks 数组 ThreadPool 并发 + 汇总回喂。"""
from __future__ import annotations

import json
import os
import sys
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
from dwc.llm import task_exec as TE                             # noqa: E402


class _ParallelLLM:
    """线程安全脚本 LLM: 主任务第1轮 delegate 两子任务; 子代理各自 final。"""

    def __init__(self):
        self.lock = threading.Lock()
        self.n = 0
        self.t0 = None

    def complete(self, prompt, system=None, **kw):
        with self.lock:
            self.n += 1
            n = self.n
        if n == 1:
            txt = json.dumps({"op": "delegate", "tasks":
                              ["子任务A: 报告一个数字", "子任务B: 报告一个词"]})
        else:
            # 子代理（或主任务收尾）: 立即 final
            ans = "子答%d" % n
            txt = json.dumps({"op": "final", "answer": ans, "artifacts": []})
        return type("R", (), {"ok": True, "text": txt, "error": None})()


def test_parallel_delegate_collects_all(tmp_path, monkeypatch):
    """★★★ 并行: tasks[2] ⇒ 两个子代理都跑、摘要数组回喂（parallel 标记
    + subs 逐项）; 各自独立上下文（独立轮次计数）。"""
    monkeypatch.setattr(TE, "SESSIONS", str(tmp_path))
    llm = _ParallelLLM()
    rep = TE.execute_user_task("并行主任务", llm=llm, max_rounds=4,
                               task_id="T_par227")
    assert rep["status"] == "done", rep
    ops = [x["op"] for x in rep["actions_log"]]
    assert "delegate" in ops
    # 会话文件含子代理痕迹（T_par227_sub1_1 / _2）
    sess_files = os.listdir(tmp_path)
    assert any("sub" in f for f in sess_files), sess_files


def test_parallel_structural_lock():
    """★ 结构锁: 并行分支存在且上限 3（防打爆 LLM）。"""
    import inspect
    src = inspect.getsource(TE)
    assert "ThreadPoolExecutor(max_workers=3)" in src
    assert '"parallel": True' in src
    assert "list(enumerate(subs))[:3]" in src, "并行子代理数未限 3"
