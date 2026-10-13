# -*- coding: utf-8 -*-
"""R233 · 保留协议：双判据三态 / 配对不兼容 / test 冻结程序锁 / 留痕。"""
from __future__ import annotations

import io
import json
import os
import sys

ROOT = r"E:\Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "src"))
from dwc.foundation import retention as R                       # noqa: E402
import pytest                                                   # noqa: E402


def _arms(p_old_old=0.50, p_old_new=0.52, p_new_old=0.51, p_new_new=0.56,
          c_old=10.0, c_new=10.0):
    return {"old_old": {"pass_rate": p_old_old, "cost": c_old},
            "old_new": {"pass_rate": p_old_new, "cost": c_old},
            "new_old": {"pass_rate": p_new_old, "cost": c_new},
            "new_new": {"pass_rate": p_new_new, "cost": c_new}}


def test_promotion_three_states():
    """★★★ 晋升判据三态锁: Δ=0.06/cost=1.0 ⇒ promote;
    Δ=0.05/cost=1.5 ⇒ 拒(成本否决); Δ=0.01 ⇒ 拒(增益不足)。"""
    ok = R.decide(_arms(), gain_min=0.02, cost_max=1.2)
    assert ok["promoted"] and ok["reasons"] == []
    expensive = R.decide(_arms(p_new_new=0.57, c_new=15.0), 0.02, 1.2)
    assert not expensive["promoted"] and any("成本" in r for r in expensive["reasons"])
    weak = R.decide(_arms(p_new_new=0.51), 0.02, 1.2)
    assert not weak["promoted"] and any("增益" in r for r in weak["reasons"])


def test_pair_incompatibility_rejected():
    """★★★ 配对不兼容锁（论文动机句机器化）: 组件单独过检（D−A>0）
    但 Δ_exec=D−B<0 且 Δ_pred=D−C>=0 ⇒ 拒 — 单组件过检 ≠ 组合可用。"""
    # D=0.56 > A=0.50 组件面看是改进; 但 B=0.60 ⇒ Δ_exec=−0.04 <0
    # C=0.53 ⇒ Δ_pred=+0.03 >=0 — 配对不兼容
    bad = R.decide(_arms(p_old_new=0.60, p_new_old=0.53, p_new_new=0.56),
                   0.02, 1.2)
    assert not bad["promoted"]
    assert any("配对不兼容" in r for r in bad["reasons"]), bad["reasons"]
    assert bad["delta_exec"] < 0 < bad["delta_pred"]


def test_four_arms_incomplete_rejected():
    """★★ 四臂不全即拒（不完整数据不许进协议）。"""
    a = _arms()
    del a["new_old"]
    with pytest.raises(R.RetentionError, match="四臂不全"):
        R.pair_check(a)


def test_test_freeze_program_lock(tmp_path, monkeypatch):
    """★★★ test 冻结程序锁: 无 manifest ⇒ evaluate_test 拒;
    冻结后只许开一次（反复调参被程序挡住, 不靠自觉）。"""
    monkeypatch.setattr(R, "RETENTION_DIR", str(tmp_path))
    with pytest.raises(R.RetentionError, match="无冻结 manifest"):
        R.evaluate_test("T_x")
    path = R.freeze_versions("T_x", "sha:abc", "pred-v1", _arms(),
                             {"promoted": True})
    assert os.path.exists(path)
    doc = R.evaluate_test("T_x")
    assert doc["test_not_opened_yet"] is False
    with pytest.raises(R.RetentionError, match="已开过"):
        R.evaluate_test("T_x")


def test_rejected_candidate_records_full_arms(tmp_path, monkeypatch):
    """★★ 拒绝留痕锁: 未晋升候选的四臂数据完整入档（拒绝也要留证据 —
    rsi.py raw_rejected_candidates_reported 同款）。"""
    monkeypatch.setattr(R, "RETENTION_LOG", str(tmp_path / "ret.jsonl"))
    bad = R.decide(_arms(p_new_new=0.51), 0.02, 1.2)
    R.record({"cand_id": "T_rej", **bad, "arms": _arms(p_new_new=0.51)})
    rows = [json.loads(x) for x in io.open(
        str(tmp_path / "ret.jsonl"), encoding="utf-8").read().splitlines()]
    assert len(rows) == 1 and not rows[0]["promoted"]
    assert set(rows[0]["arms"]) == {"old_old", "old_new", "new_old", "new_new"}


def test_component_delta():
    """★ 组件检查: pass 率差与成本比数学。"""
    d = R.component_delta({"pass_rate": 0.6, "cost": 8.0},
                          {"pass_rate": 0.5, "cost": 10.0})
    assert abs(d["delta_pass"] - 0.1) < 1e-12
    assert abs(d["cost_ratio"] - 0.8) < 1e-12
