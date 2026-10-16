# -*- coding: utf-8 -*-
"""R295-Task3 · _real_trial 分流（code_repair 写码真执行，其余老路）。

★ fake llm/judge（零真 LLM）；raises 配额见末尾。
★ judge 用真 Judge（dev 真值源只读不写——evaluate 只读 anchors＋内存 log）。
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

def _fake_llm(text):
    """★ fake llm（带 .complete，形态对齐 LLMClient 结果 ok/text）。"""
    class _R:
        ok = True
    _R.text = text
    class _LLM:
        def complete(self, prompt, max_tokens=1500):
            return _R()
    return _LLM()


CODE_007 = "def average(xs):\n    return sum(xs)/len(xs) if xs else 0.0\n"


def test_r295_trial_code_mode_passes_007():
    """★★★ code＋code_repair⇒沙箱真跑⇒success=True（007 首验收，B 路线正名）。"""
    j = Judge()
    r = EVO._real_trial(j, None, "code_fix_007", "patch文本", code=CODE_007)
    assert r["success"] is True, r
    assert r["mode"] == "code", r


def test_r295_trial_code_malicious_fails_closed():
    """★ 恶意 code⇒SandboxError⇒success=None（fail-closed，不回落报数）。"""
    j = Judge()
    r = EVO._real_trial(j, None, "code_fix_007", "p",
                        code="import os\ndef average(xs):\n    return 0.15\n")
    assert r["success"] is None, r
    assert r["mode"] == "code", r


def test_r295_extract_code_bare_def_fallback():
    """★ R295补 · 无 fence 但有裸 def⇒按 fn 起抓（鹦鹉复述指令也救回）。"""
    raw = ("写一个完整可执行 Python 函数（只输出 ```python 代码块，无解释）：\n"
           "def word_count(s):\n    return len(s.split())\n")
    assert EVO._extract_code(raw, "word_count").startswith("def word_count")
    assert EVO._extract_code("光说不练", "word_count") is None


def test_r295_peer_retries_no_code_then_scores():
    """★ R295补 · peer 第一次无码第二次出码⇒重试救回 held_out=1.0（fake 计数）。"""
    _n = []
    def _fake(p, max_tokens=1500):
        _n.append(p)
        if len(_n) == 1:
            return type("R", (), {"ok": True, "text": "解释一下思路……"})()
        return type("R", (), {"ok": True, "text": (
            "```python\ndef word_count(s):\n    return len(s.split())\n```")})()
    j = Judge()
    assert EVO._peer_held_out_code(
        j, type("L", (), {"complete": staticmethod(_fake)})(),
        "code_fix_007") == 1.0
    assert len(_n) == 2, len(_n)


def test_r295_peer_all_no_code_returns_none():
    """★ R295补 · 3 次全无码⇒None（fail-closed，空码不进沙箱不炸）。"""
    _llm = type("L", (), {"complete": staticmethod(
        lambda p, max_tokens=1500: type(
            "R", (), {"ok": True, "text": "光说不练"})())})()
    assert EVO._peer_held_out_code(
        Judge(), _llm, "code_fix_007", max_attempts=3) is None


def test_r295_trial_no_code_legacy_reports():
    """★ 无 code⇒老报数路（fake llm 报数，mode=report，零变）。"""
    import json as _json
    j = Judge()
    skel = {"average": [[[0.1, 0.2], None], [[1.1, 2.2], None]]}
    from dwc.llm.executor import obs_skeleton
    assert obs_skeleton(j.anchors, "code_fix_007") == skel
    _llm = _fake_llm(_json.dumps(
        {"average": [[[0.1, 0.2], 0.15000000000000002],
                     [[1.1, 2.2], 1.6500000000000001]]}))
    r = EVO._real_trial(j, _llm, "code_fix_007", "p", code=None)
    assert r["success"] is True, r
    assert r["mode"] == "report", r


def test_r295_trial_non_code_repair_ignores_code():
    """★ 非 code_repair 任务有 code 也走老路（分流口径=category，禁扩散）。"""
    import json as _json
    j = Judge()
    _llm = _fake_llm(_json.dumps({}))
    r = EVO._real_trial(j, _llm, "reasoning_001", "p", code=CODE_007)
    assert r["mode"] == "report", r


def test_r295_raises_quota_sandbox_import():
    """★ raises 配额：沙箱禁 import 大声炸（执行通道安全门）。"""
    from dwc.llm.sandbox import SandboxError, run_code_observed
    with pytest.raises(SandboxError):
        run_code_observed("import sys\ndef f(x):\n    return x\n",
                          {"f": [[1, None]]})
