# -*- coding: utf-8 -*-
"""R438 · 只读组件（evaluator / external_source）的**代码级**拒绝证据。

★ 改前：`editable_vocab()` 只用于新颖度候选池，从不做校验 ⇒
  直接构造 `component="evaluator"` 的 Proposal 会被**接受**
  ⇒ "不可编辑"只是文档承诺，不是代码事实（G10 密封没有落到构造口）。

锁：
1. evaluator / external_source 构造即抛 EvolverError。
2. 12 个可编辑组件仍能正常构造（不许把门焊死）。
3. `editable_vocab()` 与拒绝集互补。
"""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.organs.evolver import (   # noqa: E402
    EvolverError, Proposal, editable_vocab)


def _mk(comp):
    return Proposal(proposal_id="P_ro", failure_signature={"c": "E", "q": "q",
                                                          "fn": "f"},
                    component=comp, target="f", patch="p", rationale="r",
                    dimension="D1")


@pytest.mark.parametrize("comp", ["evaluator", "external_source"])
def test_readonly_components_rejected(comp):
    with pytest.raises(EvolverError) as ei:
        _mk(comp)
    assert "不可编辑" in str(ei.value)


def test_editable_components_still_construct():
    for comp in sorted(editable_vocab()):
        p = _mk(comp)
        assert p.component == comp


def test_vocab_excludes_readonly():
    v = editable_vocab()
    assert "evaluator" not in v
    assert "external_source" not in v
    assert "architecture" in v and "meta_evolution" in v
