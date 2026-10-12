# -*- coding: utf-8 -*-
"""R212 · 基准器: verifier 真值动态算 + 机判判据（度量引擎的度量）。"""
from __future__ import annotations

import importlib.util
import io
import json
import os
import sys

ROOT = r"E:\Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "src"))
spec = importlib.util.spec_from_file_location(
    "dwc_bench", os.path.join(ROOT, "scripts", "dwc_bench.py"))
B = importlib.util.module_from_spec(spec)
spec.loader.exec_module(B)


def test_truth_rung3_matches_machine_count():
    """★★★ 真值动态算: verifier_rung==3 计数（Layer 22 校准过的判据 —
    首版查错键名 "rung" 误得 0, 现与机器计数一致）。"""
    import ast
    data = json.loads(io.open(
        os.path.join(ROOT, "config", "anchors", "dev.json"),
        encoding="utf-8").read())
    expect = sum(1 for t in data.values()
                 if isinstance(t, dict) and t.get("verifier_rung") == 3)
    assert B._truth_rung3() == expect and expect >= 1


def test_verifier_mult3_judges_artifact_not_report():
    """★★★ verifier 机判产物文件（不看 LLM 自述 — 内容 vs 动态真值）。"""
    os.makedirs(B.WORK, exist_ok=True)
    io.open(os.path.join(B.WORK, "mult3.py"), "w", encoding="utf-8"
            ).write("print(33)")
    ok, detail = B.v_run_mult3({"status": "done"})
    assert ok, detail
    io.open(os.path.join(B.WORK, "mult3.py"), "w", encoding="utf-8"
            ).write("print(34)")
    ok2, _ = B.v_run_mult3({"status": "done"})
    assert not ok2, "错产物也判过 — verifier 失明"


def test_verifier_missing_artifact_fails():
    """★ 产物缺失必 fail（"宣称完成但没写文件" 的判据）。"""
    p = os.path.join(B.WORK, "dualsym.txt")
    if os.path.exists(p):
        os.remove(p)
    ok, _ = B.v_dual_symbol({"status": "done"})
    assert not ok


def test_verifier_gitsha_matches_live_repo():
    """★ gitsha verifier 与活仓库 HEAD 逐字节一致（真值实时取）。"""
    import subprocess
    truth = subprocess.run(["git", "-C", ROOT, "rev-parse", "HEAD"],
                           capture_output=True, text=True, timeout=30
                           ).stdout.strip()
    os.makedirs(B.WORK, exist_ok=True)
    io.open(os.path.join(B.WORK, "gitsha.txt"), "w", encoding="utf-8"
            ).write(truth)
    ok, d = B.v_gitsha({"status": "done"})
    assert ok, d
