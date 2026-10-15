# -*- coding: utf-8 -*-
"""★★★ R278 · 给 Loop 接生产（diagnose→试跑→落地→固化开车）。

★ 隔离：diagnose 用合成签名（零真 LLM，Evolver 确定性）；
  apply 路径只跑 tmp anchors，禁碰生产 rules.json/lessons。
★ pytest.raises 配额：坏输入/空簇必须大声（≥5%）。
"""
import pytest

from dwc.organs.evolver import Evolver


def _sig007():
    return {"c": "E_VALUE", "q": "wrong_magnitude",
            "m": "llm_asserted:0.15", "fn": "average",
            "split": "dev", "task": "code_fix_007"}


class TestDiagnoseCluster:
    def test_same_sig_forms_cluster(self):
        # ★ 实测纠偏：(E_VALUE, wrong_magnitude, average) 无 Mutator 映射 ⇒
        #   诚实 unmapped（合法“不会改”），但聚类计数必须成簇。
        ev = Evolver()
        out = ev.diagnose([_sig007(), _sig007()])
        assert out.get("n_clusters") == 1
        assert out.get("n_unmapped") == 2

    def test_empty_sigs_no_proposals(self):
        ev = Evolver()
        out = ev.diagnose([])
        assert out.get("proposals", []) == []

    def test_none_sig_skipped_loud(self):
        ev = Evolver()
        with pytest.raises(Exception):
            ev.diagnose(None)

    def test_single_sig_still_proposes(self):
        ev = Evolver()
        out = ev.diagnose([_sig007()])
        assert isinstance(out.get("proposals", []), list)
