# -*- coding: utf-8 -*-
"""replay（organs/replay.py）的契约 + 论文数值测试。

★★★ 为什么这份测试重要
  回放仿真器的三个承诺各有数学/原文出处, 测试锁的是**出处本身**:
  A(𝒯) 的观测树叶子语义（§2.3）· step 绝不生成+根取最早子（§2.5 逐字）·
  V 公式与 current 必含的不回退保证（§2.6/§2.7）。
★ 破坏面预设: 根特殊规则删除 → 红; current 校验删除 → 红。
"""
from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.organs.replay import (  # noqa: E402
    ReplayError, ReplaySimulator, no_worse_than_current, replay_score,
    select_policy,
)
from dwc.organs.world_model import WorldModel  # noqa: E402


def _seeded(wm=None):
    """root → a, b; a → a1（WorldTree 真对象）。"""
    wm = wm or WorldModel(depth_limit=3, max_nodes=50)
    t = wm.seed("t1", "root-action")
    t.add_child("root", node_id="a", action="act-A", provenance="observed")
    t.add_child("root", node_id="b", action="act-B", provenance="observed")
    t.add_child("a", node_id="a1", action="act-A1", provenance="observed")
    return wm, t


# ══════════════════════════════════════════════════════════
# §2.3 决策接口
# ══════════════════════════════════════════════════════════

def test_eligible_initial_is_root_only():
    """起始 𝒯^{m,0}={r} ⇒ A = {r}（§2.5 起步态）。"""
    _, t = _seeded()
    sim = ReplaySimulator(t)
    assert sim.eligible({"root"}) == {"root"}


def test_eligible_leaves_from_observed_subtree_only():
    """★★ §2.3: 叶子按**观测树**判定 — 记录了但未揭示的子不解除父的叶子身份。"""
    _, t = _seeded()
    sim = ReplaySimulator(t)
    # observed={root,a}: a 的记录子 a1 未揭示 ⇒ a 仍是观测树的叶子
    assert sim.eligible({"root", "a"}) == {"root", "a"}
    # a1 揭示后 ⇒ a 不再是叶子, a1 与 b 在列
    assert sim.eligible({"root", "a", "a1"}) == {"root", "a1"}


def test_eligible_rejects_unknown_observed():
    """观测集必须 ⊆ 𝒯（树外节点大声报错）。"""
    _, t = _seeded()
    with pytest.raises(ReplayError, match="树外"):
        ReplaySimulator(t).eligible({"root", "ghost"})


def test_validate_batch_subset_and_width():
    """批次: C ⊆ A 且 |C| ≤ W; 空批次合法（§2.4 终止条件）; W 校验。"""
    _, t = _seeded()
    sim = ReplaySimulator(t)
    sim.validate_batch([], {"root"}, W=2)                  # 空 = 合法
    sim.validate_batch(["a"], {"root", "a"}, W=2)          # ⊆A, 1≤2
    with pytest.raises(ReplayError, match="非候选"):
        sim.validate_batch(["a1"], {"root", "a"}, W=2)     # a1 未揭示不在 A
    with pytest.raises(ReplayError, match="并行度"):
        sim.validate_batch(["a"], {"root", "a"}, W=0)
    _, t2 = _seeded()
    sim2 = ReplaySimulator(t2)
    # a,b 都在 A（observed={root,a,b}, a 有未揭示子但仍算观测叶? a 的子 a1
    # 未在 obs ⇒ a 是叶; b 是叶）⇒ 2 个候选但 W=1 ⇒ 超宽
    with pytest.raises(ReplayError, match="并行度 W"):
        sim2.validate_batch(["a", "b"], {"root", "a", "b"}, W=1)


# ══════════════════════════════════════════════════════════
# §2.5 step（确定性揭示 · 绝不生成 · 根取最早）
# ══════════════════════════════════════════════════════════

