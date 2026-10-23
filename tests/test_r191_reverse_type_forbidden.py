# -*- coding: utf-8 -*-
"""R191 · REVERSE 语义裁决的**机器固化**（用户"执行你的建议"）。

三件（全零行为变更 — 只锁语义 + 挡类型二）:
  ① REVERSE_SCOPE 声明（allowed=提案侧 / forbidden=判据侧）
  ② reverse_candidates 的类型二防御（rules 带 verifier_rung/checks/golden
     ⇒ DirectionError, 不静默返候选）
  ③ 本测试文件 — 把①②钉成红/绿灯

依据: G2（判据在系统外）/ 门⑥账本只认"落地了" / R184+R161 split 分离 +
2603.25111 性质②（契约对任意 θ 成立 — f_d 退能力不退契约）
"""
from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.organs.direction import (REVERSE_SCOPE, DirectionError,        # noqa: E402
                                  EvolutionDirection, ensure_direction,
                                  reverse_candidates)
from dwc.organs.evolver import Mutator                                  # noqa: E402


# ── ① 语义锁（design 逐字不漂移）──────────────────────────
def test_reverse_semantics_verbatim_from_design():
    """★ design 两处逐字「后退 (回退到更简单的方案)」— 锁死不漂移。"""
    from dwc.organs.direction import SEMANTICS
    assert SEMANTICS[EvolutionDirection.REVERSE] == "后退 (回退到更简单的方案)"
    # "方案" = 提案侧 — 与 forbidden/清单的判据侧字面无交集
    assert "rung" not in SEMANTICS[EvolutionDirection.REVERSE]
    assert "verifier" not in SEMANTICS[EvolutionDirection.REVERSE]


def test_scope_allowed_is_proposal_side():
    """★★★ R191 裁决①: allowed = 提案侧（target/patch/proposal）。"""
    assert set(REVERSE_SCOPE["allowed"]) == {"target", "patch", "proposal"}


def test_scope_forbidden_is_judge_side():
    """★★★ R191 裁决①: forbidden = 判据侧（G2 不可被进化面改写）。"""
    f = set(REVERSE_SCOPE["forbidden"])
    assert {"verifier_rung", "checks", "anchor", "acceptance",
            "threshold", "golden", "split"} <= f
    # ★ 两侧不许有交集（否则"允许=禁止"漏判）
    assert not (f & set(REVERSE_SCOPE["allowed"]))


# ── ② 类型二防御（机器判, 不是写在注释里）──────────────────
def test_type2_rung_downgrade_raises():
    """★★★ 核心: 降 verifier_rung 的"REVERSE 规则"必须 raise — 不返候选。"""
    bad_rules = {"weakened_1": {"component": "control_flow",
                                "patch": "return 0",
                                "verifier_rung": 1}}
    with pytest.raises(DirectionError) as ei:
        reverse_candidates(bad_rules, "control_flow")
    assert "REVERSE 禁行类型二" in str(ei.value)
    assert "verifier_rung" in str(ei.value)


def test_type2_checks_edit_raises():
    """★★★ 改 checks（判据侧改写）同样 raise。"""
    bad = {"edit_checks": {"component": "prompt", "checks": [],
                           "patch": "x"}}
    with pytest.raises(DirectionError):
        reverse_candidates(bad, "prompt")


@pytest.mark.parametrize("leaked", ["golden", "acceptance", "threshold",
                                    "split", "anchor"])
def test_type2_every_forbidden_field_raises(leaked):
    """★ forbidden 表**逐字段**验（漏一个就等于没锁 — 全覆盖纪律）。"""
    bad = {"k": {"component": "c", "patch": "return 1", leaked: None}}
    with pytest.raises(DirectionError):
        reverse_candidates(bad, "c")


def test_type1_proposal_side_still_allowed():
    """★★★ 类型一（提案侧）不误伤 — patch/target 规则正常查表。"""
    rules = {"E_SHORT": {"component": "control_flow",
                         "patch": "return 1"}}
    # patch 长度 ≤ REVERSE_MAX_PATCH ⇒ 是"更简单"候选（类型一, 允许）
    assert reverse_candidates(rules, "control_flow") == \
        ["E_SHORT|return 1"]


def test_real_rules_have_no_forbidden_field():
    """★★★ 出厂 RULES 7 条不带判据侧字段 ⇒ 类型二防御永不误伤现役。"""
    rules = getattr(Mutator, "RULES", None) or {}
    assert rules, "RULES 出厂表读不到 — 真源丢了（不是空表合法）"
    for k, v in rules.items():
        assert not (set(REVERSE_SCOPE["forbidden"]) & set(v)), \
            "出厂规则 %r 带判据侧字段 ⇒ 将来 REVERSE 一律 raise（自锁）" % k


def test_reverse_candidates_real_rules_is_empty():
    """★★★ R188 实测不变: 真 RULES 无"更简单"类 ⇒ 如实 []（不是缺陷）。"""
    assert reverse_candidates(getattr(Mutator, "RULES", None),
                              "control_flow") == []


# ── ③ 上游接线的 FORWARD/LATERAL 不受影响（回归面）───────
def test_other_directions_untouched():
    """★ 裁决只碰 REVERSE 半边 — 另两方向语义原样（精准手术）。"""
    assert ensure_direction("FORWARD") is EvolutionDirection.FORWARD
    assert ensure_direction("LATERAL") is EvolutionDirection.LATERAL
    assert ensure_direction("REVERSE") is EvolutionDirection.REVERSE
    with pytest.raises(DirectionError):
        ensure_direction(None)          # None 仍不是第四方向（R188 原纪律）
    with pytest.raises(DirectionError):
        ensure_direction("reverse")     # 大小写仍拒
