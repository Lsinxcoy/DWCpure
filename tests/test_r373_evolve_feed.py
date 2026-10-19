# -*- coding: utf-8 -*-
"""R370 · B2 — 失败签名喂给 evolver（灰度开关）。

定位声明（DWC-AUTO · 进化系统）
  锁的是「生产 term 的失败签名有没有真进进化系统」这条通路：
  开关关 ⇒ 不调 diagnose（但状态可审计）；开关开 ⇒ 真调且产物可审计；
  签名不全 / 超限 ⇒ 不喂 / 截断，且如实计数。

★ 这条通路在 B2 之前**不存在**：run_term 的失败签名只回灌 EXPERIENCE
  记忆（_backfill_failures），evolver 在生产上零输入。
"""
from __future__ import annotations

import os
import sys

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if os.path.join(_ROOT, "src") not in sys.path:
    sys.path.insert(0, os.path.join(_ROOT, "src"))

from dwc.core import DWC  # noqa: E402
from dwc.harness.run_term import TermReport  # noqa: E402


# ══════════════════════════════════════════════════════════════════
# 夹具
# ══════════════════════════════════════════════════════════════════

class _FakeEvolver:
    def __init__(self, proposals=None, raises=None):
        self.calls = []
        self.proposals = proposals or []
        self.raises = raises

    def diagnose(self, sigs):
        self.calls.append(list(sigs))
        if self.raises:
            raise self.raises
        return {"proposals": self.proposals,
                "unmapped": [], "n_unmapped": 0, "n_clusters": 1}


class _P:
    """Proposal 的最小替身（只带落盘需要的字段）。"""

    def __init__(self, sig, patch="x"):
        self.failure_signature = dict(sig)
        self.proposal_id = "P1"
        self.component = "assets"
        self.target = "t"
        self.patch = patch
        self.rationale = "r"
        self.operator = "improve"
        self.target_layer = ""


@pytest.fixture(autouse=True)
def _isolate_proposals(tmp_path, monkeypatch):
    """★ 提案落盘必须隔离 —— 测试写进生产 var/ 会污染真实提案账。"""
    from dwc.harness import evo_proposals
    monkeypatch.setattr(evo_proposals, "DEFAULT_PATH",
                        str(tmp_path / "evo_proposals.jsonl"))


class _Host:
    """只借 DWC._feed_evolver，不构造整个 DWC（避免加载全部器官）。"""

    _feed_evolver = DWC._feed_evolver

    def __init__(self, evolver):
        self.evolver = evolver


def _rep(details):
    return TermReport(term_id="T1", chain_id="C1", started_at=0.0,
                      judgement={"details": details})


def _cfg(monkeypatch, feed, limit=50):
    from dwc.foundation import dial_config as dc
    monkeypatch.setattr(dc, "load_evolution",
                        lambda path=None: {"feed_from_terms": feed,
                                           "max_sigs_per_term": limit})


def _fail(sig=None, task_id="t1"):
    d = {"task_id": task_id, "success": False}
    if sig is not None:
        d["sigs"] = [sig]
    return d


# ══════════════════════════════════════════════════════════════════
# 1. 灰度关：不调 diagnose，但状态可审计
# ══════════════════════════════════════════════════════════════════

def test_feed_disabled_does_not_call_diagnose(monkeypatch):
    _cfg(monkeypatch, feed=False)
    ev = _FakeEvolver()
    out = _Host(ev)._feed_evolver(
        _rep([_fail({"c": "wrong", "q": "dev", "m": "x"})]))

    assert out["enabled"] is False
    assert "feed_from_terms=false" in out["why"]
    assert ev.calls == [], "关着就不许调 diagnose"


# ══════════════════════════════════════════════════════════════════
# 2. 灰度开：真调，且产物可审计
# ══════════════════════════════════════════════════════════════════

def test_feed_enabled_calls_diagnose_with_cqf(monkeypatch):
    _cfg(monkeypatch, feed=True)
    ev = _FakeEvolver(proposals=[
        _P({"c": "wrong", "q": "dev", "fn": "t1"}),
        _P({"c": "wrong", "q": "dev", "fn": "t1"}),
    ])
    out = _Host(ev)._feed_evolver(
        _rep([_fail({"c": "wrong", "q": "dev", "m": "assert 1==2"},
                    task_id="t1")]))

    assert out["enabled"] is True
    assert out["n_sigs"] == 1
    assert out["n_proposals"] == 2
    assert out["n_dropped"] == 0
    assert out["n_persisted"] == 2, "★ B3: 提案必须落盘（否则被 _seen 去重后丢失）"
    assert ev.calls and ev.calls[0][0]["fn"] == "t1"
    assert ev.calls[0][0]["m"] == "assert 1==2"
    assert ev.calls[0][0]["task"] == "t1"


# ══════════════════════════════════════════════════════════════════
# 3. 签名不全：不喂（diagnose 的查询键是 c/q/fn）
# ══════════════════════════════════════════════════════════════════

def test_feed_skips_sig_without_fn(monkeypatch):
    """sig 无 fn 且观测无 task_id ⇒ 查询键不全 ⇒ 不喂，不硬调。"""
    _cfg(monkeypatch, feed=True)
    ev = _FakeEvolver()
    out = _Host(ev)._feed_evolver(
        _rep([_fail({"c": "wrong", "q": "dev", "m": "x"}, task_id="")]))

    assert out["enabled"] is True
    assert out["n_sigs"] == 0
    assert "无可用失败签名" in out["why"]
    assert ev.calls == []