def test_step_root_returns_earliest_recorded_child():
    """★ §2.5: v 是根 ⇒ 返回根**最早**子（children 插入序; R81 裁决: 未观测者优先）。"""
    _, t = _seeded()
    sim = ReplaySimulator(t)
    out = sim.step({"root"}, ["root"])
    assert out == {"root", "a"}, out          # 最早 = a（先于 b 创建）


def test_step_root_opens_next_branch_after_first_revealed():
    """★★ R81 裁决读法乙: a 已观测后再 step 根 ⇒ 揭 b（第二分支可开）。

    论文裁决链（replay.step docstring 逐条）: Child=未观测子集(定义级) +
    无后继=∅ + branch opening 需多分支 ⇒ 例外句只定顺序不放宽未观测。
    读法甲（恒返 kids[0]）⇒ 此处返回 {root,a} 无新 —— 该读法被本测试锁死否定。
    """
    _, t = _seeded()
    sim = ReplaySimulator(t)
    out = sim.step({"root", "a"}, ["root"])   # a 已观测, 根开下一未观测子
    assert out == {"root", "a", "b"}, out
    out3 = sim.step({"root", "a", "b"}, ["root"])   # 全揭 ⇒ 空（不虚构）
    assert out3 == {"root", "a", "b"}, out3


def test_step_reveals_recorded_children_only():
    """step 揭示记录且未观测的子; observed 只增不减; 绝不生成。"""
    _, t = _seeded()
    sim = ReplaySimulator(t)
    out = sim.step({"root", "a", "b"}, ["a"])
    assert out == {"root", "a", "b", "a1"}    # 揭示 a1, 不生新
    # 已揭示完的节点再 step ⇒ 集合不变（没有可揭示的 = 不生成）
    out2 = sim.step(out, ["a1"])
    assert out2 == out
    # 批次节点的集合是返回值超集（单调）
    assert out2 >= {"root"}


def test_step_root_with_no_children_returns_same():
    """根无记录子（空树）⇒ 揭示空（绝不生成虚构子节点）。"""
    wm = WorldModel(depth_limit=3, max_nodes=50)
    t = wm.seed("solo", "only-root")
    sim = ReplaySimulator(t)
    assert sim.step({"root"}, ["root"]) == {"root"}


def test_step_validates_batch():
    """step 内部走同一条批次门（非法批次不半途执行）。"""
    _, t = _seeded()
    sim = ReplaySimulator(t)
    with pytest.raises(ReplayError, match="非候选"):
        sim.step({"root"}, ["a"])


# ══════════════════════════════════════════════════════════
# §2.6 V 公式
# ══════════════════════════════════════════════════════════

def test_replay_score_matches_paper_formula():
    """★ V = max s − β₁·N + β₂·(N/max{1,k}) 手算锚定。"""
    v = replay_score(max_score=1.0, n_revealed=6, n_rounds=3,
                     beta1=0.1, beta2=0.05)
    assert v == pytest.approx(1.0 - 0.1 * 6 + 0.05 * (6 / 3), abs=1e-12)


def test_replay_score_k0_uses_max1k_and_betas_required():
    """★ k=0 ⇒ max{1,0}=1 防除零（论文符号）; β 必传（论文未报告默认值）。"""
    v = replay_score(max_score=2.0, n_revealed=4, n_rounds=0,
                     beta1=0.0, beta2=0.25)
    assert v == pytest.approx(2.0 + 0.25 * 4)
    with pytest.raises(TypeError):                       # 无默认 ⇒ 缺参即错
        replay_score(max_score=1.0, n_revealed=1, n_rounds=1, beta1=0.1)
    with pytest.raises(ReplayError, match="β₁, β₂ ≥ 0"):
        replay_score(max_score=1.0, n_revealed=1, n_rounds=1,
                     beta1=-0.1, beta2=0.1)


# ══════════════════════════════════════════════════════════
# §2.7 选择与不回退保证
# ══════════════════════════════════════════════════════════

