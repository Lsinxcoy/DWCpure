# -*- coding: utf-8 -*-
"""world_model（organs/world_model.py）的契约 + 行为测试。

★★★ 为什么这份测试重要
  world_model 是第七器官、环节⑥ 的承载者 —— 在它之前，DWC 的任务源
  写死在 e2e 测试床里，agent 不会「自己找事做」。
  ⇒⇒ 所以这里测的不只是一个类，是「探索这条腿是否真的接上了」。

★ 判据族（docs/WORLD_TREE.md §4.6 + WORLD_TREE_CONVERGENCE §四）:
  W1 只有一套树结构 · W2 节点必带 provenance · W3 judge 不判想象节点
  W4 收束判据不来自世界模型自算 · W5 provenance 单向 · W6 深度外部化
  Z6 卡住检测 · §4.7 环节⑥ 任务源接口
"""
from __future__ import annotations

import glob
import inspect
import os
import re
import sys

import pytest

ROOT = r"E:/Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.foundation.dial_config import DialError  # noqa: E402
from dwc.organs.world_model import (  # noqa: E402
    Candidate, WorldModel, WorldTree, WorldNode, WorldModelError,
    information_gain,
)


def _wm() -> WorldModel:
    return WorldModel(depth_limit=3, max_nodes=50)


# ══════════════════════════════════════════════════════════
# W1–W6 · 机械判据
# ══════════════════════════════════════════════════════════

def test_w1_single_tree_class_in_src():
    """★ W1: 全仓 `class .*Tree` 只许一个（ARSI 三套树 29/24/3 是反面）。"""
    hits = []
    for fp in glob.glob(os.path.join(ROOT, "src", "**", "*.py"), recursive=True):
        s = open(fp, encoding="utf-8", errors="replace").read()
        for m in re.finditer(r"(?m)^class\s+\w*Tree\b", s):
            hits.append((os.path.relpath(fp, ROOT).replace("\\", "/"), m.group(0)))
    assert len(hits) == 1, "★ W1 违规: 命中 %s" % hits
    assert "WorldTree" in hits[0][1], hits


def test_w2_node_requires_provenance_no_default():
    """★ W2: provenance 必填无默认（缺它 ⇒ TypeError，不许隐式默认）。"""
    with pytest.raises(TypeError):
        WorldNode(id="n1", parent_id=None, action="a",
                  confidence_source="none", depth=0)


def test_w2_add_child_rejects_bad_provenance():
    """★ W2 阳性: 非法 provenance 进不了树。"""
    t = WorldTree("t", "root-act", depth_limit=3, max_nodes=10)
    with pytest.raises(WorldModelError, match="W2"):
        t.add_child("root", node_id="x", action="a", provenance="imagined")


def test_w3_judge_gets_only_observed():
    """★ W3: judgeable() 不含 simulated（想象节点不许进 judge）。"""
    wm = _wm()
    t = wm.seed("t1", "base")
    t.add_child("root", node_id="sim1", action="expand", provenance="simulated")
    t.add_child("root", node_id="obs1", action="trace", provenance="observed")
    ids = [n.id for n in t.judgeable()]
    assert "sim1" not in ids and "obs1" in ids and "root" in ids, ids


def test_w4_select_source_never_reads_confidence():
    """★ W4 机械: select / information_gain 的源码不碰任何 confidence 属性。"""
    src = (inspect.getsource(WorldModel.select)
           + inspect.getsource(information_gain))
    bad = re.findall(r"\.confidence\b|confidence_source|CONFIDENCE_SOURCES", src)
    assert not bad, "★ W4 违规: 收束路径读了 confidence: %s" % bad


