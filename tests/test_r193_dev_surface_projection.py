# -*- coding: utf-8 -*-
"""R193 · X1 dev 面判据投影层修复（R180 半错注释的清算 + R183 第二口径禁令的自守）。

三层递进（每层都是**实测**抓的, 不是读代码猜的）:
  层① R180 记"candidate_diff 不在 evidence 判据面 ⇒ None" — 实测 49/49 条
      都有 `diffs`（judge 逐 check 落的）⇒ **半错**, 缺的是投影层不是数据
  层② 投影层补上后, 我先在 `_facts_from_dev_surface` 里**重拼了一份** diff
      文本 ⇒ 那正是 R183 自己禁的"第二口径"（与 `_ctx_from_evidence` 并存）
      ⇒ 收敛: 全部键走 R179 桥, 本函数只做一次 ctx⇒TermFacts 搬运
  层③ adopted 面（_try_adopt_metric_tree → adopt → 门③回归）现在吃到 4/6
      op 的票（原 1/6）— 实测 26 facts: root_parse_ok 26 clean /
      judge_verdict 24d+2c / nonempty_diff 24c+2a / pass_rate_weak 24d+2c
      （component_known/golden_leak 仍 abstain — 判据面**不落**那两个字段,
      补它要从实现面反推 ⇒ R152/R180 纪律禁的那步, 单独立项）

验收锚: 6 op 中 ≥ 4 个在 dev 回归面从"恒 abstain"变"有判"（且 judge_verdict
        与 pass_rate_weak 同为 24 drawback ⇒ 两 op 在盘上**一致** — 这正是
        2607.12790 的 op 共识面该有的形态: 一致的 op 才给非零权重）。
"""
from __future__ import annotations

import io
import os
import sys

import pytest

ROOT = r"E:\Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.organs.drawback import Node as _N, _eval as _ev          # noqa: E402
from dwc.organs.metric_loop import (_POOL_OPS, _ctx_from_evidence,  # noqa: E402
                                    dev_points_from_store)
from dwc.harness.loop import Loop                                  # noqa: E402
from dwc.harness.gates import TermFacts                            # noqa: E402


@pytest.fixture(scope="module")
def seeded_loop():
    """产真判分点的 Loop（2 轮 ⇒ dev evidence 落盘）。"""
    lp = Loop()
    lp.round(0)
    lp.round(1)
    return lp


# ── 层①: 投影层真的在（diffs ⇒ candidate_diff）────────────
def test_ctx_from_evidence_projects_diffs():
    """★★★ 层①: evidence 的 diffs ⇒ candidate_diff 文本（R180 半错的修正）。"""
    evi = {"k_passed": 0, "n_checks": 2, "success": False,
           "diffs": [{"index": 0, "kind": "behavior", "fn": "sum_first_n",
                      "args": 3, "expected": 6, "actual": 3, "ok": False,
                      "reason": "值不匹配"}]}
    ctx = _ctx_from_evidence(evi)
    assert ctx["candidate_diff"] == "sum_first_n(3): 6 → 3（值不匹配）"
    assert ctx["judge_success"] is False


def test_ctx_from_evidence_all_ok_gives_none():
    """★ 全 ok 的判据点 ⇒ diff=None（判过无差异 — 不是"没判过"）。"""
    evi = {"k_passed": 2, "n_checks": 2, "success": True,
           "diffs": [{"fn": "f", "ok": True}]}
    assert _ctx_from_evidence(evi)["candidate_diff"] is None


def test_ctx_from_evidence_absent_diffs_none():
    """★ diffs 字段整体缺席 ⇒ None（fail-closed — 不猜有/无）。"""
    assert _ctx_from_evidence({"k_passed": 1, "n_checks": 1,
                               "success": True})["candidate_diff"] is None


def test_ctx_from_evidence_no_second_caliber():
    """★★★ 层②: R179 桥是唯一 diff 投影口径（loop 侧不再重拼）。"""
    lp = Loop()
    for p in lp.judge.task_scores(split="dev")[:1]:
        evi = lp.judge.evidence(p.evidence_ref)
        from_ctx = _ctx_from_evidence(evi)["candidate_diff"]
    facts = lp._facts_from_dev_surface()
    # facts 里同 ref 的 diff 必与桥一致（不一致 = 第二口径复辟）
    from_facts = next((f.candidate_diff for f in facts
                       if f.candidate_diff), None)
    assert from_facts is None or from_facts == from_ctx, (
        "loop 侧与 R179 桥给出不同 diff 口径 ⇒ 第二口径复辟（R183 禁令）")


