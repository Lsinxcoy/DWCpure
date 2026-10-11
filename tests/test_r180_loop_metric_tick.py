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


@pytest.fixture(autouse=True)
def _reset_tree_table():
    """★★ 注入表是进程内全局（_CURRENT_TREE）— 任何真跑 round 的测试
    （R183 起 round 会真 adopt）都必须前后复位, 否则污染同 session 后续
    文件（实测: R181/R166 的"未注入⇒出厂"断言被 R180/R183 的 round 打爆）。
    """
    yield
    from dwc.harness import gates as _g
    _g.set_current_tree(None)


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
    """★★★ dev 面 op 三态（R180 初版口径 → R193 修正, 如实标注推翻）。

    ★★ R180 原文口径（已被 R193 推翻, 保留记录）:
      "实现类 op 恒 abstain — evidence 存判据不存实现, 吃 candidate_diff 的
       op 天然第三态"。
    ★★★ R193 实测: 该口径**半错** — evidence 存 `diffs`（逐 check 的
      expected/actual/ok/reason, judge 判据面字段, 49/49 条在场）; 缺的
      是"投影成 op 吃的 diff 文本"这一层, **不是数据**。补上投影后:
        nonempty_diff — 从"恒 abstain"变"多数 clean"（判据面真能判了）
        component_known / golden_leak — 仍 abstain（判据面**不落**
          component/vocabulary/leakage_hits; 补它要从实现面反推 ⇒
          R152/R180"判据与实现分离"纪律禁的那步 ⇒ **如实保持第三态**）
    ★ 本测试现在的断言 = R193 修正后的口径（防回退: 再有人说
      "dev 面零信号"时, 机器会告诉他哪两个 op 真的判不了、为什么）。
    """
    from dwc.organs.metric_loop import (dev_points_from_store,
                                        mechanical_candidates)
    clean_loops.round(1)
    pts, notes = dev_points_from_store(clean_loops.judge, split="dev")
    assert notes["n_points"] >= 1
    # component_known/golden_leak: 判据面无字段 ⇒ 仍恒 abstain（R152 纪律）
    for key in ("component_known(1)", "golden_leak(1)"):
        vals = {p["tree_verdicts"].get(key) for p in pts}
        assert vals <= {"abstain", None}, (key, vals)
    # nonempty_diff: R193 投影层补上后, 有判据面 diff 的点必 clean
    #   （全 ok 的点 diff=None ⇒ abstain — 判过无差异）
    nv = [p["tree_verdicts"].get("nonempty_diff(1)") for p in pts]
    assert set(nv) <= {"clean", "abstain", None}, (
        "nonempty_diff 出现 drawbeck ⇒ 投影层的 diff 文本被判'空'"
        "（diffs 非空却投影失败 — 检查 _ctx_from_evidence）")
    assert any(v == "clean" for v in nv), (
        "nonempty_diff 全 abstain ⇒ R193 投影层没生效（dev 面零信号复发）")


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
