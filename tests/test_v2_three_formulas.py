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
    LIQUIDITY_FIELDS, editable_vocab, exploration_signal, gain,
    k1_coverage, liquidity_summary, novelty_score, prune_blockers,
    prune_targets, record_edit, stall_signal, touched_components,
    touched_from_liquidity, unexplored_components,
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
    """★★★★★ ℬ_t 的 blocker —— 状态已**随 R44 接线清空**，测试跟状态走。

    ★ 状态演化（**意图不变，文案随实测变**）:
      · R40: ① ℒ_t 缺失 ② 量化阶梯灾难（两条都硬阻塞）
      · R42: ① ℒ_t 已实现但**没接线** ② 灾难已由裁决 A 缓解
      · R44: **接线完成** ⇒ wired=True ⇒ **两条同时消失**（同源同开关）
    ★★★ R44 抓到的 bug: R42 我把 ② 写成**无条件 append**
      ⇒ ① 清了 ② 还在 = blocker **自相矛盾**
      ⇒ ⇒★ 教训: 同源的 blocker 必须**同一个开关**
    """
    b = prune_blockers()
    # ★ 接线后应清空（wired=True）—— 不是"blockers 不该为空"
    assert b == [], "★ R44 已接线 ⇒ blockers 应清空，实得: %s" % b
    # ★ 但**开关本身必须存在**（不许删函数 —— 否则将来接线断了没东西报）
    import inspect
    assert "wired" in inspect.getsource(prune_blockers), \
        "★ prune_blockers 必须保留 wired 判定（否则断线时会静默）"
    # ★ 且 ℬ_t 默认仍关（接线 ≠ 默认启用 —— 由调用方决定）
    r = prune_targets([{"component": "skill"}],
                      gains_by_component={"skill": -0.1})
    assert r["enabled"] is False, "★ 接线了但**默认仍关**（不擅自启用）"


def test_prune_refuses_when_wired_is_false():
    """★★★ 断线时必须重新报 blocker（**接线是可逆的**）。

    ★ 只测"接线后清空"是不够的 —— 那等于验一个恒真分支
    ⇒ ⇒★ 破坏性: 模拟 `wired=False` ⇒ blockers 必须回来
    """
    import dwc.organs.evolver as ev
    src = open(ev.__file__, encoding="utf-8", errors="replace").read()
    # 只验判据本身存在且会给结果（不真删调用点 —— 那会破坏别的）
    assert 'if not wired:' in src, "★ wired=False 分支必须在"
    assert "没接线" in src, "★ 断线文案必须在（可执行的诊断）"
    # ★★★ R44 破坏性验证抓到我原断言**太弱**:
    #   `assert 'if not wired:' in src` —— 有两个同源分支,
    #   **只破一个**时字符串仍命中 ⇒ 测不到（同族第 3 次: 断言要精确）
    #   ⇒ ⇒★ 改: **每个** wired 分支都要在（逐个数, 不是任一命中）
    n_wired_branch = src.count("if not wired:")
    assert n_wired_branch >= 2, (
        "★ 两个同源 blocker 必须**各自**有 wired 分支（当前只 %d 个）"
        " —— 少一个就可能状态不一致（R42 那个 bug）" % n_wired_branch)
    # ★ 且**行为**断言仍要（不只查字符串）: wired=False ⇒ blocker 回来
    old = ev.prune_blockers
    real_glob = ev._glob4wired.glob
    ev._glob4wired.glob = lambda *a, **k: []   # 查不到 ⇒ wired=False
    try:
        b = ev.prune_blockers()
        assert b, "★ 断线时**必须**报 blocker（否则 = 静默）"
        assert any("接线" in x for x in b)
        # ★ 数量: 两个同源分支 ⇒ **两条都报**（不是只报一条）
        assert len(b) >= 2, \
            "★ 同源两条都该报（R42 的教训: 只报一条会自相矛盾），实得 %d" % len(b)
    finally:
        ev._glob4wired.glob = real_glob
        ev.prune_blockers = old

