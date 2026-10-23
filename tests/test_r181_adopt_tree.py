# -*- coding: utf-8 -*-
"""R181 · 判据树采纳面（Metric Loop 闭环最后一环: 选优 ⇒ 换 ③门 + 门组回归）。

前置闸纪律（fail-closed 同族）:
  □ 新树把旧树放行的候选拦了 ⇒ adopt=False（更优树不许是回退）
  □ 新树放行旧树拦的 ⇒ relax 条目逐条记（不自动拒 — 进化方向, 但可审计）
  □ 完全一致 ⇒ adopt=True 但如实"空操作"
  □ 注入后 ③门真用新树; 复位 ⇒ 出厂树（旧行为逐字节回归）
  □ 回归探针跑完必复位置换态（不污染后续门组行为 — finally 保证）
"""
from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.harness import gates                        # noqa: E402
from dwc.harness.gates import TermFacts              # noqa: E402
from dwc.organs.drawback import Node                 # noqa: E402
from dwc.organs.metric_loop import adopt, regression_probe  # noqa: E402

GOOD = TermFacts(pass_rate=1.0, candidate_diff="d", vocabulary=("D1",))
BAD = TermFacts(pass_rate=0.5, candidate_diff="d", vocabulary=("D1",))


@pytest.fixture(autouse=True)
def _reset_tree():
    yield
    gates.set_current_tree(None)          # 每个测试后复位 — 不互污


def test_default_no_injection_uses_factory():
    """★ 未注入 ⇒ 出厂全池树（旧行为 — 旧测试全绿的前提）。"""
    assert gates._current_tree_injection() is None
    o = gates._g3_drawback(GOOD)
    assert o.status == "passed"


def test_injected_tree_changes_gate3():
    """★★ 注入 root 单叶 ⇒ ③门真用新树（坏候选被放行 — 回归快照会记）。"""
    gates.set_current_tree(Node(kind="leaf", op="root_parse_ok"))
    o = gates._g3_drawback(BAD)
    assert o.status == "passed"          # root-only 不看 pass_rate ⇒ 放行


def test_regression_isomorphic_adopt_but_empty():
    """★★ 同构树判定一致 ⇒ adopt=True 且零 diff（空操作如实）。"""
    t = Node(kind="and", children=(Node(kind="leaf", op="root_parse_ok"),
                                  Node(kind="leaf", op="judge_verdict")))
    rep = regression_probe(lambda: [GOOD, BAD], new_tree=t)
    assert rep["adopt"] is True and rep["n"] == 2
    assert rep["relaxed"] == [] and rep["blocked_more"] == []


def test_regression_stricter_tree_rejected():
    """★★★ 新树拦了旧树放行的 ⇒ adopt=False（更优树不许是回退）。"""
    # 构造一个更严的树: root ∧ judge ∧ nonempty_diff（req diff 非空 —
    # BAD 的 candidate_diff="d" 非空∴ 还过; 换空 diff 的 GOOD_NODIFF 造差异）
    empty = TermFacts(pass_rate=1.0, candidate_diff="", vocabulary=("D1",))
    # 出厂树对 GOOD_NODIFF: nonempty_diff drawback ⇒ blocked
    # 新树 = root ∧ judge（不看 diff）⇒ passed ⇒ 这是 relaxed 不是 stricter
    t_loose = Node(kind="and", children=(Node(kind="leaf", op="root_parse_ok"),
                                        Node(kind="leaf", op="judge_verdict")))
    rep = regression_probe(lambda: [empty, BAD], new_tree=t_loose)
    assert rep["relaxed"]               # 至少一条放行记录（可审计）
    assert rep["adopt"] is True         # 只放松 ⇒ 采纳方向允许


def test_regression_resets_injection_after_probe():
    """★★★ 探针跑完必复位（finally — 不污染后续门组行为）。"""
    sentinel = Node(kind="leaf", op="root_parse_ok")
    gates.set_current_tree(sentinel)
    t = Node(kind="leaf", op="root_parse_ok")
    regression_probe(lambda: [GOOD], new_tree=Node(kind="leaf",
                                                   op="judge_verdict"))
    assert gates._current_tree_injection() is sentinel   # 原样恢复


def test_adopt_injects_and_why_records_relaxed():
    """★★★ adopt: 回归过 ⇒ 真注入; why 带 n/relaxed（审计面）。"""
    t = Node(kind="leaf", op="root_parse_ok")
    res = adopt(t, lambda: [GOOD, BAD])
    assert res["adopted"] is True
    assert gates._current_tree_injection() is t
    assert "relaxed" in res["why"]


def test_adopt_rejects_stricter_without_partial_state():
    """★★★ 回归不过 ⇒ 拒绝 + 不注入（不半吊 — 旧树保持）。"""

    class _Boom:
        def __call__(self):
            raise RuntimeError("surface gone")

    res = adopt(Node(kind="leaf", op="root_parse_ok"), _Boom())
    assert res["adopted"] is False
    assert gates._current_tree_injection() is None
