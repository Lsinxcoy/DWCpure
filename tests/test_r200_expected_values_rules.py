# -*- coding: utf-8 -*-
"""R200 · RULES expected_values 修法族（runG3 压力全通的最后一步）。

用户令"执行1"（R199 收尾选项①: 补修法族后进化环才能真修 rung3 任务）。

落地:
  · RULES +6 键（E_OFF_BY_ONE/E_VALUE × mean/median/std/range/pow2/pow3,
    修法 = 该任务完整正确答案文本 — 与 E_MISMATCH 族同一合法性论证:
    修法本身就是任务相关知识, 规则库随任务集增长 = 2606.09498 语义）
  · loop 撞键守卫: RULES 键 = c:q:fn **不含任务维度** ⇒ "mean" 跨任务撞键
    （001/002 同 key）⇒ 文本任务提案按 target==tid 过滤（R171 语义: 文本族
    target = task_id）
  · broken_dev 自报 rules_known false→true×3（自报标随规则库演化）
"""
from __future__ import annotations

import os
import sys

ROOT = r"E:\Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.harness.loop import Loop                                    # noqa: E402
from dwc.organs.evolver import Mutator                              # noqa: E402
from dwc.organs.judge import Judge                                  # noqa: E402

FAMILY_KEYS = [
    "E_OFF_BY_ONE:off_by_one_in_range:mean",
    "E_OFF_BY_ONE:off_by_one_in_range:median",
    "E_VALUE:wrong_magnitude:std",
    "E_VALUE:wrong_magnitude:range",
    "E_VALUE:wrong_magnitude:pow2",
    "E_VALUE:wrong_magnitude:pow3",
]
FIXED = {
    "reproduce_001": "mean=6.00, std=2.83, median=6.00",
    "reproduce_002": "mean=6.00, range=10.00",
    "reproduce_003": "pow2=1024.00, pow3=243.00",
}


def test_family_lands_every_rung3_task():
    """★★★ 端到端: 三条 rung3 全修复 — 落地 impl 是**本任务**的正确答案,
    judge 复判全过（002 落自己答案 = 撞键守卫在真实流里生效的证据）。"""
    lp = Loop()
    for tid, want_impl in FIXED.items():
        out = lp._run_one_task(tid, round_no=1)
        assert out["landed"] is True, "%s 未落地: %s" % (tid, out)
        assert lp.impl_store.get(tid) == want_impl, (
            "%s 落地答案错（撞键守卫失效会落 001 的答案）: %r"
            % (tid, lp.impl_store.get(tid)))
        v = lp.judge.evaluate(tid, "dev",
                              observed={"answer": lp.impl_store[tid]})
        assert v.success is True and v.k_passed == v.n_checks


def test_collision_guard_filters_wrong_task_proposal():
    """★★★ 撞键守卫的机理证据: 002 的 mean 签名命中的 RULES 条目 target=
    reproduce_001（键空间不含任务维度 — 这就是撞键）; loop 过滤后 002 只
    剩自己 target 的提案。"""
    m = Mutator()
    sig002_mean = {"c": "E_OFF_BY_ONE", "q": "off_by_one_in_range",
                   "fn": "mean", "m": "", "task": "reproduce_002"}
    p = m.propose(sig002_mean)
    assert p is not None and p.target == "reproduce_001", (
        "前提变了: mean 键应撞到 001 的条目 — 若 RULES 键空间改了, "
        "本测试与撞键守卫一起重审")
    # loop 过滤面（守卫代码在位 — 002 的 proposals 不含 target=001 项）
    src = open(os.path.join(ROOT, "src", "dwc", "harness", "loop.py"),
               encoding="utf-8").read()
    assert 'if str(getattr(pp, "target", "")) == tid]' in src, (
        "撞键守卫从 loop.py 消失 ⇒ 002 会试 001 的答案文本")


def test_rules_entries_pass_schema():
    """★★★ 6 条新条目过 check_entry（字段全/组件∈𝒦∪𝒦_meta/九维/键三段）。"""
    for key in FAMILY_KEYS:
        entry = Mutator.RULES[key]
        missing = Mutator.check_entry(key, entry)
        assert missing == [], "%s schema 缺: %s" % (key, missing)


def test_rules_known_self_report_matches_reality():
    """★★ 自报标与 RULES 现实一致: 3 条 rung3 的 target 键都在 RULES 里。"""
    lp = Loop()
    for tid in FIXED:
        assert lp.rules_known[tid] is True, "%s 自报应为 true" % tid
        mine = [k for k, v in Mutator.RULES.items() if v["target"] == tid]
        assert mine, "%s 自报 true 但 RULES 无其条目（过期自报）" % tid


def test_behavior_family_target_semantics_unchanged():
    """★★ 守卫不误伤 behavior 族: 其 target = fn 名（不是 task_id）—
    守卫只在文本分支生效（代码位置锁）。"""
    from dwc.organs.evolver import Mutator as M
    assert M.RULES["E_VALUE:wrong_magnitude:sum_first_n"]["target"] == \
        "sum_first_n"
    src = open(os.path.join(ROOT, "src", "dwc", "harness", "loop.py"),
               encoding="utf-8").read()
    # 守卫必须嵌在 verifier_kind 文本分支判断里（不能是无条件过滤）
    i = src.find('if str(getattr(pp, "target", "")) == tid]')
    ctx = src[max(0, i - 600):i]
    assert "keyword_match" in ctx and "expected_values" in ctx, (
        "守卫不在文本分支上下文 ⇒ 可能误伤 behavior 族（target=fn 名）")


def test_diagnose_dedup_does_not_block_other_task():
    """★★★ 约束 4 兼容: 001 落地后 mean 键进 _seen ⇒ 002 的 mean 签名被
    diagnose 跳过 — 但 002 仍能经 range 键拿到自己的提案（去重不堵死
    其它任务的修复通路）。"""
    lp = Loop()
    lp._run_one_task("reproduce_001", round_no=1)   # 落地 ⇒ mean 键 seen
    sig002 = [{"c": "E_OFF_BY_ONE", "q": "off_by_one_in_range",
               "fn": "mean", "m": ""},
              {"c": "E_VALUE", "q": "wrong_magnitude",
               "fn": "range", "m": ""}]
    out = lp.evolver.diagnose([dict(x) for x in sig002])
    targets = [p.target for p in out["proposals"]]
    assert "reproduce_002" in targets, (
        "001 落地把 002 的修复通路堵死了 ⇒ 去重误伤: %r" % targets)