def test_w4_select_prefers_information_gain_over_high_score():
    """★★ W4 行为: 收束**不选最高分** —— score=1.0 的老节点输给信息增益大的新叶。

    构造: m3 谱系 (4,4) 全过 ⇒ H(5/7)≈0.863 · u1 谱系 (1,1) ⇒ H(2/3)≈0.918
    ⇒ 若按「最高分」选会选 m3（1.0 vs None）⇒ 按信息增益应选 u1。
    """
    wm = _wm()
    t = wm.seed("t1", "base")
    t.observe("root", 1.0, True)                     # 谱系 (1,1)
    parent = "root"
    for i in (1, 2, 3):                              # 深度 3 的全过谱系
        prev = "m%d" % i
        t.add_child(parent, node_id=prev, action="keep", provenance="observed")
        t.observe(prev, 1.0, True)                   # 真值 1.0
        parent = prev
    t.add_child("root", node_id="u1", action="try-new", provenance="simulated")
    m3 = t.nodes["m3"]
    u1 = t.nodes["u1"]
    assert t.lineage_obs("m3") == (4, 4) and t.lineage_obs("u1") == (1, 1)
    out = wm.select([Candidate("t1", m3), Candidate("t1", u1)])
    assert [c.node.id for c in out] == ["u1", "m3"], \
        "★ 收束应按信息增益(u1 在前)，实为 %s —— 最高分在驱动排序?" \
        % [c.node.id for c in out]
    assert out[1].node.score == 1.0, "评估段: observed 真值应保留（只是不排序）"


def test_w5_provenance_one_way_and_score_not_overwritable():
    """★ W5: simulated→observed 只许一次；再 observe ⇒ 报错（不可逆不可覆盖）。"""
    wm = _wm()
    t = wm.seed("t1", "base")
    t.add_child("root", node_id="sim1", action="a", provenance="simulated")
    t.observe("sim1", 0.5, False)
    assert t.nodes["sim1"].provenance == "observed"
    with pytest.raises(WorldModelError, match="W5"):
        t.observe("sim1", 1.0, True)


def test_w6_depth_limit_is_externalized():
    """★ W6: 深度必填无默认（省略 ⇒ TypeError），不许硬编码档位。"""
    with pytest.raises(TypeError):
        WorldTree("t", "root-act")
    with pytest.raises(TypeError):
        WorldModel()
    t = WorldTree("t", "root-act", depth_limit=1, max_nodes=10)
    t.add_child("root", node_id="d1", action="a", provenance="simulated")
    with pytest.raises(WorldModelError, match="W6"):
        t.add_child("d1", node_id="d2", action="a", provenance="simulated")


# ══════════════════════════════════════════════════════════
# 行为 · 任务源 / 展开 / 回填
# ══════════════════════════════════════════════════════════

def test_legal_actions_are_unrevealed_leaves():
    """§4.7 职责一: legal_actions = 未揭示的叶子（root 初始在列）。"""
    wm = _wm()
    t = wm.seed("t1", "base")
    assert [a["node"] for a in wm.legal_actions()] == ["root"]
    t.add_child("root", node_id="c1", action="next", provenance="simulated")
    assert [a["node"] for a in wm.legal_actions()] == ["c1"], \
        "root 已展开成父节点 ⇒ 不再是叶子 ⇒ 出列；c1（未揭示叶子）进列"
    t.observe("root", 1.0, True)      # root 揭示（且早已非叶子）⇒ 仍只 c1
    assert [a["node"] for a in wm.legal_actions()] == ["c1"]
    t.observe("c1", 1.0, True)        # c1 揭示 ⇒ 树无候选
    assert wm.legal_actions() == []


def test_legal_actions_shape_for_task_source():
    """环节⑥ 任务源形态（run_term 消费的字段）。"""
    wm = _wm()
    wm.seed("t1", "基线任务")
    a = wm.legal_actions()[0]
    assert a["tree"] == "t1" and a["node"] == "root"
    assert a["action"] == "基线任务" and a["depth"] == 0
    assert "branch" in a