def test_select_policy_argmax_and_current_required():
    """★ argmax + current 必含（缺 current ⇒ raise, 不许装保证）。"""
    v = {"m0": 0.5, "m1": 0.9, "m2": 0.7}     # m0 = current
    best, score = select_policy(v, current="m0")
    assert (best, score) == ("m1", 0.9)
    with pytest.raises(ReplayError, match="必含"):
        select_policy({"m1": 0.9}, current="m0")
    with pytest.raises(ReplayError, match="为空"):
        select_policy({}, current="m0")


def test_no_worse_than_current_holds_by_construction():
    """★★ 不回退谓词: 含 current 时 V(m*) ≥ V(current) 恒真（argmax 事实）。"""
    for v in ({"m0": 0.3, "m1": 0.8},
              {"m0": 0.9, "m1": 0.2},          # current 自己最优
              {"m0": 0.5}):                    # 只有 current
        assert no_worse_than_current(v, current="m0") is True
        m, _ = select_policy(v, current="m0")
        assert v[m] >= v["m0"]


def test_select_tie_break_is_deterministic():
    """平手: 键字典序最小（明规可复现, 不随机）。"""
    v = {"m2": 0.7, "m1": 0.7, "m0": 0.7}
    assert select_policy(v, current="m0")[0] == "m0"


def test_select_empty_raises():
    with pytest.raises(ReplayError):
        select_policy({}, current="x")


# ══════════════════════════════════════════════════════════
# 集成: 真 WorldTree 全流程（Dreaming 最小闭环）
# ══════════════════════════════════════════════════════════

def test_full_replay_walk_on_real_world_tree():
    """★ 真树走一遍: 初始→步1(根开最早支)→步2(a开a1)→全揭示终止判定。"""
    _, t = _seeded()
    sim = ReplaySimulator(t)
    obs = {"root"}
    assert sim.eligible(obs) == {"root"}
    obs = sim.step(obs, ["root"])                 # 开根 → a
    assert "a" in obs
    # a 是观测叶（a1 未揭示）; b 未揭示不在 obs
    assert sim.eligible(obs) == {"root", "a"}
    sim.validate_batch(["a"], obs, W=1)
    obs = sim.step(obs, ["a"])                    # 开 a → a1
    assert obs == {"root", "a", "a1"}
    # 决策: 只剩 a1 可开（b 不在 observed ⇒ 本回放世界里它不存在）
    assert sim.eligible(obs) == {"root", "a1"}
    # 终态: 对 a1 step 无新揭示（a1 无子）⇒ 回放可判停
    assert sim.step(obs, ["a1"]) == obs


# ══════════════════════════════════════════════════════════
# R80 · Dreaming 循环（DWC.dream 编排 + ℋ 快照 + config）
# ══════════════════════════════════════════════════════════

def _dwcd():
    from dwc.core import DWC
    from dwc.organs.actor import Receipt
    from dwc.organs.judge import TaskScoreStore

    def ex(task):
        return Receipt(ok=True, detail={}, verified=True)
    d = DWC(3, 50, executor=ex)
    d.judge.store = TaskScoreStore(dw_version="test")   # 隔离生产
    return d


def test_load_replay_units():
    """config 加载: 现文件 0/0 + history_max; β<0 与 history_max<1 拒。"""
    import tempfile
    from dwc.foundation import dial_config
    cfg = dial_config.load_replay()
    assert cfg["beta1"] >= 0 and cfg["beta2"] >= 0 and cfg["history_max"] >= 1
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False,
                                     encoding="utf-8") as f:
        f.write("replay: {beta1: -1, beta2: 0, history_max: 4, "
                "effort: {plateau_eps: 0.02, factor_up: 1.15, "
                "factor_down: 0.9, lo: 2, hi: 8}}\n")
    with pytest.raises(dial_config.DialError):
        dial_config.load_replay(f.name)
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False,
                                     encoding="utf-8") as f2:
        f2.write("replay: {beta1: 0, beta2: 0, history_max: 0, "
                 "effort: {plateau_eps: 0.02, factor_up: 1.15, "
                 "factor_down: 0.9, lo: 2, hi: 8}}\n")
    with pytest.raises(dial_config.DialError):
        dial_config.load_replay(f2.name)


