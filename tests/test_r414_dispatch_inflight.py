# -*- coding: utf-8 -*-
"""R414 · 派发即登记 running（线程还堵在信号量上也要可见）。

★★★ 现场（2026-10-21 18:29–19:31）：
    任务 `nb_1021_183508_42` 被派发 **1080 次**（prod log 实测），
    之后 6 单全部 `timeout/no-report`，整轮跑批作废。

    根因链：
      ① `running:` 标记原来写在 `run_user_task` 里；
      ② `run_user_task` 在 `with _sema:` **内部**（并发上限 2）；
      ③ 两个槽位被长任务占满 ⇒ 新线程全堵在 `with _sema:`；
      ④ 它们永远走不到写标记那一步 ⇒ `take_inbox()` 每 3s 又取到同一单；
      ⑤ 线程无限堆积（1080 个）⇒ 进程拖死。

    ⇒ 登记必须在**派发点**完成（同步、无阻塞），再加一道
      "本进程在飞集合"闸，不依赖落盘也能挡住重取。
"""
from __future__ import annotations

import json
import os
import sys
import threading
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


def test_mark_written_even_when_semaphore_full(tmp_path, monkeypatch):
    """★★★ 核心：槽位占满、线程根本没进 run_user_task，标记也必须已落盘。"""
    _iso(tmp_path, monkeypatch)
    gate = threading.Event()
    monkeypatch.setattr(A, "run_user_task", lambda it, u: gate.wait(3))
    monkeypatch.setattr(A, "_INBOX_SEMA", threading.Semaphore(0), raising=False)  # 槽位占满
    monkeypatch.setattr(A, "_INBOX_INFLIGHT", set(), raising=False)

    A._dispatch_inbox({"id": "T_x", "task": "x"}, False)
    st = json.loads((tmp_path / "done.json").read_text(encoding="utf-8"))
    assert str(st.get("T_x", "")).startswith("running:"), \
        "派发后没登记 running — 轮询会无限重投（1080 次事故）"

    # 清理：放行槽位 + 让任务返回
    A._INBOX_SEMA.release()
    gate.set()
    time.sleep(0.3)


def test_inflight_blocks_repick(tmp_path, monkeypatch):
    """★★★ 第二道闸：即使落盘失败，在飞集合也不许重取。"""
    inbox, done = _iso(tmp_path, monkeypatch)
    inbox.write_text(json.dumps({"id": "T_y", "task": "y"}) + "\\n",
                     encoding="utf-8")
    gate = threading.Event()
    monkeypatch.setattr(A, "run_user_task", lambda it, u: gate.wait(3))
    monkeypatch.setattr(A, "_INBOX_SEMA", threading.Semaphore(2), raising=False)
    monkeypatch.setattr(A, "_INBOX_INFLIGHT", set(), raising=False)

    A._dispatch_inbox({"id": "T_y", "task": "y"}, False)
    assert "T_y" in A._INBOX_INFLIGHT
    assert A.take_inbox() is None, "在飞的单被重取 — 会重复执行"

    gate.set()
    time.sleep(0.4)
    assert "T_y" not in A._INBOX_INFLIGHT, "线程退出后没出在飞集合"


def test_thread_exit_clears_inflight_even_on_crash(tmp_path, monkeypatch):
    """★★ 反面保护：任务抛异常也必须清掉在飞标记，否则这单永远取不回来。"""
    _iso(tmp_path, monkeypatch)

    def _boom(it, u):
        raise RuntimeError("boom")

    monkeypatch.setattr(A, "run_user_task", _boom)
    monkeypatch.setattr(A, "_INBOX_SEMA", threading.Semaphore(2), raising=False)
    monkeypatch.setattr(A, "_INBOX_INFLIGHT", set(), raising=False)

    A._dispatch_inbox({"id": "T_z", "task": "z"}, False)
    time.sleep(0.5)
    assert "T_z" not in A._INBOX_INFLIGHT, "异常退出没清在飞标记"


def test_normal_dispatch_still_runs(tmp_path, monkeypatch):
    """★ 旧行为保护：正常派发仍然把任务跑起来。"""
    _iso(tmp_path, monkeypatch)
    seen = []
    monkeypatch.setattr(A, "run_user_task", lambda it, u: seen.append(it["id"]))
    monkeypatch.setattr(A, "_INBOX_SEMA", threading.Semaphore(2), raising=False)
    monkeypatch.setattr(A, "_INBOX_INFLIGHT", set(), raising=False)

    A._dispatch_inbox({"id": "T_n", "task": "n"}, False)
    time.sleep(0.4)
    assert seen == ["T_n"], seen
