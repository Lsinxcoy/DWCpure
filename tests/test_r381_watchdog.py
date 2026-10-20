# -*- coding: utf-8 -*-
"""R381 · agent 存活看门狗（防跑批被静默死亡污染）。

★★★ 现场取证（2026-10-20）:
  · 08:52 agent 静默死亡（无 traceback / 无冻结 / 预算未到 / pid 文件残留）
  · 10:00 前再次死亡
  · 死因未查明 ⇒ 只能靠"死了就发现并拉起"，不能靠"先查根因"

★★ 判据坑（已致事故）:
  · `cmdline.endswith("scripts/dwc_agent.py")` **在带参数时漏判**
    （agent re-exec 后 cmdline 是 `... python.exe E:/.../dwc_agent.py
    --llm --interval 30`）⇒ 报「旧进程: []」而实际在跑 ⇒ 双开+被杀。
  · 排除自己的方式必须是排除 `-c`（内联脚本的源码字符串里含脚本路径，
    会被 contains 命中）。
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import time

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load():
    p = os.path.join(ROOT, "scripts", "dwc_watchdog.py")
    spec = importlib.util.spec_from_file_location("dwc_watchdog_r381", p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.fixture()
def W(monkeypatch):
    w = _load()
    monkeypatch.setattr(w, "ROOT", str(ROOT))
    return w


# ─────────────────────── ① 存活判据


def test_find_agents_uses_contains_not_endswith(W, monkeypatch):
    """★★★ 带参数的 cmdline 必须被认出（endswith 会漏判）。

    这条锁的是已发生的事故：agent 以 `--llm --interval 30` 启动，
    `endswith("scripts/dwc_agent.py")` 为 False ⇒ 漏判 ⇒ 双开被杀。
    """
    class _P:
        pid = 999999
        info = {"cmdline": ["C:/py/python.exe",
                            "E:/Divine Wisdom Core/scripts/dwc_agent.py",
                            "--llm", "--interval", "30"]}

    class _PS:
        @staticmethod
        def process_iter(attrs):
            return [_P()]

    import types
    fake = types.SimpleNamespace(process_iter=_PS.process_iter)
    monkeypatch.setitem(sys.modules, "psutil", fake)

    got = W.find_agents()
    assert 999999 in got, "带参数的 agent 进程漏判了（endswith 的坑）"


def test_find_agents_excludes_self_inline_script(W, monkeypatch):
    """★★★ 不许把自己的 `-c` 内联脚本当成 agent（曾命中脚本自身）。"""
    class _P:
        pid = 888888
        info = {"cmdline": ["C:/py/python.exe", "-c",
                            "import x; open('scripts/dwc_agent.py')"]}

    class _PS:
        @staticmethod
        def process_iter(attrs):
            return [_P()]

    import types
    fake = types.SimpleNamespace(process_iter=_PS.process_iter)
    monkeypatch.setitem(sys.modules, "psutil", fake)

    assert W.find_agents() == [], "把自己的内联脚本当成 agent 了"


def test_check_reports_dead_when_no_process(W, monkeypatch, tmp_path):
    """★★ 没进程 ⇒ alive=False, reason=no_process。"""
    monkeypatch.setattr(W, "find_agents", lambda: [])
    r = W.check()
    assert r["alive"] is False
    assert r["reason"] == "no_process"


def test_check_reports_stale_heartbeat(W, monkeypatch, tmp_path):
    """★★★ 进程在但心跳陈旧 ⇒ 仍判死（进程活着 ≠ 服务可用）。"""
    hb = tmp_path / "hb.json"
    hb.write_text(json.dumps({
        "ts": "2026-10-20T00:00:00+08:00",       # 很久以前
        "pid": 123, "status": "alive"}), encoding="utf-8")
    monkeypatch.setattr(W, "HB", str(hb))
    monkeypatch.setattr(W, "find_agents", lambda: [123])

    r = W.check(stale_sec=60)
    assert r["alive"] is False, "心跳陈旧却判活 —— 会掩盖服务假死"
    assert "stale" in r["reason"], r["reason"]


def test_check_alive_when_fresh(W, monkeypatch, tmp_path):
    """★★ 进程在 + 心跳新鲜 ⇒ alive=True（不许误报）。"""
    from datetime import datetime
    hb = tmp_path / "hb.json"
    hb.write_text(json.dumps({
        "ts": datetime.now().astimezone().isoformat(timespec="seconds"),
        "pid": 123}), encoding="utf-8")
    monkeypatch.setattr(W, "HB", str(hb))
    monkeypatch.setattr(W, "find_agents", lambda: [123])

    r = W.check()
    assert r["alive"] is True, r


# ─────────────────────── ② ensure 幂等


def test_ensure_noop_when_alive(W, monkeypatch):
    """★★★ 活着就不许重启（重启=自伤，生产禁手动重启）。"""
    monkeypatch.setattr(W, "check", lambda *a, **k: {
        "alive": True, "pids": [1], "hb_pid": 1, "hb_age": 1.0, "reason": ""})

    def _boom(*a, **k):
        raise AssertionError("活着却去 Popen 了 —— 会双开")

    monkeypatch.setattr(W.subprocess, "Popen", _boom)
    r = W.ensure()
    assert r["action"] == "none"


def test_ensure_restarts_when_dead(W, monkeypatch, tmp_path):
    """★★★ 死了要拉起，并清理残留 pid 文件（单例锁会拒绝启动）。"""
    pidf = tmp_path / "agent.pid"
    pidf.write_text("12345", encoding="utf-8")
    monkeypatch.setattr(W, "PIDF", str(pidf))
    monkeypatch.setattr(W, "STDERR", str(tmp_path / "err.log"))
    monkeypatch.setattr(W, "AGENT", str(tmp_path / "fake_agent.py"))
    (tmp_path / "fake_agent.py").write_text("", encoding="utf-8")

    states = [{"alive": False, "pids": [], "hb_pid": 0, "hb_age": None,
               "reason": "no_process"}]
    calls = {"n": 0}

    def _check(*a, **k):
        calls["n"] += 1
        if calls["n"] <= 1:
            return states[0]
        return {"alive": True, "pids": [4242], "hb_pid": 4242,
                "hb_age": 1.0, "reason": ""}

    monkeypatch.setattr(W, "check", _check)

    class _Pr:
        pid = 4242

    monkeypatch.setattr(W.subprocess, "Popen", lambda *a, **k: _Pr())
    monkeypatch.setattr(W.time, "sleep", lambda *_: None)

    r = W.ensure()
    assert r["action"] == "restarted", r
    assert not pidf.exists(), "残留 pid 文件没清 —— 单例锁会拒绝启动"


def test_ensure_reports_failure_if_never_comes_up(W, monkeypatch, tmp_path):
    """★★ 拉不起来要如实报 restart_failed（不许假装成功）。"""
    monkeypatch.setattr(W, "PIDF", str(tmp_path / "p.pid"))
    monkeypatch.setattr(W, "STDERR", str(tmp_path / "e.log"))
    monkeypatch.setattr(W, "AGENT", str(tmp_path / "a.py"))
    (tmp_path / "a.py").write_text("", encoding="utf-8")
    monkeypatch.setattr(W, "check", lambda *a, **k: {
        "alive": False, "pids": [], "hb_pid": 0, "hb_age": None,
        "reason": "no_process"})
    monkeypatch.setattr(W.subprocess, "Popen",
                        lambda *a, **k: type("P", (), {"pid": 1})())
    monkeypatch.setattr(W.time, "sleep", lambda *_: None)

    # ★ 用递增的假时钟让轮询窗口**自然耗尽**（把 time.time 改成恒 0 会死循环）
    _t = {"v": 0.0}

    def _fake_time():
        _t["v"] += 100.0            # 每次调用推进 100s ⇒ 两次就超 120s
        return _t["v"]

    monkeypatch.setattr(W.time, "time", _fake_time)

    r = W.ensure()
    assert r["action"] == "restart_failed", r
    assert r["alive"] is False
