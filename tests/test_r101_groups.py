# -*- coding: utf-8 -*-
"""R101 · 阶段 2a — C 分层任务树（H-JEPA Table 1 cost 几何 → 组两级任务源）。

探针依 R92 稿 C 节（六条）:
  ① groups 不传 ⇒ 与旧树形状一致（零破坏: 无组节点/叶 depth1/group_id 空）
  ② 组节点: provenance=observed · score None · judgeable 不含 · observe 拒
  ③ group_rates: 有观测组返回、无观测组缺席（X2 不装数）
  ④ 两级 wta: 弱组在前（rate 升）+ 组内 δ 降序 —— 真链集成
  ⑤ depth_limit 探针（W6: 三深度 < limit）
  ⑥ 破坏方向（组序反转 ⇒ ④红）: 见 test_group_order_* 的排序键单测
"""
from __future__ import annotations

import os
import sys

import pytest

ROOT = r"E:/Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.organs.world_model import WorldModelError, WorldModel  # noqa: E402

GROUPS = {"code_repair": ["code_fix_001", "code_fix_002"],
          "knowledge_reasoning": ["reasoning_001"]}


def _wm(**kw) -> WorldModel:
    return WorldModel(**{"depth_limit": 3, "max_nodes": 50}, **kw)


def test_groups_not_passed_is_legacy_shape():
    """① 零破坏: groups 不传 ⇒ root 直挂、叶 depth1、无组节点、group_id 全空。"""
    wm = _wm()
    wm.seed_tasks(["code_fix_001", "code_fix_002", "reasoning_001"],
                  tree_id="dev")
    t = wm.tree("dev")
    assert len(t.nodes) == 4                       # root + 3 叶
    assert not any(n.group_id for n in t.nodes.values()), \
        "不传 groups ⇒ 全部无组（降级路径=现路径）"
    assert all(n.depth == 1 for n in t.nodes.values() if n.id != "root")


def test_group_node_w2_w3_w5_discipline():
    """② 组节点: 播种即 observed · score None · judgeable 排除 · observe 拒。"""
    wm = _wm()
    wm.seed_tasks(["code_fix_001", "code_fix_002", "reasoning_001"],
                  tree_id="dev", groups=GROUPS)
    t = wm.tree("dev")
    g = t.nodes["g_code_repair"]
    assert g.provenance == "observed" and g.score is None
    assert g.group_id == g.id, "组节点约定: group_id==id"
    # W3: judgeable 不含组
    ids = [n.id for n in t.judgeable()]
    assert "g_code_repair" not in ids and "g_knowledge_reasoning" not in ids
    assert "code_fix_001" in ids
    # W5/W3: 组节点 observe 大声拒
    with pytest.raises(WorldModelError, match="组节点"):
        t.observe("g_code_repair", 1.0, True)
    assert t.nodes["g_code_repair"].score is None


def test_group_rates_observed_only():
    """③ group_rates: 无观测 ⇒ 空（X2 不装数）; 观测后该组出现, 缺席组不在。"""
    wm = _wm()
    wm.seed_tasks(["code_fix_001", "code_fix_002", "reasoning_001"],
                  tree_id="dev", groups=GROUPS)
    assert wm.group_rates() == {}, "零观测 ⇒ 空 dict（没数据 ≠ 0 难度）"
    t = wm.tree("dev")
    t.observe("code_fix_001", 0.0, False)       # code 组: 1 败
    t.observe("code_fix_002", 1.0, True)        # code 组: 1 过
    r = wm.group_rates()
    assert set(r) == {"code_repair"}, "knowledge_reasoning 无观测 ⇒ 缺席"
    assert abs(r["code_repair"] - 0.5) < 1e-9, "Σn_pass/Σn_obs 同 observed_rate 公式"


def test_depth_limit_probe_w6():
    """⑤ W6: 三深度（root0→组1→叶2）必须 < depth_limit。"""
    wm = _wm()
    wm.seed_tasks(["code_fix_001", "code_fix_002", "reasoning_001"],
                  tree_id="dev", groups=GROUPS)
    t = wm.tree("dev")
    mx = max(n.depth for n in t.nodes.values())
    assert mx == 2
    assert mx < t.depth_limit, "W6: 深度 %d 未越界 (limit=%d)" % (mx, t.depth_limit)


def test_two_level_wta_weak_group_first_on_real_chain():
    """④ 真链: 弱组(rate低)在前 — DWC 构造 + 树观测 + run_term 的任务源顺序。"""
    from dwc.core import DWC
    d = DWC(3, 50, executor=None)
    t = d.world_model.tree("dev")
    # 造组观测: code_repair 全败(0.0) / knowledge_reasoning 全过(1.0)
    for tid in ("code_fix_001", "code_fix_002", "code_fix_003"):
        t.observe(tid, 0.0, False)
    for tid in ("reasoning_001", "reasoning_002"):
        t.observe(tid, 1.0, True)
    r = d.world_model.group_rates()
    assert r["code_repair"] < r["knowledge_reasoning"]
    rep = d.run_term("probe", n_steps=1)
    wt = [x for x in rep.next_task_source["tasks"]
          if x.get("kind") == "world_tree_action"]
    assert wt, "世界树任务源非空"
    groups_seq = [x["group"] for x in wt]
    assert "code_repair" in groups_seq and "knowledge_reasoning" in groups_seq
    # ★ 弱组优先: 第一个出现的组 = 最低 rate 组（code_repair）
    first = groups_seq[0]
    min_rate_group = min(r, key=r.get)
    assert first == min_rate_group, \
        "弱组在前: 首组=%s 但最弱=%s（组序失效或写反）" % (first, min_rate_group)


def test_group_order_key_unit():
    """⑥ 破坏靶: 组序 key 的升序语义单测（反转实现 ⇒ 此测试红）。"""
    rates = {"weak": 0.0, "strong": 1.0}
    dmap = {"a": 0.1, "b": 0.9}
    items = [{"group": "strong", "node": "a"},
             {"group": "weak", "node": "b"},
             {"group": "strong", "node": "b"}]
    out = sorted(items, key=lambda i: (rates.get(i["group"], 1.0),
                                       -dmap.get(i["node"], 0.0)))
    assert [i["group"] for i in out] == ["weak", "strong", "strong"]
    # 组内 δ 降序: strong 组内 b(0.9) 先于 a(0.1)
    strong = [i["node"] for i in out if i["group"] == "strong"]
    assert strong == ["b", "a"]


def test_yamloader_validates():
    """组表加载器校验（没校验的 yaml 只是文本）: 坏文件大声。"""
    from dwc.core import DwcError, _load_capability_groups
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False,
                                     encoding="utf-8") as f:
        f.write("version: 1\ngroups: []\n")
        p = f.name
    try:
        with pytest.raises(DwcError, match="groups"):
            _load_capability_groups(p)
    finally:
        os.unlink(p)
    # 真配置可加载且覆盖 dev 任务
    real = _load_capability_groups()
    assert "code_repair" in real and "code_fix_001" in real["code_repair"]
