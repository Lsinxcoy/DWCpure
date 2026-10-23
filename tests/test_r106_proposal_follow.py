# -*- coding: utf-8 -*-
"""R106 · 阶段 3a — Proposal 遵循率报表（两读数 + 四模式 + 三列连接）。

判据（方案 §⑥T4 验收字面）:
  · 每个已采纳 Proposal 三列连接齐全（证据→后续使用→新旧任务效果,
    缺=not_assessable 显式）
  · 遵循率报表可复跑（同库两次跑, 报表主体字节一致）
  · 四模式纯判: not_invoked / invoked_not_followed / followed_beneficial
    / sacrificed(需对照臂 ⇒ 固定 not_assessable)
  · 双缺口诚实: recall/record_effect 生产零调用 + 默认 :memory: 不落盘
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from dwc.organs.memory import MemoryKind, MemoryKernel  # noqa: E402
from proposal_follow import (  # noqa: E402
    MODE_BENEFICIAL, MODE_INVOKED_NO_EFFECT, MODE_NOT_INVOKED,
    MODE_SACRIFICED, build_report, classify)


def _proposal(mem: MemoryKernel) -> str:
    return mem.remember(MemoryKind.PROPOSAL,
                        {"consumer_declared": "run_term",
                         "scene": "wta"})


def test_classify_four_modes_pure():
    assert classify(0, 0) == MODE_NOT_INVOKED
    assert classify(3, 0) == MODE_INVOKED_NO_EFFECT
    assert classify(3, 1) == MODE_BENEFICIAL
    # 牺牲旧能力: 仅当有新旧对照且回退才可判
    assert classify(3, 1, old_new_available=True, regressed=True) == MODE_SACRIFICED
    assert classify(3, 1, old_new_available=False, regressed=True) == MODE_BENEFICIAL


def test_report_three_columns_complete(tmp_path):
    """三列连接齐全（验收字面）: 每行 evidence/subsequent_use/old_vs_new_effect。"""
    mem = MemoryKernel(db_path=str(tmp_path / "m.db"))
    nid = _proposal(mem)
    rep = build_report(mem)
    row = rep["sourceA_memory_proposal"]["rows"][0]
    cols = row["columns"]
    assert set(cols) == {"evidence", "subsequent_use", "old_vs_new_effect"}
    assert cols["evidence"]["node_id"] == nid
    assert cols["evidence"]["consumer_declared"] == "run_term"
    assert cols["old_vs_new_effect"]["status"] == "not_assessable"
    # 未召回 ⇒ not_invoked
    assert row["mode"] == MODE_NOT_INVOKED
    # 召回+效果 ⇒ 两读数转移
    mem.recall(nid)
    mem.record_effect(nid)
    rep2 = build_report(mem)
    row2 = rep2["sourceA_memory_proposal"]["rows"][0]
    assert row2["activated"] and row2["faithfully_followed"]
    assert row2["mode"] == MODE_BENEFICIAL
    sa = rep2["sourceA_memory_proposal"]
    assert sa["activation_rate"] == 1.0 and sa["faithful_follow_rate"] == 1.0


def test_report_honest_gaps(tmp_path):
    """双缺口 + 源B 不装数（诚实字段在位）。"""
    mem = MemoryKernel(db_path=str(tmp_path / "m.db"))
    rep = build_report(mem)
    assert "recall()/record_effect() 零调用方" in rep["data_gap"]
    assert ":memory:" in rep["data_gap"]
    assert rep["sourceB_evolver"]["n_adopted"] == "not_instrumented"
    assert rep["sourceA_memory_proposal"]["n_proposals"] == 0
    assert rep["sourceA_memory_proposal"]["activation_rate"] is None
    # 牺牲模式 not_assessable 声明在
    assert "not_assessable" in rep["assessment_note"]


def test_report_rerunnable(tmp_path):
    """可复跑（验收字面）: 同库两次跑, 主体字节一致。"""
    db = str(tmp_path / "m.db")
    mem = MemoryKernel(db_path=db)
    _proposal(mem)
    mem.recall(  # 一个激活样本
        build_report(mem)["sourceA_memory_proposal"]["rows"][0]["node_id"])
    outs = []
    for i in range(2):
        r = subprocess.run([sys.executable,
                            os.path.join(ROOT, "scripts", "proposal_follow.py"),
                            "--db", db,
                            "--out", str(tmp_path / ("o%d.json" % i))],
                           capture_output=True, timeout=120, cwd=ROOT)
        assert r.returncode == 0, r.stderr.decode("utf-8", "replace")[-500:]
        outs.append(json.load(open(tmp_path / ("o%d.json" % i), encoding="utf-8")))
    assert outs[0] == outs[1], "同库两次跑报表必须一致（可复跑）"
    assert outs[0]["sourceA_memory_proposal"]["n_proposals"] == 1
