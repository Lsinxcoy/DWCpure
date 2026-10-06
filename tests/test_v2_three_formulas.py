# -*- coding: utf-8 -*-
"""★★★★★ R40 · V2 三式（ν_t / 𝒯_t·𝒰_t / ℬ_t）+ 判据 K1/K5/K6。

═══════════════════════════════════════════════════════════
 真源（都逐字核过原文，不是转述）:
   RRSI 2609.24972: 式12 词表 / 式13 探索 / 式14 剪枝 / 式15 K_str / 式16 ν_t
   伪码 line 6-14（论文原文，R40 抓到的完整算法）
   docs/COMPONENT_VOCABULARY.md §四②③④ + §五 K1/K5/K6
   docs/DEDUP_AUDIT_6SYSTEMS.md §2.3（21 对象**权威**清单）

 ★★★ R40 的两个 blocker（本文件会锁它们**不许被静默清掉**）:
   ① `ℒ_t` 信用日志不存在（chain 无 change 写入）
      ⇒ 论文式11 的 𝒯_t 无数据源（我用"已固化 component"做近似并标注）
   ② 量化阶梯 ⇒ 组件级 g_t 恒 0 ⇒ 照式14 **全体剪枝**（灾难）
      ⇒ ℬ_t 必须 `enabled=False` + 报 blockers（不许假装在跑）
═══════════════════════════════════════════════════════════
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.join("E:", os.sep, "Divine Wisdom Core")
if os.path.join(ROOT, "src") not in sys.path:
    sys.path.insert(0, os.path.join(ROOT, "src"))

import pytest  # noqa: E402

from dwc.organs.evolver import (  # noqa: E402
    COMPONENT_VOCAB, EVOLUTION_OBJECTS_21, K_META,
    NOVELTY_ELIGIBLE, OBJECT_TO_COMPONENT, STRUCTURAL,
    editable_vocab, k1_coverage, novelty_score, prune_blockers,
    prune_targets, touched_components, unexplored_components,
)


# ══════════════════════════════════════════════════════════
# ν_t（式16 · RRSI 原文 + DWC §四② 扩展）
# ══════════════════════════════════════════════════════════

def test_novelty_only_for_structural_components():
    """★★★ 式16: 只有 K_str ∪ {meta_evolution} 拿新颖度。

    论文原话: 「Prompt, control-flow, configuration, output-plumbing,
      and context-management edits **do not receive** this novelty bonus」
    """
    # 结构组件（K_str）拿分
    for c in STRUCTURAL:
        r = novelty_score([c], [])
        assert r["nu"] == 1, "★ K_str 的 %s 应拿分" % c
    # DWC 扩展: meta_evolution 拿分（§四②）
    assert novelty_score(["meta_evolution"], [])["nu"] == 1
    # 非结构组件**不拿**（原文明确列了这 5 项）
    for c in ("prompt", "control_flow", "config",
              "output_plumbing", "context_mgmt"):
        r = novelty_score([c], [])
        assert r["nu"] == 0, "★ 原文说 %s 不拿新颖度，实得 %d" % (c, r["nu"])


def test_novelty_zero_once_component_was_accepted():
    """★★ N_t(ℓ)=0 才给分（式16 的第二条件）。"""
    # 没采纳过 ⇒ 1
    assert novelty_score(["skill"], [])["nu"] == 1
    # 采纳过（哪怕 1 次）⇒ 0
    assert novelty_score(["skill"], [{"component": "skill"}])["nu"] == 0
    # N_t 快照要能回答"为什么是 0"
    r = novelty_score(["skill", "control_flow"],
                      [{"component": "control_flow"},
                       {"component": "control_flow"}])
    assert r["nu"] == 1, "★ control_flow 已采纳 2 次、skill 是新的"
    assert r["n_t"] == {"control_flow": 2, "skill": 0}


def test_novelty_counts_distinct_components_without_duplication():
    """★ 「counts **distinct** structural component types」（原文）。"""
    assert novelty_score(["skill", "memory"], [])["nu"] == 2
    assert novelty_score(["skill", "skill", "skill"], [])["nu"] == 1, \
        "★ 同组件重复触只算一次"
    assert novelty_score([], []) == {"nu": 0, "new": [], "n_t": {}}


def test_novelty_eligible_is_k_str_plus_meta_evolution():
    """★ NOVELTY_ELIGIBLE = 式15 的 4 项 ∪ meta_evolution（§四②）。"""
    assert STRUCTURAL == frozenset({"client_tool", "skill",
                                    "memory", "subagent"}), "★ 式15 原文"
    assert NOVELTY_ELIGIBLE == STRUCTURAL | {"meta_evolution"}
    # 按文档 §四②: code/architecture/evaluator/external_source 都拿不到 ν
    for c in ("code", "architecture", "evaluator", "external_source"):
        assert c not in NOVELTY_ELIGIBLE, "★ §四②: %s 不该拿新颖度" % c


# ══════════════════════════════════════════════════════════
# 𝒯_t / 𝒰_t（伪码 line 7-8 + DWC §四④）
# ══════════════════════════════════════════════════════════

def test_touched_is_approximation_and_says_so():
    """★★★ 𝒯_t 是**近似**——必须能说出与论文 ℒ_t 的差异（不许装成真源）。

    论文式11: 𝒯_t ← {ℓ : (t,ℓ,…) ∈ ℒ_t}（每次 measured edit）
    DWC: 没有 ℒ_t ⇒ 退用「已固化规则的 component」
    ⇒⇒ 语义差: 只记**成功的**（试过没采纳的算未探索）⇒ 偏乐观
    """
    acc = [{"component": "skill"}, {"component": "prompt"}, {}]
    T = touched_components(acc)
    assert T == frozenset({"skill", "prompt"})
    # ★ 近似的性质: 空记录 ⇒ 空 𝒯_t（而不是报错或猜）
    assert touched_components([]) == frozenset()
    assert touched_components(None) == frozenset()
    # ★ 函数的 docstring 必须**自己说清**这是近似（否则会被当真源用）
    doc = touched_components.__doc__ or ""
    assert "近似" in doc and "ℒ_t" in doc, \
        "★ 𝒯_t 必须在 docstring 里声明它是近似 + 差异"


def test_unexplored_includes_meta_editable_k6():
    """★★ K6: 𝒰_t 必须含 𝒦_meta_editable（否则架构层永不被探索）。

    文档 §四④ 原话: 「应改为 𝒰_t = (𝒦 ∪ 𝒦_meta_editable) ∖ 𝒯_t
      —— 否则『从未被测量过的组件』永远只在 𝒦 里找，架构层永不被探索」
    """
    U = unexplored_components([])
    # 未探索（空历史）时: 两表可编辑项**全部**在里面
    assert U == editable_vocab()
    for c in ("code", "architecture", "meta_evolution"):
        assert c in U, "★ K6: %s 不在 𝒰_t ⇒ 架构层永不被探索" % c
    # touched 过的要被减掉
    U2 = unexplored_components([{"component": "skill"}])
    assert "skill" not in U2 and "code" in U2


def test_editable_vocab_excludes_readonly_meta():
    """★★ K5 的交集项: evaluator/external_source **必须**不在可编辑集。

    文档 §四③ 实测修正的原话: 用并集会把 evaluator/external_source
    也算进剪枝目标（g_t 默认 -∞ ⇒ 恒满足 ≤0）⇒ 而它们不可编辑
    ⇒「删除它」这个动作根本无法执行
    """
    V = editable_vocab()
    assert "evaluator" not in V and "external_source" not in V
    assert set(COMPONENT_VOCAB) <= V, "★ 𝒦 全部可编辑"
    assert {"code", "architecture", "meta_evolution"} <= V
    # K4: K_META 必须每项显式标 editable（已有测试，这里锁与 vocab 的一致性)
    assert V == set(COMPONENT_VOCAB) | {k for k, ok in K_META.items() if ok}


# ══════════════════════════════════════════════════════════
# ℬ_t（式14 + K5 交集）—— ★ 两个 blocker 必须被锁住
# ══════════════════════════════════════════════════════════

def test_prune_blockers_report_liquidity_and_quantisation():
    """★★★★★ ℬ_t 的两个 blocker 必须**如实报出**（不许静默）。

    ① ℒ_t 缺失（chain 无 change 写入）
    ② 量化阶梯 ⇒ 组件级 gain 恒 0 ⇒ 照式14 全体剪枝
    """
    b = prune_blockers()
    assert b, "★ blockers 不该为空（R40 实测两个硬阻塞还在）"
    joined = " ".join(b)
    assert "ℒ_t" in joined and "信用日志" in joined, "① 要报 ℒ_t 缺失"
    assert "量化阶梯" in joined, "② 要报量化阶梯（那会让 g_t 恒 0）"
    assert "全体剪枝" in joined, "② 要说清后果（灾难）"


def test_prune_disabled_by_default_and_refuses_even_when_forced():
    """★★★★ ℬ_t 默认关；强开也会因 blockers 拒（不许假装在跑）。"""
    acc = [{"component": "skill"}]
    r = prune_targets(acc)
    assert r["enabled"] is False and r["targets"] == []
    assert r["blockers"], "★ 默认调用必须带出 blockers（否则 = 静默跳过）"
    # 强行 enabled=True ⇒ blockers 未清仍拒
    r2 = prune_targets(acc, enabled=True)
    assert r2["enabled"] is False
    assert "不许启用" in r2["why"]
    # ★ 即便 blockers 清了、但没给组件级 gains ⇒ 必须 raise
    #   （不许用 0 充数 —— 量化阶梯下 0 就是「恒 ≤0」⇒ 全剪）
    import dwc.organs.evolver as ev
    old = ev.prune_blockers
    ev.prune_blockers = lambda: []
    try:
        with pytest.raises(ValueError) as ex:
            prune_targets(acc, enabled=True)
        assert "不许用默认 0" in str(ex.value)
    finally:
        ev.prune_blockers = old


def test_prune_uses_intersection_not_union_k5():
    """★★★ K5: ℬ_t 必须用**交集** 𝒯_t ∩ 𝒦_editable（不是并集）。

    文档 §七 的实测: 用并集会把 evaluator/external_source 也算进去
    （g_t 默认 -∞ ⇒ 恒 ≤0 ⇒ 每次都被标成删除目标）而它们不可编辑
    """
    import dwc.organs.evolver as ev
    ev.prune_blockers = lambda: []        # 暂清 blockers 只验交集逻辑
    try:
        acc = [{"component": "skill"}, {"component": "evaluator"},
               {"component": "external_source"}]
        gains = {"skill": -0.5, "evaluator": -9.0,
                 "external_source": -9.0}
        r = prune_targets(acc, gains_by_component=gains, enabled=True)
        assert "evaluator" not in r["targets"], \
            "★ K5: 不可编辑项被标成删除目标（用了并集？）"
        assert "external_source" not in r["targets"]
        assert "skill" in r["targets"], "★ 可编辑且增益≤0 应被剪"
        assert set(r["pool"]) == {"skill"}, \
            "★ pool = 𝒯_t ∩ 𝒦_editable（交集），实得 %s" % r["pool"]
    finally:
        ev.prune_blockers = prune_blockers


# ══════════════════════════════════════════════════════════
# K1（21 对象 → 两表映射）
# ══════════════════════════════════════════════════════════

def test_k1_all_21_objects_mapped_to_valid_component():
    """★★★ K1: 21 个对象**逐个**映射到 𝒦 ∪ 𝒦_meta（无遗漏、无失效映射）。

    ★ 权威清单 = DEDUP_AUDIT §2.3（v4 严格去重 6 套体系 39 仓库）
    ⇒⇒ 我核了三处文档，COMPONENT_VOCABULARY §七 引的是**被证伪的旧表**
    """
    r = k1_coverage()
    assert r["total"] == 21, "★ 清单应 21 项（v4 严去重），实得 %d" % r["total"]
    assert not r["missing"], "★ K1 未覆盖: %s" % r["missing"]
    assert not r["bad_target"], "★ K1 映射失效: %s" % r["bad_target"]
    # 两表的每一项都要被至少一个对象覆盖（否则那个组件无对象来源）
    used = {v.rstrip("†").strip() for v in OBJECT_TO_COMPONENT.values()}
    both = set(COMPONENT_VOCAB) | set(K_META)
    assert used == both, ("★ 组件覆盖不对称: 未被映射=%s · 映射到表外=%s"
                          % (sorted(both - used), sorted(used - both)))


def test_k1_disputed_mappings_are_visible():
    """★★ 争议项必须**显式可见**（不擅自裁决 —— 文档诚实边界⑩ 的做法）。

    ★ 没有这条测试的话，把 † 全去掉也能过 K1 ⇒ 争议就**不可见**了
    """
    r = k1_coverage()
    assert r["disputed"], "★ 争议项不该为空（我标了 7 项）"
    assert r["n_disputed"] == len(r["disputed"])
    # 每个 † 的对象都要能在表里查到（只是归属存疑，不是无效）
    for d in r["disputed"]:
        obj, comp = d.split(" → ")
        assert comp in (set(COMPONENT_VOCAB) | set(K_META)), \
            "★ 争议项的目标也必须在两表: %s" % d

def test_prune_default_parameter_is_false():
    """★★★★ R40 破坏性验证抓到的**盲区**: 默认参数必须直接锁。

    ★★ 我原来只断言 `返回值["enabled"] is False` ——
      而破坏方式是改**签名默认值** `enabled: bool = False → True` ⇒
      函数走到 `if blockers: return {"enabled": False}` ⇒ 返回值**恰好不变**
      ⇒⇒ ⇒★ 也就是说: 返回值断言**测不到默认参数被改**（4/5 漏的那 1 条）
      ⇒ ⇒★ 修: 用 `inspect.signature` 直接锁默认值本身
    """
    import inspect
    from dwc.organs.evolver import prune_targets
    p = inspect.signature(prune_targets).parameters["enabled"]
    assert p.default is False, \
        ("★★ ℬ_t 的 enabled 默认值被改成了 %r —— "
         "那等于 ℬ_t **默认启用**，而 blockers 未清时会误剪" % (p.default,))


def test_novelty_default_refuses_to_invent_n_t():
    """★★ ν_t 必须按**采纳记录**算 N_t，不许按"当前是否存在"。"""
    from dwc.organs.evolver import novelty_score
    # 没采纳记录 ⇒ 即使 RULES 里存在也不算（函数只看入参）
    assert novelty_score(["skill"], [])["nu"] == 1
    # 采纳记录里有 ⇒ 0（哪怕只 1 条）
    assert novelty_score(["skill"], [{"component": "skill"}])["nu"] == 0
    # ★ 记录里 component 为空/缺失 ⇒ **不许**被当成"已采纳"
    r = novelty_score(["skill"], [{"component": ""}, {}, {"component": None}])
    assert r["nu"] == 1, "★ 空 component 的记录不该算作已采纳"
