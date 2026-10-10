# -*- coding: utf-8 -*-
"""R180 · Loop 接 Metric Loop（点火线 — 只读选+留痕, 不换判据树）。

验收:
  □ _metric_loop_tick 在 round 出口被调（痕迹落 res["metric_pick"]）
  □ 缺席如实化: dev 面空/异常 ⇒ picked=None + why（不 raise 断主链）
  □ 判据面分离的实测纪律（R180 发现, 非缺陷）: dev 面上吃"实现面"的 op
    （nonempty_diff/component_known/golden_leak）恒 abstain ⇒ 选择仍有效
  □ Judge.evidence 委派在场（R180 补的缺口 — 落盘模式证据在 jsonl 里,
    store._evidence 内存表空 ⇒ 无委派时 metric_loop 全点 skip 假阴性）
"""
from __future__ import annotations

import os
import sys

import pytest

ROOT = r"E:/Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.harness.gates import TermFacts                 # noqa: E402
from dwc.harness.loop import Loop                       # noqa: E402
from dwc.organs.judge import Judge                      # noqa: E402


@pytest.fixture()
def clean_loops():
    lp = Loop()
    return lp


def test_round_exposes_metric_pick(clean_loops):
    """★ round 出口带 metric_pick 痕迹（R180 点火线的可观测面）。"""
    r1 = clean_loops.round(1)
    assert "metric_pick" in r1 and "metric_loop_why" in r1
    # r1 时刻 dev 面刚被本轮判分追加 ⇒ picked 可能 None（fail-closed 如实）
    assert r1["metric_pick"] is None or "picked_key" in r1["metric_pick"]


def test_second_round_selects_or_stays(clean_loops):
    """★★★ r2 起 dev 面含真点 ⇒ select 在有效候选集中选/保持（都如实）。"""
    clean_loops.round(1)
    r2 = clean_loops.round(2)
    mp = r2["metric_pick"]
    assert mp is not None
    assert mp["n_points"] >= 1
    # picked None（无候选优于现任）是合法输出 — 论文"不折腾"纪律
    assert mp["picked_key"] is None or isinstance(mp["picked_key"], str)


def test_criterion_surface_ops_abstain_on_dev(clean_loops):
    """★★★ R180 实测纪律: dev 面（判据投影）上实现类 op 恒 abstain。

    ★ 非缺陷 — evidence 存的是判据投影（diffs/success/k/n, R152 约定:
      点与证据成对存判据不存实现）⇒ 吃 candidate_diff/component 的 op 在
      dev 面**天然**第三态（三值协议的诚实 — 不造值喂 op）
    """
    from dwc.organs.metric_loop import (dev_points_from_store,
                                        mechanical_candidates)
    clean_loops.round(1)
    pts, notes = dev_points_from_store(clean_loops.judge, split="dev")
    assert notes["n_points"] >= 1
    impl_ops = ("nonempty_diff(1)", "component_known(1)", "golden_leak(1)")
    for key in impl_ops:
        vals = {p["tree_verdicts"].get(key) for p in pts}
        assert vals <= {"abstain", None}, (key, vals)


def test_judge_evidence_delegation():
    """★★★ Judge.evidence 委派在场（R180 补缺 — 无它时全点 skip 假阴性）。"""
    j = Judge()
    assert hasattr(j, "evidence") and callable(j.evidence)
    # 落盘模式真跑: 一圈判分后点+证据成对可取
    from dwc.harness.loop import Loop as _L
    lp = _L()
    lp.round(1)
    pts = lp.judge.task_scores(split="dev")
    assert pts
    evi = lp.judge.evidence(pts[0].evidence_ref)
    assert evi["task_id"] == pts[0].task_id
    assert "success" in evi and "k_passed" in evi


def test_tick_failure_keeps_chain_alive():
    """★★★ tick 内异常被自吞留痕（picked=None + why — 不 raise 断主链）。

    ★ R180 实测纪律: 观察面的异常**不许**冒泡到 round（主链连续性 > 观察
      面可用性; 但必须留 why 可审计 — G7 与"缺席≠完成"两不欠）
    """
    lp = Loop()
    lp.round(1)
    lp.judge.task_scores = lambda **kw: (_ for _ in ()).throw(
        RuntimeError("broken surface"))
    out = lp._metric_loop_tick()
    assert out["picked_key"] is None
    assert "broken surface" in out["why"]
    assert lp._last_metric_pick is None and lp._metric_loop_why