def test_simulated_node_gets_observed_anchor_branch():
    """WORLD_TREE §4.1: simulated 节点必带 branch（自动锚到最近 observed 祖先）。"""
    wm = _wm()
    t = wm.seed("t1", "base")
    t.add_child("root", node_id="s1", action="a", provenance="simulated")
    t.add_child("s1", node_id="s2", action="b", provenance="simulated")
    assert t.nodes["s1"].branch == "root"
    assert t.nodes["s2"].branch == "root", "锚点是最近 observed 祖先（root）"
    t.add_child("root", node_id="o1", action="c", provenance="observed")
    t.add_child("o1", node_id="s3", action="d", provenance="simulated")
    assert t.nodes["s3"].branch == "o1"


def test_lineage_obs_sums_path():
    """信息增益的输入口径: 沿 root→node 路径求和。"""
    wm = _wm()
    t = wm.seed("t1", "base")
    t.observe("root", 1.0, True)
    t.add_child("root", node_id="a1", action="x", provenance="observed")
    t.observe("a1", 0.0, False)
    t.add_child("a1", node_id="a2", action="y", provenance="simulated")
    assert t.lineage_obs("root") == (1, 1)
    assert t.lineage_obs("a1") == (2, 1)
    assert t.lineage_obs("a2") == (2, 1), "未观测叶子只继承谱系"
    with pytest.raises(WorldModelError, match="不存在"):
        t.lineage_obs("ghost")


def test_select_includes_current_node():
    """★ 不回退保证（§4.7）: current 必在返回集 ⇒ V^{m⋆} ≥ V^0。"""
    wm = _wm()
    t = wm.seed("t1", "base")
    t.add_child("root", node_id="c1", action="a", provenance="simulated")
    c1 = Candidate("t1", t.nodes["c1"])
    elsewhere = Candidate("t1", t.nodes["root"])   # root 不在候选（已被 c1 挤出? 未揭示故在）
    # 构造 current 不在 candidates 的情形
    t.observe("root", 1.0, True)
    assert [n.id for n in t.legal_actions()] == ["c1"]
    out = wm.select([c1], current=elsewhere)
    assert (elsewhere in out) and (c1 in out), "current 必被保留"
    # current 已在候选时不重复
    out2 = wm.select([c1, elsewhere], current=c1)
    assert len(out2) == 2


def test_select_unknown_tree_rejected():
    """阳性: 候选引用不存在的树 ⇒ 大声报错（不静默丢弃）。"""
    wm = _wm()
    t = wm.seed("t1", "base")
    with pytest.raises(WorldModelError, match="不存在的树"):
        wm.select([Candidate("ghost", t.nodes["root"])])


# ══════════════════════════════════════════════════════════
# config · Z1/Z6
# ══════════════════════════════════════════════════════════

def test_world_model_loads_real_config():
    """Z1: 真实 config/world_tree.yaml 可加载（strategy 必填已由 dial 校验）。"""
    wm = _wm()
    assert wm.strategy == "ig_tree"
    assert int(wm.stuck_cfg["n_stuck"]) >= 1


def test_world_model_rejects_config_missing_strategy(tmp_path):
    """★ Z1 阳性: 缺 strategy 的 config ⇒ DialError（不许隐式默认）。"""
    p = tmp_path / "wt.yaml"
    p.write_text("world_tree:\n  pareto_dim: task\n", encoding="utf-8")
    with pytest.raises(DialError):
        WorldModel(depth_limit=2, max_nodes=10, config_path=str(p))


def test_z6_stuck_detection_fires_once_then_resets():
    """★ Z6: 连续 n_stuck 轮无改进 ⇒ 返回 on_stuck；触发即复位、改进即清零。"""
    wm = _wm()
    n = int(wm.stuck_cfg["n_stuck"])            # 真 config: 3
    assert wm.record_round(improved=True) is None
    assert wm.record_round(improved=False) is None          # 第 1 轮
    assert wm.record_round(improved=False) is None          # 第 2 轮
    assert wm.record_round(improved=True) is None           # 改进 ⇒ 清零
    for _ in range(n - 1):
        assert wm.record_round(improved=False) is None
    assert wm.record_round(improved=False) == wm.stuck_cfg["on_stuck"], \
        "连续 %d 轮无改进应触发处置" % n
    assert wm.stuck_events and wm.stuck_events[-1]["action"] == wm.stuck_cfg["on_stuck"]
    assert wm.record_round(improved=False) is None, "触发后复位，不许连发"


