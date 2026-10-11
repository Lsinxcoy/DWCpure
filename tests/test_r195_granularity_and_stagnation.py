# -*- coding: utf-8 -*-
"""R195 · Y2/Y3 验收（用户令"你来深度思考 做出最好的决策"）。

两条决策的核心（详见 docs/R195_Y2Y3_DECISIONS.md）:
  Y3 停滞只对**前进类**记（EvoTS 2608.17933 §4.2 L20 逐字口径）
  Y2 granularity 三层**收口**成查询面（不新造组件 — R189 第二次"查函数名"误判修正）
"""
from __future__ import annotations

import os
import sys

import pytest

ROOT = r"E:/Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.organs.direction import (DirectionAttempt, EvolutionDirection as D,
                                  ensure_direction, next_action,   # noqa: E402
                                  stagnant_of)
from dwc.foundation.granularity import (GRANULARITY_LEVELS, coarsest,  # noqa: E402
                                        granularity_of, is_coarser,
                                        level_of)
from dwc.organs.evolver import Mutator                          # noqa: E402


# ══════════════════════════════════════════════════════════
# Y3 · 停滞只对前进类（FORWARD）记
# ══════════════════════════════════════════════════════════
def test_stagnant_forward_invalid_still_true():
    """★★ 原行为不变: FORWARD + blocked/error 仍是停滞（回归保护）。"""
    assert stagnant_of(DirectionAttempt(D.FORWARD, verdict="blocked"))
    assert stagnant_of(DirectionAttempt(D.FORWARD, verdict="error"))


def test_stagnant_forward_gain_band_still_true():
    """★★ 原行为不变: FORWARD + gain≤带 仍是停滞。"""
    assert stagnant_of(DirectionAttempt(D.FORWARD, score_gain=0.0))
    assert stagnant_of(DirectionAttempt(D.FORWARD, score_gain=-0.4))


def test_stagnant_forward_no_candidate_still_true():
    """★★ 原行为不变: FORWARD + 零候选仍是停滞（unfixable_now 一等输出）。"""
    assert stagnant_of(DirectionAttempt(D.FORWARD, n_candidates=0))


def test_stagnant_lateral_is_false_even_when_invalid():
    """★★★ Y3 新口径: LATERAL 失败 = **该方向本身失败**, 不记"停滞"。

    EvoTS 2608.17933 §4.2 L20: z_k ← (op=Revision) ∧ (…)
    Alternative Strategy 是**被停滞触发**的算子, 它自己失败不是"停滞"。
    """
    assert not stagnant_of(DirectionAttempt(D.LATERAL, verdict="blocked"))
    assert not stagnant_of(DirectionAttempt(D.LATERAL, score_gain=-0.4))
    assert not stagnant_of(DirectionAttempt(D.LATERAL, n_candidates=0))


def test_stagnant_reverse_is_false_even_when_invalid():
    """★★★ Y3 新口径: REVERSE 后退同理（DWC 特有第三方向 — R188 已记差异）。"""
    assert not stagnant_of(DirectionAttempt(D.REVERSE, verdict="error"))
    assert not stagnant_of(DirectionAttempt(D.REVERSE, n_candidates=0))


def test_stagnant_first_try_none_gain_still_false():
    """★ 首试（gain None ⇒ v None ⇒ 不进 band）仍不下判 — 与旧口径一致。"""
    assert not stagnant_of(DirectionAttempt(D.FORWARD))
    assert not stagnant_of(DirectionAttempt(D.LATERAL))


def test_stagnant_direction_less_chain_behaviour_unchanged():
    """★★★ 论文"两位独立"的链级形态: LATERAL 失败**仍占** tried_all
    （04128 不回退 — once stagnant/tried, 本轮不再选它）⇒ R195 改的只是
    "停滞"这个事实陈述, **不改 fallback 序的选择行为**。
    """
    state = [DirectionAttempt(D.FORWARD, verdict="blocked"),
             DirectionAttempt(D.LATERAL, verdict="blocked")]
    # LATERAL 失败按新口径不算停滞, 但**试过了** ⇒ 下一跳只可能是 REVERSE
    dec = next_action(state, round_no=0, task_id="t")
    assert dec.direction is D.REVERSE, (
        "LATERAL 失败后链回退/循环 ⇒ R195 动了 next_action（不许）")


