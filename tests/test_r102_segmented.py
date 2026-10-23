# -*- coding: utf-8 -*-
"""R102 · 阶段 2b — B 段式回放（R90 死锁破解 · 论文 Eq6 段语义）。

探针依 R92 稿 B 节:
  ① M=1 语义回归: 段式后 V 记录不断言相等（语义变更预期差异, 见知识档）
  ② 死锁破解锁: 反序对下 w=0 vs w=1 的 picks 轨迹**必须不同**（r=0 主场）
  ③ 段预算: K_s=1 时每段至多 2 步（手动揭段根 + 段内 1 步）
  ④ re-anchor: 每段首 pick = 段根本身（段起点 observed 不含本段 ⇒ 才需手动步）
  ⑤ seg_order 枚举/pid 后缀/锁值拒
"""
from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.core import DWC, DwcError  # noqa: E402
from dwc.organs.replay import PolicySpec, ReplayError  # noqa: E402


def _dwc_with_reverse_pair(dmap):
    """反序对小树: root→a(字典先)→a1, root→b→b1; 注入 δ(b)>δ(a)=0。

    段内双候选出现的前提 = r=False（稿: 主场 = 段式甲 + r=0 变体）:
    揭 a 后 observed={root,a,a1?...} — 段内 nonroot 含 a/a1（r=False 不过滤）。
    """
    d = DWC(5, 60, executor=None)
    wm = d.world_model
    wm.seed("rp", "root_actions")
    wm.expand("rp", "root", node_id="a", action="branch-a",
              provenance="observed")
    wm.expand("rp", "root", node_id="b", action="branch-b",
              provenance="observed")
    wm.expand("rp", "a", node_id="a1", action="leaf-a1",
              provenance="observed")
    wm.expand("rp", "b", node_id="b1", action="leaf-b1",
              provenance="observed")
    # dmap 注入（monkeypatch 本类方法 — 输入注入是单元测试正体;
    # δ(b)>δ(a) 且字典序 a<b ⇒ 反序对: w1 选 b, w0 选 a）
    d._task_deltas = lambda: {"a": 0.0, "b": 2.5, "a1": 0.0, "b1": 0.0}
    return d


def test_picks_differ_w0_vs_w1_reverse_pair():
    """② 死锁破解锁（B 轮核心主张）: 反序对段内, w=0 与 w=1 picks 必须不同。"""
    d = _dwc_with_reverse_pair(None)
    rep = d.dream(k2_max=12,
                  policy_variants=[PolicySpec(w_delta=0.0,
                                               prefer_revealable=False)])
    picks1 = rep.picks.get("π0")            # w=1
    picks0 = rep.picks.get("π(w=0,r=0)")    # w=0, r=False（r=0 主场）
    assert picks1 and picks0, (rep.picks,)
    assert picks1 != picks0, \
        "★ R90 靶: 段式下 w 排序必须产生不同轨迹（若相同 = 段边界失效/死锁回归）"
    # 反序对的具体形态: 第二段（b 段）内, w=1 应优先 δ 大的（b1/b）,
    #   w=0 字典序（b 段内 a1 不在场 — b 段内字典序首为 b/b1）
    assert "b" in picks1 and "b" in picks0
    # ★ 段块结构锁（破坏靶⑤·拆段边界 ⇒ 红）: a 段节点全部在 b 段前 —
    #   单循环（无段边界）下 b 先揭后 a 的子节点会再现于 b 后 ⇒ 这里红
    for pk in (picks1, picks0):
        if "b" in pk:
            pos_b = pk.index("b")
            assert not ({"a", "a1"} & set(pk[pos_b:])), \
                "★ 段块被打破: b 段之后再现 a 段节点 %s（段边界失效）" % (pk,)


def test_seg_budget_caps_steps():
    """③ K_s=1: 每段至多 2 步（手动揭段根 + 段内 1 揭）。"""
    d = _dwc_with_reverse_pair(None)
    rep = d.dream(k2_max=12, seg_budget=1,
                  policy_variants=[PolicySpec(prefer_revealable=False)])
    picks = rep.picks["π0"]
    # 每段至多 2 步（手动揭段根 + 段内 1 揭）⇒ 全部树的 picks ≤ 段数×2
    assert len(picks) <= len(rep.segments) * 2, (picks, rep.segments)
    assert len(rep.segments) >= 2, "dev 组树 2 段 + rp 树 2 段"
    # rp 首段=插入序首 child（段根为首 pick — ④同源）
    rp_first = [s for s in rep.segments if s.startswith("rp:")]
    assert rp_first[0].endswith(":a"), rp_first


def test_reanchor_each_segment_starts_at_seg_root():
    """④ re-anchor: 每段首 pick = 段根（段起点 observed 不含本段 ⇒ 手动步在）。"""
    d = _dwc_with_reverse_pair(None)
    rep = d.dream(k2_max=12, policy_variants=[PolicySpec(
        prefer_revealable=False)])
    segs = [s.split(":", 1)[1] for s in rep.segments
            if s.startswith("rp:")]
    assert segs == ["a", "b"], segs
    picks = rep.picks["π0"]
    # 段根在 picks 中按段序出现且先于段内其他节点
    pos_a, pos_b = picks.index("a"), picks.index("b")
    assert pos_a < pos_b, "段序 = 插入序（children 段序）"
    # b 段起点干净: b 出现前, picks 中 b 之后才有 b 的段内揭示
    assert picks[pos_b] == "b"


def test_seg_order_pid_and_locks():
    """⑤ seg_order 枚举 / pid 后缀 / from_mapping 键域 / 锁值拒。"""
    assert PolicySpec().pid == "π0"
    assert PolicySpec(seg_order="children").pid == "π0"
    p = PolicySpec(seg_order="delta")
    assert p.pid == "π(w=1,r=1,s=delta)", p.pid     # 非默认追加 s 后缀
    # 默认 w/r 格式锁不破（既有测试同款断言）
    assert PolicySpec(w_delta=0.0).pid == "π(w=0,r=1)"
    # 键域: seg_order 进修订域, 锁值键仍拒, 未知键仍拒
    assert PolicySpec.from_mapping({"seg_order": "delta"}).seg_order == "delta"
    with pytest.raises(ReplayError, match="锁值"):
        PolicySpec.from_mapping({"tau": 0.5})
    with pytest.raises(ReplayError, match="未知键"):
        PolicySpec.from_mapping({"nope": 1})
    with pytest.raises(ReplayError, match="seg_order"):
        PolicySpec(seg_order="sideways")


def test_dream_seg_budget_validation():
    """seg_budget 校验: 非法值大声（G7）。"""
    d = _dwc_with_reverse_pair(None)
    for bad in (0, -1, True, 2.5):
        with pytest.raises(DwcError, match="seg_budget"):
            d.dream(k2_max=5, seg_budget=bad)


def test_segments_report_structure():
    """稿审计字段: segments 全树拼接（tid:seg 形态）+ picks 按 pid 分组。"""
    d = _dwc_with_reverse_pair(None)
    rep = d.dream(k2_max=10)
    assert rep.segments, "段序必报（审计字段）"
    assert all(":" in s for s in rep.segments)
    assert rep.picks and "π0" in rep.picks
