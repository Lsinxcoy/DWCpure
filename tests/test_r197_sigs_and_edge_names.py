# -*- coding: utf-8 -*-
"""R197 · ① 数据面改进 + ③ 边表命名修正（用户令"先做1+3"）。

①（数据面）: Loop→evolver.diagnose 的入参从 [主签名] 扩为 **全量签名簇**
  （judge 新产 Verdict.sigs — 每个 notok check 一条, 按 (c,q,fn) 去重）。
③（记账）: coupling 边名从**事件式**改为**事实形态描述**（我 R196 的边名误导:
  三条边没有事件可接, 但有真实耦合形态 — 按实测重命名, 不是改行为）。
"""
from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.harness.coupling import (COUPLING_EDGES, current_stage,  # noqa: E402
                                  pressures_from, pressures_to)
from dwc.organs.judge import Judge                              # noqa: E402


@pytest.fixture
def j():
    """真 Judge（出厂 anchors — code_fix_001 有 3 个 checks ⇒ 多 check 场景天然在场）。"""
    from dwc.organs.judge import Judge
    return Judge()


def test_multi_check_fail_produces_sig_cluster(j):
    """★★★ ① 的核心证据: 多 notok check ⇒ sigs 有多条（旧行为只看首个）。"""
    # 全错的观测 ⇒ 3 个 checks 全 fail（judge 实测路径）
    obs = {"sum_first_n": [[3, 999]]}
    v = j.evaluate("code_fix_001", "dev", observed=obs)
    assert v.failure_signature is not None
    assert v.sigs and len(v.sigs) >= 2, (
        "多 notok check 却只产 1 条签名 ⇒ ① 没落地（旧行为 = 只看首个）")
    # 主签名仍是**首个**（R30 原口径不变）
    fs = v.failure_signature
    assert v.sigs[0]["fn"] == fs["fn"] and v.sigs[0]["c"] == fs["c"], (
        "sigs[0] 不是主签名 ⇒ 改动偷偷换了主口径")
    # 去重: 同 (c,q,fn) 的重复 check 不产重复签名
    keys = [(x.get("c"), x.get("q"), x.get("fn")) for x in v.sigs]
    assert len(keys) == len(set(keys)), "sigs 里有重复签名 ⇒ 去重漏了"


def test_pass_verdict_has_no_sigs(j):
    """★★ pass 时 sigs = []（pass 无签名可产 — 不造空签名）。

    ★★ R199 重写（原版是**双重弱断言**, R199 冒烟抓的真 bug 正是它漏的）:
      ① PE.REFERENCE 查找姿势错（非 dict fn->impl）⇒ 分支从未执行
      ② `if v.success:` 守卫 — 那次实测 verdict 恰 fail ⇒ 断言从未跑
      ⇒⇒ 而 pass 路径真实行为是 sigs=[None]（R197 契约写的是 []）
      ⇒⇒ ⇒★ G4 族教训: 有条件执行的断言 = 没有断言
    现用 expected_values pass 态（R199 起可稳定构造）**无条件**断言。
    """
    v = j.evaluate("reproduce_001", "dev",
                   observed={"answer": "mean=6.00, std=2.83, median=6.00"})
    assert v.success is True, "前置: 正确答案必须 pass"
    assert v.sigs == [], "pass 路径 sigs 必须 []（实测曾为 [None] — R199 修）"
    assert v.failure_signature is None


def test_sigs_serialized_to_evidence():
    """★★ R72 补齐纪律: 新字段必须序列化 — 否则 evidence 侧丢（R72 抓过同款洞）。"""
    src = open(os.path.join(ROOT, "src", "dwc", "organs", "judge.py"),
               encoding="utf-8").read()
    i = src.find("def to_dict")
    assert '"sigs"' in src[i:i + 2000], "Verdict.to_dict 没序列化 sigs"


