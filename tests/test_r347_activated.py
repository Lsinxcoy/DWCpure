# -*- coding: utf-8 -*-
"""★ R347 · trial 记录 activated (Raven activation gate)。"""
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


def test_r347_activated_present():
    import dwc_evo_round as E
    r = E._real_trial(_Judge(), None, "code_fix_007", "patch",
                      agent_executor=lambda t, p, c: {"success": True, "in_score": 1.0})
    assert "activated" in r
    assert r["activated"] is True
