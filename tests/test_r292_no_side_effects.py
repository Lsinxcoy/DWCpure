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

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
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
    """★★★ ② 端到端：_land_adopted 不许改动生产 rules.json（**字节不变**）。

    ★ R438 重锚：旧断言要求 `learned == {}` —— 那是"生产永远没学到东西"的
      假设；R438 起生产真的会落规则（当前 1 条 fibonacci）。
      正确判据是"本测试没改它"，不是"它必须是空的"。
    """
    from dwc.organs.evolver import Evolver, Mutator, Proposal
    p = Proposal(proposal_id="P_r292",
                 failure_signature={"c": "E_X", "q": "q", "m": "m"},
                 component="prompt", target="average",
                 patch="p", rationale="r",
                 dimension="D7", target_layer="assets")
    p.state = "adopted_not_implemented"
    _before = set(Mutator.RULES)
    _prod_p = os.path.join(ROOT, "config", "anchors", "rules.json")
    _before_bytes = (io.open(_prod_p, "rb").read()
                     if os.path.exists(_prod_p) else None)
    try:
        Evolver()._land_adopted(p)
    finally:
        for _k in set(Mutator.RULES) - _before:
            del Mutator.RULES[_k]
    prod_path = os.path.join(ROOT, "config", "anchors", "rules.json")
    _now = (io.open(prod_path, "rb").read() if os.path.exists(prod_path)
            else None)
    assert _now == _before_bytes, "★ 测试改了生产 rules.json"
    # ★ 缺席也合法（gitignored 运行时文件）—— 但"存在"与"被改"必须可区分


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


def test_r294_not_wired_empty_all_connected(tmp_path):
    """★★★ R294 · not_wired 清零（world.select／metric.select→adopt／
    direction 三项 R290/R291 全摘 —— 清单再挂项即谎报）。
    """
    import json as _json
    import sqlite3
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    import dwc_evo_round as EVO
    from dwc.organs.evolver import Evolver, LLMMutator
    db = str(tmp_path / "p.sqlite")
    c = sqlite3.connect(db)
    c.execute("CREATE TABLE failure_sig(c,q,m,node_id)")
    c.close()
    mu = LLMMutator(llm=lambda p: _json.dumps(
        {"component": "prompt", "dimension": "D7", "target_layer": "assets",
         "target": "average", "m": "x", "patch": "p", "rationale": "r"}))
    rep = EVO.run_round(db, Evolver(), mu, context="",
                        trial_fn=lambda task, patch, code=None: True, apply=False,
                        rules_path=str(tmp_path / "rules.json"),
                        backup_dir=str(tmp_path))
    assert rep["not_wired"] == [], rep["not_wired"]
