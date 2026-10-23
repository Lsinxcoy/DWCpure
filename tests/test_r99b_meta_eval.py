# -*- coding: utf-8 -*-
"""R99 · 阶段 1b 探针 —— meta-eval / pass^k / 锚定探针。

★ obs 契约回归锁（首读踩坑的教训测试）: behavior 观测 = {fn: [[args, val]]}
  第一版造成裸 [val] ⇒ 6/6 误判 — 本测试锁死契约防回退。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))


# ══════════════════════════════════════════════════════════
# meta-eval
# ══════════════════════════════════════════════════════════

def test_obs_pass_contract_is_pairs_not_bare_values():
    """★ 教训锁: observed = {fn: [[args, val], ...]}（裸 [val] = 构造 bug）。"""
    from judge_meta_eval import Judge, obs_pass, obs_fail
    j = Judge()
    tid = "code_fix_001"
    op = obs_pass(j.anchors, tid)
    fn = j.anchors[tid]["checks"][0]["fn"]
    first = op[fn][0]
    assert isinstance(first, (list, tuple)) and len(first) == 2, \
        "★ behavior 观测必须是 [args, val] 对（judge._diff 的 _eq(call[0], args) 契约）"
    assert first[1] == 6, "对值 = golden expected（sum_first_n(3)==6）"
    of = obs_fail(j.anchors, tid)
    bad = of[fn][0]
    assert bad[0] == first[0] and bad[1] != first[1], \
        "错值观测: args 对位正确、值错"


def test_meta_eval_perfect_and_structure():
    """meta-eval 对现锚点: 已知真值观测对 ⇒ 结构齐全 + 实测读数可复核。"""
    from judge_meta_eval import evaluate_meta
    out = evaluate_meta()
    assert out["n_behavior_tasks"] >= 6
    cf = out["confusion_pass_as_positive"]
    assert cf["tp"] + cf["fn"] + cf["tn"] + cf["fp"] == out["n_behavior_tasks"] * 2
    assert out["human_percentile"] == "not_applicable", \
        "★ 无医生分布 ⇒ 分位显式不适用（不编造）"
    assert out["length_bias_audit"]["status"] == "no_source", \
        "★ 长度审计原料缺失须显式声明（Verdict 不存观测原文）"
    if out["macro_f1"] is not None:
        assert 0.0 <= out["macro_f1"] <= 1.0


# ══════════════════════════════════════════════════════════
# pass^k
# ══════════════════════════════════════════════════════════

def test_pass_k_unbiased_formula():
    """τ-bench 无偏式 C(c,k)/C(n,k) 手算锁 + 越界大声。"""
    from pass_k_report import pass_k
    # n=6, c=4, k=2: C(4,2)/C(6,2) = 6/15
    assert abs(pass_k(4, 6, 2) - 6 / 15) < 1e-12
    assert pass_k(2, 6, 3) == 0.0          # c<k ⇒ 0（不装可达成）
    assert abs(pass_k(6, 6, 4) - 1.0) < 1e-12   # 全过 ⇒ 1
    import pytest
    with pytest.raises(ValueError):
        pass_k(3, 2, 4)                    # k>n 越界（不静默）


def test_pass_k_script_runs_on_trial_reports():
    """脚本对真 trial 报告可跑: 五报告出数 + approx_iid=false 口径声明在。"""
    script = os.path.join(ROOT, "scripts", "pass_k_report.py")
    outp = os.path.join(ROOT, "docs", "pass_k_report.json")
    r = subprocess.run([sys.executable, script],
                       capture_output=True, timeout=120, cwd=ROOT)
    assert r.returncode == 0, r.stderr.decode("utf-8", "replace")[-600:]
    data = json.load(open(outp, encoding="utf-8"))
    reps = data["reports"]
    assert len(reps) >= 5
    for rep in reps:
        assert rep["approx_iid"] is False, "★ 非严格 iid 必须声明"
        if rep["n_tasks"]:
            assert rep["per_task"]
            for row in rep["per_task"].values():
                assert 0.0 <= row["rate"] <= 1.0


# ══════════════════════════════════════════════════════════
# 锚定探针
# ══════════════════════════════════════════════════════════

def test_anchoring_probe_synthetic_and_script_no_data():
    """probe 合成数据可算 + 脚本对缺文件显式 no_data（不装 0.0）。"""
    from anchoring_probe import probe, THRESH
    syn = [{"d_i": "def a(): return 1"}, {"d_i": "def a(): return 1"},
           {"d_i": " totally different text"}]
    out = probe(syn)
    assert out["n_records"] == 3 and out["n_with_diff"] == 3
    assert out["n_pairs"] == 3
    assert out["max_ratio"] >= THRESH, "两条相同 diff ⇒ max≥阈值"
    assert out["near_identical_pairs"] >= 1
    # 脚本对缺失文件: no_data 显式
    script = os.path.join(ROOT, "scripts", "anchoring_probe.py")
    outp = os.path.join(ROOT, "docs", "anchoring_probe.json")
    r = subprocess.run([sys.executable, script],
                       capture_output=True, timeout=60, cwd=ROOT)
    assert r.returncode == 0, r.stderr.decode("utf-8", "replace")[-400:]
    data = json.load(open(outp, encoding="utf-8"))
    assert data["status"] in ("ok", "no_data")
    if data["status"] == "no_data":
        assert data["why"], "no_data 必须带原因"
