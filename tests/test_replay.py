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

ROOT = r"E:/Divine Wisdom Core"
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
    """★ §2.5 逐字: v 是根 ⇒ 返回根**最早**的已记录子节点（children 插入序）。"""
    _, t = _seeded()
    sim = ReplaySimulator(t)
    out = sim.step({"root"}, ["root"])
    assert out == {"root", "a"}, out          # 最早 = a（先于 b 创建）


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
