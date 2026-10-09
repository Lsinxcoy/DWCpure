# -*- coding: utf-8 -*-
"""R103 · 阶段 2c — 成功侧归纳聚合（Trace2Skill A+ 对称物）+ 序列任务流。

判据:
  · 成功聚合 = 描述统计（n/k/rate/streak）不给阈值判定（L1105 同族）
  · None 不计入分母（judge 纪律）· 无观测任务不入表（成功侧入表=有观测）
  · 序列 = weak 重复 + strong 干扰（确定性编排）· 合成观测如实标注
  · 执行链 = core.step（R84 自动判分）— 用 run_term 是错入口（教训锁）
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

ROOT = r"E:/Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from dwc.core import DWC  # noqa: E402
from dwc.organs.judge import TaskScoreStore  # noqa: E402
from dwc.organs.actor import Receipt  # noqa: E402


def _dwc_seq(n_roles="weak"):
    d = DWC(3, 50, executor=None)
    d.judge.store = TaskScoreStore(dw_version="r103-test")
    return d


def test_success_stats_on_real_chain():
    """真链: step 判分后 success_stats 出 n/k/rate/streak（None 不计分母）。"""
    from sequence_eval import obs_for
    d = _dwc_seq()
    anchors = d.judge.anchors
    # 同任务两步: 先对值(过) 再错值(败) — streak 应 0, rate 0.5
    tid = next(t for t in sorted(anchors) if not t.startswith("_")
               and anchors[t].get("verifier_kind") == "behavior")

    def _ex(task):
        t = task.get("task_id", "")
        wrong = getattr(_ex, "wrong", False)
        obs = obs_for(anchors, t, wrong=wrong)
        return Receipt(ok=True, verified=True,
                       detail={"observed": obs} if obs else {})
    d.executor = _ex
    d.step({"task_id": tid, "kind": "dev"})
    _ex.wrong = True
    d.step({"task_id": tid, "kind": "dev"})
    st = d.success_stats()
    assert tid in st, st
    row = st[tid]
    assert row["n"] == 2 and row["k"] == 1, row
    assert abs(row["rate"] - 0.5) < 1e-9
    assert row["streak"] == 0, "尾部是失败 ⇒ streak=0"
    assert row["group"], "组归属随分数点"
    # 未观测任务不入表
    other = next(t for t in anchors if not t.startswith("_") and t != tid)
    assert other not in st, "无观测不装（成功侧入表语义=有观测）"


def test_success_stats_empty_store():
    """零观测 ⇒ {}（不装数, X2 同族）。"""
    d = _dwc_seq()
    assert d.success_stats() == {}


def test_success_stats_pure_function_unevaluated_excluded():
    """纯函数: success=None（未评价）不计入分母 — 纯口径单测。"""
    from dwc.organs.weakness import task_success_stats

    class P:
        def __init__(self, tid, ref, g="g"):
            self.task_id, self.evidence_ref, self.group_id = tid, ref, g
    ev = {"e1": {"success": True}, "e2": {"success": None},
          "e3": {"success": False}}
    out = task_success_stats(
        [P("t", "e1"), P("t", "e2"), P("t", "e3")], lambda r: ev[r])
    row = out["t"]
    assert row["n"] == 2, "None 不入分母（judge 纪律）"
    assert row["k"] == 1 and abs(row["rate"] - 0.5) < 1e-9
    assert row["streak"] == 0


def test_build_sequence_roles_deterministic():
    """确定性编排: weak 重复两步 + strong 干扰一步, 周期 3; 无历史保底。"""
    from sequence_eval import build_sequence
    d = _dwc_seq()
    seq = build_sequence(d, 9)
    assert len(seq) == 9
    roles = [s["role"] for s in seq]
    assert roles == (["weak_repeat"] * 2 + ["strong_interfere"]) * 3
    # weak ≠ strong 任务集
    wk = {s["task"] for s in seq if s["role"] == "weak_repeat"}
    st = {s["task"] for s in seq if s["role"] == "strong_interfere"}
    assert wk and st and not (wk & st), (wk, st)


def test_sequence_eval_script_runs():
    """脚本可跑: 判分链走 core.step（R84 契约 ⇒ outcomes 全 bool）+ 结构断言。"""
    script = os.path.join(ROOT, "scripts", "sequence_eval.py")
    outp = os.path.join(ROOT, "docs", "sequence_eval.json")
    r = subprocess.run([sys.executable, script, "--n", "6"],
                       capture_output=True, timeout=300, cwd=ROOT)
    assert r.returncode == 0, r.stderr.decode("utf-8", "replace")[-800:]
    out = json.load(open(outp, encoding="utf-8"))
    assert len(out["sequence"]) == 6
    assert all(isinstance(x, bool) for x in out["outcomes"]), \
        "★ R84 契约: step 链必判分 — outcomes 不许 None"
    assert out["pass_rate"] is not None
    assert "longest_pass_run" in out["k_eff"]
    # 合成观测如实标注 + 口径 caveats（不冒充）
    assert all(row["synthetic_obs"] for row in out["sequence"])
    assert "未核" in out["caveat"] and "非判分有效" in out["protocol"]