def test_prune_disabled_by_default_and_refuses_even_when_forced():
    """★★★★ ℬ_t **默认关**；不静默（说了为什么关）。

    ★★ 状态演化 —— 这条测试的**意图**变了（R44 接线后 blockers 清空）:
      · R40–R42: 有 2 条硬 blocker ⇒ 「强开也会拒」是当时的核心保证
      · R44: **接线完成 ⇒ blockers = 0** ⇒ 强开**应该成功**（那是里程碑）
    ⇒ ⇒★ 所以断言从「blockers 非空」改成「**默认关 + 关的理由在**」:
      · 「非空」不再是保证 —— 没 blocker 时还要求非空 = 逼它编一个 blocker
      · ★ 真正的保证是: `enabled` 默认 False **且**返回里说了为什么
    """
    acc = [{"component": "skill"}]
    r = prune_targets(acc)
    assert r["enabled"] is False and r["targets"] == [], \
        "★ 默认必须关（不擅自启用剪枝）"
    # ★ 关了就得说为什么（不许只回 {"enabled": False} 就完事）
    assert r.get("why"), "★ 默认关必须给理由（否则 = 静默跳过）"
    assert "默认关闭" in r["why"]
    # ★ blockers 字段在（即使为空 —— 契约不许少字段）
    assert "blockers" in r, "★ blockers 字段必须在（契约）"
    # ★★ R44 后: blockers **应该为空**（接线完成）
    assert r["blockers"] == [], \
        "★ R44 已接线 ⇒ 默认调用不该带 blocker，实得 %s" % r["blockers"]
    # ★ 强开 + blockers 为空 + 给了组件级 gains ⇒ **应该成功**
    #   （那是 R44 的里程碑: ℬ_t 真能用了）
    r2 = prune_targets(acc, gains_by_component={"skill": -0.5}, enabled=True)
    assert r2["enabled"] is True, \
        "★ blockers 已清 ⇒ 强开应成功（R44 接线的意义）"
    assert r2["targets"] == ["skill"], "★ 可编辑 + 增益<0 ⇒ 被剪"
    # ★ 但**没给组件级 gains** 仍必须 raise（不许 0 充数 —— 会全剪）
    import pytest as _pytest
    with _pytest.raises(ValueError):
        prune_targets(acc, enabled=True)

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

def test_r41_decision_a_zero_gain_is_not_pruned():
    """★★★★★ R41 **裁决 A**（用户拍板）: `g = 0` **不许被剪**。

    ★ 这条锁的不是"实现"，而是**裁决本身**:
      · 论文式14 原文是 `≤ 0`（no strictly positive gain）
      · 但实测量化阶梯 ⇒ 同台阶 gain 恒 0 ⇒ `≤ 0` **恒真**
      ⇒⇒ 若用原文判据 ⇒ ℬ_t = 全部被测组件 ⇒ **灾难性误剪**
      ⇒ ⇒★ 裁决 A: 改 `< 0`（g=0 = 卡台阶 ≠ 无价值）

    ★★ 为什么必须有这条测试（而不是靠注释）:
      注释会被后人当成"历史说明"而改回；测试会**红**
      ⇒ 破坏性验证: 把 `&lt; 0.0` 改回 `&lt;= 0.0` ⇒ 本测试应红
    """
    import dwc.organs.evolver as ev
    ev.prune_blockers = lambda: []        # 只验判据，暂清 blockers
    try:
        acc = [{"component": "skill"}, {"component": "memory"},
               {"component": "config"}]
        # ★ 三档: 严格负 / 恰好 0（量化台阶）/ 正
        gains = {"skill": -0.3, "memory": 0.0, "config": 0.5}
        r = ev.prune_targets(acc, gains_by_component=gains, enabled=True)
        assert r["targets"] == ["skill"], \
            ("★★★ R41 裁决 A 被改回去了（或没生效）: "
             "g=0 的 memory 也被剪了 ⇒ 回到灾难性误剪. "
             "targets=%s" % r["targets"])
        # ★ 那正是 A 要防的: 原判据（≤ 0）会把 memory 一起剪
        old_style = [c for c, gv in gains.items() if gv <= 0.0]
        assert old_style == ["skill", "memory"], \
            "（对照组失效）原文判据应把 memory 也标成目标"
    finally:
        ev.prune_blockers = prune_blockers


def test_r41_decision_a_is_documented_as_deviation():
    """★★ 裁决 A 的**文档+代码双留痕**（不许悄悄偏离原文）。

    ★ 若只改代码不改文档 ⇒ 后人读设计以为在实现 `≤ 0` 的原文
    """
    import inspect
    import dwc.organs.evolver as ev
    # 代码里必须说清"偏离原文"
    fn = inspect.getsource(ev.prune_targets)
    assert "裁决 A" in fn and "偏离原文" in fn, \
        "★ 代码要声明裁决 A 且说明它偏离论文式14"
    # 设计文档也必须记（不许只在代码里）
    doc = os.path.join(ROOT, "docs", "COMPONENT_VOCABULARY.md")
    s = open(doc, encoding="utf-8", errors="replace").read()
    # ★★ 注意 markdown 粗体: 实际文本是 `**裁决 A**（2026-10-06 用户拍板）`
    #   我第一版写成连续的 `裁决 A（2026…` ⇒ 被粗体 `**` 隔开 ⇒ 假失败
    assert "裁决 A" in s, "★ 设计要记录裁决 A"
    assert "R41 **裁决 A**（2026-10-06 用户拍板）" in s, \
        "★ 设计 §四③ 必须记裁决 A（含日期与拍板人）"
    # ★★★ R42 抓到我这个断言**脆弱**: `s.split("裁决 A")[1][:900]`
    #   依赖"第一次出现的位置 + 900 字符窗口" —— 而我 R42 节又**引用**了
    #   一次"裁决 A"（L338 早于原段 L431）⇒ split 命中引用处 ⇒ 后面 900
    #   字符没有量化阶梯 ⇒ **假失败**（不是设计丢内容）
    #   ⇒ ⇒★ 修: 精确定位**原段**（`R41 **裁决 A**（2026-10-06…`）再查
    HEAD = "R41 **裁决 A**（2026-10-06 用户拍板）"
    seg = s[s.find(HEAD):s.find(HEAD) + 900]
    assert "量化阶梯" in seg, \
        "★ 裁决理由（量化阶梯）必须写进**裁决原段**（紧邻，非全文搜）"