# ══════════════════════════════════════════════════════════
# 阳性 · 池上限 / 播种 / 判分回填
# ══════════════════════════════════════════════════════════

def test_pool_overflow_rejected_explicitly():
    """★ 池子上限 + 超限显式拒绝（母巢 L3: 1,447 生 / 5 死 的最小防线）。"""
    t = WorldTree("t", "root-act", depth_limit=3, max_nodes=3)
    t.add_child("root", node_id="a", action="x", provenance="simulated")
    t.add_child("root", node_id="b", action="y", provenance="simulated")
    with pytest.raises(WorldModelError, match="池子超限"):
        t.add_child("root", node_id="c", action="z", provenance="simulated")


def test_seed_and_tree_lookup_errors():
    """阳性: 重复播种 / 查不存在的树 ⇒ 报错。"""
    wm = _wm()
    wm.seed("t1", "base")
    with pytest.raises(WorldModelError, match="已存在"):
        wm.seed("t1", "again")
    with pytest.raises(WorldModelError, match="不存在"):
        wm.tree("ghost")


def test_observe_validates_score_source():
    """★ 真值必须是 judge 给的数值（None/字符串进不来 —— G2 同族）。"""
    wm = _wm()
    t = wm.seed("t1", "base")
    with pytest.raises(WorldModelError, match="score"):
        t.observe("root", None, True)
    with pytest.raises(WorldModelError, match="score"):
        t.observe("root", "high", True)
    with pytest.raises(WorldModelError, match="不存在"):
        t.observe("ghost", 1.0, True)


def test_record_observation_routes_through_model():
    """模型层回填通路（环节⑥ 消费方用的入口）。"""
    wm = _wm()
    wm.seed("t1", "base")
    wm.record_observation("t1", "root", 0.5, False)
    node = wm.tree("t1").nodes["root"]
    assert node.provenance == "observed" and node.score == 0.5
    assert (node.n_obs, node.n_pass) == (1, 0)
    with pytest.raises(WorldModelError):
        wm.record_observation("ghost", "root", 1.0, True)


# ══════════════════════════════════════════════════════════
# 环节⑥ 接线 · run_term 的下一轮任务源
# ══════════════════════════════════════════════════════════

def test_run_term_task_source_includes_world_tree_leaves():
    """★★ 环节⑥ 接线: 注入 world_model ⇒ next_task_source 含世界树任务。"""
    from dwc.harness.run_term import TermRunner
    wm = _wm()
    wm.seed("wt", "基线任务")
    tr = TermRunner(world_model=wm)
    rep = tr.run_term("t", n_steps=1)
    tasks = rep.next_task_source["tasks"]
    wt_tasks = [x for x in tasks if x["kind"] == "world_tree_action"]
    assert wt_tasks, "★ 注入了 world_model ⇒ 任务源必须含世界树叶子, 实为 %s" % tasks
    assert wt_tasks[0]["action"] == "基线任务"
    assert rep.next_task_source["n_tasks"] == len(tasks)


def test_run_term_without_world_model_keeps_old_behavior():
    """不注入 ⇒ 行为与 R59 之前一致（可选注入，与 judge 同款纪律）。"""
    from dwc.harness.run_term import TermRunner
    tr = TermRunner()
    rep = tr.run_term("t", n_steps=1)
    kinds = [x["kind"] for x in rep.next_task_source["tasks"]]
    assert "world_tree_action" not in kinds
    assert isinstance(kinds, list)
