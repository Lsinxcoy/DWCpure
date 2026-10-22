# -*- coding: utf-8 -*-
"""R436 · A/B 期间关掉「任务记忆」注入（跨臂泄漏）。

★★★ 现场（23:53 探针任务）：
    模型第 1 轮 analysis 就写「任务记忆已明确：CLI 入口路由文件是
    task_router.py。历史失败是因为答成了 cli_main.py」——
    它读到了**此前跑同一题时留下的 findings**。

★★★ 为什么这会毁掉 A/B：
    `recall_sources` 按任务文本的**词元重叠**召回历史记录，而两臂用的是
    **同一句任务原文** ⇒ stable 臂刚写下的 findings（常含答案）会被
    candidate 臂召回注入。泄漏方向恒定（后跑的那一臂占便宜），
    结论会系统性偏向 candidate。
"""
from __future__ import annotations

import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import dwc.agent_quality as Q     # noqa: E402
import dwc_prompt_ab as AB        # noqa: E402


def test_default_is_on(monkeypatch):
    """★★ 默认（无 env、无文件）必须**照常注入** —— 生产行为不能变。"""
    monkeypatch.delenv("DWC_SOURCES", raising=False)
    monkeypatch.setenv("DWC_VAR_DIR", os.path.join(ROOT, "var", "__nope__"))
    assert Q._sources_off() is False


def test_env_off(monkeypatch):
    monkeypatch.setenv("DWC_SOURCES", "off")
    assert Q._sources_off() is True


def test_file_off(tmp_path, monkeypatch):
    """★★ A/B 脚本用文件开关（不用重启 agent）。"""
    monkeypatch.delenv("DWC_SOURCES", raising=False)
    monkeypatch.setenv("DWC_VAR_DIR", str(tmp_path))
    assert Q._sources_off() is False
    (tmp_path / "sources_off").write_text("x", encoding="utf-8")
    assert Q._sources_off() is True


def test_context_empty_when_off(monkeypatch):
    """★★★ 关掉后即使有命中也必须返回空串（不许"少注入一点"）。"""
    monkeypatch.setattr(Q, "recall_sources",
                        lambda task, k=3: [{"task": task,
                                            "findings": "答案是 cli_main.py"}])
    monkeypatch.setenv("DWC_SOURCES", "off")
    assert Q.sources_context("随便什么问题") == ""


def test_context_present_when_on(monkeypatch):
    """★★ 开着时照常注入（证明上一条不是"永远返回空"）。"""
    monkeypatch.setattr(Q, "recall_sources",
                        lambda task, k=3: [{"task": task,
                                            "findings": "答案是 cli_main.py"}])
    monkeypatch.delenv("DWC_SOURCES", raising=False)
    monkeypatch.setenv("DWC_VAR_DIR", os.path.join(ROOT, "var", "__nope__"))
    out = Q.sources_context("随便什么问题")
    assert "cli_main.py" in out


def test_ab_script_toggles_sources_flag():
    """★★ A/B 脚本必须自己开/关这个开关（含 finally 恢复）。"""
    src = io.open(os.path.join(ROOT, "scripts", "dwc_prompt_ab.py"),
                  encoding="utf-8").read()
    assert "SOURCES_OFF" in src
    assert "os.remove(SOURCES_OFF)" in src
    assert "finally:" in src
