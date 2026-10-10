# -*- coding: utf-8 -*-
"""R164 · 常驻循环引擎 — 轮转/记账/四熔断/checkpoint（不重造引擎）。

验收:
  □ 循环驱动 + rounds 数到停机
  □ checkpoint: daemon_state.json 原子写 + rounds.jsonl 追加（断点可续）
  □ 四熔断: stop_file / SIGINT / consecutive_idle / budget
  □ 异常轮不中断（记 error 继续 — 除非连空转超限）
  □ 跳过≠空转（熔断计数分开）
  □ CLI: --demo/--once/--rounds
  □ round_fn 非 callable ⇒ DaemonError
"""
from __future__ import annotations

import json
import os
import sys

import pytest

ROOT = r"E:/Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.daemon import (  # noqa: E402
    DAEMON_MECHANICS, Daemon, DaemonError, DaemonState, RoundLog, main)


def _mk(tmp_path, fn, **kw):
    return Daemon(fn, state_dir=str(tmp_path / "rt"), **kw)


def test_loop_runs_n_rounds_and_checkpoints(tmp_path):
    """★ rounds=N 跑 N 轮; state/log 落盘（崩溃可续的锚）。"""
    calls = []

    def fn(n, d):
        calls.append(n)
        return {"n_candidates": 1, "chain_verdict": "applicable_passed_with_na",
                "landed": True, "score": 0.5 + n * 0.1}

    d = _mk(tmp_path, fn)
    out = d.run(rounds=3)
    assert calls == [1, 2, 3]
    assert out["stop_reason"] == "rounds_exhausted"
    assert out["n_landed"] == 3
    st = json.load(open(os.path.join(str(tmp_path / "rt"),
                                     "daemon_state.json"), encoding="utf-8"))
    assert st["round_no"] == 3                        # ★ checkpoint 续轮锚
    lines = open(os.path.join(str(tmp_path / "rt"), "rounds.jsonl"),
                 encoding="utf-8").read().strip().splitlines()
    assert len(lines) == 3


def test_exception_round_does_not_interrupt(tmp_path):
    """★★ 单轮异常 ⇒ 记 error 继续（熔断≠失败 — 母巢教训）。"""
    n = {"i": 0}

    def fn(r, d):
        n["i"] += 1
        if r == 2:
            raise RuntimeError("LLM 超时模拟")
        return {"landed": True}

    d = _mk(tmp_path, fn)
    out = d.run(rounds=3)
    assert out["n_error"] == 1 and out["n_landed"] == 2
    assert out["rounds_run"] == 3        # ★ 异常轮也推进（不卡死同轮）
    log = [json.loads(l) for l in open(d._log_path, encoding="utf-8")]
    assert log[1]["error"] and "RuntimeError" in log[1]["error"]


def test_consecutive_idle_fuse(tmp_path):
    """★★★ 连续空转（无可落地）⇒ 熔断停机（防空转烧 quota）。"""
    def fn(r, d):
        return {"chain_verdict": "blocked", "blocked": ["x"]}   # 无可落地

    d = _mk(tmp_path, fn, max_idle_rounds=3)
    out = d.run(rounds=100)
    assert out["stop_reason"] == "consecutive_idle_fuse"
    assert out["rounds_run"] == 3                    # 到限即停, 不跑 100


def test_skip_is_not_idle(tmp_path):
    """★ 跳过（有原因）不计空转 — 熔断计数分开（两种状态不同因）。"""
    def fn(r, d):
        return {"skipped_reason": "LLM 超时"}

    d = _mk(tmp_path, fn, max_idle_rounds=2)
    out = d.run(rounds=5)
    assert out["stop_reason"] == "rounds_exhausted"   # 跳过≠空转 ⇒ 不被熔断
    assert out["n_skipped"] == 5


def test_stop_file_consumed_once(tmp_path):
    """★★ stop 文件: 一次消费即删（否则每轮都被判停 — 语义漂移）。"""
    stop = tmp_path / "rt" / "STOP"
    stop_parent = tmp_path / "rt"
    stop_parent.mkdir(parents=True)
    stop.write_text("stop\n", encoding="utf-8")

    def fn(r, d):
        return {"landed": True}

    d = _mk(tmp_path, fn)
    out = d.run(rounds=10)
    assert out["stop_reason"] == "stop_file"
    # ★ stop 语义 = "别再开新轮" ⇒ 轮前检查 ⇒ 一轮不跑即停
    assert out["rounds_run"] == 0
    assert not stop.exists()                          # ★ 消费即删


def test_sigint_sets_flag_not_kill(tmp_path):
    """★ SIGINT: 置停机标志（当前轮收尾后退出 — 不半轮死）。"""
    seen = {}

    def fn(r, d):
        # 第 1 轮内模拟外部 SIGINT（直接调 state 置位 — 信号处理器同效果）
        if r == 1:
            d.state.stop_requested = True
        seen["last"] = r
        return {"landed": True}

    d = _mk(tmp_path, fn)
    out = d.run(rounds=10)
    assert out["stop_reason"] == "signal"
    assert seen["last"] == 1                          # 第 1 轮完整跑完才停


def test_budget_seconds_cap(tmp_path):
    """★ 预算尽 ⇒ 停机（budget_exhausted — 防跑飞）。"""
    import time

    def fn(r, d):
        time.sleep(0.05)
        return {"landed": True}

    d = _mk(tmp_path, fn)
    out = d.run(rounds=100, budget_seconds=0.2)
    assert out["stop_reason"] == "budget_exhausted"
    assert out["elapsed_s"] < 5


def test_cli_demo(tmp_path, capsys):
    """★ CLI --demo --rounds 2 跑通（循环本身可运维验证）。"""
    rc = main(["--demo", "--rounds", "2",
               "--state-dir", str(tmp_path / "cli")])
    assert rc == 0
    out = capsys.readouterr().out
    assert "rounds_exhausted" in out
    # 无 --demo ⇒ 用法提示 rc=2
    rc2 = main(["--state-dir", str(tmp_path / "cli2")])
    assert rc2 == 2


def test_round_fn_must_be_callable(tmp_path):
    """round_fn 非 callable ⇒ DaemonError（入口拦 — 不猜）。"""
    with pytest.raises(DaemonError):
        Daemon("not-callable", state_dir=str(tmp_path / "x"))


def test_mechanics_documented():
    """四熔断/checkpoint/不重造引擎/无 HTTP 在档。"""
    assert "consecutive_idle" in DAEMON_MECHANICS["four_fuses"]
    assert "round_fn 注入" in DAEMON_MECHANICS["not_engine"]
    assert "不做 HTTP" in DAEMON_MECHANICS["no_http"]
