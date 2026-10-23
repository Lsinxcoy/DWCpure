# -*- coding: utf-8 -*-
"""R310-③ · triage 分类机：report 结果分类＋recommendations（只呈现，不改判）。"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))


def test_triage_categories():
    import importlib.util as _ilu
    spec = _ilu.spec_from_file_location(
        "evo_round_triage_test",
        os.path.join(ROOT, "scripts", "dwc_evo_round.py"))
    EVO = _ilu.module_from_spec(spec)
    spec.loader.exec_module(EVO)
    rep = {"n_clusters": 4, "results": [
        {"key": "K1", "landed": True, "trial": True},
        {"key": "K2", "landed": False, "trial": True},
        {"key": "K3", "landed": False, "trial": False,
         "reason": "重试预算耗尽（3 次 trial 未过）"},
        {"key": "K4", "landed": False, "trial": None,
         "reason": "ledger 已做（resume 跳过）"},
    ]}
    tr = EVO.triage_report(rep)
    cats = {t["key"]: t["category"] for t in tr["tasks"]}
    assert cats == {"K1": "landed", "K2": "ready", "K3": "stuck",
                    "K4": "skipped"}, cats
    assert tr["summary"] == {"total": 4, "landed": 1, "ready": 1,
                             "stuck": 1, "skipped": 1,
                             "draft_failed": 0}, tr["summary"]
    assert any("K2" in r for r in tr["recommendations"]), tr
    assert any("K3" in r for r in tr["recommendations"]), tr


def test_triage_draft_failed():
    import importlib.util as _ilu
    spec = _ilu.spec_from_file_location(
        "evo_round_triage2_test",
        os.path.join(ROOT, "scripts", "dwc_evo_round.py"))
    EVO = _ilu.module_from_spec(spec)
    spec.loader.exec_module(EVO)
    rep = {"n_clusters": 1, "results": [
        {"key": "K9", "landed": False, "trial": None, "drafted": False,
         "reason": "起草抛错：boom"},
    ]}
    tr = EVO.triage_report(rep)
    assert tr["tasks"][0]["category"] == "draft_failed"
    assert tr["summary"]["draft_failed"] == 1
