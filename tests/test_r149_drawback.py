# -*- coding: utf-8 -*-
"""R149 · drawback 检测器 — clean≠认证正确（门③; op 三值 + 表达式树）。

验收:
  □ VERDICTS 三值枚举 + op 返回枚举外显式拒（None 当 clean 禁）
  □ 表达式树六形态（leaf/or/and/not/k_of_v/weighted）契约
  □ abstain 子节点排除 + 全 abstain ⇒ 不过门（没查≠干净）
  □ k_of_v 的 k 越界 / weighted 的 θ 越界 / 负权重全拒
  □ Grader: op 重名拒 / 树挂未注册 op 拒 / 未设树 ⇒ no_tree
  □ 门③语义: verdict=clean 也只=没找到缺点 (note 写死)
"""
from __future__ import annotations

import os
import sys

import pytest

ROOT = r"E:/Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.organs.drawback import (  # noqa: E402
    ABSTAIN, CLEAN, DRAWBACK, DRAWBACK_MECHANICS, NODE_KINDS, VERDICTS,
    DrawbackError, Grader, Node, Op)


def _op(name: str, v: str) -> Op:
    return Op(name=name, fn=lambda t, y, c: v)


def test_verdicts_and_op_contract():
    """★ 三值枚举 + op 返回枚举外显式拒（None 当 clean = 静默放行禁）。"""
    assert VERDICTS == ("drawback", "clean", "abstain")
    o = _op("x", CLEAN)
    assert o.run(1, 2, {}) == "clean"
    bad = Op(name="bad", fn=lambda t, y, c: None)
    with pytest.raises(DrawbackError):
        bad.run(1, 2, {})
    with pytest.raises(DrawbackError):
        Op(name="", fn=lambda t, y, c: CLEAN)


def test_leaf_op_lookup():
    """★ 树挂未注册 op ⇒ set_tree 即拒（等不到 grade 才炸）。"""
    g = Grader()
    with pytest.raises(DrawbackError):
        g.set_tree(Node(kind="leaf", op="missing"))


def test_or_and_not_semantics():
    """★ 组合三值: or 有 drawback ⇒ drawback; and 有 drawback ⇒ drawback; not 互换。"""
    g = Grader()
    g.register_op(_op("a", CLEAN))
    g.register_op(_op("b", DRAWBACK))
    g.register_op(_op("c", ABSTAIN))
    g.register_op(_op("d", ABSTAIN))
    # or: (clean, drawback) ⇒ drawback
    g.set_tree(Node(kind="or", children=(Node(kind="leaf", op="a"),
                                         Node(kind="leaf", op="b"))))
    assert g.grade(1, 2)["verdict"] == "drawback"
    # or: (clean, abstain) ⇒ abstain 排除 ⇒ clean（原文排除规则）
    g.set_tree(Node(kind="or", children=(Node(kind="leaf", op="a"),
                                         Node(kind="leaf", op="c"))))
    assert g.grade(1, 2)["verdict"] == "clean"
    # not(clean) ⇒ drawback; not(abstain) ⇒ abstain 透传
    g.set_tree(Node(kind="not", children=(Node(kind="leaf", op="a"),)))
    assert g.grade(1, 2)["verdict"] == "drawback"
    g.set_tree(Node(kind="not", children=(Node(kind="leaf", op="c"),)))
    assert g.grade(1, 2)["verdict"] == "abstain"


def test_all_abstain_never_passes():
    """★★ 全 abstain ⇒ abstain ⇒ 不过门（没查≠干净 — X2 同族）。"""
    g = Grader()
    g.register_op(_op("x", ABSTAIN))
    g.register_op(_op("y", ABSTAIN))
    g.set_tree(Node(kind="and", children=(Node(kind="leaf", op="x"),
                                          Node(kind="leaf", op="y"))))
    out = g.grade(1, 2)
    assert out["verdict"] == "abstain"
    assert out["ok"] is False                     # ★ abstain 不过门
    assert "没查≠干净" in out["note"]


def test_k_of_v_and_weighted():
    """★ k-of-v 无权重投票 + weighted 阈值（越界即拒）。"""
    g = Grader()
    g.register_op(_op("d1", DRAWBACK))
    g.register_op(_op("d2", DRAWBACK))
    g.register_op(_op("c1", CLEAN))
    # k=2: 两个 drawback ⇒ drawback; 只 1 个 ⇒ clean
    g.set_tree(Node(kind="k_of_v", k=2, children=(
        Node(kind="leaf", op="d1"), Node(kind="leaf", op="d2"),
        Node(kind="leaf", op="c1"))))
    assert g.grade(1, 2)["verdict"] == "drawback"
    g.set_tree(Node(kind="k_of_v", k=3, children=(
        Node(kind="leaf", op="d1"), Node(kind="leaf", op="d2"),
        Node(kind="leaf", op="c1"))))
    assert g.grade(1, 2)["verdict"] == "clean"
    # weighted: 权重 (1,3) θ=3 ⇒ 3 权处 drawback ⇒ drawback; θ=4 ⇒ clean
    g.set_tree(Node(kind="weighted", weights=(1.0, 3.0), theta=3.0,
                    children=(Node(kind="leaf", op="c1"),
                              Node(kind="leaf", op="d2"))))
    assert g.grade(1, 2)["verdict"] == "drawback"
    g.set_tree(Node(kind="weighted", weights=(1.0, 3.0), theta=4.0,
                    children=(Node(kind="leaf", op="c1"),
                              Node(kind="leaf", op="d2"))))
    assert g.grade(1, 2)["verdict"] == "clean"


def test_node_contract_violations():
    """契约: k 越界 / θ 越界 / 负权重 / not 多 child / 空 children 全拒。"""
    leaf = Node(kind="leaf", op="a")
    with pytest.raises(DrawbackError):
        Node(kind="k_of_v", k=0, children=(leaf, leaf))     # k<1
    with pytest.raises(DrawbackError):
        Node(kind="k_of_v", k=3, children=(leaf, leaf))     # k>n
    with pytest.raises(DrawbackError):
        Node(kind="weighted", weights=(-1.0, 1.0), theta=1.0,
             children=(leaf, leaf))                         # 负权重
    with pytest.raises(DrawbackError):
        Node(kind="weighted", weights=(1.0,), theta=99.0,
             children=(leaf, leaf))                         # θ > Σw
    with pytest.raises(DrawbackError):
        Node(kind="not", children=(leaf, leaf))             # not 多 child
    with pytest.raises(DrawbackError):
        Node(kind="or", children=())                        # 空组合


def test_grader_registrations_and_no_tree():
    """Grader: op 重名拒 / 树挂未注册 op 拒 / 未设树 ⇒ no_tree。"""
    g = Grader()
    g.register_op(_op("a", CLEAN))
    with pytest.raises(DrawbackError):
        g.register_op(_op("a", DRAWBACK))         # 重名不静默覆盖
    with pytest.raises(DrawbackError):
        g.set_tree(Node(kind="leaf", op="ghost"))  # 未注册 op
    g2 = Grader()
    out = g2.grade(1, 2)
    assert out["verdict"] == "no_tree" and out["ok"] is False


def test_clean_note_not_correctness():
    """★★ clean 的 note 必须明说"非认证正确"（门③语义防误读）。"""
    g = Grader()
    g.register_op(_op("a", CLEAN))
    g.set_tree(Node(kind="leaf", op="a"))
    out = g.grade(1, 2)
    assert out["verdict"] == "clean" and out["ok"] is True
    assert "非" in out["note"] and "认证正确" in out["note"]
    assert "not_correctness" in DRAWBACK_MECHANICS
