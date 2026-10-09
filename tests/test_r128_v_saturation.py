# -*- coding: utf-8 -*-
"""R128 · V_max_saturation 探针 — R127 恒等根因的量化证据。

验收:
  □ 探针五档全跑, 结构性质坐实: 有 1.0 在观测面 ⇒ V 不受 0.0 位置影响
  □ 全 0.0（无满分节点）⇒ V 掉下来（对照档, 排除"注入没生效"）
  □ V_eq_max_s 字段=探针文档真记录了 V==max 的关系（可审计）
  □ R127 的整改路径被写死（观测面构成 / judge 逐任务分 — 不是换 executor）
"""
from __future__ import annotations

import json
import os
import sys

import pytest

ROOT = r"E:/Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from probe_v_saturation import probe  # noqa: E402


def _search_ids():
    a = json.load(open(os.path.join(ROOT, "config", "anchors",
                                    "dev.json"), encoding="utf-8"))
    return list((a.get("_split") or {}).get("search", []))


def test_saturation_structural_property():
    """★ 核心: 0.0 位置不影响 V（max 吃掉低分）; 全 0.0 才掉。"""
    ids = _search_ids()
    n = len(ids)
    v_all1 = probe([1.0] * n, ids)["v_pi0"]
    v_head0 = probe([0.0] + [1.0] * (n - 1), ids)["v_pi0"]
    v_tail0 = probe([1.0] * (n - 1) + [0.0], ids)["v_pi0"]
    v_all0 = probe([0.0] * n, ids)["v_pi0"]
    assert v_head0 == v_all1 == v_tail0 == 1.0     # max 饱和（位置无关）
    assert v_all0 == 0.0                          # 全 0 ⇒ 掉（对照有效）
    assert v_all1 != v_all0                       # 排除"注入没生效"


def test_injected_observation_lands_in_tree():
    """注入的 score 真落在树节点（探针前提, 不是空跑）。"""
    ids = _search_ids()
    r = probe([0.0] + [1.0] * (len(ids) - 1), ids)
    assert r["n_scored_nodes"] == len(ids)
    assert r["max_s_in_tree"] == 1.0
    assert r["min_s_in_tree"] == 0.0              # 0.0 确实写进去了
    assert r["V_eq_max_s"] is True                # V==max（论文式可审计点）


def test_probe_doc_written_and_has_conclusions():
    """探针文档落盘且结论字段在位（可复跑取证）。"""
    p = os.path.join(ROOT, "docs", "v_saturation_probe.json")
    assert os.path.exists(p), "先跑 python scripts/probe_v_saturation.py"
    d = json.load(open(p, encoding="utf-8"))
    c = d["conclusions"]
    assert c["saturates"] is True
    assert c["one_zero_head_v"] == c["all_ones_v"] == c["one_zero_tail_v"]
    assert c["no_ones_v"] != c["all_ones_v"]
    assert "executor" in c["含义"]        # 整改路径被写死（不是换 executor）
    assert "max 饱和" in c["★ 结论"]


def test_probe_is_not_a_llm_call(monkeypatch):
    """探针用注入观测（不走真端点）⇒ 无网络依赖, 可重复。"""
    import dwc.llm as llm_pkg
    def _boom(*a, **k):
        raise AssertionError("探针不应调 LLM")
    monkeypatch.setattr(llm_pkg, "LLMClient", _boom)
    ids = _search_ids()
    r = probe([1.0] * 2, ids[:2])           # 小注入也应无 LLM
    assert r["n_scored_nodes"] == 2
