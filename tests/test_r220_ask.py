# -*- coding: utf-8 -*-
"""R220 · 权限三态 ask 级（allow/deny/ask — 头部 agent 标配的审批在环）。"""
from __future__ import annotations

import os
import sys

ROOT = r"E:\Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "src"))
from dwc.llm import task_exec as TE                             # noqa: E402
import pytest                                                   # noqa: E402


def test_ask_level_three_way():
    """★★★ 三态分级: 危险词→deny（调用方硬拒）; ask 词→ask; 普通→放行。"""
    assert TE._ask_level("git push origin master") == "git push"
    assert TE._ask_level("curl http://x.com") == "curl "
    assert TE._ask_level("rm old.txt") == "rm "
    assert TE._ask_level("ls -la src") is None
    assert TE._ask_level("python scripts/gate.py") is None


def test_ask_action_refused_with_clear_reason(monkeypatch):
    """★★★ ask 级动作执行结果: **不执行** + 明确告知需人工授权（LLM 能换路
    或 final 说明 — 不静默不硬吞, 报告可审计）。
    ★ 隔离+短等待（R225 后 ask 走轮询; 生产答复文件的真授权不许被测试
    消费也不许让测试放行）。"""
    iso = os.path.join(TE.ROOT, "var", "__test_ask__")
    os.makedirs(iso, exist_ok=True)
    monkeypatch.setattr(TE, "ASK_PENDING", os.path.join(iso, "p3.jsonl"))
    monkeypatch.setattr(TE, "ASK_ANSWERS", os.path.join(iso, "a3.jsonl"))
    monkeypatch.setattr(TE, "ASK_WAIT", 1)
    monkeypatch.setattr(TE, "_notify_feishu", lambda t: None)
    with pytest.raises(TE.TaskExecError, match="ask_required"):
        TE._do_action("run", {"cmd": ["git", "push", "origin", "master"]})
    with pytest.raises(TE.TaskExecError, match="ask_required"):
        TE._do_action("run", {"cmd": ["curl", "http://example.com"]})


def test_deny_still_hard_blocks_first():
    """★★ 黑名单优先于 ask（rm -rf 是 deny 不是 ask — 顺序不能反）。"""
    with pytest.raises(TE.TaskExecError, match="黑名单"):
        TE._do_action("run", {"cmd": ["rm", "-rf", "/"]})