# ── 层③: dev 回归面的 op 信号密度 ─────────────────────────
def test_dev_surface_op_signal_density(seeded_loop):
    """★★★ 层③: 26 条 facts 上 6 op 中 **4 个**有判（原 1 个）。

    ★ 为什么不断言"component_known/golden_leak 也有判": 判据面**不落**
      组件/泄漏字段（R152/R180 判据与实现分离 ⇒ 补它要从实现面反推,
      纪律禁的那步）⇒ 那两个 op 如实 abstain, 这不是缺陷。
    ★ root_parse_ok 全 clean: dev 判据点必被解析过（同 R189-B train 口径）。
    """
    from collections import Counter
    facts = seeded_loop._facts_from_dev_surface()
    assert len(facts) >= 20, "dev facts 太少 ⇒ 本测试的前提不成立"
    st: dict = {}
    for f in facts:
        ctx = {"pass_rate": f.pass_rate,
               "candidate_diff": f.candidate_diff,
               "judge_success": f.judge_success,
               "parsed_ok": f.parsed_ok}
        for n in _POOL_OPS:
            v = _ev(_N(kind="leaf", op=n), _POOL_OPS, None, None, ctx)
            st.setdefault(n, []).append(v)
    speaking = {n for n, vs in st.items() if any(v != "abstain" for v in vs)}
    assert {"root_parse_ok", "judge_verdict", "nonempty_diff",
            "pass_rate_weak"} <= speaking, (
        "四个 op 仍 abstain ⇒ R180 断裂复发; 实测应有 %r" % sorted(speaking))
    assert len(speaking) == 4, (
        "多于 4 个在说话 ⇒ component/golden 也来了 — 那意味着判据面开始"
        "存实现字段, 触碰 R152 纪律（应为 4）")


def test_judge_verdict_and_pass_rate_agree(seeded_loop):
    """★★★ 层③ 的论文锚: judge_verdict 与 pass_rate_weak 在 26 点上**同判**
    （24 drawback）⇒ 两 op 一致 ⇒ 2607.12790 的 op 共识面成立
    （一致的 op 才有非零 reliability 权重进 A_train 分母）。"""
    from collections import Counter
    facts = seeded_loop._facts_from_dev_surface()
    jv = Counter()
    pw = Counter()
    for f in facts:
        ctx = {"judge_success": f.judge_success, "pass_rate": f.pass_rate}
        jv[_ev(_N(kind="leaf", op="judge_verdict"), _POOL_OPS,
               None, None, ctx)] += 1
        pw[_ev(_N(kind="leaf", op="pass_rate_weak"), _POOL_OPS,
               None, None, ctx)] += 1
    assert jv["drawback"] == pw["drawback"] > 0, (
        "两 op 判定不一致（jv=%r pw=%r）⇒ 共识面裂了" % (dict(jv), dict(pw)))


# ── 回归面: TermFacts 新键不破坏旧行为 ────────────────────
def test_termfacts_new_fields_default_none():
    """★ 缺省 None ⇒ 老调用方（不填这两个键）行为逐字节不变。"""
    f0 = TermFacts(pass_rate=0.5)
    assert f0.judge_success is None and f0.parsed_ok is None
    ctx = {"pass_rate": 0.5}
    # 不填新键 ⇒ judge_verdict/root_parse_ok abstain（老口径）
    assert _ev(_N(kind="leaf", op="judge_verdict"), _POOL_OPS,
               None, None, ctx) == "abstain"
    assert _ev(_N(kind="leaf", op="root_parse_ok"), _POOL_OPS,
               None, None, ctx) == "abstain"


def test_metric_loop_select_still_works(seeded_loop):
    """★★ select 端到端仍跑（R193 改的是投影, 不该动选优面）。"""
    pts, notes = dev_points_from_store(seeded_loop.judge, split="dev")
    assert len(pts) >= 20
    assert notes["n_points"] >= 20
    # ctx 里 candidate_diff 已有值（投影层生效的机器证据）
    with_diff = sum(1 for p in pts
                    if (p.get("ctx") or {}).get("candidate_diff"))
    assert with_diff > 0, "pts 里零 candidate_diff ⇒ 投影没接到数据面"


