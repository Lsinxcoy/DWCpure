# -*- coding: utf-8 -*-
"""R438 · 记忆维度：教训晋升后**真的被任务路径读到**。

★ 诚实记账：`lessons_context` 早就存在（聊天路径用），
  缺的不是"注入函数"，而是 **task_exec 的 sources_context 没调它**。
  所以本轮改的是 `sources_context`（加一段），不是另写一个 lessons_context
  —— 同一件事两种写法 = 两条真源（R426 教训；本文件首版正是踩了这个坑）。

锁：
1. 任务路径（sources_context）能带出"历史教训"。
2. 零重叠 ⇒ 不带（零命中零开销）。
3. 同 overlap 下，晋升过的教训（medium/long）排在 short 前面
   —— 否则 promote_lessons 晋升了也没用。
4. 信源段与教训段可以并存。
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc import agent_quality as AQ   # noqa: E402


def _write(tmp_path, rows):
    p = tmp_path / "lessons.jsonl"
    with open(p, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return str(p)


def _row(tier, task, detail, use=0, tid="t1"):
    return {"tier": tier, "task": task, "detail": detail,
            "fail_mode": "wrong_value", "use_count": use, "task_id": tid}


def test_task_path_injects_lessons(tmp_path, monkeypatch):
    monkeypatch.setattr(AQ, "LESSONS", _write(
        tmp_path, [_row("short", "读取 search_code 定义", "要用 DEFINITIONS 段")]))
    monkeypatch.setattr(AQ, "_sources_off", lambda: False)
    out = AQ.sources_context("读取 search_code 定义")
    assert "历史教训" in out and "DEFINITIONS" in out


def test_no_overlap_means_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(AQ, "LESSONS", _write(
        tmp_path, [_row("short", "完全无关的主题", "毫不相干")]))
    monkeypatch.setattr(AQ, "_sources_off", lambda: False)
    # 生产 sources 库是另一份数据；本测试只测教训段 ⇒ 信源段固定空
    monkeypatch.setattr(AQ, "recall_sources", lambda task, k=3: [])
    assert AQ.sources_context("读取 search_code 定义") == ""


def test_promoted_lesson_ranks_first(tmp_path, monkeypatch):
    monkeypatch.setattr(AQ, "LESSONS", _write(tmp_path, [
        _row("short", "读取 search_code 定义", "SHORT 提示", tid="a"),
        _row("long", "读取 search_code 定义", "LONG 提示", tid="b"),
    ]))
    monkeypatch.setattr(AQ, "_sources_off", lambda: False)
    out = AQ.sources_context("读取 search_code 定义", k=1)
    assert "LONG 提示" in out and "SHORT 提示" not in out


def test_sources_and_lessons_coexist(tmp_path, monkeypatch):
    monkeypatch.setattr(AQ, "LESSONS", _write(
        tmp_path, [_row("short", "读取 search_code 定义", "要用 DEFINITIONS 段")]))
    monkeypatch.setattr(AQ, "_sources_off", lambda: False)
    monkeypatch.setattr(AQ, "recall_sources", lambda task, k=3: [
        {"urls": [{"kind": "doc", "url": "http://x"}], "queries": ["q"],
         "findings": "f"}])
    out = AQ.sources_context("读取 search_code 定义")
    assert "历史任务找到的相关材料" in out
    assert "历史教训" in out
