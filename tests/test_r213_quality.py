# -*- coding: utf-8 -*-
"""R213 · 任务质量回路: 失败分类判据表 + 教训沉淀 + 检索注入。"""
from __future__ import annotations

import json
import os
import sys

ROOT = r"E:\Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "src"))
from dwc import agent_quality as Q                             # noqa: E402


def test_classify_covers_all_branches():
    """★★★ 判据表全覆盖: ok/llm_reject/llm_format/no_artifact/exhausted/
    wrong_result 六分支 — 每分支行为级构造。"""
    assert Q.classify_fail({"status": "done"}, True) == "ok"
    assert Q.classify_fail({"status": "incomplete",
                            "why": "LLM 失败: x"}, False) == "llm_reject"
    assert Q.classify_fail({"status": "incomplete",
                            "why": "LLM 响应非 JSON: y"}, False) == "llm_format"
    assert Q.classify_fail({"status": "done", "artifacts": []},
                           False) == "no_artifact"
    assert Q.classify_fail({"status": "incomplete",
                            "why": "达轮数上限未 final"}, False) == "exhausted"
    assert Q.classify_fail({"status": "done",
                            "artifacts": ["var/inbox_work/x.md"]},
                           False) == "wrong_result"


def _isolate(monkeypatch, tmp_path):
    """★ 测试隔离: lessons/skills 全指临时目录（生产库真实教训不污染断言,
    2026-10-12 实测生产数据让 recall/阈值断言串味）。"""
    monkeypatch.setattr(Q, "LESSONS", str(tmp_path / "lessons.jsonl"))
    monkeypatch.setattr(Q, "SKILLS_DIR", str(tmp_path / "skills"))


def test_lesson_roundtrip_record_then_recall(monkeypatch, tmp_path):
    """★★★ 沉淀→检索闭环: 记一条『写脚本类』失败 ⇒ 同类任务文本能召回
    ⇒ 注入块含 fail_mode 与 detail。"""
    _isolate(monkeypatch, tmp_path)
    Q.record_lesson("T_lock213", "llm_format",
                    "写一个 python 脚本计算素数个数", "响应非 JSON")
    hits = Q.recall_lessons("写 python 脚本统计质数")
    assert any(h.get("task_id") == "T_lock213" for h in hits), hits
    ctx = Q.lessons_context("写 python 脚本计算素数个数")
    assert "llm_format" in ctx and "历史教训" in ctx


def test_recall_ignores_unrelated_task(monkeypatch, tmp_path):
    """★ 检索不乱命中: 无关任务文本返回空 ⇒ 注入零开销（不污染上下文）。"""
    _isolate(monkeypatch, tmp_path)
    Q.record_lesson("T_x", "exhausted", "统计文件个数", "轮数耗尽")
    assert Q.recall_lessons("zzzqqq www aaa") == []
    assert Q.lessons_context("zzzqqq www aaa") == ""


def test_tokens_handle_chinese_bigram():
    """★ 中文分词 2-gram（中英混排任务文本的召回基础）。"""
    toks = Q._tokens("统计文件个数 count files")
    assert "统计" in toks and "count" in toks
