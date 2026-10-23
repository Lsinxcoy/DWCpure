# -*- coding: utf-8 -*-
"""R150 · 非补偿门三步（门⑤）— 噪声地板→成本规则/整形→领域守卫; 独立否决不可互偿。

验收:
  □ 三步顺序（NONCOMP_ORDER — 顺序即契约）
  □ ① 地板: Ŝ≥S*−δ; δ 缺 ⇒ blocked（不硬设 0 = 静默放行禁）
  □ ② 分支: ΔS>δ ⇒ cost rule; ΔS≤δ ⇒ shaped（权重非负不全 0）
  □ ③ 守卫: 缺判定 ⇒ blocked; 守卫挂 ⇒ reject（①②好也不补偿）
  □ 非补偿: 任一步败 ⇒ 后续不跑（短路 — 不可互偿）
"""
from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.organs.noncomp import (  # noqa: E402
    BLOCKED, NONCOMP_MECHANICS, NONCOMP_ORDER, PASS, REJECT, GateInput,
    NonCompError, batch, evaluate)


def _in(**kw) -> GateInput:
    base = dict(score=0.9, score_star=0.9, delta_s=0.0, delta_c=0.0,
                nu_str=0.0, noise_band=0.01, domain_guard_ok=True)
    base.update(kw)
    return GateInput(**base)


def test_order_and_mechanics():
    """★ 三步顺序 + 非补偿/blocked 语义在档。"""
    assert NONCOMP_ORDER == ("noise_floor", "cost_or_shaped",
                             "domain_guards")
    assert "补偿" in NONCOMP_MECHANICS["non_compensatory"]
    assert "blocked_not_pass" in NONCOMP_MECHANICS


def test_noise_floor_reject_short_circuits():
    """① 地板未过 ⇒ reject 且后续不跑（非补偿: 不可互偿）。"""
    r = evaluate(_in(score=0.85, score_star=0.9, noise_band=0.01))
    assert r["verdict"] == REJECT
    assert [s["step"] for s in r["steps"]] == ["noise_floor"]
    assert "非补偿" not in r["why"] or "①" in r["why"]      # 只报①败因


def test_missing_noise_band_blocked():
    """★★ δ 缺 ⇒ blocked（硬设 0 = 地板失效 = 静默放行禁）。"""
    r = evaluate(_in(noise_band=None))
    assert r["verdict"] == BLOCKED
    assert r["steps"] == []                       # 一步都没判


def test_cost_rule_branch():
    """②a ΔS>δ ⇒ ΔC ≤ ΔS（缺省 β₀=0,β₁=1 — 标注口径）。"""
    ok = evaluate(_in(delta_s=0.5, delta_c=0.4))
    assert ok["verdict"] == PASS and ok["steps"][1]["branch"].startswith("2a")
    bad = evaluate(_in(delta_s=0.5, delta_c=0.6))     # ΔC>ΔS ⇒ 拒
    assert bad["verdict"] == REJECT and bad["steps"][1]["ok"] is False


def test_shaped_branch():
    """②b ΔS≤δ ⇒ ws·ΔS−wc·ΔC+wn·ν_str > 0（含新颖度奖励通道）。"""
    # ΔS 0, ν_str 0.3 ⇒ +0.3 > 0 ⇒ 过（结构新颖可过小步门）
    ok = evaluate(_in(delta_s=0.005, delta_c=0.0, nu_str=0.3))
    assert ok["verdict"] == PASS
    assert ok["steps"][1]["branch"].startswith("2b")
    # 纯花钱无收益 ⇒ <0 ⇒ 拒
    bad = evaluate(_in(delta_s=0.0, delta_c=0.5, nu_str=0.0))
    assert bad["verdict"] == REJECT
    # 自定义权重（ws=200 ⇒ 200×0.005=1.0 > ΔC=0.5 ⇒ 过;
    # ws=100 时 0.5−0.5=0 恰不 >0 ⇒ reject — 边界不为过, 见下）
    ok2 = evaluate(_in(delta_s=0.005, delta_c=0.5, nu_str=0.0,
                       floor_weights={"ws": 200.0, "wc": 1.0, "wn": 1.0}))
    assert ok2["verdict"] == PASS
    edge = evaluate(_in(delta_s=0.005, delta_c=0.5, nu_str=0.0,
                        floor_weights={"ws": 100.0, "wc": 1.0, "wn": 1.0}))
    assert edge["verdict"] == REJECT                 # =0 不是 >0


def test_domain_guards_blocked_and_reject():
    """★★ ③ 守卫: 缺判定 ⇒ blocked; 守卫挂 ⇒ reject（①②好也不补偿）。"""
    # ①②过（ΔS≤δ 且不花钱 ⇒ shaped>0）⇒ ③入口被缺判定拦 ⇒ blocked
    r = evaluate(_in(domain_guard_ok=None, delta_s=0.005, delta_c=0.0))
    assert r["verdict"] == BLOCKED
    assert [x["step"] for x in r["steps"]] == ["noise_floor", "shaped"]
    # 守卫挂 ⇒ reject 且在③（①②全过 ⇒ 三步都跑过才拒 — 非补偿）
    r2 = evaluate(_in(domain_guard_ok=False, delta_s=0.005, delta_c=0.0))
    assert r2["verdict"] == REJECT
    assert len(r2["steps"]) == 3 and r2["steps"][2]["ok"] is False


def test_all_pass():
    """①②③全过 ⇒ pass（每步独立成立）。"""
    r = evaluate(_in(score=0.95, score_star=0.9, delta_s=0.05, delta_c=0.01))
    assert r["verdict"] == PASS
    assert [s["ok"] for s in r["steps"]] == [True, True, True]


def test_input_contract():
    """输入契约: 非数值/负 δ/守卫非 bool ⇒ 显式拒。"""
    with pytest.raises(NonCompError):
        _in(noise_band=-0.1)                       # 负 δ
    with pytest.raises(NonCompError):
        GateInput(score="x", score_star=0.9, delta_s=0, delta_c=0)  # 非数值
    with pytest.raises(NonCompError):
        _in(domain_guard_ok="yes")                 # 守卫非 bool
    # ★ 权重全 0 是**求值层**拒绝（2b 分支才用到 — 构造层不预判分支,
    #   与 R142 noncomp 的"构造期只做值域校验"同口径）
    with pytest.raises(NonCompError):
        evaluate(_in(delta_s=0.0, delta_c=0.0,
                     floor_weights={"ws": 0, "wc": 0, "wn": 0}))   # 全 0 禁
    # 负权重同层拒
    with pytest.raises(NonCompError):
        evaluate(_in(delta_s=0.0, delta_c=0.0,
                     floor_weights={"ws": -1.0, "wc": 1.0, "wn": 1.0}))


def test_batch_preserves_order():
    """批量保序。"""
    # _in() 默认 ΔS=ΔC=0 ⇒ shaped=0 不 >0 ⇒ reject; 首条给个真过②的
    out = batch([_in(delta_s=0.005), _in(domain_guard_ok=False, delta_s=0.005)])
    assert [o["verdict"] for o in out] == [PASS, REJECT]
