# -*- coding: utf-8 -*-
"""R107 · 阶段 3b — 三维解耦实验 + 等预算安慰剂臂 + 复现硬规则。

判据（方案 §⑥T4 验收字面: 对照臂进报告协议）:
  · author(A 实例)≠user(全新 B 实例) 的解耦结构在位
  · 三臂 = transplant / blind_placebo(等数量盲造) / baseline — 同预算同任务
  · 归因 = 内容效应须 transplant−placebo>0（Verma 手段; ≤0 不冒充增益）
  · 复现协议四条(seed/全新实例/安慰剂在协议/确定性 executor) + 效度边界如实
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

ROOT = r"E:/Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from transfer_and_attribution import run_arms  # noqa: E402

ANCHORS = json.load(open(os.path.join(ROOT, "config", "anchors", "dev.json"),
                         encoding="utf-8"))
TASKS = sorted(t for t in ANCHORS
               if not t.startswith("_")
               and ANCHORS[t].get("verifier_kind") == "behavior")


def _arms():
    author, user = TASKS[:1], TASKS[1:] or TASKS
    return run_arms(ANCHORS, author, user, n_author=2, n_user=3, seed=42)


def test_three_arms_structure():
    """三臂 + 同预算 + 同任务批（结构验收）。"""
    exp = _arms()
    arms = exp["arms"]
    assert set(arms) == {"transplant", "blind_placebo", "baseline"}
    # 同预算: 三臂 n_steps 相同
    steps = {a: v["n_steps"] for a, v in arms.items()}
    assert len(set(steps.values())) == 1, steps
    # 盲安慰剂 = 同批注入数（与 transplant 等数量 — 等预算字面）
    assert (arms["blind_placebo"]["n_artifacts"]
            == max(arms["transplant"]["n_artifacts"], 1))
    assert arms["baseline"]["n_artifacts"] == 0
    # 判分必到（R84 契约 — outcomes 不许 None）
    for a, v in arms.items():
        assert all(isinstance(x, bool) for x in v["outcomes"]), a


def test_author_user_decoupled():
    """author≠user 解耦: author 任务不进 user 批。"""
    exp = _arms()
    author_tasks = TASKS[:1]
    user_tasks = TASKS[1:] or TASKS
    assert not (set(author_tasks) & set(user_tasks))
    assert exp["author_steps"] == 2 and exp["user_steps"] == 3


def test_reproducibility_rules_in_protocol():
    """复现硬规则进协议（验收字面）+ 效度边界如实。"""
    script = os.path.join(ROOT, "scripts", "transfer_and_attribution.py")
    out = subprocess.run([sys.executable, script],
                         capture_output=True, timeout=600, cwd=ROOT)
    assert out.returncode == 0, out.stderr.decode("utf-8", "replace")[-600:]
    rep = json.load(open(os.path.join(ROOT, "docs",
                                      "transfer_attribution.json"),
                         encoding="utf-8"))
    rules = "\n".join(rep["reproducibility_rules"])
    assert "seed" in rules and "安慰剂" in rules
    assert rep["protocol"].count("等预算") >= 1
    assert rep["attribution"]["content_effect_verdict"] in (
        "content_gain", "placebo_equal", "negative", "not_computable")
    # 效度边界: golden 替身不读记忆的声明在位（不许把恒等当记忆无效证据）
    cave = json.dumps(rep["caveats"], ensure_ascii=False)
    assert "旁路" in cave and "结构必然" in cave
    # 归因数字 = transplant − placebo 算术一致
    arms = rep["experiment"]["arms"]
    t, p = arms["transplant"]["success_rate"], arms["blind_placebo"]["success_rate"]
    got = rep["attribution"]["transplant_minus_placebo"]
    assert got == (t - p), (got, t, p)
