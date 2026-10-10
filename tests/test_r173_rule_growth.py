# -*- coding: utf-8 -*-
"""R173 · RULES 增长面 — LATERAL 泛化提案 + landed 固化（三闸, non-seed only）。

验收:
  □ Mutator.propose_lateral 同 (c,q) 近亲查询（无同族 ⇒ None — 不编）
  □ Loop 无本 fn 规则 ⇒ LATERAL 候选生成（Evolver 委派入口）
  □ 泛化提案**不硬过**: 试跑失败 ⇒ 门拦 ⇒ blocked 弃权（002 实测）
  □ landed ⇒ 固化三闸（land_rule + check_entry + evidence）:
    · 种子键 ⇒ seed_noop（如实 — 查表学到的不是新规则）
    · 非种子键 ⇒ consolidated + persist_learned 落盘 rules.json
  □ 未验证（trial success=False）不许固化
"""
from __future__ import annotations

import json
import os
import sys

import pytest

ROOT = r"E:/Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.harness.loop import Loop                    # noqa: E402
from dwc.organs.actor import Actor, execute_task     # noqa: E402
from dwc.organs.evolver import Evolver, Mutator      # noqa: E402


@pytest.fixture()
def loop():
    lp = Loop()
    lp.impl_store = dict(lp.impl_store)
    yield lp


def _sig_of(lp, tid):
    o = execute_task(lp.actor, lp.judge, tid,
                     implementation=lp.impl_store[tid])
    v = lp.judge.evaluate(tid, "dev", observed=o["observation"])
    return dict(v.failure_signature or {})


def test_lateral_finds_same_cq_family():
    """★★ 同 (c,q) 不同 fn ⇒ 出泛化提案（rationale 标来源）。"""
    ev = Evolver()
    sig = {"c": "E_VALUE", "q": "wrong_magnitude", "fn": "average"}
    p = ev.propose_lateral(sig)
    assert p is not None
    assert "LATERAL" in p.rationale
    assert p.failure_signature.get("m_source") == "lateral_rule"


def test_lateral_none_when_no_family():
    """★★ 无同族（c,q 全新）⇒ None ⇒ 调用方弃权（不编修法）。"""
    ev = Evolver()
    sig = {"c": "E_BRAND_NEW", "q": "never_seen", "fn": "zzz"}
    assert ev.propose_lateral(sig) is None


def test_lateral_proposal_does_not_force_pass(loop):
    """★★★★ 泛化提案**不网开一面**——002 的泛化修法试跑无效 ⇒ 门拦 blocked。

    ★ 这是门组的诚实: LATERAL 只是**候选生成**; sum_first_n 的修法
    合成到 average 跑不对 ⇒ 真 drawback ⇒ 拒（不是"借来的就能过"）
    """
    out = loop._run_one_task("code_fix_002", round_no=1)
    assert out["landed"] is False
    # ★★ R174 起路径细化: 泛化候选生成 ⇒ 试跑无效（prop=0.0 平 current）
    #   ⇒ replay 选择面**更早一步**拦（kept_current — §2.7 不劣于保证）
    #   ⇒ 语义同向（都不落地, 都不给借来的修法免费过）, 但拦点从
    #   "六门"前移到"replay select"——这更论文（选择面先判, 门再审质量）
    assert out["chain_verdict"] in ("blocked", "kept_current")
    if out["chain_verdict"] == "kept_current":
        assert loop._last_replay_pick["picked"] == "__current__"
    assert out.get("score") == 0.0


def test_consolidation_seed_noop(loop):
    """★★★ 种子键固化 = no-op 如实记（查表学到的不是新规则）。"""
    out = loop._run_one_task("code_fix_003", round_no=1)
    assert out["landed"] is True
    c = loop._last_consolidation
    assert c and c["outcome"] == "seed_noop"
    assert c["key"] == "E_NO_RESULT:abstained_or_missing:factorial"


def test_consolidation_writes_nonseed_to_disk(loop):
    """★★★★ 非种子键: 真 land_rule 三闸 ⇒ 落盘 rules.json（跨进程存活）。

    ★ 构造路径: 手动造一个**不在种子**的失败签名 + 一个过 judge 的
      patch（用 reasoning_002 的答案填充 — 键换成新 fn ⇒ 非种子）⇒
      _consolidate_rule 走全链（schema/evidence/readback/flush）。
    """
    sig = {"c": "E_MISMATCH", "q": "extra_content",
           "fn": "brand_new_kw_probe", "m": "r173_probe",
           "m_source": "rule"}
    from dwc.organs.evolver import Proposal
    class _P:
        component = "prompt"
        dimension = "D3"
        target_layer = "assets"
        patch = "x"
    trial = {"success": True, "impl": "含 一致性/可用性/分区容错 的答案。",
             "pass_rate": 1.0}
    before = os.path.exists(Mutator.LEARNED_PATH)
    rec = loop._consolidate_rule("reasoning_002", sig, _P(), trial, None)
    assert rec is not None and rec["outcome"] == "consolidated"
    assert rec["readback_ok"] is True
    key = "E_MISMATCH:extra_content:brand_new_kw_probe"
    assert key in Mutator.RULES
    assert os.path.exists(Mutator.LEARNED_PATH)
    d = json.load(open(Mutator.LEARNED_PATH, encoding="utf-8"))
    assert key in (d.get("learned") or {})
    # 清理（不污染跨测 — e2e 入口自洁同款）
    Mutator.RULES.pop(key, None)
    Mutator.persist_learned()
    if not (json.load(open(Mutator.LEARNED_PATH, encoding="utf-8"))
            .get("learned")):
        os.remove(Mutator.LEARNED_PATH)


def test_consolidation_rejects_unverified(loop):
    """★★★ trial.success=False ⇒ 固化被拒（不假装学会 — land_rule 闸②）。"""
    sig = {"c": "E_VALUE", "q": "wrong_magnitude",
           "fn": "unverified_probe", "m": "", "m_source": "rule"}

    class _P:
        component = "control_flow"
        dimension = "D7"
        target_layer = "assets"
        patch = "x"
    rec = loop._consolidate_rule("code_fix_001", sig, _P(),
                                 {"success": False, "impl": "junk"}, None)
    assert rec is not None and rec["outcome"] == "error"   # 闸② raise ⇒ 留痕
    key = "E_VALUE:wrong_magnitude:unverified_probe"
    assert key not in Mutator.RULES
