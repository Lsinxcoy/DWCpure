# -*- coding: utf-8 -*-
"""★ R342 · patch 层 dedup 不崩（无 LLM 路径）。"""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))


class _Judge:
    anchors = {"code_fix_001": {"expected_behavior": "sum_first_n(3)==6"}}


def test_r342_dedup_no_crash():
    import dwc_evo_round as E
    from dwc.organs.evolver import Evolver, LLMMutator
    db = os.path.join(os.path.expanduser("~"), ".dwc", "var", "dwc_prod.sqlite")
    if not os.path.exists(db):
        pytest.skip("本机无生产记忆库（CI 正常）")
    mu = LLMMutator(llm=None)
    rep = E.run_round(db, Evolver(), mu, "ctx",
                      lambda t, p, code=None: {"success": None},
                      apply=False, rules_path="",
                      fn_of=lambda r: "average",
                      task_of=lambda r: "code_fix_007",
                      reproducible_only=False,
                      max_clusters=1)
    assert isinstance(rep, dict)
    assert "results" in rep
