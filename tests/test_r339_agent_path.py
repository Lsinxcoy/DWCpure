# -*- coding: utf-8 -*-
"""★ R339 · trial 支持可插拔 agent 路径（fail-closed）。"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))


class _Judge:
    anchors = {}
    def task_scores(self, split=None):
        return []


def test_r339_agent_executor_used():
    import dwc_evo_round as E
    calls = {}

    def exec_fn(task, patch, code):
        calls["n"] = calls.get("n", 0) + 1
        return {"success": True, "in_score": 1.0, "held_out": 1.0}

    r = E._real_trial(_Judge(), None, "code_fix_007", "patch", agent_executor=exec_fn)
    assert calls["n"] == 1
    assert r["mode"] == "agent"
    assert r["success"] is True


def test_r339_agent_executor_fail_closed():
    import dwc_evo_round as E

    def exec_fn(task, patch, code):
        return None

    r = E._real_trial(_Judge(), None, "code_fix_007", "patch", agent_executor=exec_fn)
    assert r["success"] is None
    assert r["mode"] == "agent"
