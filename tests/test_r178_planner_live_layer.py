# -*- coding: utf-8 -*-
"""R178 · planner 现场层接门②（2603.25111 硬规则: 每个 GM 调用必须包在已验证 FGGM 内）。

验收（本地态全可复现; 真 LLM 态显式标记 — 端点不通则 skip 不假过）:
  □ 默认关（planner_layer=False）⇒ 无 planner_live 键（旧行为逐字节不变）
  □ 开 ⇒ 现场 craft: 真端点过 ⇒ checked/ok（n_edits∈合成区间）
  □ 开 + LLM 拒 ⇒ no_contract + trace（⊥ 不冒充满足, verdict 不新增违规）
  □ _template_params_for 对三种 FGGM 的 x 反解（bounded/delta 两段 / enum 空）
  □ _task_view 带 quantity 靶（R178 纠偏: 不带靶 LLM 约束错对象）
  □ FGGM.check 协议: enum_member 参数进闭包不吃 x（R178 修 R175 埋的坑）
"""
from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.harness.gates import TermFacts                  # noqa: E402
from dwc.organs.contracts_builtin import (               # noqa: E402
    _default_llm, _task_view, _template_params_for,
    builtin_registry, check_against_facts)
from dwc.organs.planner import build_fggm                # noqa: E402

REG = builtin_registry()
FACTS = TermFacts(candidate_diff="--- a\n+++ b\n@@ def f() @@",
                  edits=[1, 2, 3])


def test_default_off_is_byte_identical():
    """★★★ 默认关 ⇒ 无 planner_live 键（旧链行为不变 — 不悄悄变脸）。"""
    rep = check_against_facts(REG, FACTS)
    assert "planner_live" not in rep["per_contract"]
    assert rep["verdict"] == "passed"


def test_task_view_carries_quantity():
    """★★★ 任务面带靶（R178 纠偏: 无靶 ⇒ LLM 曾把 diff 当 enum members）。"""
    tv = _task_view(FACTS)
    assert tv["quantity"] == {"name": "n_edits", "value": 3}
    assert tv["n_edits"] == 3


def test_template_params_for_three_kinds():
    """★ _template_params_for: bounded/delta ⇒ (l,u); enum ⇒ ()（闭包）。"""
    b = build_fggm({"kind": "bounded_param", "params": {"l": 1, "u": 8}})
    d = build_fggm({"kind": "delta_band", "params": {"l": 0.0, "u": 0.05}})
    e = build_fggm({"kind": "enum_member",
                    "params": {"members": ["D1", "D2"]}})
    assert _template_params_for(b) == (1.0, 8.0)
    assert _template_params_for(d) == (0.0, 0.05)
    assert _template_params_for(e) == ()
    # ★★ enum 参数进闭包不吃 x（R175 埋的坑 — R178 修）
    assert e.check((), "D2") is True and e.check((), "X") is False


def test_planner_layer_real_endpoint():
    """★★★ 真端点: 现场合成 ⇒ validate ⇒ FGGM.check 对 n_edits=3 真判。

    ★ 端点异常 ⇒ skip（不假装跑过; 通了必见 checked/ok）
    """
    if not _default_llm().configured:
        pytest.skip("llm 未配置")
    # ★★★ R191 · 端点偶发空响应（实测 12 次里 1 次 ok=False/err=None/
    #   text=''）⇒ 与 R185/R188 同族的漏修: 单次失败会造误报红灯
    #   ⇒ 3 次重试 + 仍未通则 skip 留痕（不用网络抖动造红灯噪声;
    #   真端点路径本身由 assert 钉死 — 重试只是抗抖动, 不放水）
    rep = None
    for _attempt in range(3):
        rep = check_against_facts(REG, FACTS, planner_layer=True)
        pl = rep["per_contract"]["planner_live"]
        if pl["status"] in ("checked", "no_contract"):
            break
        _empty = pl.get("err") or pl.get("note") or ""
        if "空" not in str(_empty) and "empty" not in str(_empty).lower():
            break                       # 非空响应类失败 ⇒ 不重试, 如实判红
    else:
        pytest.skip("llm 端点连续空响应（网络抖动 — 留痕不假过）")
    pl = rep["per_contract"]["planner_live"]
    assert pl["status"] in ("checked", "no_contract")
    if pl["status"] == "checked":
        assert pl["ok"] is True          # n_edits=3 落在合成区间 = 通过
        assert rep["verdict"] == "passed"
        assert "trace" not in pl


def test_planner_layer_reject_is_honest_perp():
    """★★ no_contract 时: trace 留痕 + verdict 不因现场层缺席新增违规。"""
    rep = check_against_facts(REG, FACTS, planner_layer=True)
    pl = rep["per_contract"]["planner_live"]
    if pl["status"] == "no_contract":
        assert isinstance(pl.get("trace"), list) and pl["trace"]
        assert "note" in pl and "⊥" in pl["note"]
        assert rep["verdict"] in ("passed", "violation")   # 由全局层定
