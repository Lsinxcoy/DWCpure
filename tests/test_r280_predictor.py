# -*- coding: utf-8 -*-
"""★★★ R280 · predictor 接生产（观测喂数＋Brier 可算）。

★ 隔离：log/ckpt 全走 tmp；禁碰生产 var。
★ 判分落点只增 observe 调用（append-only），判分语义零改。
"""
import json as _json
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(_HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.organs.predictor import OutcomePredictor


def _p(tmp_path, name="p.jsonl"):
    return OutcomePredictor(log_path=str(tmp_path / name))


class TestObserve:
    def test_task_key_roundtrip(self, tmp_path):
        p = _p(tmp_path)
        assert p.predict("task:code_fix_007")["p"] == 0.5  # 先验
        p.observe("task:code_fix_007", False, evidence_ref="t1")
        p.observe("task:code_fix_007", True, evidence_ref="t2")
        r = p.predict("task:code_fix_007")
        assert r["n"] == 2 and r["source"] == "ledger"
        assert abs(r["p"] - 0.5) < 1e-9  # 1胜1负 ⇒ 后验均值仍 0.5 但 n=2

    def test_two_wins_shifts_p(self, tmp_path):
        p = _p(tmp_path)
        p.observe("task:x", True)
        p.observe("task:x", True)
        assert _p(tmp_path) is not p  # 新实例读同一文件前先落盘
        assert p.predict("task:x")["p"] > 0.5

    def test_brier_computable(self, tmp_path):
        p = _p(tmp_path)
        for ok in (True, True, False, True):
            p.observe("task:y", ok)
        c = p.calibrate()
        assert c["n"] == 4 and c["brier"] is not None
        assert 0.0 <= c["brier"] <= 1.0

    def test_replay_rebuilds(self, tmp_path):
        p = _p(tmp_path)
        p.observe("task:z", True)
        p.observe("task:z", False)
        q = OutcomePredictor(log_path=str(tmp_path / "p.jsonl"))
        assert q.predict("task:z")["n"] == 2  # 重放恢复，不靠内存

    def test_empty_calibrate_honest(self, tmp_path):
        c = _p(tmp_path).calibrate()
        assert c == {"n": 0, "brier": None, "note": "无观测"}

    def test_tree_key_rejected(self, tmp_path):
        with pytest.raises(Exception):
            _p(tmp_path).observe("tree:t/n", True)
