# -*- coding: utf-8 -*-
"""★ A3 · 小Δ熔断（|Δ_in|<spread ⇒ 跳过 peer 验证，省 LLM 预算）。

锁：
1. _small_delta_fused 纯逻辑：spread 缺席/Δ 缺席⇒不熔断；|Δ|<spread⇒熔；
   >=⇒不熔；spread=0.0 且 Δ=0.0⇒不熔（零对零语义保守，诚实边界）。
2. _real_trial report 路：d=0.1<spread=0.5⇒熔断（peer 零调用、held_out
   None、reason 带 A3）；spread=0.01⇒不熔断（peer 路走了，llm 被调）。
"""
from __future__ import annotations

import os
import sys
from types import SimpleNamespace

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import dwc_evo_round as E


def _judge(base, peer=None):
    pts = [SimpleNamespace(task_id="T", split="dev", score=base)]
    j = SimpleNamespace(
        anchors={"T": {"category": "other",
                       "checks": [{"fn": "f", "args": "1"}]}},
        sealed={"P": {"checks": [{"fn": "pf", "args": "1"}]}},
        task_scores=lambda split=None: (
            [p for p in pts if p.split == split] if split else list(pts)),
        held_out_peer=lambda t: peer,
        evaluate=lambda task, split, observed=None, **k:
            SimpleNamespace(success=True),
    )
    return j


def _llm(calls):
    def _complete(prompt, max_tokens=1500):
        calls.append(prompt)
        if len(calls) == 1:
            return SimpleNamespace(ok=True, text='{"f": [[1, 1]]}')
        return SimpleNamespace(ok=True, text="no code here")
    return SimpleNamespace(complete=_complete)


def test_a3_fuse_logic():
    assert E._small_delta_fused(1.0, 0.9) in [(False, 0.1), (False, 0.09999999999999998)]
    # spread 缺席（_evo_spread 坏/无文件）⇒ 不熔断：打桩 _evo_spread
    E._evo_spread, _bak = (lambda: None), E._evo_spread
    try:
        assert E._small_delta_fused(1.0, 0.9)[0] is False
        assert E._small_delta_fused(None, 0.9) == (False, None)
    finally:
        E._evo_spread = _bak


def test_a3_fuse_boundary(monkeypatch):
    monkeypatch.setattr(E, "_evo_spread", lambda: 0.5)
    assert E._small_delta_fused(1.0, 0.9)[0] is True   # 0.1<0.5 熔
    assert E._small_delta_fused(1.0, 0.4)[0] is False  # 0.6>=0.5 不熔
    monkeypatch.setattr(E, "_evo_spread", lambda: 0.0)
    assert E._small_delta_fused(0.0, 0.0) == (False, 0.0)  # 零对零不熔


def test_a3_trial_fused(monkeypatch):
    monkeypatch.setattr(E, "_evo_spread", lambda: 0.5)
    monkeypatch.setattr(E, "_extract_code", lambda text, fn: "")
    calls = []
    out = E._real_trial(_judge(0.9), _llm(calls), "T", patch="p")
    assert out["held_out"] is None
    assert "A3" in (out.get("reason") or "")
    assert len(calls) == 1  # 只跑了 dev trial，peer 零调用


def test_a3_trial_not_fused(monkeypatch):
    monkeypatch.setattr(E, "_evo_spread", lambda: 0.01)
    monkeypatch.setattr(E, "_extract_code", lambda text, fn: "")
    calls = []
    out = E._real_trial(_judge(0.9, peer="P"), _llm(calls), "T", patch="p")
    assert len(calls) == 1 + 3  # dev 1 次 + peer 无码重试 3 次
    assert out["held_out"] is None  # 无码耗尽 fail-closed
    assert "A3" not in (out.get("reason") or "")
