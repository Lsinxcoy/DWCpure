# -*- coding: utf-8 -*-
"""★ R354 · Trajectory recovery (prefix continuation field)."""
import os
import sys

ROOT = "E:/Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))


class _Judge:
    anchors = {}
    def task_scores(self, split=None):
        return []
    def held_out_peer(self, t):
        return None
    def evaluate(self, task, split, observed=None):
        class _R:
            success = True
        return _R()


def test_r354_recovery_field_present():
    import dwc_evo_round as E
    r = E._real_trial(_Judge(), None, "code_fix_007", "patch",
                      agent_executor=lambda t, p, c: {"success": True, "in_score": 1.0})
    assert "recovery_attempted" in r
