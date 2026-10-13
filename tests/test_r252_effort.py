# -*- coding: utf-8 -*-
"""R252 · §5.2 交替节流-冲刺调度锁（2609.14858 Figure 6）。

★ 论文是单任务行为观察、未形式化 ⇒ 系数必传无默认（β 同款纪律）;
  自验 = simulate_schedule 合成序列（深读「必须自验」的兑现）。
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from dwc.organs.effort import (EffortError, next_effort,  # noqa: E402
                               simulate_schedule)

_EF = dict(plateau_eps=0.02, factor_up=1.15, factor_down=0.9, lo=2, hi=8)


def test_next_effort_three_states():
    """★★★ 三态锁: 平台(gain<ε)冲刺放大 / 上升节流收缩 / [lo,hi] 夹逼。"""
    # 平台: 4 × 1.15 = 4.6 → 5
    assert next_effort(gain=0.0, prev=4, **_EF) == 5
    # 上升: 4 × 0.9 = 3.6 → 4
    assert next_effort(gain=0.3, prev=4, **_EF) == 4
    # 上升且大: 10 × 0.9 = 9 → hi=8 夹住
    assert next_effort(gain=0.5, prev=10, **_EF) == 8
    # 平台且小: 2 × 1.15 = 2.3 → 2 = lo 夹住
    assert next_effort(gain=0.0, prev=2, **_EF) == 2


def test_simulate_alternation():
    """★★★ 自验锁: 三平台→冲刺连升, 后接上升→节流回落（§5.2 交替可复现）。"""
    gains = [0.0, 0.0, 0.0, 0.3, 0.4]
    traj = simulate_schedule(gains=gains, init=4, **_EF)
    # 平台×3: 4→5→6→7; 上升×2: 7→6→5
    assert traj == [5, 6, 7, 6, 5], traj


def test_param_validation():
    """★★★ 参数校验锁: 方向错/负值/区间错全 raise（G7 同族 — 不静默）。"""
    with pytest.raises(EffortError):
        next_effort(gain=0.0, prev=4, **dict(_EF, factor_up=0.9))   # 应>1
    with pytest.raises(EffortError):
        next_effort(gain=0.0, prev=4, **dict(_EF, factor_down=1.2))  # 应<1
    with pytest.raises(EffortError):
        next_effort(gain=0.0, prev=4, **dict(_EF, lo=0))
    with pytest.raises(EffortError):
        next_effort(gain=0.0, prev=4, **dict(_EF, lo=8, hi=2))
    with pytest.raises(EffortError):
        next_effort(gain=-0.1, prev=4, **dict(_EF, plateau_eps=-1))


def test_config_effort_required():
    """★★★ 配置锁: effort 段必填（论文未报系数 ⇒ 无默认）+ 现文件可读。"""
    import tempfile
    from dwc.foundation import dial_config
    cfg = dial_config.load_replay()
    ef = cfg["effort"]
    assert ef["factor_up"] > 1 and 0 < ef["factor_down"] < 1
    assert ef["lo"] >= 1 and ef["hi"] >= ef["lo"]
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False,
                                     encoding="utf-8") as f:
        f.write("replay: {beta1: 0, beta2: 0, history_max: 4}\n")  # 无 effort
    with pytest.raises(dial_config.DialError):
        dial_config.load_replay(f.name)


def test_core_dream_adaptive():
    """★★★ 集成锁: adaptive_effort=True 两轮 — 首轮无先例不调度,
    第二轮 gain<V 平台 ⇒ 冲刺调大; 报告 effort 字段如实。"""
    from dwc.core import DWC
    from dwc.organs.actor import Receipt
    from dwc.organs.judge import TaskScoreStore

    def ex(task):
        return Receipt(ok=True, detail={}, verified=True)
    d = DWC(3, 50, executor=ex)
    d.judge.store = TaskScoreStore(dw_version="test")
    wm = d.world_model
    wm.seed("t1", "r")
    wm.expand("t1", "root", node_id="a", action="A", provenance="observed")
    wm.record_observation("t1", "a", 3.0, True)
    r1 = d.dream(k2_max=4, adaptive_effort=True)
    # 首轮: gain=None 不调度（prev=nxt=4）
    assert r1.effort is not None
    p1, n1, g1 = r1.effort
    assert p1 == 4 and n1 == 4 and g1 is None
    # 第二轮: 树未变 ⇒ v_star 同 3.0 ⇒ gain=0 平台 ⇒ 冲刺 4→5
    r2 = d.dream(k2_max=99, adaptive_effort=True)   # 传入 99 不该被用
    p2, n2, g2 = r2.effort
    assert g2 == 0.0, g2
    assert p2 == 4 and n2 == 5, (p2, n2)
    # 非 adaptive: effort=None（旧行为）
    r3 = d.dream(k2_max=4)
    assert r3.effort is None
