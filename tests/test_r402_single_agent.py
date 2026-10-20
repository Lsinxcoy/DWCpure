# -*- coding: utf-8 -*-
"""R402 · 有进程就绝不拉第二个 agent（重复消费者 = 同一单跑 N 次）。

★★★ 现场（2026-10-21 03:25）：
    两个 `dwc_agent.py --llm --interval 20` 同时在跑（pid 37480 父、2788 子），
    消费同一个 `var/dwc_inbox.jsonl`：

      · `T_r400d1_..._cl02` 一分钟内跑了 **13 次**
      · 报告被后跑的覆盖（我先看到 ✓，两分钟后同一文件变成 ✗）
      · 6 单投进去 15 分钟一条报告都没有（状态互相覆盖，谁都没登记上）

★ 根因：`dwc_watchdog.ensure()` 里
    ① `check()` 把"心跳过期"判成"进程死了"
    ② 于是**删掉 pid 锁**再 Popen 一个新 agent
    ③ 但老进程还活着 ⇒ 两个消费者

  心跳过期 ≠ 进程死亡（长任务里心跳线程可能被 GIL/IO 卡住）。

★ 修法：`ensure()` 在 `pids` 非空时**一律不拉新进程**，
  只写一条告警（action="stale_heartbeat_refused"）。
  宁可心跳过期告警，也绝不允许出现第二个消费者。
"""
from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import dwc_watchdog as W  # noqa: E402


@pytest.fixture
def no_spawn(monkeypatch, tmp_path):
    """把 Popen 换成"记录调用"，避免测试真的拉起进程。"""
    calls = []

    class _Fake:
        pid = 999999

    def _fake_popen(*a, **kw):
        calls.append((a, kw))
        return _Fake()

    monkeypatch.setattr(W.subprocess, "Popen", _fake_popen)
    monkeypatch.setattr(W, "PIDF", str(tmp_path / "agent.pid"))
    monkeypatch.setattr(W, "STDERR", str(tmp_path / "err.log"))
    return calls


def test_no_spawn_when_heartbeat_stale_but_process_alive(no_spawn, monkeypatch):
    """★★★ 进程还在（心跳过期）⇒ 不许拉新进程。"""
    monkeypatch.setattr(W, "check", lambda *a, **k: {
        "alive": False, "pids": [1234], "hb_pid": 1234,
        "hb_age": 3000.0, "reason": "heartbeat_stale(3000s)"})
    r = W.ensure(20)
    assert r["action"] == "stale_heartbeat_refused", r
    assert no_spawn == [], "仍然拉起了第二个 agent（会双份消费）"


def test_spawn_when_truly_no_process(no_spawn, monkeypatch):
    """★★ 确实没有进程 ⇒ 正常拉起（不能因为修复把自愈能力弄丢）。"""
    monkeypatch.setattr(W, "check", lambda *a, **k: {
        "alive": False, "pids": [], "hb_pid": 0,
        "hb_age": None, "reason": "no_process"})
    # 拉起后会轮询 check；让它第二次就返回 alive
    seq = [{"alive": False, "pids": [], "hb_pid": 0, "hb_age": None,
            "reason": "no_process"},
           {"alive": True, "pids": [555], "hb_pid": 555, "hb_age": 1.0,
            "reason": ""}]
    monkeypatch.setattr(W, "check", lambda *a, **k: seq.pop(0) if seq else
                        {"alive": True, "pids": [555], "hb_pid": 555,
                         "hb_age": 1.0, "reason": ""})
    monkeypatch.setattr(W.time, "sleep", lambda s: None)
    r = W.ensure(20)
    assert r["action"] == "restarted", r
    assert len(no_spawn) == 1


def test_alive_returns_none(no_spawn, monkeypatch):
    """★★ 活着 ⇒ action=none，不动任何东西。"""
    monkeypatch.setattr(W, "check", lambda *a, **k: {
        "alive": True, "pids": [1], "hb_pid": 1, "hb_age": 1.0, "reason": ""})
    assert W.ensure(20)["action"] == "none"
    assert no_spawn == []
