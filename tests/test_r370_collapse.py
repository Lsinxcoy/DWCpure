# -*- coding: utf-8 -*-
"""★ Phase 1.3 · collapse 判定回归测试。"""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import dwc_agent as A

def test_collapse_not_triggered_first_low():
    trig, c = A.collapse_triggered(0.5, 0.05, 0)
    assert trig is False
    assert c == 1

def test_collapse_triggered_second_low():
    trig, c = A.collapse_triggered(0.5, 0.05, 1)
    assert trig is True
    assert c == 2

def test_collapse_reset_on_recovery():
    trig, c = A.collapse_triggered(0.5, 0.5, 1)
    assert trig is False
    assert c == 0

def test_collapse_synthetic_never_triggers():
    trig, c = A.collapse_triggered(0.5, 0.05, 1, synthetic=True)
    assert trig is False
    assert c == 0

def test_collapse_no_trigger_without_history():
    trig, c = A.collapse_triggered(0.0, 0.05, 0)
    assert trig is False
