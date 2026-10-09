# -*- coding: utf-8 -*-
"""R137 · δ_θ 盘点修正 + 行为级验证 — live 从 grep 计数变实测。

背景（声称 vs 实测的又一次兑现）:
  R136 盘点把 δ_θ 判 partial（正则只扫 "delta_theta" 字样 ⇒ 漏掉
  真实现 weakness.py 的 task_delta_map/delta_group/Difficulty 命名）。
  R137 修正: code=41 wire=12 ⇒ live; 且本测试做行为级验证。

验收（行为级, 非计数级）:
  □ Difficulty 契约: semantics ∈ {group_baseline, world_knowledge} 值枚举
  □ X2 纪律: n_obs 必填 ≥0 整数（0 ⇒ NaN 语义, 不裸 float）
  □ z 三类显式编码: __pass__ / __unsigned_fail__ / c:…|q:…
  □ 管线可跑: z_history_from_scores（要 group_id/evidence_ref）
    + task_delta_map 返回 {task: float} 全序可排
  □ δ 公式: 罕见失败(组内唯一 z) δ 最大; 无失败任务显式 0.0
  □ X3 诚实边界: world_knowledge ⇒ delta_group raise
  □ TRUTH_SOURCE 声明在位（G2）
"""
from __future__ import annotations

import json
import math
import os
import subprocess
import sys

import pytest

ROOT = r"E:/Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.organs.weakness import (  # noqa: E402
    SEMANTICS, TRUTH_SOURCE, Z_PASS, Z_UNSIGNED, Difficulty,
    DifficultyEstimator, WeaknessError, repair_layer, task_delta_map,
    task_success_stats, z_history_from_scores, z_id_from_signature)


class _P:
    """判分点 stub — z_history/task_delta_map 契约:
    task_id / group_id / evidence_ref / score。"""

    def __init__(self, task_id: str, group_id: str, ref: str, score: float):
        self.task_id = task_id
        self.group_id = group_id
        self.evidence_ref = ref
        self.score = score


def _ev(ref: str):
    """evidence_lookup callable — ref ⇒ evidence dict（None ⇒ 无签名）。"""
    table = {
        "r_t1a": {"success": False, "failure_signature": {"c": "c:off_by_one", "q": "q:sum_first_n"}},
        "r_t1b": {"success": False, "failure_signature": {"c": "c:off_by_one", "q": "q:sum_first_n"}},
        "r_t2": {"success": False, "failure_signature": {"c": "c:type_err", "q": "q:sum_first_n"}},
        "r_ok": {"success": True, "failure_signature": None},
    }
    return table.get(ref)


def test_difficulty_semantics_enum():
    """★ X1: semantics 值枚举（group_baseline/world_knowledge）。"""
    assert SEMANTICS == ("group_baseline", "world_knowledge")
    d = Difficulty(delta=1.0, semantics="group_baseline", z_id="c:x",
                   group_id="g1", n_obs=3, estimated_at="t")
    assert d.delta == 1.0
    with pytest.raises(WeaknessError):
        Difficulty(delta=0.0, semantics="made_up", z_id="c:x", group_id="g1",
                   n_obs=1, estimated_at="t")
    # n_obs 必填 ≥0 整数（bool 也不是 int — X2 双保险）
    with pytest.raises(WeaknessError):
        Difficulty(delta=0.0, semantics="group_baseline", z_id="c:x",
                   group_id="g1", n_obs=True, estimated_at="t")


def test_truth_source_declared():
    """★ G2: TRUTH_SOURCE 声明在位（不自判 + 无阈值）。"""
    assert "不自判" in TRUTH_SOURCE["声明"]
    assert ("无阈值" in TRUTH_SOURCE["自判禁止"]
            or "排序偏置" in TRUTH_SOURCE["自判禁止"])


