# -*- coding: utf-8 -*-
"""R148 · FGGM 契约检查（门②）— 机械 check + 已验证 fallback + 一阶面诚实缺口。

验收:
  □ FGGM_FIELDS 七字段（Eq.15 BNF）
  □ f_d 必填（性质 4: 无 fallback ⇒ 拒）
  □ boundedParam 实例: Ψ_l 边界判定 + f_d = clamp
  □ dafnyAnnotate 实例: 反射性子集 y==x + f_d = p
  □ check 三值: no_contract(None) ≠ 违规(False)（X2 纪律）
  □ 重注册即抛; unregister 不存在即 KeyError
"""
from __future__ import annotations

import os
import sys

import pytest

ROOT = r"E:/Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.organs.contract import (  # noqa: E402
    CONTRACT_MECHANICS, FGGM_FIELDS, ST_CHECKED, ST_NO_CONTRACT, ContractError,
    ContractRegistry, FGGM, bounded_param, dafny_annotate_identity)


def test_seven_fields_enum():
    """★ 七字段与 Eq.15 BNF 一致。"""
    assert FGGM_FIELDS == ("id", "gmid", "type_sig", "phi_l", "psi_l",
                           "f_p", "f_d")
    assert "seven_fields" in CONTRACT_MECHANICS


def test_fallback_required():
    """★ 性质 4: 无 f_d ⇒ 注册即拒（fallback 是机制不是可选项）。"""
    with pytest.raises(ContractError):
        FGGM(id="x", type_sig="t", check=lambda x, y: True, fallback=None)
    # check 必须 callable
    with pytest.raises(ContractError):
        FGGM(id="x", type_sig="t", check="notcallable", fallback=lambda x: x)


def test_bounded_param_instance():
    """★ 实例 1: Ψ_l 边界 + f_d=clamp（论文 §4.2 逐字映射）。"""
    g = bounded_param(0.0, 10.0)
    assert "boundedParam" in g.id
    assert "(l <= f(l,u))" in g.psi_l
    # Ψ_l: y ∈ [l,u]
    assert g.check((0.0, 10.0), 5.0) is True
    assert g.check((0.0, 10.0), -1.0) is False
    assert g.check((0.0, 10.0), 11.0) is False
    # f_d = clamp: min(max(l, y), u)
    assert g.run_fallback((0.0, 10.0), 99.0) == 10.0
    assert g.run_fallback((0.0, 10.0), -5.0) == 0.0
    assert g.run_fallback((0.0, 10.0), 7.0) == 7.0


def test_dafny_annotate_reflexive_subset():
    """★ 实例 2: Φ parse + 反射性子集（y==x）+ f_d=p（DWC 等价形态）。"""
    g = dafny_annotate_identity("prog")
    assert g.check("prog", "prog") is True
    assert g.check("prog", "other") is False
    # f_d(p,y)=p — 回退到原程序（不变性）
    assert g.run_fallback("prog", "modified") == "prog"
    assert "反射" in g.info


def test_registry_check_three_valued():
    """★★ 三值: 未注册(None) ≠ 违规(False) — X2 纪律。"""
    reg = ContractRegistry()
    out = reg.check("nope", 1, 1)
    assert out["status"] == ST_NO_CONTRACT and out["ok"] is None
    g = bounded_param(0.0, 1.0)
    reg.register(g)
    ok = reg.check(g.id, (0.0, 1.0), 0.5)
    assert ok["status"] == ST_CHECKED and ok["ok"] is True
    bad = reg.check(g.id, (0.0, 1.0), 2.0)
    assert bad["ok"] is False and "不许过门" in bad["note"]


def test_registry_duplicate_and_unregister():
    """重注册即抛（不静默换契约）; unregister 不存在即 KeyError。"""
    reg = ContractRegistry()
    g = bounded_param(0.0, 1.0)
    reg.register(g)
    with pytest.raises(ContractError):
        reg.register(g)
    reg.unregister(g.id)
    with pytest.raises(KeyError):
        reg.unregister(g.id)
    reg.register(g)          # 注销后可重注册
    assert reg.summary()["n_registered"] == 1


def test_verify_gap_documented():
    """★ 一阶验证面缺口在档（契约检查≠契约证明）。"""
    assert "not_instrumented" in CONTRACT_MECHANICS["verify_gap"]
