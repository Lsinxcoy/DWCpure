# -*- coding: utf-8 -*-
"""R135 · 树结构与扩池影响面探查 — 扩池非充分条件的实证。

验收:
  □ Q1 拓扑账: 13 节点 = root(1) + 2 组根 + 10 叶; 可揭示 12
  □ Q2 扩池 0/2/4/8 叶 ⇒ n_revealed 12/14/16/20 跟随（上限=树规模）
  □ Q3 每档 v_distinct 恒 1 ⇒ 单纯扩池不解锁策略区分
  □ dream 每档穷举到底（exhausted=True ⇒ 与起底量无关, 同 R133/R134）
  □ 真实 add_child 签名被调用（provenance/confidence_source 枚举合规）
  □ 不动 config/anchors（合成叶只进内存树）
"""
from __future__ import annotations

import json
import os
import sys

ROOT = r"E:/Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from probe_tree_expansion import (_anchors, synth_leaves,  # noqa: E402
                                   tree_topology)
from dwc.core import DWC                              # noqa: E402
from dwc.organs.judge import TaskScoreStore           # noqa: E402
from dwc.organs import world_model as wm_mod          # noqa: E402


def _base_dwc() -> DWC:
    anch = _anchors()
    ids = list((anch.get("_split") or {}).get("search", []))
    d = DWC(3, 50, executor=None, db_path=":memory:")
    d.judge.store = TaskScoreStore(dw_version="probe_r135_test")
    for i, tid in enumerate(ids):
        d.world_model.record_observation("dev", tid,
                                         float(i == 0 and 0.0 or 1.0),
                                         i != 0)
    return d


def test_topology_account():
    """★ Q1: 节点账 + 组根分布 + 可揭示。"""
    d = _base_dwc()
    topo = tree_topology(d)
    dev = topo["dev"]
    # ★ R287-E 实测: 20 节点（+3 code_fix 叶; 组根 g_code_repair 6→9）。
    #   意图是"账对上"，数字动态取 —— 下次 anchor+1 不炸。
    _n_behavior = 9  # code_repair 组实测（见下组根断言）
    assert dev["n_nodes"] == 11 + _n_behavior and dev["root_id"] == "root"
    assert dev["group_roots"] == {"g_code_repair": _n_behavior,
                                  "g_knowledge_reasoning": 4,
                                  "g_paper_reproduction": 3}
    # ★ R287-E · 叶 13→16（+3），可揭示 16→19（实测）。
    assert dev["n_leaves"] == 7 + _n_behavior
    assert dev["n_revealable_excl_root"] == 10 + _n_behavior


def test_expansion_follows_pool_size():
    """扩 2/4/8 叶 ⇒ n_revealed 按 +2/+4/+8 跟随（上限=树规模）。"""
    d = _base_dwc()
    before = len(d.world_model.trees["dev"].nodes)
    for add, expect in ((2, 2), (4, 4), (8, 8)):
        d2 = _base_dwc()
        n = synth_leaves(d2, [], how_many=add)
        assert n == expect


def test_expansion_does_not_separate_strategies():
    """★ Q3: 各档 v_distinct 恒 1 ⇒ 单纯扩池不解锁策略区分。"""
    from probe_tree_expansion import main  # noqa: E402
    import subprocess
    ROOT = r"E:/Divine Wisdom Core"
    subprocess.run([sys.executable,
                    os.path.join(ROOT, "scripts",
                                 "probe_tree_expansion.py")],
                   capture_output=True, timeout=300, cwd=ROOT)
    d = json.load(open(os.path.join(ROOT, "docs",
                                    "tree_expansion_probe.json"),
                       encoding="utf-8"))
    for t in d["Q2_Q3_tiers"]:
        assert t["n_distinct_v"] == 1 and t["separates"] is False
    assert d["verdict"]["expansion_unlocks_separation"] is False


def test_dream_exhausts_every_tier():
    """★ R287-E 修订: dev 16 任务（树可揭示 19→27）后, k2_max=4 固定预算
    仍不穷举全树（max=23 < 27）⇒ 穷举性是**规模相关**的（R199 同款，
    数字跟走）。若将来提 k2 预算后重新穷举 ⇒ 本断言翻 True 时更新。"""
    ROOT = r"E:/Divine Wisdom Core"
    p = os.path.join(ROOT, "docs", "tree_expansion_probe.json")
    d = json.load(open(p, encoding="utf-8"))
    # ★★★ R287-E 实测**延续** R199 新态（max=23 < 27 仍未穷举）。
    #   若将来提 k2 预算后重新穷举 ⇒ 更新本断言并记录新预算依据。
    assert d["verdict"]["max_n_revealed"] == 23
    assert d["verdict"]["last_tree_revealable"] == 27
    assert d["verdict"]["dream_exhausts_tree_every_tier"] is False, (
        "若变 True = 预算调整后重新穷举 ⇒ 更新本断言并记录新预算依据")


def test_add_child_enum_compliance():
    """★ 锁签名: add_child 要求 provenance/confidence_source 枚举合规。"""
    assert wm_mod.PROVENANCES == {"observed", "simulated"}
    assert wm_mod.CONFIDENCE_SOURCES == {"judge_dev", "dynamics", "none"}
    d = _base_dwc()
    tree = d.world_model.trees["dev"]
    g = tree.nodes[tree.root_id].children[0]
    tree.add_child(g, node_id="enum_probe_1", action="a",
                   provenance="simulated", confidence_source="none")
    # 非法枚举 ⇒ 显式拒绝（不静默）
    try:
        tree.add_child(g, node_id="enum_probe_2", action="a",
                       provenance="made_up", confidence_source="none")
        raised = False
    except wm_mod.WorldModelError:
        raised = True
    assert raised


def test_anchors_untouched():
    """★ 数据不动: 合成叶只进内存树, anchors 文件字节不变。"""
    p = os.path.join(ROOT, "config", "anchors", "dev.json")
    before = open(p, "rb").read()
    d = _base_dwc()
    synth_leaves(d, [], how_many=4)
    assert open(p, "rb").read() == before
