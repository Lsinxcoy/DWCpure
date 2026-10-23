# -*- coding: utf-8 -*-
"""★ R337 · 组织级 RSI 传播验证脚本可运行。"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))


def test_r337_verify_runs():
    import verify_inbox_propagation as V
    db = os.path.join(os.path.expanduser("~"), ".dwc", "var", "dwc_prod.sqlite")
    prod = os.path.join(os.path.expanduser("~"), ".dwc")
    r = V.verify(db, prod)
    assert "checked" in r and "verified" in r and "results" in r
    assert isinstance(r["results"], list)
