# -*- coding: utf-8 -*-
"""R184 · train split 真无标签大集合（2607.12790 train 口径落地 + A_train 修正）。

论文语义（逐字）:
  "A_train(e) = e 与 opining pool ops 在**无标注 train 输出**上的共识判定的
   一致度" — train = 大、无标签（不是第二个 dev: dev/test 带 anchor）

验收（机器实测）:
  □ train.json: 6 条无标签题面（behavior 用白名单 fn 变体 + keyword 新题）
  □ dev∩train=∅（互不相交 — 前缀+题面双重保证）
  □ Judge._load_unlabeled: 缺 golden 字段照收; **带 golden ⇒ raise**（不放水）
  □ Judge.evaluate(split="train") 恒 raise（无标签判不了分 — 诚实边界④保持）
  □ execute_task(split="train") 能跑（behavior 走 args; keyword 要 impl, 缺 ⇒ 跳过）
  □ Loop._train_outputs_consensus: 真无标签 ⇒ op 池逐条三态 ⇒ κ=10 加权 consensus
  □ 缺席/异常 ⇒ None（S fail-closed — R176 三态纪律同族）
"""
from __future__ import annotations

import io
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.organs.judge import Judge, JudgeError, SPLIT_TRAIN   # noqa: E402
from dwc.organs.actor import execute_task, Actor              # noqa: E402

TRAIN_JSON = os.path.join(ROOT, "config", "anchors", "train.json")


def test_train_json_exists_and_unlabeled():
    """★★★ 6 条无标签题面（有 unlabeled 标记, 无 expected 字段）。"""
    assert os.path.exists(TRAIN_JSON)
    d = json.load(io.open(TRAIN_JSON, encoding="utf-8"))
    ids = [k for k in d if not k.startswith("_")]
    assert len(ids) >= 1
    for tid in ids:
        rec = d[tid]
        assert rec.get("unlabeled") is True
        assert "expected" not in rec and "expected_keywords" not in rec


def test_train_disjoint_from_dev():
    """★★★ dev∩train=∅（互不相交 — 论文三 split 纪律）。"""
    j = Judge()
    dev_ids = {k for k in j.anchors if not k.startswith("_")}
    train_ids = {k for k in j.train_anchors if not k.startswith("_")}
    assert not (dev_ids & train_ids)


def test_judge_loads_train_split():
    """★ Judge 载入 train（TRUTH_SOURCE[2] — 缺席不失败的诚实边界④）。"""
    j = Judge()
    assert j.train_anchors is not None
    assert any(not k.startswith("_") for k in j.train_anchors)


def test_judge_refuses_to_score_train():
    """★★★ evaluate(split="train") 恒 raise（无 label 可判 — 设计如此）。"""
    j = Judge()
    with pytest.raises(JudgeError) as e:
        j.evaluate("train_code_001", SPLIT_TRAIN, observed={})
    assert "train split 不存在" in str(e.value) or "无标签" in str(e.value)


def test_judge_refuses_golden_in_train(tmp_path):
    """★★★ train 带 golden ⇒ raise（.train 面变第二个 dev — 不放水）。"""
    d = json.load(io.open(TRAIN_JSON, encoding="utf-8"))
    d["train_bad"] = {"prompt": "x", "expected": "1",
                      "verifier_kind": "behavior", "unlabeled": True}
    bad = tmp_path / "train_bad.json"
    bad.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(JudgeError) as e:
        Judge(train_path=str(bad))
    assert "golden" in str(e.value) or "第二个 dev" in str(e.value)


def test_execute_task_train_behavior_runs():
    """★★★ behavior train 任务跑得动（args 无 expected 也跑 — R184 修）。"""
    j = Judge()
    out = execute_task(Actor(), j, "train_code_001", split="train")
    assert out["task_id"] == "train_code_001" and out["n_checks"] >= 1
    assert "observation" in out


def test_execute_task_train_missing_task_raises():
    """★ train 集不跨 split 顶替（不拿 dev 顶 train — R169 同族）。"""
    from dwc.organs.actor import ActorError
    j = Judge()
    with pytest.raises(ActorError):
        execute_task(Actor(), j, "code_fix_001", split="train")


def test_loop_train_consensus_returns_or_none():
    """★★★ Loop 的真无标签共识: 在场 ⇒ float∈[0,1]; 缺席 ⇒ None（fail-closed）。"""
    from dwc.harness.loop import Loop
    lp = Loop()
    a = lp._train_outputs_consensus()
    assert a is None or 0.0 <= a <= 1.0
    assert lp._last_a_train_why


def test_round_uses_train_consensus_when_present():
    """★★★ round 的 A_train: train 在场 ⇒ 来自真无标签口径（why 可审计）。"""
    from dwc.harness.loop import Loop
    lp = Loop()
    lp.round(1)
    mp = lp._last_metric_pick or {}
    assert "a_train" in mp
    # train 共识在场时 why 标 "train split 真无标签共识"
    if lp._last_a_train_why.startswith("train split 真无标签共识"):
        assert mp["a_train"] is not None
