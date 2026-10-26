# -*- coding: utf-8 -*-
"""★ R341 · archive priors 注入 search（不崩 + 可关闭）。"""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))


def test_r341_archive_priors_toggle():
    import dwc_evo_round as E
    db = os.path.join(os.path.expanduser("~"), ".dwc", "var", "dwc_prod.sqlite")
    if not os.path.exists(db):
        pytest.skip("本机无生产记忆库（CI 正常）")
    from dwc.organs.evolver import Evolver
    ev = Evolver()
    r1 = E.collect_unmapped(db, ev, lambda r: "average",
                            lambda r: "code_fix_007",
                            reproducible_only=False,
                            use_archive_priors=True)
    r2 = E.collect_unmapped(db, ev, lambda r: "average",
                            lambda r: "code_fix_007",
                            reproducible_only=False,
                            use_archive_priors=False)
    assert isinstance(r1, list) and isinstance(r2, list)
