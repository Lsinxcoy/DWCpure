# -*- coding: utf-8 -*-
"""R222 · ask 真审批: 人工授权通道（ctx '人工授权: <词>' 放行 + 留痕）。"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
from dwc.llm import task_exec as TE                             # noqa: E402
import pytest                                                   # noqa: E402


def test_parse_confirmed_lines():
    """★★ 授权解析: ctx 多行中 '人工授权: <词>' → 放行词集合; 无则空。"""
    ctx = "任务背景\n人工授权: git push\n人工授权: curl\n普通行"
    assert TE._parse_confirmed(ctx) == {"git push", "curl"}
    assert TE._parse_confirmed(None) == set()
    assert TE._parse_confirmed("无授权行") == set()


def test_confirmed_ask_runs_with_human_stamp():
    """★★★ 已授权 ask 动作: 真执行 + 观察带 confirmed_by_human 留痕
    （授权链可审计 — 谁放行的哪类操作有据可查）。"""
    import tempfile
    victim = os.path.join(tempfile.gettempdir(), "dwc_r222_victim.txt")
    with open(victim, "w", encoding="utf-8") as fh:
        fh.write("x")
    obs = TE._do_action("run", {"cmd": ["rm", victim],
                                "_confirmed": {"rm "}})
    assert obs["ok"] and obs["confirmed_by_human"] == "rm "
    assert not os.path.exists(victim), "授权后未真执行"


def test_unconfirmed_ask_still_refused(monkeypatch):
    """★ 未授权 ask 仍拒（授权不是默认 — 通道开了门没开）。
    ★ 隔离答复文件+短等待（生产答复文件里的真授权不许被测试消费）。"""
    iso = os.path.join(TE.ROOT, "var", "__test_ask__")
    os.makedirs(iso, exist_ok=True)
    monkeypatch.setattr(TE, "ASK_PENDING", os.path.join(iso, "p2.jsonl"))
    monkeypatch.setattr(TE, "ASK_ANSWERS", os.path.join(iso, "a2.jsonl"))
    monkeypatch.setattr(TE, "ASK_WAIT", 1)
    monkeypatch.setattr(TE, "_notify_feishu", lambda t: None)
    with pytest.raises(TE.TaskExecError, match="ask_required"):
        TE._do_action("run", {"cmd": ["curl", "http://x"]})