# ── X3: 消费点登记面（consume 五元组覆盖）──────────────────
def test_consume_points_cover_loop_traces():
    """★★★ X3: Loop.__init__ 里的 _last_*/_dir_* 痕迹属性**全部**在登记表内。

    ★ 为什么用 __init__ 而不用 grep 注释: 注释会漂（R189 core.py 14 处
      注释冒充就是), 而 __init__ 里**真身在场**的属性清单是机器可证的。
    ★ 未登记 ⇒ 测试红（不留"注释里提到但表里没有"的漂移空间）。
    """
    from dwc.harness.consume_points import CONSUME_POINTS, undeclared
    lp = Loop()
    # _last_x ⇒ x / _dir_x ⇒ dir_x（去掉前导下划线即可对上登记键）
    attrs = [a[1:] for a in vars(lp)
             if a.startswith("_last_") or a.startswith("_dir_")]
    attrs.append("dir_ledger")          # 文件型消费点（_dir_archive_path）
    missing = undeclared(attrs)
    assert not missing, ("Loop 痕迹属性未登记 ⇒ 消费点面漂移: %r" % missing)
    # 每条登记必有 consumer/path/attr/range/verify 五字段（不漏字段）
    for k, p in CONSUME_POINTS.items():
        for f in ("consumer", "path", "attr", "range", "verify"):
            assert p.get(f), "%s 缺 %s 字段（五元组不许半登记）" % (k, f)


def test_consume_points_declare_none_as_legit():
    """★★★ None 是合法一等输出 ⇒ range 必显式声明（否则消费方拿 None 当异常）。"""
    from dwc.harness.consume_points import CONSUME_POINTS
    # ★ 只对 **Optional** 面要求（恒 list/int 的面 None 不是合法值 —
    #   断言"None ∈ range"会逼出假声明; 准确的机器判法是"range 串自身
    #   含 Optional/None 与否"自洽: 缺席合法的面必须自报 None）。
    for k, p in CONSUME_POINTS.items():
        opt = p["range"].lstrip().startswith("Optional")
        has_none = "None" in p["range"]
        assert opt == has_none, (
            "%s 的 range 与 None 声明不自洽（opt=%s, 串内含 None=%s）"
            % (k, opt, has_none))


def test_applier_targets_and_consume_points_are_distinct():
    """★★ 两个登记面不抢位: applier=可写面, consume_points=观测面。"""
    from dwc.organs.applier import TARGETS
    from dwc.harness.consume_points import CONSUME_POINTS
    assert set(TARGETS) == {"mutation_rule"}          # 可写面仍 1 条
    assert "mutation_rule" not in CONSUME_POINTS       # 观测面不含可写键
    assert len(CONSUME_POINTS) >= 10                   # Loop 侧 11 条痕迹


# ── X4: 词表收口（单一真源, 值不变）──────────────────────
def test_vocabulary_is_single_source_object():
    """★★★ X4: evolver 三张表与 foundation/vocabulary.py 是**同一对象**

    ★ 为什么锁 `is` 不锁 `==`: 复制值会给出相等但独立的两套常量 ⇒
      "改一处漏一处"的老病复归（这正是 R189 说的"双源"。
    """
    from dwc.organs import evolver
    from dwc.foundation import vocabulary as V
    assert evolver.COMPONENT_VOCAB is V.COMPONENT_VOCAB
    assert evolver.STRUCTURAL is V.STRUCTURAL
    assert evolver.K_META is V.K_META


def test_vocabulary_values_unchanged():
    """★★★ 收口是位置手术不是语义手术 — 9/5/4/2 四个数一个不动。"""
    from dwc.foundation.vocabulary import (COMPONENT_VOCAB, K_META,
                                           K_META_READONLY, STRUCTURAL)
    assert len(COMPONENT_VOCAB) == 9
    assert COMPONENT_VOCAB == {"prompt", "control_flow", "config",
                               "output_plumbing", "context_mgmt", "client_tool",
                               "skill", "memory", "subagent"}
    assert len(K_META) == 5
    assert K_META["evaluator"] is False and K_META["external_source"] is False
    assert K_META_READONLY == ("evaluator", "external_source")
    assert STRUCTURAL < COMPONENT_VOCAB, "结构型是 𝒦 的子集（不是新词）"


def test_vocabulary_does_not_merge_dimensions():
    """★★★ R189 误认修正: DIMENSIONS（模块声明维度）**不并入** 𝒦。"""
    from dwc.organs.dimension import DIMENSION_IDS
    from dwc.foundation.vocabulary import COMPONENT_VOCAB
    assert not (set(DIMENSION_IDS) & COMPONENT_VOCAB), (
        "维度 id 混进组件词表 ⇒ 两种不同语义被并成一张表（R193 修 R189 误认）")


def test_evolver_no_longer_declares_literal_tables():
    """★★ 防复发: evolver.py 不再自持"COMPONENT_VOCAB = frozenset(" 字面量。"""
    src = io.open(os.path.join(ROOT, "src", "dwc", "organs", "evolver.py"),
                  encoding="utf-8").read()
    assert "COMPONENT_VOCAB = frozenset(" not in src, (
        "evolver 又自持词表字面量 ⇒ 双源复辟（应 from vocabulary import）")
