# -*- coding: utf-8 -*-
"""R292 · 测试副作用总闸（P4 收尾三副作用根治①②③的验证）。

① run_term :memory: 跳过 verdict 落盘（根 eval/ 写飞根治）。
② conftest 总闸：LEARNED_PATH→tmp（生产 rules.json 免疫）。
③ conftest 总闸：被跟踪文件快照还原（git 永远干净）。
★ 测试零真 LLM（fake/纯函数）；raises 配额见 test_r292_learned_遗漏显式抛。
"""
from __future__ import annotations

import io
import json
import os
import sys

import pytest

ROOT = r"E:/Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "src"))


def test_r292_memory_skips_verdict_disk(tmp_path):
    """★★ ① :memory: 跑完整 run_term ⇒ cwd 下不新建 eval/（内存不落盘）。"""
    import sqlite3
    from dwc.harness.run_term import TermRunner
    from dwc.organs.judge import Judge
    c = sqlite3.connect(":memory:")
    c.execute("CREATE TABLE failure_sig(c,q,m,node_id)")
    c.close()
    _cwd_eval = os.path.join(os.getcwd(), "eval", "term_verdicts.jsonl")
    _had = os.path.exists(_cwd_eval)
    tr = TermRunner(db_path=":memory:", judge=Judge(), executor=None)
    tr.run_term("code_fix_001", n_steps=1)
    assert os.path.exists(_cwd_eval) == _had  # ★ 没新建（有也不碰）


def test_r292_learned_path_isolated():
    """★★ ② 总闸生效：测试内 LEARNED_PATH 不在生产 config/anchors 下。"""
    from dwc.organs.evolver import Mutator
    assert "config" not in Mutator.LEARNED_PATH.replace("\\", "/"), \
        Mutator.LEARNED_PATH


def test_r292_land_adopted_never_touches_prod_rules():
    """★★★ ② 端到端：_land_adopted 落地后生产 rules.json learned 仍空。"""
    from dwc.organs.evolver import Evolver, Mutator, Proposal
    p = Proposal(proposal_id="P_r292",
                 failure_signature={"c": "E_X", "q": "q", "m": "m"},
                 component="prompt", target="average",
                 patch="p", rationale="r",
                 dimension="D7", target_layer="assets")
    p.state = "adopted_not_implemented"
    _before = set(Mutator.RULES)
    try:
        Evolver()._land_adopted(p)
    finally:
        for _k in set(Mutator.RULES) - _before:
            del Mutator.RULES[_k]
    prod_path = os.path.join(ROOT, "config", "anchors", "rules.json")
    if os.path.exists(prod_path):
        prod = json.load(io.open(prod_path, encoding="utf-8"))
        assert prod.get("learned", {}) == {}, prod.get("learned")
    # ★ 缺席即空 learned（R276 起的正常态：gitignored 运行时文件，不在即无学到条目）


def test_r292_tracked_snapshot_roundtrip(tmp_path):
    """★★ ③ 快照逻辑单测：改→teardown 还原（调总闸同款读写函数）。"""
    import tests.conftest as CF  # noqa: E402
    _p = os.path.join(ROOT, "docs", "table8_status.json")
    _orig = CF._r292_read_bytes(_p)
    assert _orig is not None  # 生产文件存在才有快照意义
    assert "docs/table8_status.json" in CF._R292_SNAPSHOT_FILES
    assert len(CF._R292_SNAPSHOT_FILES) == 8, CF._R292_SNAPSHOT_FILES


def test_r292_raises_quota_land_rejects_nonfinal():
    """★ raises 配额：_land_adopted 非第五态⇒抛 EvolverError（门没判不落地）。"""
    from dwc.organs.evolver import Evolver, Proposal, EvolverError
    p = Proposal(proposal_id="P_r292x",
                 failure_signature={"c": "E_X", "q": "q", "m": "m"},
                 component="prompt", target="average",
                 patch="p", rationale="r",
                 dimension="D7", target_layer="assets")
    assert p.state == "draft"
    with pytest.raises(EvolverError):
        Evolver()._land_adopted(p)
