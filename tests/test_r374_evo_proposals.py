# -*- coding: utf-8 -*-
"""R370 · B3 — 提案落盘 + evo_round 消费。

定位声明（DWC-AUTO · 进化系统）
  B2 让 live term 把签名喂进 diagnose，但产物只返回一次（Evolver._seen
  会按 key 去重）⇒ 没人消费 = 丢掉。B3 把产物写进 append-only 账本，
  再让 dwc_evo_round 从账本读未映射簇起草。

  本测试锁三件事：
    ① 落盘/读回/坏行处理/消费标记的语义
    ② 簇形态与 run_round 认的形状一致（key + sigs）
    ③ run_round 收到 clusters 时**不读库**（live 路径带 fn/task，比
       failure_sig 表准 —— 那张表没有 fn 列）
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if os.path.join(_ROOT, "src") not in sys.path:
    sys.path.insert(0, os.path.join(_ROOT, "src"))

from dwc.harness import evo_proposals as ep  # noqa: E402


def _sig(c="E_VALUE", q="wrong", fn="sum_first_n", m="assert", task="t1"):
    return {"c": c, "q": q, "fn": fn, "m": m, "task": task}


# ══════════════════════════════════════════════════════════════════
# 1. 落盘 / 读回
# ══════════════════════════════════════════════════════════════════

def test_append_and_read_roundtrip(tmp_path):
    p = str(tmp_path / "x.jsonl")
    n = ep.append_records(p, [{"kind": "unmapped", "key": "a:b:c",
                               "sig": _sig()},
                              {"kind": "proposal", "key": "a:b:d",
                               "sig": _sig(fn="f")}])
    assert n == 2
    recs = ep.read_records(p)
    assert len(recs) == 2
    assert recs[0]["kind"] == "unmapped"
    assert recs[1]["sig"]["fn"] == "f"


def test_read_missing_file_returns_empty(tmp_path):
    assert ep.read_records(str(tmp_path / "nope.jsonl")) == []


def test_bad_line_is_counted_not_raised(tmp_path):
    p = str(tmp_path / "x.jsonl")
    ep.append_records(p, [{"kind": "unmapped", "key": "a:b:c", "sig": _sig()}])
    with open(p, "a", encoding="utf-8") as fh:
        fh.write("{not json\n")
        fh.write("[1,2,3]\n")
    before = ep.read_error_count()
    recs = ep.read_records(p)
    assert len(recs) == 1                      # 好行仍然读得到
    assert ep.read_error_count() == before + 2  # 坏行留痕（不静默）


# ══════════════════════════════════════════════════════════════════
# 2. 消费语义
# ══════════════════════════════════════════════════════════════════

def test_consumed_keys_excluded_from_pending(tmp_path):
    p = str(tmp_path / "x.jsonl")
    ep.append_records(p, [
        {"kind": "unmapped", "key": "a:b:c", "sig": _sig(fn="c")},
        {"kind": "unmapped", "key": "a:b:d", "sig": _sig(fn="d")},
    ])
    assert len(ep.pending_unmapped(p)) == 2

    ep.mark_consumed(p, ["a:b:c"])
    left = ep.pending_unmapped(p)
    assert len(left) == 1
    assert left[0]["key"] == "a:b:d"


def test_group_by_key_merges_same_key(tmp_path):
    """pending 不去重（保留频次），合并交给 group_by_key。"""
    p = str(tmp_path / "x.jsonl")
    ep.append_records(p, [
        {"kind": "unmapped", "key": "a:b:c", "sig": _sig(fn="c")},
        {"kind": "unmapped", "key": "a:b:c", "sig": _sig(fn="c")},
    ])
    assert len(ep.pending_unmapped(p)) == 2          # 频次保留
    clusters = ep.group_by_key(ep.pending_unmapped(p))
    assert len(clusters) == 1
    assert len(clusters[0]["sigs"]) == 2


def test_pending_skips_sig_missing_keys(tmp_path):
    p = str(tmp_path / "x.jsonl")
    ep.append_records(p, [
        {"kind": "unmapped", "key": "a:b:c", "sig": {"c": "x"}},  # 缺 q/fn
        {"kind": "unmapped", "key": "a:b:d"},                     # 缺 sig
    ])
    assert ep.pending_unmapped(p) == []


def test_pending_ignores_proposal_records(tmp_path):
    """proposal 已被规则映射，不是 evo_round 的起草对象。"""
    p = str(tmp_path / "x.jsonl")
    ep.append_records(p, [{"kind": "proposal", "key": "a:b:c",
                           "sig": _sig()}])
    assert ep.pending_unmapped(p) == []


# ══════════════════════════════════════════════════════════════════
# 3. 簇形态
# ══════════════════════════════════════════════════════════════════

def test_group_by_key_shape_and_order(tmp_path):
    p = str(tmp_path / "x.jsonl")
    ep.append_records(p, [
        {"kind": "unmapped", "key": "k1", "sig": _sig(fn="f1")},
        {"kind": "unmapped", "key": "k2", "sig": _sig(fn="f2")},
        {"kind": "unmapped", "key": "k1", "sig": _sig(fn="f1")},
    ])
    clusters = ep.group_by_key(ep.pending_unmapped(p))
    assert [c["key"] for c in clusters] == ["k1", "k2"]   # 首现顺序
    assert len(clusters[0]["sigs"]) == 2                  # 同键两条都保留


# ══════════════════════════════════════════════════════════════════
# 4. proposal 记录
# ══════════════════════════════════════════════════════════════════

class _P:
    failure_signature = {"c": "E_VALUE", "q": "wrong", "fn": "f"}
    proposal_id = "P9"
    component = "assets"
    target = "x.py"
    patch = "return 1"
    rationale = "because"
    operator = "debug"
    target_layer = "assets"


def test_proposal_record_carries_audit_fields():
    r = ep.proposal_record({"term_id": "T1", "chain_id": "C1"},
                           _P.failure_signature, _P())
    assert r["kind"] == "proposal"
    assert r["term_id"] == "T1"
    assert r["key"] == "E_VALUE:wrong:f"
    assert r["proposal"]["proposal_id"] == "P9"
    assert r["proposal"]["operator"] == "debug"
    assert r["proposal"]["patch"] == "return 1"


# ══════════════════════════════════════════════════════════════════
# 5. run_round 注入簇 ⇒ 不读库
# ══════════════════════════════════════════════════════════════════

def _load_evo_round():
    path = os.path.join(_ROOT, "scripts", "dwc_evo_round.py")
    spec = importlib.util.spec_from_file_location("dwc_evo_round_mod", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["dwc_evo_round_mod"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_run_round_with_injected_clusters_skips_db(monkeypatch):
    m = _load_evo_round()

    def _boom(*a, **kw):
        raise AssertionError("注入了 clusters 还去读库 = 接线错")

    monkeypatch.setattr(m, "collect_unmapped", _boom)

    rep = m.run_round(":memory:", object(), object(), "", lambda *a, **k: None,
                      apply=False, rules_path="", clusters=[])
    assert rep["n_clusters"] == 0
    assert rep["results"] == []


def test_run_round_without_clusters_still_reads_db(monkeypatch):
    m = _load_evo_round()
    called = {"n": 0}

    def _stub(*a, **kw):
        called["n"] += 1
        return []

    monkeypatch.setattr(m, "collect_unmapped", _stub)
    rep = m.run_round(":memory:", object(), object(), "", lambda *a, **k: None,
                      apply=False, rules_path="")
    assert called["n"] == 1, "老路（clusters=None）必须仍然读库"
    assert rep["n_clusters"] == 0
