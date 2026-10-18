# -*- coding: utf-8 -*-
"""★ R327 · client 回退链认 reasoning 键（opencode-go/MiMo 实测：content
空串＋reasoning 5891 字＋finish length —— 旧链只认 reasoning_content，
5891 字被当空丢弃）。

锁（fake urlopen，不碰真端点）：
1. content 非空 ⇒ 用 content（老路）。
2. content 空＋reasoning 有 ⇒ 用 reasoning（新）。
3. 双空 ⇒ ok=False“返回内容为空”（纪律不变）。
"""
from __future__ import annotations

import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.llm.client import LLMClient


class _FakeResp:
    def __init__(self, payload):
        self._raw = json.dumps(payload).encode("utf-8")

    def read(self):
        return self._raw

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _body(content, reasoning=None, reasoning_content=None):
    msg = {"role": "assistant", "content": content, "reasoning": reasoning}
    if reasoning_content is not None:
        msg["reasoning_content"] = reasoning_content
    return {"choices": [{"message": msg, "finish_reason": "length"}],
            "usage": {}}


def _client(monkeypatch, payload):
    c = LLMClient(base_url="http://127.0.0.1:9", api_key="x",
                  model="m", timeout=5)
    monkeypatch.setattr("urllib.request.urlopen",
                        lambda *a, **k: _FakeResp(payload))
    return c


def test_r327_content_wins(monkeypatch):
    c = _client(monkeypatch, _body("CONTENT", reasoning="RS"))
    r = c.complete("hi", max_tokens=10)
    assert r.ok and r.text == "CONTENT"


def test_r327_reasoning_fallback(monkeypatch):
    c = _client(monkeypatch, _body("", reasoning="RS-DRAFT"))
    r = c.complete("hi", max_tokens=10)
    assert r.ok and r.text == "RS-DRAFT"


def test_r327_both_empty_still_error(monkeypatch):
    c = _client(monkeypatch, _body("", reasoning=""))
    r = c.complete("hi", max_tokens=10)
    assert not r.ok and "为空" in r.error


def test_r327_cron_wires_draft_tokens():
    src = open(os.path.join(ROOT, "scripts",
                            "dwc_evo_round_cron.py"),
               encoding="utf-8").read()
    assert '"--draft-tokens"' in src
    assert "max_tokens=_a.draft_tokens" in src
