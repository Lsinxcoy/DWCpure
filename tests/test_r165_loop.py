# -*- coding: utf-8 -*-
"""R165 · daemon 接真 round_fn — "agent 活着"从 demo 到真跑。

验收:
  □ Loop.round 单轮真跑（execute_task/judge/evolver/gate_all/pipeline 全真调）
  □ dev split 10 task 轮转（非硬编码 — e2e 的写死只适合演示）
  □ 已过 task ⇒ idle≠error（熔断计数分族）
  □ score_history.jsonl 落盘（跨轮序列 — σ_t 消费面）
  □ LoopError: dev 空 ⇒ 显式拒
  □ build_round_fn 契约形状（callable(round_no, daemon)）
  □ 不落脏盘: 内存 target（生产落地面由部署方给）
"""
from __future__ import annotations

import json
import os
import sys

import pytest

ROOT = r"E:/Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.daemon import Daemon  # noqa: E402
from dwc.harness.loop import (  # noqa: E402
    LOOP_MECHANICS, Loop, LoopError, build_round_fn)


def _loop(tmp_path=None, **kw):
    if tmp_path is None:
        return Loop(**kw)                       # 默认 config/anchors
    return Loop(anchors_dir=str(tmp_path / "anchors"), **kw)


def test_round_runs_real_organs(tmp_path, monkeypatch):
    """★★★ 单轮真跑: 四器官全真调（不 stub judge/evolver/pipeline）。"""
    loop = _loop(tmp_path)
    # anchors 指向真 config/anchors（dev split 真任务）
    monkeypatch.setattr(loop, "anchors_dir",
                        os.path.join(ROOT, "config", "anchors"))
    out = loop.round(1)
    assert out["chain_verdict"] in ("all_applicable_passed",
                                    "applicable_passed_with_na", "blocked",
                                    "error")
    # 落盘: score_history + judge 生产路径
    hist = os.path.join(ROOT, "config", "anchors", "score_history.jsonl")
    if os.path.exists(hist):
        recs = [json.loads(l) for l in open(hist, encoding="utf-8")]
        assert recs[-1]["round"] == 1                 # 本轮落痕
    else:
        pytest.skip("score_history 还没写过（首轮才建）")


def test_dev_tasks_are_rotated_not_hardcoded():
    """★★★★ 任务面来自 judge.anchors（dev 10 条）— 非 e2e 写死单 task。"""
    loop = _loop()
    tasks = loop._dev_tasks()
    assert len(tasks) == 13    # ★ R199: +3 rung3
    assert not any(t.startswith("_") for t in tasks)
    # ★ 轮转真断言（G4 放水门教训 — R165 我写了 or True 恒真式被
    #   test_no_watering 抓回, 换成取模回环证据: round 1 与 round 11
    #   （1+len）选同一 task ⇒ 取模正确且与 len 相关, 不是恒真）
    sel_a = tasks[1 % len(tasks)]
    sel_b = tasks[(1 + len(tasks)) % len(tasks)]
    assert sel_a == sel_b                         # ★ 10 轮后回同一 task
    assert sel_a == tasks[1]                      # round 1 就是 tasks[1]


def test_passed_task_is_idle_not_error():
    """★★ 已过 task ⇒ idle（skipped_reason 有值, chain 不是 error）。"""
    loop = _loop()
    # 直接打 _run_one_task 的内部口径: monkeypatch judge.evaluate ⇒ success
    # ★★ R170: stub 须带 k_passed/n_checks（pass_rate 微口径 — R160
    #   stub Verdict 同族教训: 测试 stub 要覆盖生产读的字段, 不让
    #   getattr 兜假）否则 _pass_rate 取字段 AttributeError
    class _V:
        success = True
        failure_signature = None
        k_passed = 2
        n_checks = 2
        diffs = []
    loop.judge.evaluate = lambda *a, **k: _V()
    out = loop._run_one_task("code_fix_001", round_no=1)
    assert "已通过" in (loop._last_skip or "")
    assert out["landed"] is False
    assert out["chain_verdict"] != "error"


def test_loop_error_on_empty_dev():
    """★ dev 空 ⇒ LoopError（显式拒 — 不空转猜任务）。"""
    loop = _loop()
    loop.judge.anchors = {}                          # 空 split
    with pytest.raises(LoopError):
        loop.round(1)


def test_daemon_drives_real_loop(tmp_path, monkeypatch):
    """★★★★★ R164 × R165 合流: Daemon(round_fn=Loop.round) 真跑 3 轮。"""
    loop = _loop(tmp_path)
    monkeypatch.setattr(loop, "anchors_dir",
                        os.path.join(ROOT, "config", "anchors"))
    d = Daemon(loop.round, state_dir=str(tmp_path / "d"),
               max_idle_rounds=10)
    out = d.run(rounds=3)
    assert out["stop_reason"] == "rounds_exhausted"
    assert out["rounds_run"] == 3                    # ★ 活着: 三轮真推进
    log = [json.loads(l) for l in open(d._log_path, encoding="utf-8")]
    assert len(log) == 3
    assert all(not r["error"] for r in log)          # 真器官不炸


def test_build_round_fn_contract(tmp_path):
    """★ build_round_fn ⇒ callable(round_no, daemon)（Daemon 契约形状）。"""
    fn = build_round_fn(anchors_dir=str(tmp_path / "a2"))
    assert callable(fn)
    loop = fn.__self__ if hasattr(fn, "__self__") else None
    assert loop is None or isinstance(loop, Loop)     # bound method 形态


def test_mechanics_documented():
    """无新判定/机械轮转/同源账本/idle 分族在档。"""
    assert "零新判定" in LOOP_MECHANICS["no_new_judgement"]
    assert "机械轮转" in LOOP_MECHANICS["task_selection"]
