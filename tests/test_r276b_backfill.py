# -*- coding: utf-8 -*-
"""★★★ R276b · 开回灌：判分→EXPERIENCE 生产回灌（run_term 收尾）。

★ 隔离：TermRunner 默认 :memory: 库；合成 verdict dict；零真 LLM。
★ 口径：success is False 才记（None 跳过）；D6 要 c/q/m。
"""
import pytest

from dwc.harness.run_term import TermRunner, TermReport
from dwc.organs.memory import MemoryKind


def _v(fail=({"c": "E_X", "q": "x_q", "m": "x_m", "fn": "f"},
             "t1", False),
       extra=()):
    ds = [{"task_id": tid, "success": ok,
           "failure_signature": dict(sig) if sig else None,
           "sigs": [dict(sig)] if sig else []}
          for sig, tid, ok in [fail, *extra]]
    return {"pass_rate": 0.5, "details": ds}


class TestBackfill:
    def test_fail_is_remembered(self):
        rt = TermRunner()
        assert rt._backfill_failures(_v()) == 1
        ids = rt.memory.by_signature("E_X", "x_q", "x_m")
        assert len(ids) == 1
        node = rt.memory.get(ids[0])
        assert node.payload["task"] == "t1"

    def test_none_and_pass_skipped(self):
        rt = TermRunner()
        v = _v(extra=[(None, "t2", None),
                      ({"c": "E_Y", "q": "y", "m": "y"}, "t3", True)])
        assert rt._backfill_failures(v) == 1

    def test_missing_keys_skipped(self):
        rt = TermRunner()
        v = _v(fail=({"c": "E_X"}, "t1", False))
        assert rt._backfill_failures(v) == 0

    def test_empty_verdict_is_zero(self):
        assert TermRunner()._backfill_failures({}) == 0
        assert TermRunner()._backfill_failures(None) == 0

    def test_report_field_defaults_zero(self):
        import time as _t
        rep = TermReport(term_id="t", chain_id="c",
                         started_at=_t.time())
        assert rep.evo_backfilled == 0

    def test_remember_kind_is_failure_signature(self):
        rt = TermRunner()
        rt._backfill_failures(_v())
        kinds = {r["kind"] for r in
                 rt.memory._conn.execute("select kind from memory_node")}
        assert kinds == {MemoryKind.FAILURE_SIGNATURE.value}

    def test_broken_memory_never_breaks_term(self):
        rt = TermRunner()
        def _boom(*a, **k):
            raise OSError("库坏了")
        rt.memory.remember = _boom
        assert rt._backfill_failures(_v()) == 0
