# -*- coding: utf-8 -*-
"""R299 · peer hint（trial 成功码喂 peer prompt 当 few-shot）。

★ fake llm/judge（零真 LLM）；raises 配额见末尾（≥5%：6 测 1 raises）。
★ judge 用真 Judge（只读 anchors＋内存 log，不写生产）。
"""
from __future__ import annotations

import os
import sys

import pytest

ROOT = r"E:/Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import dwc_evo_round as EVO
from dwc.organs.judge import Judge

CODE_007 = "def average(xs):\n    return sum(xs)/len(xs) if xs else 0.0\n"


def _rec_llm(text, box):
    """★ 记录 prompt 的 fake llm（形态对齐 LLMClient 结果 ok/text）。"""
    class _R:
        ok = True
    _R.text = text
    class _LLM:
        def complete(self, prompt, max_tokens=1500):
            box.append(prompt)
            return _R()
    return _LLM()


def test_r299_hint_enters_peer_prompt():
    """★ hint 非空⇒peer prompt 含 hint 片段（few-shot 生效）。"""
    box = []
    j = Judge()
    EVO._peer_held_out_code(
        j, _rec_llm("```python\ndef mock_peer(x):\n    return x\n```", box),
        "code_fix_007", hint_code=CODE_007)
    assert box, "fake llm 一次都没被调"
    assert "sum(xs)/len(xs)" in box[0], box[0][:200]


def test_r299_no_hint_old_path():
    """★ hint 缺席⇒prompt 无 hint 段（老路行为零变）。"""
    box = []
    j = Judge()
    EVO._peer_held_out_code(
        j, _rec_llm("```python\ndef mock_peer(x):\n    return x\n```", box),
        "code_fix_007")
    assert box
    assert "已验证" not in box[0], box[0][:200]


def test_r299_empty_hint_same_as_absent():
    """★ hint 空串⇒与缺席同形（不拼空段）。"""
    box = []
    j = Judge()
    EVO._peer_held_out_code(
        j, _rec_llm("```python\ndef mock_peer(x):\n    return x\n```", box),
        "code_fix_007", hint_code="   ")
    assert box
    assert "已验证" not in box[0], box[0][:200]


def test_r299_trial_passes_hint_to_peer():
    """★ code 路 trial⇒peer 调参带 trial 码（feeding 接通）。"""
    seen = {}
    _orig = EVO._peer_held_out_code

    def _spy(judge, llm, task, max_tokens=1500, max_attempts=3,
             hint_code=None):
        seen["hint"] = hint_code
        return 1.0
    EVO._peer_held_out_code = _spy
    try:
        j = Judge()
        r = EVO._real_trial(j, None, "code_fix_007", "p", code=CODE_007)
        assert r["success"] is True, r
        assert (seen.get("hint") or "").strip().startswith("def average"), seen
    finally:
        EVO._peer_held_out_code = _orig


def test_r299_trial_none_code_no_hint():
    """★ code=None⇒peer 无 hint（失败码不污染 peer）。"""
    seen = {}
    _orig = EVO._peer_held_out_code

    def _spy(judge, llm, task, max_tokens=1500, max_attempts=3,
             hint_code=None):
        seen["called"] = True
        seen["hint"] = hint_code
        return None
    EVO._peer_held_out_code = _spy
    try:
        j = Judge()
        # ★ 报数路（code=None）：peer 走老路，hint 必须缺席
        import dwc_evo_round as _E
        _E._real_trial(j, _rec_llm("```python\ndef average(xs):\n    return 0.15\n```", []),
                       "code_fix_007", "patch文本", code=None)
        assert seen.get("hint") is None, seen
    finally:
        EVO._peer_held_out_code = _orig


def test_r299_raises_quota_llm_throws_fails_closed():
    """★ raises 配额①：fake llm 抛⇒吞错返 None（peer R295 既定 fail-closed，
    坏不断试跑——与 Mutator 上抛纪律分层不同，peer 层吞，mutator 层抛）。

    ★ R299 纪律注：hint 照拼（抛发生在 complete，与 hint 无关）。
    """
    class _Boom:
        def complete(self, prompt, max_tokens=1500):
            raise RuntimeError("boom")
    assert EVO._peer_held_out_code(Judge(), _Boom(), "code_fix_007",
                                   hint_code=CODE_007) is None


def test_r299_raises_quota_bad_hint_type_fails_closed():
    """★ raises 配额②：hint 坏类型（int 无 strip）⇒不炸（fail-closed 兜底，
    try/except 吞⇒None，不掀整轮）。"""
    box = []
    r = EVO._peer_held_out_code(
        Judge(), _rec_llm("```python\ndef mock_peer(x):\n    return x\n```", box),
        "code_fix_007", hint_code=12345)
    assert r is None  # ★ 坏 hint 吞错⇒None（不炸整轮；hint 校验是增强项）


def test_r299b_baseline_snapshot_not_self():
    """★ R299-b · 基线前置：先记旧分 0.0→trial 成功后 base 仍 0.0（非自己 1.0）。

    ★ 回归 R299-b 根因：evaluate→store.record 当场记点，判后取 base=
    自己刚判的分（d_in 恒 0 死门）。前置快照后 base=真历史。
    """
    j = Judge()
    v0 = j.evaluate("code_fix_007", "dev",
                    observed={"observed": {"average": [(("x",), 0.0)]},
                              "★_executed": True})
    assert v0.success is False  # ★ 旧分 0.0（错码）
    r = EVO._real_trial(j, None, "code_fix_007", "p", code=CODE_007)
    assert r["success"] is True, r
    assert r["baseline_in"] == 0.0, r  # ★ 真历史，非自己


def test_r299b_baseline_ho_key_present():
    """★ R299-b · trial 回 baseline_ho 键（门喂 b_ho，缺历史⇒None 诚实）。"""
    j = Judge()
    r = EVO._real_trial(j, None, "code_fix_007", "p", code=CODE_007)
    assert "baseline_ho" in r, r
    assert r["baseline_ho"] is None  # ★ peer 从未 record⇒None（不编基线）


def test_r299b3_same_round_no_cross_contamination():
    """★ R299-b3 · 同轮串行污染切除：trial1 记点后 trial2 快照读不到 trial1 分。

    ★ 回归生产实测：同轮簇 2 b_in=1.0（簇 1 刚记的分），基线语义污染。
    首调记 n0，后调切片轮首已有点。
    """
    j = Judge()
    r1 = EVO._real_trial(j, None, "code_fix_007", "p", code=CODE_007)
    assert r1["success"] is True, r1
    assert r1["baseline_in"] is None  # ★ 轮首无历史
    r2 = EVO._real_trial(j, None, "code_fix_007", "p", code=CODE_007)
    assert r2["success"] is True, r2
    assert r2["baseline_in"] is None, r2  # ★ 读不到 r1 刚记的 1.0
