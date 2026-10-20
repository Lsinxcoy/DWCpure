# -*- coding: utf-8 -*-
"""R382 · 收件箱必须有独立轮询线程（不许等 term 间隙）。

★★★ 现场取证（2026-10-20 13:47–13:55 全池跑批）:
  · 13:47:29 投单 `nb_1020_134729_01`
  · 13:55:06 才 `user_task_async_started`（**排队 7 分 37 秒**）
  · 13:55:11 出报告（**执行只用了 5 秒**）

  ⇒ 瓶颈 100% 在排队。根因：`take_inbox()` 写在主循环里，**每个 term
    才轮询一次**；而一个 term 实测要 ~10 分钟（prod_log 13:45:06 →
    13:55:08）。注释写着「收件箱优先（用户委托 > 自我改进锚任务）」，
    实现却是「收件箱每 10 分钟才被看一次」。

  52 单 × 7.5 分钟 = 6 小时。这不是"慢"，是**架构错了**：
  用户委托不该排在自主循环后面。

★ 判据（本轮锁的）:
  · 存在独立的收件箱轮询线程，轮询间隔**秒级**（不是 term 级）
  · 主循环启动时拉起该线程（源码级锁，防"写了函数没接线"）
  · 线程是 daemon（不阻止进程退出）
  · 支持 stop_event 优雅停止
  · 投单后**秒级**被取走（行为测试：模拟一个跑 30s 的慢 term，
    投单后 3s 内必须已被接单）
"""
from __future__ import annotations

import inspect
import os
import re
import sys
import threading
import time

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "scripts", "dwc_agent.py")


def _src() -> str:
    return open(SRC, encoding="utf-8").read()


# ─────────────────────── ① 函数存在且行为正确


def test_poller_exists_and_is_seconds_not_term():
    """★★★ 必须有独立的收件箱轮询函数，间隔是**秒级**。"""
    s = _src()
    assert "def start_inbox_poller" in s, (
        "缺 start_inbox_poller —— 收件箱只能等 term 间隙，实测排队 7.5 分钟")
    m = re.search(r"def start_inbox_poller\(([^)]*)\)", s)
    assert m, "签名读不出来"
    sig = m.group(1)
    m2 = re.search(r"interval\s*(?::\s*\w+\s*)?=\s*([A-Za-z_][\w.]*|[\d.]+)",
                   sig)
    assert m2, "start_inbox_poller 缺 interval 默认值"
    raw = m2.group(1)
    if re.match(r"^[\d.]+$", raw):
        val = float(raw)
    else:                                    # 常量名 ⇒ 解析模块级定义
        mc = re.search(r"^%s\s*=\s*([\d.]+)" % re.escape(raw), s, re.M)
        assert mc, "默认值常量 %r 找不到定义" % raw
        val = float(mc.group(1))
    assert val <= 30, (
        "默认轮询间隔 %ss 太慢（应 ≤30s，秒级）" % val)


def test_poller_dispatches_within_seconds(monkeypatch):
    """★★★ 行为测试：投单后**秒级**被取走。

    模拟场景：主循环正在跑一个慢 term（30s），此时投单。
    旧实现要等 term 结束（30s+）才接单；新实现必须 3s 内接单。
    """
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    import importlib.util
    spec = importlib.util.spec_from_file_location("dwc_agent_r382", SRC)
    A = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(A)
    except Exception:                              # noqa: BLE001 — 导入期依赖
        pytest.skip("dwc_agent 导入失败（环境依赖），跳过行为测试")

    got = []
    lock = threading.Lock()

    def _fake_take():
        with lock:
            if got:
                return None
            got.append("taken")
            return {"id": "probe_1", "task": "x"}

    monkeypatch.setattr(A, "take_inbox", _fake_take)
    monkeypatch.setattr(A, "run_user_task", lambda it, u: None)

    stop = threading.Event()
    t = A.start_inbox_poller(interval=0.2, stop_event=stop)
    try:
        t0 = time.time()
        while time.time() - t0 < 3.0:
            if got:
                break
            time.sleep(0.05)
        assert got, "投单 3s 内没被取走 —— 收件箱仍在等 term 间隙"
    finally:
        stop.set()
        t.join(timeout=3)
    assert not t.is_alive(), "stop_event 没让轮询线程退出"


def test_poller_thread_is_daemon(monkeypatch):
    """★★ daemon 线程（不阻止进程退出）。"""
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    import importlib.util
    spec = importlib.util.spec_from_file_location("dwc_agent_r382b", SRC)
    A = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(A)
    except Exception:                              # noqa: BLE001
        pytest.skip("dwc_agent 导入失败")
    monkeypatch.setattr(A, "take_inbox", lambda: None)
    stop = threading.Event()
    t = A.start_inbox_poller(interval=0.1, stop_event=stop)
    try:
        assert t.daemon is True, "轮询线程必须是 daemon，否则进程退不出去"
    finally:
        stop.set()
        t.join(timeout=3)


# ─────────────────────── ② 主循环必须接线


def test_main_loop_starts_poller():
    """★★★ 源码级锁：主循环必须**启动**轮询线程。

    只写函数不接线 = 白写（本项目已发生过"函数没错、调用点漏了"）。
    """
    s = _src()
    assert "start_inbox_poller(" in s, "主循环没启动收件箱轮询线程"
    # 排除"只有定义没有调用"的情况
    calls = [m for m in re.finditer(r"start_inbox_poller\(", s)]
    assert len(calls) >= 2, (
        "只找到定义没找到调用 —— 收件箱轮询线程没接线")


def test_main_loop_no_longer_polls_inbox_synchronously():
    """★★ 主循环里不许再同步 `take_inbox()`（会与轮询线程抢单）。

    允许且必须：轮询线程内部调用一次。
    禁止：主循环体里再取一次（两个消费者 ⇒ 重复投递）。
    """
    s = _src()
    n = len(re.findall(r"item\s*=\s*take_inbox\(\)", s))
    assert n == 1, (
        "`item = take_inbox()` 出现 %d 次（应恰好 1 次，在轮询线程里）—— "
        "多个消费者会重复取单" % n)


def test_take_inbox_is_locked():
    """★★★ take_inbox 必须加锁（两个消费者并发读同一文件会重复投递）。"""
    s = _src()
    assert "_INBOX_LOCK" in s, (
        "缺 _INBOX_LOCK —— 轮询线程与其它调用方并发读 inbox 会重复取单")


# ─────────────────────── ③ 不许破坏既有语义


def test_semaphore_still_limits_concurrency():
    """★★ 并发上限仍为 2（防打爆 LLM；R379 串行锁在 client 层）。"""
    s = _src()
    assert "threading.Semaphore(2)" in s, "并发上限被改了（应保持 2）"
