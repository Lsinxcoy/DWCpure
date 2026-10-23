# -*- coding: utf-8 -*-
"""R215 · trust 窗口化（Layer 22 判据校准 — 永久降级自锁的解除）。"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
from dwc.organs.iwm import IwmOrgan                              # noqa: E402
from dwc.foundation import dial_config                          # noqa: E402


def _iwm():
    return IwmOrgan(baseline={})


def test_window_rescues_trust_after_behavior_change():
    """★★★ 死锁解除的行为级锁: 前 25 轮采纳降级全无改进（全历史 trust=5/30
    < 0.35 永久降级）⇒ 行为改变后 5 轮改进 ⇒ **窗口 trust=1.0 保持**。
    （旧判据下这个系统永远出不来 — 台账 66/66 全 drop 的判据根因）。"""
    w = _iwm()
    for _ in range(25):
        w.record_round(adopted=True, improved=False)   # 采纳降级, 无改进
    for _ in range(w.trust_window):                    # 行为改变, 连续改进
        w.record_round(adopted=True, improved=True)
    st = w.self_trust()
    assert st["degrade"] is False, (
        "窗口失效: trust=%.3f（全历史口径 %.3f < 0.35 会永久降级 — 死锁复现）"
        % (st["trust"], 25 / (25 + w.trust_window)))
    # 窗口=最近 20 轮 iwm 臂全改进 ⇒ trust=1.0（全历史口径仅 ~0.56 仍降级）
    assert st["trust"] == 1.0 and st["n_iwm"] == w.trust_window
    assert st["total_iwm"] == 25 + w.trust_window, "累计审计丢失"


def test_window_truncates():
    """★ 窗口截断: _arm_window 恒 ≤ trust_window（内存不涨）。"""
    w = _iwm()
    for i in range(w.trust_window + 10):
        w.record_round(adopted=(i % 2 == 0), improved=bool(i % 3))
    assert len(w._arm_window) == w.trust_window


def test_min_samples_still_guards():
    """★ 样本不足纪律保留: 窗口内 iwm 臂 < min_samples ⇒ trust=0 degrade
    （ARSI 语义不放松 — 窗口化只改口径不改门槛）。"""
    w = _iwm()
    for _ in range(2):
        w.record_round(adopted=True, improved=True)
    st = w.self_trust()
    assert st["degrade"] and st["trust"] == 0.0 and st["n_iwm"] == 2


def test_load_drift_requires_trust_window():
    """★★ 校验器: drift.yaml 缺 trust_window ⇒ DialError（"没有校验器的
    yaml 只是文本" — 新档位必须过校验器）。"""
    import tempfile
    bad = os.path.join(tempfile.gettempdir(), "drift_bad.yaml")
    with open(bad, "w", encoding="utf-8") as fh:
        fh.write("""version: 1
drift:
  weights: {semantic: 0.3, lexical: 0.25, structural: 0.25, distributional: 0.2}
  tau_gdi: 0.35
  car_floor: 0.0
  degrade_below: 0.35
  min_samples: 5
""")
    import pytest
    with pytest.raises(dial_config.DialError, match="trust_window"):
        dial_config.load_drift(bad)
    # 真 config 能过
    assert dial_config.load_drift()["drift"]["trust_window"] >= 1