def test_loop_feeds_sigs_to_diagnose():
    """★★★ 主路径 + 换向路径 **同口径**（我的测试逮到过两口径并存）。"""
    src = open(os.path.join(ROOT, "src", "dwc", "harness", "loop.py"),
               encoding="utf-8").read()
    assert "self.evolver.diagnose(sigs)" in src, "主路径没吃 sigs ⇒ ① 没落"
    assert "diagnose(list(sigs or []) or [sig])" in src, "换向路径没同口径"
    assert "diagnose([sig])" not in src, "旧单签名调用还在 ⇒ 两条口径并存"


def test_dir_generate_sigs_backward_compatible():
    """★★ sigs=None 的旧调用 ⇒ 回退 [sig]（行为逐字节不变）。"""
    from dwc.harness.loop import Loop
    src = open(os.path.join(ROOT, "src", "dwc", "harness", "loop.py"),
               encoding="utf-8").read()
    # ★ R审计-P1 · 断言跟随 PEP585 现代化（ruff UP006/UP045 把
    #   Optional[List[Dict[str, str]]] 规范为 list[dict[str, str]] | None）:
    #   锁的是"默认 None 保留"的语义，不是键入法。
    assert "sigs: list[dict[str, str]] | None = None" in src, (
        "_dir_generate 没留默认 None ⇒ 老调用方（测试）会 TypeError")


def test_diagnose_clusters_multi_sigs():
    """★★★ 约束 4 逐字: 多签名不会重复提案（同 (c,q,m) 才算一簇）。"""
    from dwc.organs.evolver import Evolver
    ev = Evolver()                            # 真实例（RULES 索引在场）
    out = ev.diagnose([{"c": "x", "q": "y", "m": "", "fn": "a"},
                       {"c": "x", "q": "y", "m": "", "fn": "a"},
                       {"c": "z", "q": "y", "m": "", "fn": "b"}])
    # ★ 3 条签名（2 条同三元组 + 1 条不同）⇒ n_clusters == 2
    #   ⇒ 同三元组**不被重复提案**（约束 4 逐字: 精确一致才算一簇）
    assert out["n_clusters"] == 2, out
    assert len(out["proposals"]) <= 2, (
        "重复签名产出重复提案 ⇒ 约束 4（精确一致才算一簇）被破")


# ══════════════════════════════════════════════════════════
# ③ · coupling 边表命名修正（事实形态, 不是事件）
# ══════════════════════════════════════════════════════════
def test_edge_names_describe_facts_not_events():
    """★★★ R197 ③: 边名不许再暗示"事件驱动"（三条边实测没有事件可接）。"""
    names = {pn for (_f, _t, pn) in COUPLING_EDGES}
    for bad in ("op_verdicts_changed", "verdict_distribution_shifted"):
        assert bad not in names, (
            "边名 %r 还在 ⇒ 事件式误导复辟（metric 面实为每轮常开）" % bad)
    for good in ("metric_surface_refreshed_every_round",
                 "landing_enters_next_round_data",
                 "direction_switches_do_not_enter_select",
                 "failure_signature_clusters_fed"):
        assert good in names, "边名 %r 丢了 ⇒ 命名修正没落全" % good


def test_metric_surface_is_always_on_not_event_driven():
    """★★★ 机器证据: metric 面**每轮常开**（loop.py 每轮无条件调 dev_points_from_store）。"""
    src = open(os.path.join(ROOT, "src", "dwc", "harness", "loop.py"),
               encoding="utf-8").read()
    assert "pts, notes = dev_points_from_store(self.judge, split=\"dev\")" in src
    # 且它不在任何 if 分支里被条件触发（常开）
    i = src.find("def _metric_loop_tick")
    body = src[i:i + 2200]
    assert "if " not in body.split("dev_points_from_store")[0].split("try:")[-1], (
        "metric 面被条件包装 ⇒ 不是每轮常开")


def test_stage_and_queries_unchanged_after_rename():
    """★★ 改名不改判: stage/查询的语义与 R196 完全一致（防借改名偷改判据）。"""
    n, name = current_stage()
    assert (n, name) == (2, "Stage2_agent_environment")
    assert pressures_from("metric_loop")[0][0] == "direction"
    assert pressures_to("judge")[0][0] == "evolver"