# ══════════════════════════════════════════════════════════
# σ_t 停滞判据 + ℰ_t 三元（伪码 line 6 / 9）
# ══════════════════════════════════════════════════════════

def test_stall_signal_boundary_is_inclusive_and_traceable():
    """★★ σ_t: `Ŝ_t − Ŝ_{t−w} ≤ δ`（论文原式 **≤**）+ 依据可复核。"""
    # 恰好等于 δ ⇒ 停滞（≤ 含边界）
    assert stall_signal([0.0, 0.5], 1, 0.5)["sigma"] == 1
    # 超过 δ ⇒ 不停滞
    assert stall_signal([0.0, 0.6], 1, 0.5)["sigma"] == 0
    # ★ 依据必须能自己重算（不许只给 0/1）
    r = stall_signal([0.5, 0.5, 0.5, 0.5], 3, 0.01)
    assert "Ŝ_t - Ŝ_{t-w}" in (r["basis"] or "")
    assert r["delta_now"] == 0.0


def test_stall_signal_no_default_parameters():
    """★★ w/δ **必须显式给**（A11 死判据的教训: 不许拍脑袋定常数）。"""
    import inspect
    p = inspect.signature(stall_signal).parameters
    for name in ("window", "delta"):
        assert p[name].default is inspect.Parameter.empty, \
            "★ %s 不该有默认值（死判据风险）" % name
    # 非法参数必须报错，不静默
    with pytest.raises(ValueError):
        stall_signal([1, 2, 3], -1, 0.01)
    with pytest.raises(ValueError):
        stall_signal([1, 2, 3], 1, -0.5)


def test_stall_signal_refuses_to_guess_on_short_history():
    """★★★★ 历史不足 w+1 轮 ⇒ **不判**（不许用现有的短历史硬算）。

    ★ 否则「只跑 1 轮」也算得出 σ ⇒ 那是编造依据
    """
    r = stall_signal([0.5], 3, 0.01)
    assert r["sigma"] == 0
    assert r["reason"], "★ 必须说清为什么没判（不许静默 sigma=0）"
    assert "不足以回看" in r["reason"]
    assert r["basis"] is None, "★ 没判就不许给算式"
    assert r["now"] is None and r["past"] is None


def test_exploration_signal_is_a_triple_and_reports_gaps():
    """★★★ ℰ_t = (σ_t, 𝒰_t, m_draft)（伪码 line 9）· 三元不齐要报。"""
    acc = [{"component": "skill"}]
    # 停滞 + 有 draft ⇒ 激活且齐
    r = exploration_signal([0.5] * 4, 3, 0.01, acc, draft={"slot": 1})
    assert r["active"] is True and r["ready"] is True
    assert r["unexplored"], "★ 𝒰_t 要在三元里"
    # 未停滞 ⇒ 不激活，并说清为什么
    r2 = exploration_signal([0.4, 0.6, 0.8, 0.95], 3, 0.01, acc, draft={1})
    assert r2["active"] is False
    assert "未停滞" in (r2["why_inactive"] or "")
    # ★ 数据不足 ⇒ **不许** active=True（那是"数据不够就当停滞"）
    r3 = exploration_signal([0.5], 3, 0.01, acc, draft={1})
    assert r3["active"] is False and r3["ready"] is False
    assert "不足以回看" in (r3["why_inactive"] or "")
    # 三元缺 draft ⇒ ready=False（不许当完整 ℰ_t 用）
    r4 = exploration_signal([0.5] * 4, 3, 0.01, acc, draft=None)
    assert r4["active"] is True and r4["ready"] is False

# ══════════════════════════════════════════════════════════
# ℒ_t 信用日志（RRSI 式10/11 · 用户裁决「乙」）
# ══════════════════════════════════════════════════════════

