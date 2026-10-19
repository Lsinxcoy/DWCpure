# -*- coding: utf-8 -*-
"""★ Phase 3.1 · benchmark_fitness 回归测试。"""
import os, sys
ROOT = "E:/Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "src"))
from dwc.organs.benchmark_fitness import external_score, calibration, fitness_signal

def test_external_score_rate():
    r = {"rate": 0.25, "results": [{"resolved": True}, {"resolved": False}]}
    assert abs(external_score(r) - 0.25) < 1e-9

def test_external_score_from_results():
    r = {"results": [{"resolved": True}, {"resolved": True}, {"resolved": False}]}
    assert abs(external_score(r) - 2/3) < 1e-9

def test_external_score_empty():
    assert external_score({}) == 0.0

def test_calibration_aligned():
    c = calibration(0.2, 0.18)
    assert c["verdict"] == "aligned"

def test_calibration_overestimates():
    c = calibration(0.5, 0.176)
    assert c["verdict"] == "internal_overestimates"
    assert c["delta"] > 0

def test_fitness_signal():
    r = {"rate": 0.176, "results": [{} for _ in range(17)]}
    sig = fitness_signal(r, 0.5)
    assert sig["fitness"] == 0.176
    assert sig["n_instances"] == 17
