# -*- coding: utf-8 -*-
"""R115 · E2 — challenger 首次对拍（平票在位者 + 行为差异证据 + dep 联动）。

验收（设计稿④ §⑧ E2 字面）:
  □ 对拍跑通可复跑（meta-F1 同锚）· 平票判在位者断言 · 输者归档不静默
  □ 换代未发生 ⇒ 历史分可比性连续（broken_since=None 如实）
  □ ε 策略键: 默认 0 零破坏（delta≥0 同式）· 负 ε 拒 · 返回含 epsilon
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

ROOT = r"E:/Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from dwc.organs.judge import Judge, JudgeError  # noqa: E402


def _pair(n=200, base_pass=160, cur_pass=159):
    def mk(p):
        return {"details": [{"task_id": "t%03d" % i, "success": i < p}
                            for i in range(n)]}
    return mk(base_pass), mk(cur_pass)


def test_regression_epsilon_default_zero_compat():
    """ε 默认 0 = 现行行为（delta<0 ⇒ regression 同式零破坏）。"""
    j = Judge()
    b, c = _pair()                              # delta = -0.005
    r0 = j.regression_check(b, c)
    assert r0["verdict"] == "regression" and r0["epsilon"] == 0.0
    # ε=0.02 容忍 -0.5% 回退 ⇒ ok（策略键生效）
    r2 = j.regression_check(b, c, epsilon=0.02)
    assert r2["verdict"] == "ok" and r2["epsilon"] == 0.02
    # 回退超过容忍仍 regression
    b2, c2 = _pair(base_pass=160, cur_pass=150)   # delta=-0.05
    assert j.regression_check(b2, c2, epsilon=0.02)["verdict"] == "regression"
    # 负 ε = 反向放水 ⇒ 拒
    with pytest.raises(JudgeError, match="epsilon"):
        j.regression_check(b, c, epsilon=-0.01)
    # 无回退 ⇒ ok（ε 不把 ok 变 regression）
    b3, c3 = _pair(base_pass=159, cur_pass=160)
    assert j.regression_check(b3, c3)["verdict"] == "ok"


def test_challenger_duel_script_runs_tie_holds():
    """★ E2 首次对拍: 平票判在位者 + 行为差异证据 + 归档不静默 + 可比连续。"""
    outp = os.path.join(ROOT, "docs", "challenger_duel.json")
    r = subprocess.run([sys.executable,
                        os.path.join(ROOT, "scripts", "challenger_duel.py")],
                       capture_output=True, timeout=600, cwd=ROOT)
    assert r.returncode == 0, r.stderr.decode("utf-8", "replace")[-700:]
    d = json.load(open(outp, encoding="utf-8"))
    duel = d["duel"]
    # ε 不进 diff 判分 ⇒ F1 结构性相同 ⇒ 平票 ⇒ 在位者续任（稿§⑤ RQGM 字面）
    assert duel["tie"] is True
    assert duel["decision"] == "incumbent_holds"
    assert d["regime_change_happened"] is False
    # 行为差异=描述性证据（ε 改变回归判定 — 策略键真有效）
    beh = d["behaviour_evidence"]
    assert beh["behaviour_differs"] is True
    assert beh["incumbent_verdict"] == "regression"
    assert beh["challenger_verdict"] == "ok"
    # 输者归档不静默（G7）
    arch = d["challenger_archive"]
    assert arch["proposal"]["status"] == "archived_not_adopted"
    assert "平票" in arch["why"] and "不静默" in arch["why"]
    # 可比性连续（无换代 ⇒ broken_since=None）
    assert d["historical_comparability"]["broken_since"] is None
    # 结构性平票的诚实注记在位（不装"对拍失败"也不装"换代成功"）
    h = "\n".join(d["honest"])
    assert "不敏感" in h and "分层设计" in h and "呈用户过目" in h
    # dep 扫描联动（分栏在位 — 计数随源状态, 不锁死值）
    assert set(d["dep_scan_after"]) == {"active",
                                        "deprecated_by_evaluator",
                                        "pre_depz_legacy"}
