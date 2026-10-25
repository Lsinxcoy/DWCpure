# -*- coding: utf-8 -*-
"""R139 · AppendixD 核实 + 语义判据 — 附录算法欠账不存在, routing 回落 partial。

验收:
  □ 论文核实: 2609.11873 全文 0 编号 Algorithm; 附录 A/B 是综述名录
  □ AppendixD code_rx 只认实现名（注释讨论不算 — 6 处 docstring 已排除）
  □ ★ 语义判据: routing_coverage() 用 AST 数 ACTIONS vs dispatched=True
    分支 ⇒ 2/5 未全覆盖 ⇒ partial（有 dispatch 面≠全路由）
  □ semantic 字段落档（可审计: actions_total/branches/uncovered）
  □ 汇总 4/1/2, 待办三项（ECE/AppendixD/routing）
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from deep_water_audit import (ITEMS, audit, routing_coverage,  # noqa: E402
                               scan)


def test_paper_has_no_numbered_algorithm():
    """★ 论文核实: 2609.11873 全文 0 编号 Algorithm（"Appendix D 算法"是误描述）。"""
    txt = os.path.join(ROOT, "papers", "arxiv_2609.11873",
                       "2609.11873.txt")
    assert os.path.exists(txt), "论文 txt 应在"
    hits = scan(r"Algorithm\s+[0-9]+", sub="papers/arxiv_2609.11873")
    assert not hits, hits[:5]


def test_appendix_d_code_rx_only_impl_names():
    """AppendixD code_rx 只认实现名（appendix/AppD 字样是注释 ⇒ 不算）。"""
    item = [i for i in ITEMS if i["id"] == "AppendixD"][0]
    assert "def\\s+appendix" in item["code_rx"]
    # 旧版宽正则曾匹配 6 处 docstring ⇒ 现行版必须 0 命中
    assert scan(item["code_rx"]) == []


def test_routing_semantic_coverage():
    """★ 语义判据: ACTIONS=5, dispatched=True 分支=3 ⇒ 未全覆盖 ⇒ partial。

    R369 · B1 后 evolve 也进 dispatched=True（remember/dream/evolve 三条），
    未覆盖降为 learn/maintain 两条 —— 仍非全覆盖，判据口径不变。
    """
    cov = routing_coverage()
    assert cov["actions_total"] == 5
    assert cov["dispatched_true_branches"] == 4      # remember + dream + evolve + maintain
    assert cov["uncovered"] == 1                     # learn
    assert cov["fully_routed"] is False


def test_routing_partial_not_fooled_by_wording():
    """★ 反字样误判: 源码有 dispatch 面（code=7）但语义未全覆盖 ⇒ partial。"""
    res = audit()
    r = [o for o in res["items"] if o["id"] == "routing"][0]
    assert r["code_hits"] > 0          # 有 dispatch 面（字样证据在）
    assert r["status"] == "partial"    # 但语义判据否决 live
    assert r["wire_hits"] == 0
    assert r["semantic"]["fully_routed"] is False


def test_audit_summary_4_1_2():
    """汇总 4/1/2；待办三项（ECE/AppendixD/routing）。"""
    res = audit()
    # ★ R140: ECE 落地（calibration.py + iwm 轻接线）⇒ 5/1/1
    assert res["summary"] == {"live": 5, "partial": 1, "absent": 1}
    by = {o["id"]: o["status"] for o in res["items"]}
    assert by["ECE"] == "live"
    assert by["AppendixD"] == "absent"
    assert by["routing"] == "partial"


def test_doc_has_semantic_and_notes():
    """文档须带 semantic 字段 + AppendixD 不存在说明。"""
    p = os.path.join(ROOT, "docs", "deep_water_audit.json")
    assert os.path.exists(p)
    d = json.load(open(p, encoding="utf-8"))
    r = [o for o in d["items"] if o["id"] == "routing"][0]
    assert r["semantic"]["actions_total"] == 5
    ad = [o for o in d["items"] if o["id"] == "AppendixD"][0]
    assert "欠账不存在" in ad["doc_note"]
