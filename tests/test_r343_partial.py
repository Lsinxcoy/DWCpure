# -*- coding: utf-8 -*-
"""★ R343 · trial 记录 partial credit（Terminal-RSI SPR partial subordinate）。"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))


class _Judge:
    anchors = {}
    def task_scores(self, split=None):
        return []
    def held_out_peer(self, t):
        return None


def test_r343_partial_present():
    import dwc_evo_round as E
    r = E._real_trial(_Judge(), None, "code_fix_007", "patch",
                      agent_executor=lambda t, p, c: {"success": True, "in_score": 1.0})
    assert "partial" in r
    assert r["partial"] == 1.0
