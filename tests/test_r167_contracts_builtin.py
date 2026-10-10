# -*- coding: utf-8 -*-
"""R167 · contract 真注册 + 门② 升级 — 从"表非空"到逐 check 真判。

验收:
  □ builtin_registry 出厂一条全局契约（budget_window = boundedParam 实例）
  □ 两层契约分层: 全局静态层(值域) / 候选现场层(反射, 不入全局表)
  □ 被约束量 = edits 数（与 budget 门同源 — 非 diff 字符数, 实测纠偏锁）
  □ 无 edits ⇒ no_input（不凑 check — 没对象不判）
  □ edits>8 ⇒ violation（议程外真 veto）
  □ 空表 ⇒ no_contracts verdict（门② blocked 的输入）
  □ 门②接上: 表空⇒blocked / 对象齐⇒逐 check / 违反⇒blocked
"""
from __future__ import annotations

import os
import sys

import pytest

ROOT = r"E:/Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.organs.contracts_builtin import (  # noqa: E402
    BUILTIN_MECHANICS, builtin_registry, budget_window_contract,
    check_against_facts, install_builtin)
from dwc.organs.budget import EditItem  # noqa: E402


class _F:
    def __init__(self, diff="clean = 1", edits=None):
        self.candidate_diff = diff
        self.edits = edits


def test_builtin_registry_one_global_contract():
    """★ 出厂表只一条全局契约（budget_window — 常量值域全局成立）。"""
    reg = builtin_registry()
    ids = reg.summary()["ids"]
    assert len(ids) == 1
    assert ids[0].startswith("boundedParam(")
    f = budget_window_contract()
    assert f.check((1.0, 8.0), 5) is True           # 5 ∈ [1,8]
    assert f.check((1.0, 8.0), 20) is False         # 20 > 8


def test_two_layer_not_mixed():
    """★★ 两层契约分层（现场层不入全局表 — per-candidate 语义不钉死）。"""
    reg = builtin_registry()
    assert "dafnyAnnotate" not in reg.summary()["ids"]   # 全局表无反射契约
    out = check_against_facts(reg, _F(edits=[EditItem("prompt", "h")]))
    assert "dafnyAnnotate_live" in out["per_contract"]    # 现场层报告在场


def test_constrained_quantity_is_edits():
    """★★★ 被约束量 = edits 数（R167 实测纠偏: diff 字符数是编的口径）。"""
    reg = builtin_registry()
    # "clean = 1" len=9 > 8 ⇒ 首版会误 violation; edits=2 才对
    out = check_against_facts(reg, _F(diff="clean = 1",
                                      edits=[EditItem("prompt", "a"),
                                             EditItem("prompt", "b")]))
    assert out["verdict"] == "passed"
    assert out["per_contract"]["boundedParam(1.0,8.0)"]["ok"] is True


def test_no_edits_no_input():
    """★ 无 edits 申报 ⇒ no_input（不凑 check — 没对象不判）。"""
    reg = builtin_registry()
    out = check_against_facts(reg, _F(edits=[]))
    assert out["per_contract"]["boundedParam(1.0,8.0)"]["status"] == "no_input"
    assert out["verdict"] == "passed"                # 注册面在 ⇒ 不否决


def test_over_agenda_violation():
    """★★ edits=20 > b_max=8 ⇒ violation（议程外 — 真 veto 输入）。"""
    reg = builtin_registry()
    out = check_against_facts(reg, _F(
        edits=[EditItem("prompt", "h%d" % i) for i in range(20)]))
    assert out["verdict"] == "violation"
    assert out["n_violation"] == 1
    assert out["per_contract"]["boundedParam(1.0,8.0)"]["ok"] is False


def test_empty_table_verdict():
    """★ 空表 ⇒ no_contracts（门② blocked 的输入 — 显式缺席非通过）。"""
    from dwc.organs.contract import ContractRegistry
    out = check_against_facts(ContractRegistry(), _F())
    assert out["verdict"] == "no_contracts"


def test_gate2_upgraded():
    """★★★★ 门②升级: 空表⇒blocked / 对象齐⇒passed / 违反⇒blocked。

    ★★ R170 语义细化: "None（未注入）⇒ 回落 builtin ⇒ passed"（R167
      裁决落地）; "显式空表 ⇒ blocked"（纪律不变 — 没契约≠契约满足）
    """
    from dwc.harness.gates import install_registry, run_gates, TermFacts
    from dwc.organs.budget import EditItem as EI
    from dwc.organs.contract import ContractRegistry
    # 未注入 ⇒ 回落 builtin ⇒ 真判 passed（不是"没表就 blocked"假阴性）
    install_registry(None)
    o_default = run_gates(TermFacts(pass_rate=1.0))
    g2d = [g for g in o_default["gates"] if g["gate"] == "contract"][0]
    assert g2d["status"] == "passed"
    # 显式空表 ⇒ blocked
    install_registry(ContractRegistry())
    o_empty = run_gates(TermFacts(pass_rate=1.0))
    g2 = [g for g in o_empty["gates"] if g["gate"] == "contract"][0]
    assert g2["status"] == "blocked"
    # 装 builtin + 对象齐 ⇒ passed
    install_registry(builtin_registry())
    o_ok = run_gates(TermFacts(pass_rate=1.0,
                               edits=[EI(component="prompt", hunk="h")]))
    g2b = [g for g in o_ok["gates"] if g["gate"] == "contract"][0]
    assert g2b["status"] == "passed"
    # 违反（edits=20）⇒ blocked
    o_bad = run_gates(TermFacts(pass_rate=1.0,
                                edits=[EI(component="prompt", hunk="h%d" % i)
                                       for i in range(20)]))
    g2c = [g for g in o_bad["gates"] if g["gate"] == "contract"][0]
    assert g2c["status"] == "blocked"
    assert g2c["detail"].get("n_violation", 0) >= 1
    install_registry(None)


def test_mechanics_documented():
    """两层/被约束量/flexibility 诚实边界在档。"""
    assert "编辑数" in BUILTIN_MECHANICS["constrained_quantity"]
    assert "planner" in BUILTIN_MECHANICS["flexibility_honest"]
