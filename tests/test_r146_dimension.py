# -*- coding: utf-8 -*-
"""R146 · 九维分类 + 三维声明校验 — 语义查重降为属性冲突检测（V2 §4.2）。

验收:
  □ DIMENSIONS 九维逐字（HarnessX D1-D9 + 中文标签）
  □ ModuleDeclaration 契约: 未知维度拒绝 / 三字段非空
  □ find_conflicts: 重名 + 同位同组抢位; 跨维复用组不算冲突（论文不禁）
  □ declares_valid_hook: 枚举真源在 hook.HOOKS（不重抄）
  □ dimension_index: 覆盖 + 空维度（哪个维没模块一目了然）
"""
from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.organs.dimension import (  # noqa: E402
    DIMENSION_IDS, DIMENSION_MECHANICS, DIMENSIONS, DimensionError,
    ModuleDeclaration, declares_valid_hook, dimension_index, find_conflicts)
from dwc.organs.hook import HOOKS  # noqa: E402  (枚举真源跨模块复用)


def _d(module: str, dim: str = "D3", hook: str = "step_start",
       group=None) -> ModuleDeclaration:
    # ★ 三态（R145 同款教训: 助手不许比实现更宽容 — 空串必须透传给契约层）
    grp = ("g_" + module) if group is None else group
    return ModuleDeclaration(
        module=module, dimension=dim, hook=hook,
        singleton_group=grp)


def test_nine_dimensions_match_paper():
    """★ 九维与 HarnessX §3.3 原文逐字（D1 model selection … D9 training bridge）。"""
    ids = [d[0] for d in DIMENSIONS]
    assert ids == ["D%d" % i for i in range(1, 10)]
    names = [d[1] for d in DIMENSIONS]
    assert names == ["model_selection", "context_assembly",
                     "memory_management", "tool_ecosystem",
                     "execution_env", "evaluation", "control_safety",
                     "observability", "training_bridge"]
    assert DIMENSION_IDS == tuple(ids)


def test_declaration_contract():
    """★ 契约: 未知维度拒绝 / 三字段非空 / as_dict 带中文标签。"""
    with pytest.raises(DimensionError):
        _d("m", dim="D10")                  # 九维外不猜
    with pytest.raises(DimensionError):
        ModuleDeclaration(module="", dimension="D3", hook="step_start",
                          singleton_group="g")
    with pytest.raises(DimensionError):
        _d("m", hook="")
    with pytest.raises(DimensionError):
        _d("m", group="")
    d = _d("mm", dim="D3")
    assert d.as_dict()["dimension_label"] == "记忆管理"


def test_conflicts_duplicate_module_and_triple():
    """★★ 两类冲突: 重名 + 同位同组抢位。"""
    r = find_conflicts([_d("a"), _d("a")])
    kinds = [c["kind"] for c in r["conflicts"]]
    assert "duplicate_module" in kinds
    assert r["ok"] is False
    # 同位同组（D3/step_start/g_same 两个模块）
    r2 = find_conflicts([_d("a", group="same"), _d("b", group="same")])
    c2 = [c for c in r2["conflicts"]
          if c["kind"] == "duplicate_dimension_hook"][0]
    assert c2["dimension"] == "D3" and c2["singleton_group"] == "same"


def test_cross_dimension_reuse_not_conflict():
    """★ 跨维复用组不算冲突（论文只禁同组同 hook 点 — 防误伤）。"""
    r = find_conflicts([_d("a", dim="D3", group="memory"),
                        _d("b", dim="D1", group="memory")])
    assert r["ok"] is True
    assert r["n_conflicts"] == 0
    assert r["cross_dimension_group_reuse"]["memory"] == ["D1", "D3"]


def test_same_dim_different_hook_not_conflict():
    """同维不同 hook 点/不同组 ⇒ 不冲突（每个位一个处理器是允许的）。"""
    r = find_conflicts([_d("a", hook="step_start", group="g1"),
                        _d("b", hook="step_end", group="g2")])
    assert r["ok"] is True


def test_declares_valid_hook_single_source():
    """★ hook 枚举唯一真源 = hook.HOOKS（本模块不重抄枚举）。"""
    d = _d("m", hook="step_start")
    assert declares_valid_hook(d, HOOKS) is True
    d2 = _d("m", hook="task_done")      # 构造层不校验名（枚举在 hook）
    assert declares_valid_hook(d2, HOOKS) is False   # 真源校验在后


def test_dimension_index_coverage():
    """★ 索引: 覆盖计数 + 空维度（哪个维没挂模块）。"""
    idx = dimension_index([_d("a", dim="D3"), _d("b", dim="D3"),
                           _d("c", dim="D6")])
    assert idx["coverage"]["D3"] == 2 and idx["coverage"]["D6"] == 1
    assert "D9" in idx["empty_dimensions"]
    assert idx["labels"]["D7"] == "控制/安全"


def test_mechanics_doc_string():
    """机制说明在位（防后人改法丢口径）。"""
    assert "抢位" in DIMENSION_MECHANICS["conflict_kinds"]
    assert "hook_enum_single_source" in DIMENSION_MECHANICS