def test_dream_beta0_degenerates_to_max_score():
    """★★ 裁决③: β=0 ⇒ V = max s_v 退化（纯 discovery quality）—— 手工有分树。"""
    d = _dwcd()
    wm = d.world_model
    wm.seed("t1", "r")
    wm.expand("t1", "root", node_id="a", action="act-A",
              provenance="observed")
    wm.record_observation("t1", "a", 3.0, True)          # s_a = 3.0
    rep = d.dream(k2_max=8)
    assert rep.betas == (0.0, 0.0)
    assert rep.m_star == "π0" and rep.monotone_no_worse
    # β=0 ⇒ V = max(s of observed) = 3.0; a 被揭示 ⇒ N=1, k=1
    by = {t: (V, k, n) for t, V, k, n in rep.per_world}
    assert by["t1"] == (3.0, 1, 1)                        # 按 tid 索引, 不赌世界序
    assert rep.v_by_version["π0"] > 0


def test_dream_k2_cap_and_termination():
    """K₂ 上限: 小 k2 ⇒ 轮数不超; 大 k2 ⇒ 全树揭示后自然停（观测面=全树）。"""
    d = _dwcd()
    wm = d.world_model
    wm.seed("t1", "r")
    # 深度 2: root→(a,b), a→a1 —— 叶无子(选它们空转即断) ⇒ 要多轮须有链
    wm.expand("t1", "root", node_id="a", action="act-A", provenance="observed")
    wm.expand("t1", "root", node_id="b", action="act-B", provenance="observed")
    wm.expand("t1", "a", node_id="a1", action="act-A1", provenance="observed")
    for nid in ("a", "b", "a1"):
        wm.record_observation("t1", nid, 1.0, True)
    # R81 裁决读法乙后: 轮1 根揭 a · 轮2 a 揭 a1 · 轮3 a1 无子可揭 ⇒
    #   π^0 选根开第二分支揭 b · 轮4 无新 ⇒ break ⇒ k=3, N=3（全树揭示）
    small = d.dream(k2_max=1)
    ks = {t: (k, n) for t, V, k, n in small.per_world}
    assert ks["t1"][0] == 1                               # k ≤ K₂ 截断生效
    big = d.dream(k2_max=50)
    kb = {t: (k, n) for t, V, k, n in big.per_world}
    assert kb["t1"] == (3, 3)                             # 读法乙: 全树揭示（b 可开）


def test_dream_without_snapshot_uses_current_tree():
    """无 ℋ 快照 ⇒ 现树兜底（裁决①）; run_term 快照后用快照。"""
    d = _dwcd()
    d.world_model.seed("t1", "r")
    assert d._replay_history == []
    rep0 = d.dream(k2_max=4)
    assert rep0.n_worlds == 2                             # dev(播种)+t1 两树兜底
    d.run_term("t", n_steps=1)
    assert len(d._replay_history) == 2                    # 每树一份快照
    rep1 = d.dream(k2_max=4)
    assert rep1.n_worlds == 2                             # 用快照


def test_snapshot_is_deep_independent():
    """★ 快照必须 deepcopy —— 后续 expand 不污染历史回放面。"""
    d = _dwcd()
    d.world_model.seed("t1", "r")
    d._snapshot_worlds()
    snap_nodes = set(d.world_model.trees["t1"].nodes)
    d.world_model.expand("t1", "root", node_id="late", action="act-L",
                         provenance="observed")
    snap_t1 = [x for x in d._replay_history if x[0] == "t1"]
    assert snap_t1, "★ 按树取快照 — [0]=dev 浅引用也过 (测试自弱教训)"
    tid, snap = snap_t1[0]
    assert set(snap.nodes) == snap_nodes and "late" not in snap.nodes

