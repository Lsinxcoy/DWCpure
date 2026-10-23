# -*- coding: utf-8 -*-
"""R219 · 异步接单: running 标记防重取 + stale 恢复 + 主循环不阻塞。"""
from __future__ import annotations

import io
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.path.insert(0, os.path.join(ROOT, "src"))
import dwc_agent as A                                           # noqa: E402


def _iso(tmp_path, monkeypatch):
    inbox = tmp_path / "inbox.jsonl"
    done = tmp_path / "done.json"
    monkeypatch.setattr(A, "INBOX", str(inbox))
    monkeypatch.setattr(A, "INBOX_DONE", str(done))
    done.write_text("{}", encoding="utf-8")
    return inbox, done


def test_running_mark_skips_and_stale_recovers(tmp_path, monkeypatch):
    """★★★ running 标记: 新鲜 running(<15min) 跳过不重取; 过期(>15min)=
    线程死了 ⇒ 重取恢复（异步接单的崩溃自愈面）。"""
    inbox, done = _iso(tmp_path, monkeypatch)
    inbox.write_text(json.dumps({"id": "T_a", "task": "x"}) + "\n",
                     encoding="utf-8")
    done.write_text(json.dumps(
        {"T_a": "running:%.0f" % time.time()}), encoding="utf-8")
    assert A.take_inbox() is None, "新鲜 running 被重取 — 并发双跑"
    done.write_text(json.dumps(
        {"T_a": "running:%.0f" % (time.time() - 1000)}), encoding="utf-8")
    got = A.take_inbox()
    assert got and got["id"] == "T_a", "stale 未恢复 — 线程死了单子永久卡死"
    st = json.loads(done.read_text(encoding="utf-8"))
    assert st["T_a"] == "stale_recovered", "恢复未留痕"


def test_done_state_not_retrieved(tmp_path, monkeypatch):
    """★ 终态不重取（done/cancelled/incomplete 都是终态）。"""
    inbox, done = _iso(tmp_path, monkeypatch)
    inbox.write_text(json.dumps({"id": "T_b", "task": "y"}) + "\n",
                     encoding="utf-8")
    done.write_text(json.dumps({"T_b": "done"}), encoding="utf-8")
    assert A.take_inbox() is None


def test_main_loop_is_async_structural():
    """★★ 结构锁: 主循环 inbox 消费走后台线程 + 并发信号量 + 不阻塞
    （源码级: threading.Thread daemon + _INBOX_SEMA + 无阻塞 continue）。"""
    import inspect
    src = inspect.getsource(A)
    assert 'threading.Thread(target=_bg, daemon=True' in src, "接单未异步化"
    # ★ R435 重锚：宽度可配，但默认仍是 2
    assert "_INBOX_SEMA" in src and "threading.Semaphore(_width)" in src, "无并发上限"
    assert "DWC_TASK_CONCURRENCY" in src and "or 2" in src, "默认并发不是 2"
    assert "user_task_async_started" in src, "无异步启动留痕"
    assert "user_task_crashed" in src, "线程异常无兜底留痕（不许静默死）"
