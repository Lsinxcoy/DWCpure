# -*- coding: utf-8 -*-
"""★ A4 · J 保护机器化（G8＋K5：evo 侧写 judge/anchor 即红）。

锁：
1. 现状干净：gate8_contract() 0 违规（含 K5 扫描三文件）。
2. K5 口径：禁写名（judge.py/dev.json/test_sealed.json/task_scores.jsonl
   等 9 个）出现在 evo 侧 open 行＋写标志才红；rules.json/ledger/纯读放行。
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import gate as G


def test_a4_k5_clean():
    r = G.gate8_contract()
    assert r["pass"] is True
    assert r["violations"] == []


def test_a4_k5_guarded_names():
    import inspect
    src = inspect.getsource(G.gate8_contract)
    for name in ("judge.py", "dev.json", "test_sealed.json",
                 "task_scores.jsonl", "evidence.jsonl"):
        assert name in src
    assert "K5 J 被写" in src
    # 放行项在注释/逻辑里：rules.json 与 ledger 不在禁写集
    assert "rules.json" in src
