# -*- coding: utf-8 -*-
"""R295-Task1 · 沙箱 run_code_observed（code_repair 写码真执行）。

★ B 路线第一步：LLM 写码→沙箱真跑出 observed→复用 judge.evaluate。
★ 测试零真 LLM（fake 代码串）；raises 配额≥5%（恶意代码必须大声炸）。
"""
from __future__ import annotations

import pytest


def test_r295_sandbox_runs_code_to_observed():
    """★★ 正常路：average 代码真跑出 observed（007 本题必过是此语义保证）。"""
    from dwc.llm.sandbox import run_code_observed
    code = "def average(xs):\n    return sum(xs)/len(xs) if xs else 0.0\n"
    skel = {"average": [[[0.1, 0.2], None], [[1.1, 2.2], None]]}
    obs = run_code_observed(code, skel)
    assert obs == {"average": [[[0.1, 0.2], 0.15000000000000002],
                               [[1.1, 2.2], 1.6500000000000001]]}


def test_r295_sandbox_import_rejected():
    """★ 禁 import（沙箱禁网禁文件第一道门）。"""
    from dwc.llm.sandbox import SandboxError, run_code_observed
    with pytest.raises(SandboxError):
        run_code_observed("import os\ndef average(xs):\n    return 0.15\n",
                          {"average": [[[0.1, 0.2], None]]})


def test_r295_sandbox_open_rejected():
    """★ 禁 open（文件开口不开）。"""
    from dwc.llm.sandbox import SandboxError, run_code_observed
    with pytest.raises(SandboxError):
        run_code_observed("def average(xs):\n    open('/tmp/x')\n    return 0.15\n",
                          {"average": [[[0.1, 0.2], None]]})


def test_r295_sandbox_dunder_rejected():
    """★ 禁双下划线属性（逃逸口不开）。"""
    from dwc.llm.sandbox import SandboxError, run_code_observed
    with pytest.raises(SandboxError):
        run_code_observed("def average(xs):\n    return ().__class__\n",
                          {"average": [[[0.1, 0.2], None]]})


def test_r295_sandbox_while_rejected():
    """★ 禁 while（无限循环 AST 层拒，不靠超时碰运气）。"""
    from dwc.llm.sandbox import SandboxError, run_code_observed
    with pytest.raises(SandboxError):
        run_code_observed("def average(xs):\n    while True:\n        pass\n",
                          {"average": [[[0.1, 0.2], None]]})


def test_r295_sandbox_missing_fn_returns_none():
    """★ 代码里没被测函数⇒None＋reason（不炸，trial 侧判未评价）。"""
    from dwc.llm.sandbox import run_code_observed
    assert run_code_observed("def other(x):\n    return 1\n",
                             {"average": [[[0.1, 0.2], None]]}) is None


def test_r295_sandbox_raises_quota_sixth():
    """★ raises 配额第 6 枪：exec/eval 内建调用⇒炸。"""
    from dwc.llm.sandbox import SandboxError, run_code_observed
    with pytest.raises(SandboxError):
        run_code_observed("def average(xs):\n    return eval('0.15')\n",
                          {"average": [[[0.1, 0.2], None]]})