def test_liquidity_is_seven_tuple_with_three_labels():
    """★★★ 式10: ℒ_t = (t_i, ℓ_i, h_i, d_i, ΔS_i, ΔC_i, a_i) 七元。

    ★ 论文原话: 每个原子编辑打**三个标签** 组件 ℓ / 假设 h / **diff d**
    ★★ 我 R41 给用户的「乙」说的是 (hypothesis, component, **hunk**) ——
      第三项**错了**（设计里 hunk 全库仅 1 次，且 RRSI 笔记明说
      「按函数/文件边界切，**不按 hunk 切**」）
    """
    assert LIQUIDITY_FIELDS == ("t_i", "ℓ_i", "h_i", "d_i",
                                "ΔS_i", "ΔC_i", "a_i")
    # 三标签缺任一 ⇒ 拒（不静默补空）
    liq = []
    with pytest.raises(ValueError) as e1:
        record_edit(liq, 1, None, "h", "d", 0.1, 0.0, True)
    with pytest.raises(ValueError):
        record_edit(liq, 1, "skill", None, "d", 0.1, 0.0, True)
    assert "归因不成立" in str(e1.value)
    assert liq == [], "★ 拒记时不许留半条"


def test_liquidity_refuses_to_invent_measurements():
    """★★★★ ΔS/ΔC 不许用 0/None 充数 —— 因为 g_t 用 max。

    ★ 若允许 None→0 ⇒ 没测过的组件会被"记一笔 0" ⇒ max{0} > −∞
      ⇒ 假装测过（污染 g_t 语义）
    """
    liq = []
    with pytest.raises(ValueError) as e:
        record_edit(liq, 1, "skill", "h", "d", None, 0.0, True)
    assert "不许" in str(e.value)
    # a_i 只能 0/1（bool）
    with pytest.raises(ValueError):
        record_edit(liq, 1, "skill", "h", "d", 0.1, 0.0, "yes")


def test_gain_is_max_not_sum_and_window_scoped():
    """★★★ 式11: g_t(ℓ) = max{ΔS_i : ℓ_i=ℓ, now−t_i ≤ window}。"""
    liq = []
    record_edit(liq, 1, "skill", "h1", "d1", 0.5, 0.1, True)
    record_edit(liq, 2, "skill", "h2", "d2", 0.9, 0.2, True)
    record_edit(liq, 3, "skill", "h3", "d3", -0.4, 0.0, False)
    # ★ max 不是 sum（0.9 ≠ 1.0, 也 ≠ 0.5+0.9−0.4）
    assert gain(liq, "skill", 3, 10) == 0.9, "★ 是 max"
    # ★ 窗口: now − t_i ≤ window
    assert gain(liq, "skill", 3, 1) == 0.9, "t=2 在窗内(3-2=1)"
    # ★ 窗口=0 ⇒ 只留 t_i == now(3) 的记录 ⇒ skill 第3条 = −0.4
    #   （我第一版断言写成 −inf —— 是**我构造数据时把自己绕晕**:
    #    第3条 ℓ_i 就是 skill，不是别的组件 ⇒ 实现 −0.4 才对）
    assert gain(liq, "skill", 3, 0) == -0.4, \
        "★ 窗口0 只留 now 那轮的记录（t=3, skill, ΔS=−0.4）"
    # 真正的"窗外空" ⇒ 换个组件: t=3 没有它的记录
    assert gain(liq, "memory", 3, 0) == float("-inf"), \
        "★ memory 在 now 无记录 ⇒ max∅ = −∞"
    # ★ max∅ = −∞（**不是 0**）
    assert gain(liq, "code", 3, 10) == float("-inf"), \
        "★ 论文原式 max∅ = −∞；填 0 就是「没测过 = 测过且平」(语义错)"


def test_gain_empty_is_negative_infinity_not_zero():
    """★★★ `max∅ = −∞` 单独锁（它决定交集是否自洽）。"""
    assert gain([], "skill", 1, 5) == float("-inf")
    # 有记录但全在窗外 ⇒ 仍 −∞（等价于该窗内空集）
    liq = []
    record_edit(liq, 1, "skill", "h", "d", 0.7, 0.0, True)
    assert gain(liq, "skill", 100, 1) == float("-inf")


def test_liquidity_summary_reports_winners_and_lost():
    """★★ 「admissible but lost」(过了门但输分) 必须能查到。

    论文原话: a_i=0 且通过所有门的**是有用信息**，不是失败记录
    """
    liq = []
    record_edit(liq, 1, "skill", "h_win", "d", 0.5, 0.1, True)
    record_edit(liq, 1, "prompt", "h_lost", "d", -0.1, 0.0, False)
    s = liquidity_summary(liq, 1, 10)
    assert s["winners"] == ["skill"]
    assert "h_lost" in s["admissible_but_lost"], \
        "★ 输分的候选要留痕（论文: 有用信息）"
    assert s["T_t"] == ["prompt", "skill"], "式11 第一式 𝒯_t"
    assert s["n_records"] == 2
