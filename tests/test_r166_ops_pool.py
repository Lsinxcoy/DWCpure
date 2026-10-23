# -*- coding: utf-8 -*-
"""R166 · drawback op 池 + 固定 root — 门③从"投影 op"到"真检测器"。

验收:
  □ 五 op 出厂 + root 恒在 conjunction 首位（构造保证非约定）
  □ 逐 op 三值真判（abstain≠clean — R149 纪律不破）
  □ ctx_from_facts 投影（不重算 — R152 口径桥同族）
  □ C(e)=节点计数（论文 λ·C(e) 口径）
  □ TermFacts 无 component ⇒ 从 edits 取（不猜）
  □ root 缺 parsed_ok ⇒ abstain（缺席≠0）
  □ evaluate_pool 双路报告（逐 op + 树汇总可对账）
"""
from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.organs.ops import (  # noqa: E402
    POOL_MECHANICS, PoolReport, build_grader, ctx_from_facts,
    evaluate_pool, _count_nodes, op_component_known, op_golden_leak,
    op_judge_verdict, op_nonempty_diff, op_root_parse_ok)


def test_five_ops_and_root_first():
    """★★ 五 op 出厂; root 恒在 conjunction 首位（构造保证）。"""
    g, tree = build_grader()
    assert set(g.ops) == {"root_parse_ok", "judge_verdict", "nonempty_diff",
                          "component_known", "golden_leak",
                          "pass_rate_weak"}   # ★ 六 op（含收编）
    # 树的左脊第一个 leaf 必是 root（and 左结合 — 构造钉死, 非约定）
    n, first = tree, None
    while n.kind != "leaf":
        n = n.children[0]
    first = n.op
    assert first == "root_parse_ok"


def test_ops_three_valued_real_judge():
    """★★★ 每个 op 三值真判（拿 ctx 的既有结论, 不猜不重算）。"""
    # root: 缺键 ⇒ abstain; False ⇒ drawback; True ⇒ clean
    r = op_root_parse_ok()
    assert r.run(None, None, {}) == "abstain"
    assert r.run(None, None, {"parsed_ok": False}) == "drawback"
    assert r.run(None, None, {"parsed_ok": True}) == "clean"
    # judge: None ⇒ abstain; True ⇒ clean; False ⇒ drawback
    jv = op_judge_verdict()
    assert jv.run(None, None, {}) == "abstain"
    assert jv.run(None, None, {"judge_success": False}) == "drawback"
    # diff 空 ⇒ drawback
    assert op_nonempty_diff().run(None, None, {"candidate_diff": ""}) == "drawback"
    # 组件越界 ⇒ drawback
    assert op_component_known().run(None, None,
                                    {"component": "x", "vocabulary": ("a",)}) == "drawback"
    # 泄漏 ⇒ drawback
    assert op_golden_leak().run(None, None, {"leakage_hits": ["k1"]}) == "drawback"


def test_evaluate_pool_double_report():
    """★★ 双路报告（逐 op + 树汇总 — 可对账, 不单一来源）。"""
    g, _ = build_grader()
    rep = evaluate_pool(g, {"parsed_ok": True, "judge_success": True,
                            "candidate_diff": "x", "leakage_hits": [],
                            "component": "prompt",
                            "vocabulary": ("prompt",)})
    assert isinstance(rep, PoolReport)
    assert rep.tree_verdict == "clean"
    assert rep.root_verdict == "clean"
    # ★ C(e) = 6 leaf + 5 and 连接 = 11（收编第六 op 后节点数增加 —
    #   首版 5→9 漏算连接节点的教训已记; 6 op 左结合链 = 11）
    assert rep.n_nodes == 11