# ══════════════════════════════════════════════════════════
# R86 · M>1 策略修订（R85 稿批准实现）
# ══════════════════════════════════════════════════════════

def _mk_observed():
    """★ 有观测树的 DWC（同 R80 dream 测试构造）—— M>1 测试共用。"""
    d = _dwcd()
    wm = d.world_model
    wm.seed("t1", "r")
    wm.expand("t1", "root", node_id="a", action="act-A",
              provenance="observed")
    wm.record_observation("t1", "a", 3.0, True)
    return d

def test_policy_spec_pid_and_defaults():
    """★ PolicySpec: 默认=π0（current 键）; 非默认生成可审计 pid。"""
    from dwc.organs.replay import PolicySpec
    assert PolicySpec().pid == "π0"
    assert PolicySpec(w_delta=1.0, prefer_revealable=True).pid == "π0"
    assert PolicySpec(w_delta=0.0).pid == "π(w=0,r=1)"
    assert PolicySpec(prefer_revealable=False).pid == "π(w=1,r=0)"


def test_policy_spec_from_mapping_rejects_locked_keys():
    """★★ 锁值键不进修订域（R85 稿② — 校准纪律硬边界）; 未知键也拒。"""
    from dwc.organs.replay import PolicySpec, ReplayError
    for bad in ({"tau": 0.5}, {"b": 12}, {"beta1": 1.0}, {"delta": 0.15}):
        with pytest.raises(ReplayError, match="锁值"):
            PolicySpec.from_mapping(bad)
    with pytest.raises(ReplayError, match="未知键"):
        PolicySpec.from_mapping({"nope": 1})
    ok = PolicySpec.from_mapping({"w_delta": 0.5})
    assert ok.w_delta == 0.5 and ok.prefer_revealable is True


def test_policy_spec_validates_w_delta():
    """w_delta 负数/非数值 ⇒ raise（构造校验）。"""
    from dwc.organs.replay import PolicySpec, ReplayError
    with pytest.raises(ReplayError):
        PolicySpec(w_delta=-0.1)
    with pytest.raises(ReplayError):
        PolicySpec(w_delta="x")


def test_dream_m1_unchanged_when_no_variants():
    """★ M=1 向后兼容: 无变体 ⇒ v_by 只有 π0, policy_variants=1 个, why 标 M=1。"""
    from dwc.organs.replay import DreamReport  # noqa: F401
    d = _mk_observed()
    rep = d.dream(k2_max=4)
    assert list(rep.v_by_version) == ["π0"]
    assert len(rep.policy_variants) == 1
    assert rep.policy_variants[0].pid == "π0"
    assert "M=1" in rep.why


def test_dream_m_gt_1_evaluates_all_variants():
    """★★ M>1: 每版本评估 → v_by 全表可审计 → m* ∈ 候选 → current 必含。"""
    from dwc.organs.replay import PolicySpec
    d = _mk_observed()
    variants = [PolicySpec(w_delta=0.0), PolicySpec(prefer_revealable=False)]
    rep = d.dream(k2_max=4, policy_variants=variants)
    assert set(rep.v_by_version) == {"π0", "π(w=0,r=1)", "π(w=1,r=0)"}
    assert rep.m_star in rep.v_by_version            # argmax ∈ 候选
    assert len(rep.policy_variants) == 3             # π0 + 2 变体
    assert "M=3" in rep.why and "锁值不进" in rep.why
    # §2.7 单调性非平凡谓词: 胜者 ≥ π0
    assert rep.monotone_no_worse is True
    assert rep.v_star >= rep.v_by_version["π0"]


def test_dream_dedupes_identical_variant():
    """★ 与 π0 同参的变体去重（防双 π0 键自覆盖）。"""
    from dwc.organs.replay import PolicySpec
    d = _mk_observed()
    rep = d.dream(k2_max=4, policy_variants=[PolicySpec()])   # 等参 π0
    assert list(rep.v_by_version) == ["π0"]
    assert len(rep.policy_variants) == 1