def test_feed_skips_sig_without_cq(monkeypatch):
    _cfg(monkeypatch, feed=True)
    ev = _FakeEvolver()
    out = _Host(ev)._feed_evolver(
        _rep([_fail({"m": "x"}, task_id="t1")]))

    assert out["n_sigs"] == 0
    assert ev.calls == []


def test_feed_skips_success_none_and_true(monkeypatch):
    """success is True/None 都不喂（None 是「未评价」，不是失败）。"""
    _cfg(monkeypatch, feed=True)
    ev = _FakeEvolver()
    out = _Host(ev)._feed_evolver(_rep([
        {"task_id": "t1", "success": True,
         "sigs": [{"c": "wrong", "q": "dev"}]},
        {"task_id": "t2", "success": None,
         "sigs": [{"c": "wrong", "q": "dev"}]},
    ]))

    assert out["n_sigs"] == 0
    assert ev.calls == []


# ══════════════════════════════════════════════════════════════════
# 4. 超限截断：如实记 n_dropped
# ══════════════════════════════════════════════════════════════════

def test_feed_truncates_to_limit(monkeypatch):
    _cfg(monkeypatch, feed=True, limit=2)
    ev = _FakeEvolver()
    details = [_fail({"c": "c%d" % i, "q": "dev"}, task_id="t%d" % i)
               for i in range(5)]

    out = _Host(ev)._feed_evolver(_rep(details))

    assert out["n_sigs"] == 2
    assert out["n_dropped"] == 3
    assert len(ev.calls[0]) == 2


# ══════════════════════════════════════════════════════════════════
# 5. diagnose 抛异常：留痕不崩
# ══════════════════════════════════════════════════════════════════

def test_feed_diagnose_error_is_recorded(monkeypatch):
    _cfg(monkeypatch, feed=True)
    ev = _FakeEvolver(raises=ValueError("boom"))
    out = _Host(ev)._feed_evolver(
        _rep([_fail({"c": "wrong", "q": "dev"}, task_id="t1")]))

    assert out["enabled"] is True
    assert "ValueError" in out["error"]
    assert "boom" in out["error"]
    assert out["n_sigs"] == 1


# ══════════════════════════════════════════════════════════════════
# 6. 配置契约：必填无默认
# ══════════════════════════════════════════════════════════════════

def test_load_evolution_requires_both_keys(tmp_path):
    from dwc.foundation.dial_config import DialError, load_evolution
    p = tmp_path / "e.yaml"
    p.write_text("version: 1\nevolution:\n  feed_from_terms: true\n",
                 encoding="utf-8")
    with pytest.raises(DialError):
        load_evolution(str(p))


def test_load_evolution_rejects_non_bool(tmp_path):
    from dwc.foundation.dial_config import DialError, load_evolution
    p = tmp_path / "e.yaml"
    p.write_text("evolution:\n  feed_from_terms: 1\n"
                 "  max_sigs_per_term: 10\n", encoding="utf-8")
    with pytest.raises(DialError):
        load_evolution(str(p))


def test_load_evolution_rejects_zero_limit(tmp_path):
    from dwc.foundation.dial_config import DialError, load_evolution
    p = tmp_path / "e.yaml"
    p.write_text("evolution:\n  feed_from_terms: true\n"
                 "  max_sigs_per_term: 0\n", encoding="utf-8")
    with pytest.raises(DialError):
        load_evolution(str(p))


def test_real_config_is_off_by_default():
    """★ 生产配置当前必须是关 —— 打开要用户拍板，不许偷偷开。"""
    from dwc.foundation.dial_config import load_evolution
    cfg = load_evolution()
    assert cfg["feed_from_terms"] is False
    assert cfg["max_sigs_per_term"] >= 1


# ══════════════════════════════════════════════════════════════════
# 7. 接线级：生产入口 DWC.run_term 真的调它
# ══════════════════════════════════════════════════════════════════

def test_run_term_wires_evo_feed(monkeypatch):
    """★ 不是测 _feed_evolver 本身 —— 是测「生产入口真的调它」。

    `scripts/dwc_agent.py:688` 调的就是 `d.run_term`；
    所以这里打桩 runner（不跑六层链），只验接线存在。
    """
    from dwc.organs.judge import TaskScoreStore

    d = DWC(depth_limit=3, max_nodes=50)
    d.judge.store = TaskScoreStore(dw_version="test")

    rep = _rep([_fail({"c": "wrong", "q": "dev"}, task_id="t1")])
    d.runner.run_term = lambda task, n_steps=3, **kw: rep
    monkeypatch.setattr(d, "_snapshot_worlds", lambda: 0)

    # 关：仍然写 evo_feed（可审计的「关」）
    _cfg(monkeypatch, feed=False)
    out = d.run_term("t1", n_steps=1)
    assert out is rep
    assert out.evo_feed["enabled"] is False

    # 开：真调
    _cfg(monkeypatch, feed=True)
    ev = _FakeEvolver()
    d.evolver = ev
    out2 = d.run_term("t1", n_steps=1)
    assert out2.evo_feed["enabled"] is True
    assert out2.evo_feed["n_sigs"] == 1
    assert len(ev.calls) == 1