def test_zero_production_call_sites_for_stagnant_of():
    """★★★ 风险断言的机器化: stagnant_of 在 src/ 下**零生产调用**。

    ★ 这条测试存在的意义: 万一将来有人接了线, 它会亮 — 提醒"链行为开始
      依赖 EvoTS 专属口径了", 须重新评估（R195 结案的前提就是零调用）。
    """
    # 只扫**链路宿主**（direction.py 自身除外 — 它 docstring 里光明正大
    # 引用本函数名, 与 A1 逮我 docstring 反例文字同款; 若它自己不调自己
    # 就没有生产消费点）。真调用形态 = `stagnant_of(` 左值非 def/注释。
    import re as _re
    targets = []
    for root, _dirs, files in os.walk(os.path.join(ROOT, "src")):
        for f in files:
            if not f.endswith(".py") or f == "direction.py":
                continue
            fp = os.path.join(root, f)
            for ln, line in enumerate(open(fp, encoding="utf-8"), 1):
                if "stagnant_of(" not in line or line.strip().startswith("#"):
                    continue
                targets.append("%s:%d" % (os.path.relpath(fp, ROOT), ln))
    assert not targets, ("stagnant_of 出现生产调用 ⇒ R195 的零链变更前提失效, "
                         "必须重评: %r" % targets)


# ══════════════════════════════════════════════════════════
# Y2 · granularity 三层记账（收口, 不是新造）
# ══════════════════════════════════════════════════════════
def _real_proposal():
    """真 RULES 提案（不是手搓假件 — 与生产同构造路径）。"""
    key = sorted(Mutator.RULES)[0]
    rule = Mutator.RULES[key]
    from dwc.organs.evolver import Proposal
    return Proposal(proposal_id="p1",
                    failure_signature={"fn": rule["target"], "m": rule["component"]},
                    component=rule["component"],
                    target=rule["target"],
                    patch=rule["patch"],
                    rationale="R195 测试件")


def test_granularity_three_levels_from_real_proposal():
    """★★★ Y2: 真 Proposal ⇒ 三层齐（L1/L2/L3 都有值, 不是 None 糊弄）。"""
    g = granularity_of(_real_proposal())
    assert len(g) == 3
    l1, l2, l3 = g
    assert l1 == "undeclared", "RULES 提案不声明方向 ⇒ 如实 undeclared"
    assert ":" in l2 and l2.split(":", 1)[1] in ("assets", "architecture")
    assert "@" in l3 and l3.split("@", 1)[0]                     # target 在场


def test_granularity_l1_declared_direction():
    """★★ direction 已声明 ⇒ L1 直载（R78 字段被记账面读到）。"""
    p = _real_proposal()
    p.direction = "FORWARD"
    l1, _, _ = granularity_of(p)
    assert l1 == "FORWARD"


def test_granularity_l2_layer_follows_layer_of():
    """★★ L2 的层 = layer_of 的真值（A1 族唯一入口 — 不另判一次）。"""
    p = _real_proposal()
    from dwc.organs.evolver import layer_of
    _, l2, _ = granularity_of(p)
    assert l2 == "%s:%s" % (p.component, layer_of(p.component))


def test_granularity_l3_summary_uses_separator():
    """★★ L3 = target@patch摘要（摘要截断, 防账本膨胀）。"""
    p = _real_proposal()
    _, _, l3 = granularity_of(p)
    tgt, _, head = l3.partition("@")
    assert tgt == p.target
    assert head and len(head) <= 24


def test_granularity_l1_rejects_none_as_fourth():
    """★★★ undeclared 是**字符串** — 不是 None（R188「None 不是第四方向」同族）。"""
    _, l1 = None, granularity_of(_real_proposal())[0]
    assert l1 == "undeclared" and isinstance(l1, str)


def test_levels_stay_three_and_ordered():
    """★★ 层锁 3 + 全序 coarser 定义成立（不加第四层 — 与 direction 锁 3 同纪律）。"""
    assert GRANULARITY_LEVELS == ("L1_direction", "L2_component",
                                  "L3_intervention")
    assert level_of("L1_direction") == 0
    assert is_coarser("L1_direction", "L3_intervention")
    assert not is_coarser("L3_intervention", "L1_direction")
    assert not is_coarser("L2_component", "L2_component")       # 同级 False
    with pytest.raises(ValueError):
        level_of("L4_whatever")                                  # 未知层 ⇒ raise
    with pytest.raises(ValueError):
        coarsest(())                                             # 空 ⇒ raise 不返 None


def test_granularity_is_projection_not_second_source():
    """★★★ Y2 防漂移锁: granularity.py **不含**字面量常量表
    （0 常量 — 值全在 Proposal/evolver; 这里是唯一投影面）。"""
    src = open(os.path.join(ROOT, "src", "dwc", "foundation",
                            "granularity.py"), encoding="utf-8").read()
    assert "COMPONENT_VOCAB" not in src, (
        "granularity 里出现组件词表 ⇒ 又造一个判据来源（A1 病翻版）")
    body = [l for l in src.splitlines()
            if l.startswith(("LAYER", "K_META", "RULES"))]
    assert not body, "granularity 出现常量表 ⇒ 第二真源复辟"


def test_astar_mapping_is_documented_in_docstring():
    """★★ 论文出处必须在场（R73 — 声称有据 ⇒ 可查）。"""
    src = open(os.path.join(ROOT, "src", "dwc", "foundation",
                            "granularity.py"), encoding="utf-8").read()
    assert "2608.27287" in src and "Coarse-Grained Direction" in src
