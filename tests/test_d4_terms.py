# -*- coding: utf-8 -*-
"""★ D4 · 术语对齐（18813 四段 diagnose/propose/assess/admit）。

锁：run_round docstring 四段映射＋四段行内注释在位（删即红）。
口径：旧函数名保留（collect_unmapped 被 r278 测试直调 —— 对齐先行
术语，真改名另轮）；行为零改只改名面注释。
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import dwc_evo_round as E


def test_d4_four_stages_named():
    doc = E.run_round.__doc__ or ""
    for stage in ("diagnose", "propose", "assess", "admit"):
        assert stage in doc, stage
    src = open(os.path.join(ROOT, "scripts", "dwc_evo_round.py"),
               encoding="utf-8").read()
    for tag in ("D4-① diagnose", "D4-② propose",
                "D4-③ assess", "D4-④ admit"):
        assert tag in src, tag
