# -*- coding: utf-8 -*-
"""★ R336 · recursive-progress 轻量 ablation 审计可运行。"""
import importlib.util
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))


def test_r336_audit_runs():
    import audit_recursive_progress as A
    db = os.path.join(os.path.expanduser("~"), ".dwc", "var", "dwc_prod.sqlite")
    if not os.path.exists(db):
        pytest.skip("本机无生产记忆库（CI 正常）")
    r = A.audit(db)
    assert set(r.keys()) == {"n_unmapped_with_inheritance",
                             "n_unmapped_without_inheritance",
                             "improver_gain_proxy", "verdict"}
    assert r["verdict"] in {"improver_gain", "no_improver_gain",
                            "inheritance_hurts"}
    assert r["improver_gain_proxy"] == (
        r["n_unmapped_without_inheritance"] - r["n_unmapped_with_inheritance"])
