# -*- coding: utf-8 -*-
"""R201 · 深度严格工程化审计的补救锁（R197-R200 四轮 + 集成缝的审计产出）。

审计发现（详见 docs/AUDIT_R197_R200.html）:
  P1-2: epoch 双真源（账本机器值 vs 知识档手打值）无机器守卫 ⇒ 本测试补守卫
  P2-1: Verdict.to_dict 的 sigs 序列化只有**文本锁**（Layer 18.4 风险:
        可给死代码发证书）⇒ 本测试补**行为级**证据
"""
from __future__ import annotations

import glob
import json
import os
import re
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.harness.anchor_drift import epoch_of                          # noqa: E402
from dwc.organs.judge import Judge                                     # noqa: E402


def _latest_knowledge():
    files = glob.glob(os.path.join(ROOT, "archive", "knowledge3_R*.json"))
    assert files, "知识档目录空 — 前提变了"

    def _gen(f):
        m = re.search(r"R(\d+)", os.path.basename(f))
        return int(m.group(1)) if m else -1
    files.sort(key=_gen)
    return files[-1]


def test_latest_knowledge_epoch_matches_ledger():
    """★★★ P1-2 补救锁: 最新知识档的 epoch_id 必须 == epoch 账本机器值。

    ★ 为什么需要: epoch 有**两条口径** — anchor_epochs.jsonl（record_epoch
      机器写）与知识档 evaluation_config.epoch_id（提交流程手打）。当前两
      者一致, 但无机器守卫 ⇒ 将来 record_epoch 后忘改知识档会**静默失配**
      （审计链说谎）。本测试 = 失配即红。
    ★ R197/R198 档记 epoch_id=1 是**历史正确**（当时账本尚未存在/未换代）,
      守卫只查**最新**一档（历史档是时间胶囊, 不许改）。
    """
    f = _latest_knowledge()
    d = json.load(open(f, encoding="utf-8"))
    eid = (d.get("inheritance") or {}).get(
        "evaluation_config", {}).get("epoch_id")
    led = epoch_of(ROOT)
    assert eid == led, (
        "最新知识档 %s 的 epoch_id=%s 与账本=%d 失配 ⇒ 双真源已分叉, "
        "提交流程必须用 epoch_of(ROOT) 不得手打" % (os.path.basename(f), eid, led))


def test_verdict_to_dict_serializes_sigs_behaviorally():
    """★★★ P2-1 补救锁: sigs 序列化的**行为级**证据（原只有文本锁 —
    Layer 18.4: 文本断言会给死代码发证书）。

    ★ 构造: 失败 verdict（reproduce_001 错答案）⇒ to_dict() 的 sigs 必须
      是 list[dict] 且与 Verdict.sigs 逐项相等; pass 态必须是 []。
    """
    j = Judge()
    v_fail = j.evaluate("reproduce_001", "dev",
                        observed={"answer": "mean=5.00, std=1.00, median=5.00"})
    d = v_fail.to_dict()
    assert isinstance(d.get("sigs"), list), "to_dict 缺 sigs 或非 list"
    assert d["sigs"] == v_fail.sigs, "序列化值 ≠ 内存值（序列化口径漂移）"
    assert d["sigs"] and all(isinstance(x, dict) for x in d["sigs"]), (
        "fail 态 sigs 应为非空 dict 列表, 实得 %r" % d["sigs"])
    v_pass = j.evaluate("reproduce_001", "dev",
                        observed={"answer": "mean=6.00, std=2.83, median=6.00"})
    assert v_pass.to_dict()["sigs"] == [], "pass 态序列化必须 []"