def test_ctx_from_facts_projection():
    """★ TermFacts ⇒ ctx 投影（component 从 edits 取 — 无则 None⇒abstain）。"""
    from dwc.harness.gates import TermFacts
    from dwc.organs.budget import EditItem
    f1 = TermFacts(pass_rate=1.0, candidate_diff="d",
                   vocabulary=("prompt",),
                   edits=[EditItem(component="prompt", hunk="h")])
    c1 = ctx_from_facts(f1)
    assert c1["judge_success"] is True             # pass_rate=1 ⇒ True
    assert c1["component"] == "prompt"             # 从 edits 首项
    assert c1["parsed_ok"] is True
    f2 = TermFacts()                               # 全空
    c2 = ctx_from_facts(f2)
    assert c2["judge_success"] is None and c2["component"] is None


def test_absent_not_zero_root():
    """★★★ 缺 parsed_ok ⇒ abstain ⇒ **不许过门**（没查≠干净）。"""
    g, _ = build_grader()
    rep = evaluate_pool(g, {})                     # 空 ctx
    assert rep.per_op["root_parse_ok"] == "abstain"
    assert rep.tree_verdict in ("abstain", "drawback")
    assert rep.tree_verdict != "clean"


def test_cost_fn_node_count():
    """★ C(e)=节点计数（论文 λ·C(e) 口径 — 无权重计点）。"""
    from dwc.organs.drawback import Node
    n = Node(kind="and", children=(Node(kind="leaf", op="a"),
                                   Node(kind="leaf", op="b")))
    assert _count_nodes(n) == 3                     # and + 2 leaf


def test_mechanics_documented():
    """三类成本层/固定 root/不重算/evolved 部分 backlog 在档。"""
    assert "judge" in POOL_MECHANICS["cost_layers"]
    assert "backlog" in POOL_MECHANICS["evolved_part"]
    assert "不重算" in POOL_MECHANICS["no_second_judge"]


def test_gate_chain_compat_invariant():
    """★★★★★ 链上接池后兼容不变量（R166 不破坏 R152 的绿）:
      · pass_rate=1.0 ⇒ 门③ passed（与旧匿名版同结论）
      · pass_rate=0.5 ⇒ 门③ blocked
      · detail 带 per_op 六值（新增可观测面）
    """
    from dwc.harness.gates import TermFacts, _g3_drawback
    ok = _g3_drawback(TermFacts(pass_rate=1.0))
    assert ok.status == "passed"
    assert ok.detail["per_op"]["pass_rate_weak"] == "clean"
    bad = _g3_drawback(TermFacts(pass_rate=0.5))
    assert bad.status == "blocked"
    assert bad.detail["per_op"]["pass_rate_weak"] == "drawback"
    assert set(bad.detail["per_op"]) == {
        "root_parse_ok", "judge_verdict", "nonempty_diff", "component_known",
        "golden_leak", "pass_rate_weak"}


def test_empty_vocabulary_abstains_not_veto():
    """★★★★ R166 归因修复锁: 空词表 () ⇒ abstain（没词表≠越界 veto）。"""
    from dwc.harness.gates import TermFacts, _g3_drawback
    from dwc.organs.budget import EditItem
    f = TermFacts(pass_rate=1.0, vocabulary=(),       # ★ run_term 无候选流形态
                  edits=[EditItem(component="prompt", hunk="h")])
    out = _g3_drawback(f)
    assert out.status == "passed"                   # 不被误 veto
    assert out.detail["per_op"]["component_known"] == "abstain"


def test_chain_gate_sees_new_detectors():
    """★★ 候选在场时真检测器开判（component 越界 ⇒ drawback 穿链 blocked）。"""
    from dwc.harness.gates import TermFacts, _g3_drawback
    from dwc.organs.budget import EditItem
    f = TermFacts(pass_rate=1.0, vocabulary=("prompt",),
                  edits=[EditItem(component="bogus_xyz", hunk="h")])
    out = _g3_drawback(f)
    assert out.status == "blocked"                  # ★ 真检测器 veto
    assert out.detail["per_op"]["component_known"] == "drawback"