def test_z_three_kinds_explicit():
    """★ z 三类显式: __pass__ / __unsigned_fail__ / c:…|q:…（丢一类=分母不匹配）。"""
    assert Z_PASS == "__pass__" and Z_UNSIGNED == "__unsigned_fail__"
    signed = z_id_from_signature({"c": "c:off_by_one", "q": "q:sum"})
    assert signed and signed != Z_PASS and signed != Z_UNSIGNED
    assert z_id_from_signature(None) == Z_UNSIGNED


def test_pipeline_runs_and_delta_formula():
    """★ 行为级: 管线跑通 + 公式核对（罕见失败 δ 最大, 无失败=显式 0.0）。"""
    pts = [
        _P("t1", "g1", "r_t1a", 0.0),   # t1 签名 A
        _P("t1", "g1", "r_t1b", 0.0),   # t1 签名 A 再现
        _P("t2", "g1", "r_t2", 0.0),    # t2 签名 B（组内唯一 ⇒ 最罕见）
        _P("t3", "g1", "r_ok", 1.0),    # t3 成功
    ]
    hist = z_history_from_scores(pts, _ev)
    assert isinstance(hist, dict) and "g1" in hist
    # 分母 = 组内全部判分（4 条, 含 __pass__ 占位）
    assert len(hist["g1"]) == 4
    dmap = task_delta_map(pts, _ev)
    assert isinstance(dmap, dict)
    # 全部 task_id 在表里（无失败也显式 0.0 — 不混"没数据"与"零难度"）
    assert set(dmap) == {"t1", "t2", "t3"}
    assert dmap["t3"] == 0.0                      # 全成功 ⇒ 显式 0
    # t2 的签名组内唯一 ⇒ r 最小 ⇒ −log r 最大 ⇒ δ 最大
    assert dmap["t2"] > dmap["t1"] > dmap["t3"]
    # 公式手算对账: r_B = (1+1)/(4+1) = 0.4 ⇒ δ = −log(0.4)
    assert abs(dmap["t2"] - (-math.log(2 / 5))) < 1e-9
    # r_A = (2+1)/(4+1) = 0.6 ⇒ δ = −log(0.6)
    assert abs(dmap["t1"] - (-math.log(3 / 5))) < 1e-9


def test_laplace_k1_n0_defined():
    """★ Laplace k=1: n=0 也有定义（NaN 显式, 不炸不静默）。"""
    est = DifficultyEstimator({"g1": []})          # 组内零观测
    d = est.delta_group(Z_PASS, "g1")
    assert d.n_obs == 0
    assert math.isnan(d.delta)                     # X2: 0 观测 ⇒ NaN 显式


def test_world_knowledge_raises():
    """★ X3 诚实边界: world_knowledge ⇒ raise（没有代理不假装能算）。"""
    est = DifficultyEstimator({"g1": ["__pass__"]})
    try:
        est.delta_group("c:x", "g1", semantics="world_knowledge")
        raised = False
    except Exception:
        raised = True
    assert raised, "world_knowledge 路线未实现 ⇒ 必须 raise 不静默"


def test_repair_layer_three_way():
    """★ R99 三级修复层: receipt/judge/未知 ⇒ execution/verification/unmapped。"""
    assert repair_layer("c:x", "receipt") == "execution"
    assert repair_layer("c:x", "judge") == "verification"
    assert repair_layer("c:x", "unknown_src") == "unmapped"


def test_deep_water_audit_delta_theta_now_live():
    """★ 盘点修正落档: 再跑 deep_water_audit ⇒ delta_theta=live 4/1/2。"""
    subprocess.run([sys.executable,
                    os.path.join(ROOT, "scripts", "deep_water_audit.py")],
                   capture_output=True, timeout=300, cwd=ROOT)
    d = json.load(open(os.path.join(ROOT, "docs",
                                    "deep_water_audit.json"),
                       encoding="utf-8"))
    by = {o["id"]: o["status"] for o in d["items"]}
    assert by["delta_theta"] == "live"
    assert d["summary"] == {"live": 4, "partial": 1, "absent": 2}
