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


class _FakeOP:
    def __init__(self):
        self.calls = []

    def observe(self, key, ok, evidence_ref=""):
        self.calls.append((key, ok, evidence_ref))


class TestFeedPredictor:
    """★★★ R287 · 逐 task 喂数（修整轮一票否决）。

    ★ 前置：run_term._feed_predictor(details, db_path, task, op_factory)
      纯函数（提纯自内联块，语义零改）。红测时它不存在 ⇒ AttributeError。
    """

    def test_mixed_round_feeds_decided_only(self, tmp_path):
        from dwc.harness.run_term import _feed_predictor
        fake = _FakeOP()
        n = _feed_predictor(
            [{"task_id": "a", "success": True},
             {"task_id": "b", "success": None},
             {"task_id": "c", "success": False}],
            str(tmp_path), "round_x", op_factory=lambda p: fake)
        assert n == 2, "True/False 各喂一条，None 跳过"
        assert [c[0] for c in fake.calls] == ["task:a", "task:c"]
        assert [c[1] for c in fake.calls] == [True, False]

    def test_all_none_feeds_zero_loud(self, tmp_path):
        from dwc.harness.run_term import _feed_predictor
        fake = _FakeOP()
        n = _feed_predictor([{"task_id": "a", "success": None}],
                            str(tmp_path), "round_x",
                            op_factory=lambda p: fake)
        assert n == 0 and fake.calls == []


class TestFeedCredit:
    """★★★ R287-D · credit 首个生产 record 调用（内存有数，落盘下一步）。

    ★ 前置：run_term._feed_credit(details, task, ledger) 纯函数；
      ledger 是 CreditLedger 真类（零真 LLM，本来就是纯数据结构）。
    """

    def test_decided_tasks_recorded(self):
        from dwc.harness.run_term import _feed_credit
        from dwc.organs.credit import CreditLedger
        led = CreditLedger()
        n = _feed_credit([{"task_id": "a", "success": True},
                          {"task_id": "b", "success": None},
                          {"task_id": "c", "success": False}],
                         "round_x", led)
        assert n == 2
        assert led.summary()["n"] == 2
        assert led.summary()["n_winner"] == 1

    def test_no_ledger_skips_loud(self):
        from dwc.harness.run_term import _feed_credit
        assert _feed_credit([{"task_id": "a", "success": True}],
                            "round_x", None) == 0
