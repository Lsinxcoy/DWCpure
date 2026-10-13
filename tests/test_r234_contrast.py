# -*- coding: utf-8 -*-
"""R234 · contrast 教训检索：成败对照优先（incumbent.py 同构 · 调整C）。"""
from __future__ import annotations

import os
import sys

ROOT = r"E:\Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "src"))
from dwc.organs.predictor import OutcomePredictor              # noqa: E402
from dwc.organs import predictor as P                          # noqa: E402
from dwc import agent_quality as Q                             # noqa: E402


def _two_logs(tmp_path):
    """独立 predictor 日志（隔离生产）。★ 与 lesson_contrast 的 patch
    lambda 必须指同一 log 文件（否则观测/读取两处, 判据恒 False）。"""
    return OutcomePredictor(log_path=str(tmp_path / "p.jsonl"))


def test_contrast_flag_math(tmp_path, monkeypatch):
    """★★ 对照标注锁: 同键有成有败 ⇒ True; 只有单侧/无观测 ⇒ False。
    ★ 判据 = 先验外两侧观测（succ>0 且 fail>0）— p∈(0,1) 在 Laplace 下恒真
      不可用（Layer 22 判据校准）。"""
    monkeypatch.setattr(P, "PRED_LOG", str(tmp_path / "p.jsonl"))
    pred = _two_logs(tmp_path)
    monkeypatch.setattr(P, "OutcomePredictor", lambda *a, **k: OutcomePredictor(
        log_path=str(tmp_path / "p.jsonl")))
    pred.observe("bench:t_mix", True)
    assert Q.lesson_contrast("t_mix") is False       # 单侧(仅成) ⇒ False
    pred.observe("bench:t_mix", False)
    assert Q.lesson_contrast("t_mix") is True        # 成+败 ⇒ 对照成立
    assert Q.lesson_contrast("t_never") is False     # 无观测


def test_recall_prefers_contrast_lessons(tmp_path, monkeypatch):
    """★★ 排序锁: 同 overlap 分下有对照的 lesson 先返回（强证据先注入）。"""
    import io, json
    les = str(tmp_path / "lessons.jsonl")
    rows = [
        {"task_id": "T_a", "fail_mode": "llm_format", "task": "去重 排序 列表",
         "detail": "噪声教训(只见过失败)"},
        {"task_id": "T_b", "fail_mode": "exhausted", "task": "去重 排序 列表",
         "detail": "对照教训(同任务有成有败)"},
    ]
    io.open(les, "w", encoding="utf-8").write(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    monkeypatch.setattr(Q, "LESSONS", les)
    # T_b 有对照, T_a 无 — 同 overlap(3) ⇒ T_b 先
    monkeypatch.setattr(Q, "lesson_contrast", lambda tid: tid == "T_b")
    hits = Q.recall_lessons("去重 排序 列表", k=2)
    assert [h["task_id"] for h in hits] == ["T_b", "T_a"], hits


def test_contrast_never_breaks_retrieval(tmp_path, monkeypatch):
    """★ 对照读取抛错静默降级: lesson_contrast 炸了检索照常（加分项不是门）。"""
    import io, json
    les = str(tmp_path / "lessons.jsonl")
    io.open(les, "w", encoding="utf-8").write(json.dumps(
        {"task_id": "T_x", "fail_mode": "exhausted", "task": "测试 任务",
         "detail": "d"}) + "\n")
    monkeypatch.setattr(Q, "LESSONS", les)

    def _boom(tid):
        raise RuntimeError("boom")
    monkeypatch.setattr(Q, "lesson_contrast", _boom)
    hits = Q.recall_lessons("测试 任务", k=1)   # 不许抛错
    assert hits and hits[0]["task_id"] == "T_x"
