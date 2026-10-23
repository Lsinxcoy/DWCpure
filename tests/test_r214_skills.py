# -*- coding: utf-8 -*-
"""R214 · 技能固化: 同类教训 ≥ 阈值 ⇒ 规矩文件 + 注入。"""
from __future__ import annotations

import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
from dwc import agent_quality as Q                             # noqa: E402


def _isolate(monkeypatch, tmp_path):
    """★ 测试隔离（生产教训库不污染阈值断言 — 实测生产已有 exhausted 残留）。"""
    monkeypatch.setattr(Q, "LESSONS", str(tmp_path / "lessons.jsonl"))
    monkeypatch.setattr(Q, "SKILLS_DIR", str(tmp_path / "skills"))
    os.makedirs(str(tmp_path / "skills"), exist_ok=True)


def _seed(mode, n):
    for i in range(n):
        Q.record_lesson("T_seed214_%s_%d" % (mode[:4], i), mode,
                        "测试任务 %d 类" % i, "例证 %d" % i)


def test_consolidate_threshold(monkeypatch, tmp_path):
    """★★★ 固化阈值: <3 条不固化; ≥3 条出技能文件且含模板规矩。"""
    _isolate(monkeypatch, tmp_path)
    sp = os.path.join(str(tmp_path / "skills"), "exhausted.md")
    _seed("exhausted", 2)
    assert Q.consolidate_skills().get("exhausted") is None, "2 条就固化 — 阈值失守"
    _seed("exhausted", 1)
    made = Q.consolidate_skills()
    assert made.get("exhausted", 0) >= 3, made
    body = open(sp, encoding="utf-8").read()
    assert "精简步骤" in body and "例证" in body, "技能文件缺规矩或例证"


def test_lessons_context_includes_skill_when_recalled(monkeypatch, tmp_path):
    """★★ 技能注入: 召回的 fail_mode 已固化 ⇒ 规矩全文进上下文。"""
    _isolate(monkeypatch, tmp_path)
    _seed("exhausted", 3)
    Q.consolidate_skills()
    ctx = Q.lessons_context("测试任务 exhausted 相关")
    assert "已固化规矩" in ctx and "精简步骤" in ctx, ctx[:200]


def test_skill_file_never_touches_anchors(monkeypatch, tmp_path):
    """★★★ GAI 底线: 技能写 var/（运行时经验）, 绝不进 config/anchors/（真值
    源只增不改 — agent 不可写锚区的纪律延伸）。"""
    _isolate(monkeypatch, tmp_path)
    _seed("no_artifact", 3)
    Q.consolidate_skills()
    anchor_dir = os.path.join(ROOT, "config", "anchors")
    leaked = [f for f in os.listdir(anchor_dir) if f.endswith(".md")]
    assert leaked == [], "技能文件漏进真值源目录: %s" % leaked
