# -*- coding: utf-8 -*-
"""★★★ R276 · 进化第一轮跑通（三根线：回灌／落地落盘／账落盘）。

★ 隔离：memory 用 fake；Mutator.LEARNED_PATH→tmp；
  consolidate 用的合成键事后 pop；不碰生产 rules.json/lessons。
★ 零真 LLM：Loop(use_llm=False)＋合成 proposal/trial。
"""
import io
import json as _json
import os as _os
import types as _types

import pytest

from dwc.harness.loop import Loop
from dwc.organs.evolver import Mutator
from dwc.organs.memory import MemoryKernel as Memory, MemoryError


class _FakeMem:
    def __init__(self):
        self.rows = []

    def remember(self, kind, payload, chain_id=None, node_id=None):
        self.rows.append((str(kind), dict(payload)))
        return "fake-%d" % len(self.rows)


class _BadMem:
    def remember(self, *a, **k):
        raise OSError("库坏了")


def _sig(**kw):
    d = {"c": "E_T", "q": "t_q", "m": "t_m", "fn": "sum_first_n"}
    d.update(kw)
    return d


class TestRememberWire:
    def test_no_memory_is_zero(self):
        assert Loop()._remember_failure("t1", [_sig()]) == 0

    def test_fail_sig_written(self):
        lp, fm = Loop(), _FakeMem()
        assert lp.attach_memory(fm) is fm
        assert lp._remember_failure("t1", [_sig(), _sig(m="m2")]) == 2
        kinds = [k for k, _ in fm.rows]
        assert all("FAILURE_SIGNATURE" in k for k in kinds)
        assert fm.rows[0][1]["c"] == "E_T" and fm.rows[0][1]["task"] == "t1"

    def test_missing_keys_skipped(self):
        lp, fm = Loop(), _FakeMem()
        lp.attach_memory(fm)
        assert lp._remember_failure("t1", [{"c": "E_T"}, None, {}]) == 0
        assert fm.rows == []

    def test_bad_memory_never_breaks_diagnose(self):
        lp = Loop()
        lp.attach_memory(_BadMem())
        assert lp._remember_failure("t1", [_sig()]) == 0


class TestConsolidateFlush:
    def test_land_flushes_to_disk(self, tmp_path, monkeypatch):
        lp = Loop()
        monkeypatch.setattr(Mutator, "LEARNED_PATH",
                            str(tmp_path / "rules.json"))
        # ★ R285 · 环境假设修正：R278 起仓库 config/anchors/rules.json 有
        #   影子（跨根 learned 可见性所需）⇒ "生产 rules 不存在"已永久失效。
        #   本意是"consolidate 不碰生产" ⇒ 改为快照对比（存在则 mtime+size，
        #   不存在则哨兵），行为本质不变。
        _repo = _os.path.dirname(_os.path.dirname(
            _os.path.abspath(__file__)))
        _prod = _os.path.join(_repo, "config", "anchors", "rules.json")
        _before = ((_os.path.getmtime(_prod), _os.path.getsize(_prod))
                   if _os.path.exists(_prod) else None)
        sig = _sig(c="E_R276", q="r276_q")
        key = Mutator.key_for(sig)
        prop = _types.SimpleNamespace(component="control_flow",
                                      dimension="D1",
                                      target_layer="assets",
                                      patch="return 1")
        trial = {"impl": "def f(): return 1", "success": True}
        try:
            out = lp._consolidate_rule("code_fix_001", sig, prop, trial,
                                       _types.SimpleNamespace())
        finally:
            Mutator.RULES.pop(key, None)
        assert out["outcome"] == "consolidated", out
        assert out.get("flushed") is True
        disk = _json.load(io.open(str(tmp_path / "rules.json"),
                                  encoding="utf-8"))
        assert key in disk["learned"]
        assert key not in Mutator.RULES  # ★ 内存恢复（不污染后续测试）
        _after = ((_os.path.getmtime(_prod), _os.path.getsize(_prod))
                  if _os.path.exists(_prod) else None)
        assert _after == _before, "consolidate 碰了生产 rules.json"


class TestCreditPersist:
    def test_entries_append_jsonl(self, tmp_path, monkeypatch):
        lp = Loop()
        p = tmp_path / "credit_ledger.jsonl"
        monkeypatch.setattr(lp, "_var_path", lambda _n: str(p))
        lp._last_ledger_entries = [{"k": "v1"}, {"k": "v2"}]
        assert lp._persist_credit("t9", 7) == 2
        rows = [ _json.loads(l) for l in
                 io.open(str(p), encoding="utf-8") if l.strip()]
        assert len(rows) == 2 and rows[0]["round"] == 7
        assert rows[0]["task"] == "t9"

    def test_empty_ledger_returns_zero(self, tmp_path, monkeypatch):
        lp = Loop()
        monkeypatch.setattr(lp, "_var_path",
                            lambda _n: str(tmp_path / "c.jsonl"))
        lp._last_ledger_entries = []
        assert lp._persist_credit("t9", 7) == 0


class TestDestructive:
    def test_remember_bad_kind_raises(self):
        m = Memory(":memory:")
        with pytest.raises(MemoryError):
            m.remember("不是Kind", {"c": "x"})

    def test_remember_missing_cqm_raises(self):
        m = Memory(":memory:")
        with pytest.raises(MemoryError):
            from dwc.organs.memory import MemoryKind
            m.remember(MemoryKind.FAILURE_SIGNATURE, {"c": "x"})
