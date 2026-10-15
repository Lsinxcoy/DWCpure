# -*- coding: utf-8 -*-
"""★★★ R287-C · adopt 第五态下游落地（幂等）。

★ 前置：Evolver._land_adopted(proposal, backup_dir=None) —— adopt() 判
  adopted_not_implemented 的提案落盘进 Mutator.RULES＋persist；同 key 第
  二次 ⇒ already_landed（幂等，不长双胞胎）。
★ 隔离：LEARNED_PATH monkeypatch 到 tmp；禁碰生产 rules.json。
"""
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(_HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.organs.evolver import Evolver, Mutator, Proposal


def _prop(state="adopted_not_implemented"):
    p = Proposal(
        proposal_id="P_test adopted",
        failure_signature={"c": "E_X", "q": "q", "m": "m_test",
                           "m_source": "rule"},
        component="prompt", target="f_avg",
        patch="铁律句", rationale="R287-C 测试提案",
        dimension="D7", target_layer="assets")
    p.state = state
    return p


class TestLandAdopted:
    def test_lands_once(self, tmp_path, monkeypatch):
        monkeypatch.setattr(Mutator, "LEARNED_PATH",
                            str(tmp_path / "rules.json"))
        ev = Evolver()
        r1 = ev._land_adopted(_prop())
        assert r1["outcome"] == "landed"
        assert "E_X:q:f_avg" in Mutator.RULES
        r2 = ev._land_adopted(_prop())
        assert r2["outcome"] == "already_landed"
        Mutator.RULES.pop("E_X:q:f_avg", None)

    def test_disk_roundtrip(self, tmp_path, monkeypatch):
        monkeypatch.setattr(Mutator, "LEARNED_PATH",
                            str(tmp_path / "rules.json"))
        ev = Evolver()
        ev._land_adopted(_prop())
        import json
        disk = json.load(open(str(tmp_path / "rules.json"),
                              encoding="utf-8"))
        assert "E_X:q:f_avg" in disk["learned"]
        Mutator.RULES.pop("E_X:q:f_avg", None)

    def test_rejected_proposal_refused_loud(self, tmp_path, monkeypatch):
        monkeypatch.setattr(Mutator, "LEARNED_PATH",
                            str(tmp_path / "rules.json"))
        ev = Evolver()
        p = _prop(state="rejected")
        with pytest.raises(Exception, match="state"):
            ev._land_adopted(p)
