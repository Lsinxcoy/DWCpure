# -*- coding: utf-8 -*-
"""★ D1 · execution variation（同任务 frozen 重跑，均分±spread 常驻 report）。

锁：
1. --repeat 3 且 pass 序列 [T,F,T] ⇒ pass_mean≈0.6667 / spread≈0.4714 /
   n_repeats=3 / 顶层 repeat=3 / spread_mean 非 None。
2. 默认（无 --repeat）⇒ n_repeats=1 / spread=None（未测≠0）/
   spread_mean=None。
3. frozen 纪律：repeat 内三轮 ctx 逐字相同；record_lesson 只在末轮调一次
   （中间轮纯测不沉淀）；predictor.observe 同样只末轮。
"""
from __future__ import annotations

import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import dwc_bench as B


def _fake_env(monkeypatch, tmp_path, passes, fail_modes=None):
    """execute/验证/沉淀全打桩：passes 按轮消费，verifier 读 report 标记。"""
    monkeypatch.setattr(B, "VAR", str(tmp_path))
    monkeypatch.setattr(B, "WORK", str(tmp_path))
    calls = {"ctxs": [], "records": [], "observes": []}
    seq = {"i": 0}

    def _exec(task, ctx=None, llm=None, max_rounds=6):
        calls["ctxs"].append(ctx)
        ok = passes[seq["i"] % len(passes)]
        seq["i"] += 1
        return {"status": "done", "rounds": 1, "actions_log": [],
                "why": "", "_pass": ok}

    monkeypatch.setattr(B.TE, "execute_user_task", _exec)
    monkeypatch.setattr(B, "VERIFIERS",
                        {"classes": lambda rep: (rep["_pass"], "fake")})
    monkeypatch.setattr(B, "LLMClient", lambda *a, **k: object())
    fms = list(fail_modes) if fail_modes else ["ok"] * len(passes)
    monkeypatch.setattr(B.Q, "classify_fail",
                        lambda rep, ok: fms[min(seq["i"] - 1, len(fms) - 1)])
    monkeypatch.setattr(B.Q, "record_lesson",
                        lambda *a: calls["records"].append(a))
    monkeypatch.setattr(B.Q, "load_lessons", lambda: [])
    monkeypatch.setattr(B.Q, "lessons_context", lambda task: "INJ")
    monkeypatch.setattr(B.Q, "consolidate_skills", lambda: [])
    import dwc.organs.predictor as P

    class _FakePred:
        def observe(self, *a, **k):
            calls["observes"].append(a)

    monkeypatch.setattr(P, "OutcomePredictor", lambda *a, **k: _FakePred())
    return calls


def _only_tid():
    bench = json.loads(io.open(os.path.join(ROOT, "config", "task_bench.json"),
                               encoding="utf-8").read())
    for t in bench["tasks"]:
        if t["verifier"] == "classes":
            return t["id"]
    raise AssertionError("task_bench.json 无 classes 任务")


def test_d1_repeat_spread(monkeypatch, tmp_path):
    calls = _fake_env(monkeypatch, tmp_path, [True, False, True],
                      fail_modes=["ok", "ok", "boom"])
    tid = _only_tid()
    assert B.main(["dwc_bench.py", "--only", tid, "--repeat", "3"]) == 0
    out = json.loads(io.open(str(tmp_path / "dwc_bench_results.json"),
                             encoding="utf-8").read())
    assert out["repeat"] == 3
    assert out["spread_mean"] is not None
    row = [r for r in out["results"] if r["id"] == tid][0]
    assert row["n_repeats"] == 3
    assert row["pass_mean"] == round(2 / 3, 4)
    assert row["pass_spread"] == B._spread([1.0, 0.0, 1.0])
    assert row["pass_spread"] == 0.4714
    # frozen：三轮 ctx 逐字相同且带首轮注入
    assert len(calls["ctxs"]) == 3
    assert calls["ctxs"][0] == calls["ctxs"][1] == calls["ctxs"][2]
    assert "INJ" in calls["ctxs"][0]
    # 末轮沉淀一次（boom 在末轮），中间轮零写
    assert len(calls["records"]) == 1
    assert len(calls["observes"]) == 3  # 末轮 3 次 observe（bench+rung+fail）


def test_d1_single_no_spread(monkeypatch, tmp_path):
    _fake_env(monkeypatch, tmp_path, [True])
    tid = _only_tid()
    assert B.main(["dwc_bench.py", "--only", tid]) == 0
    out = json.loads(io.open(str(tmp_path / "dwc_bench_results.json"),
                             encoding="utf-8").read())
    assert out["repeat"] == 1
    assert out["spread_mean"] is None  # 未测≠0
    row = [r for r in out["results"] if r["id"] == tid][0]
    assert row["n_repeats"] == 1
    assert row["pass_mean"] == 1.0
    assert row["pass_spread"] is None


def test_d1_spread_math():
    assert B._spread([1.0]) is None
    assert B._spread([]) is None
    assert B._spread([1.0, 1.0]) == 0.0  # 测了零方差≠未测
    assert B._spread([1.0, 0.0]) == 0.5
