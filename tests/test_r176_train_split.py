# -*- coding: utf-8 -*-
"""R176 · train split 语义落地（2607.12790 式2 A_train — DWC 同构翻译）。

论文语义（精读逐字）:
  · train = **大、无标签**（不是第二套 gold）; 用途 = 暴露候选何时分歧/弃权
  · A_train(e) = e 与 op 池在无标签 train 输出上的**共识判定**一致度
  · dev/test 铁律: "audit and never a training signal" — train 不进判定面
DWC 翻译（不发明）:
  · train outputs = **已落地历史修法**（rules.json learned — 门收下过 =
    无 gold 标签的过程产物; ℒ_t adopted=False 的有标签负面不进 train）
  · 一致度口径 = 提案 (component,target) 在历史 clean 修法中的出现率
    （可判定可复现 — 无 LLM; κ=10 reliability 归 R177 Metric Loop 重组）
  · None(无历史) ≠ 0.0(有历史无同族): 缺席不伪造（S(e) 里 A_train 乘性进
    A_dev — None 时保持 A_dev 单独裁决, 不假装 1.0）

验收:
  □ 冷启动 train 空 ⇒ None + 原因
  □ 有历史无同族 ⇒ 0.0（不同族判过 — 不是缺席）
  □ 有历史有同族 ⇒ clean 一致度
  □ train 集只来自 rules.json learned（不读 ℒ_t 负面 — 有标签不进）
  □ Loop 痕迹 _last_a_train 落 round 路径（003 landed 时是 None — 冷启）
"""
from __future__ import annotations

import io
import json
import os
import sys

import pytest

ROOT = r"E:/Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.harness.loop import Loop                    # noqa: E402
from dwc.organs.evolver import Mutator               # noqa: E402


@pytest.fixture()
def loop():
    lp = Loop()
    lp.impl_store = dict(lp.impl_store)
    yield lp


@pytest.fixture()
def clean_rules():
    """造/清 rules.json（learnded 面 — 测试后还原原状）。"""
    path = Mutator.LEARNED_PATH
    had = os.path.exists(path)
    bak = io.open(path, encoding="utf-8").read() if had else None
    if os.path.exists(path):
        os.remove(path)
    yield path
    if had:
        io.open(path, "w", encoding="utf-8").write(bak)
    elif os.path.exists(path):
        os.remove(path)


def _write_learned(path, entries):
    io.open(path, "w", encoding="utf-8").write(json.dumps(
        {"learned": {k: v for k, v in entries.items()}}, ensure_ascii=False))


def test_cold_start_absent_not_zero(loop):
    """★★ 空 train ⇒ None（缺席不是 0 — fail-closed: 不伪造一致度）。"""
    a, why = loop._a_train("prompt", "reasoning_002")
    assert a is None and "缺席" in why["why"]


def test_warm_no_same_component_is_zero(loop, clean_rules):
    """★★ 有历史无同族 ⇒ 0.0（判过"不同族", 不是冷启缺席）。"""
    _write_learned(clean_rules, {
        "E_VALUE:wrong_magnitude:sum_first_n": {
            "component": "control_flow", "target": "code_fix_001",
            "dimension": "D7", "m": "x", "m_source": "rule",
            "patch": "return n", "rationale": "t"}})
    a, why = loop._a_train("prompt", "reasoning_002")
    assert a == 0.0 and why["n_train"] == 1
    assert why.get("n_same_component") == 0 or "冷启动" in why.get("why", "")


def test_warm_same_component_rate(loop, clean_rules):
    """★★★ 有历史有同族 ⇒ clean 出现率（train 里 prompt 2/2 ⇒ 1.0）。"""
    _write_learned(clean_rules, {
        "k1": {"component": "prompt", "target": "reasoning_002",
               "dimension": "D3", "m": "x", "m_source": "rule",
               "patch": "a", "rationale": "t"},
        "k2": {"component": "prompt", "target": "reasoning_003",
               "dimension": "D3", "m": "x", "m_source": "rule",
               "patch": "b", "rationale": "t"}})
    a, why = loop._a_train("prompt", "reasoning_002")
    assert a == 1.0 and why["n_same_component"] == 2


def test_train_set_source_is_learned_only(loop, clean_rules):
    """★★★ train 集只来自 rules.json learned（ℒ_t 负面不进 — 无标签纪律）。"""
    _write_learned(clean_rules, {
        "k1": {"component": "prompt", "target": "t1", "dimension": "D3",
               "m": "x", "m_source": "rule", "patch": "a",
               "rationale": "r"}})
    got = loop._learned_attempts()
    assert len(got) == 1 and got[0][0] == "prompt" and got[0][2] is True


def test_loop_round_traces_a_train(loop, clean_rules):
    """★ round 路径留 _last_a_train 痕迹（审计面 — S(e) R177 重组时读它）。"""
    out = loop._run_one_task("code_fix_003", round_no=1)
    assert out["landed"] is True
    assert loop._last_a_train is None            # 冷启 train 空 ⇒ 缺席
    assert "n_train" in loop._last_a_train_why
