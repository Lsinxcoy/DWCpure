# -*- coding: utf-8 -*-
"""R225 · 实时审批: pending→飞书问→轮询答复→放行/拒 + RPC ask_answer。"""
from __future__ import annotations

import io
import json
import os
import sys
import time

ROOT = r"E:\Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "src"))
from dwc.llm import task_exec as TE                             # noqa: E402
from dwc import agent_rpc as R                                  # noqa: E402


def _iso(tmp_path, monkeypatch):
    # ★ 隔离目录须在 var/ 下（生产守卫: pending 只许落 var/ — Layer 22:
    #   守卫是对的, 测试让路）
    iso = os.path.join(TE.ROOT, "var", "__test_ask__")
    os.makedirs(iso, exist_ok=True)
    monkeypatch.setattr(TE, "ASK_PENDING", os.path.join(iso, "p.jsonl"))
    monkeypatch.setattr(TE, "ASK_ANSWERS", os.path.join(iso, "a.jsonl"))
    monkeypatch.setattr(TE, "ASK_WAIT", 8)
    monkeypatch.setattr(TE, "_notify_feishu", lambda t: None)   # 打桩通知


def test_ask_human_approved_via_answers_file(tmp_path, monkeypatch):
    """★★★ 审批回路: pending 落盘 + 答复文件 approve ⇒ 放行（真实轮询,
    非 mock）。"""
    _iso(tmp_path, monkeypatch)
    import threading

    def _answer_later():
        time.sleep(1)
        with io.open(TE.ASK_ANSWERS, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"word": "rm ", "approve": True}) + "\n")
    threading.Thread(target=_answer_later, daemon=True).start()
    victim = os.path.join(TE.ROOT, "var", "__test_ask__", "v.txt")
    with open(victim, "w", encoding="utf-8") as fh:
        fh.write("x")
    obs = TE._do_action("run", {"cmd": ["rm", victim],
                                "_task_id": "T_ask225"})
    assert obs["ok"] and obs["confirmed_by_human"] == "rm "
    assert not os.path.exists(victim)
    # pending 留痕
    pend = io.open(TE.ASK_PENDING, encoding="utf-8").read()
    assert "T_ask225" in pend and "rm" in pend


def test_ask_human_timeout_refuses(tmp_path, monkeypatch):
    """★★ 超时=拒（不无限挂线程 — ASK_WAIT 上限语义）。"""
    _iso(tmp_path, monkeypatch)
    monkeypatch.setattr(TE, "ASK_WAIT", 1)
    r = TE._ask_human("curl ", "curl http://x", "T_to")
    assert "timeout" in str(r)


def test_ask_answer_rpc_writes(tmp_path, monkeypatch):
    """★★ RPC ask_answer 指令: 写答复文件（Hermes 飞书→RPC 的落点）。"""
    monkeypatch.setattr(R, "ASK_ANSWERS", str(tmp_path / "ra.jsonl"))
    out = R.cmd_ask_answer("curl ", True)
    assert out["ok"] and "ask_answer" in R.METHODS
    rows = [json.loads(x) for x in
            io.open(tmp_path / "ra.jsonl", encoding="utf-8").read().splitlines()]
    assert rows[-1]["word"] == "curl" and rows[-1]["approve"] is True


def test_denied_answer_refuses(tmp_path, monkeypatch):
    """★ deny 答复 ⇒ 拒。"""
    _iso(tmp_path, monkeypatch)
    with io.open(TE.ASK_ANSWERS, "w", encoding="utf-8") as fh:
        fh.write(json.dumps({"word": "curl ", "approve": False}) + "\n")
    r = TE._ask_human("curl ", "curl http://x", "T_deny")
    assert "denied" in str(r)
