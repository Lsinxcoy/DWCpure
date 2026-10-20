# -*- coding: utf-8 -*-
"""★ R327 · client 回退链认 reasoning 键（opencode-go/MiMo 实测：content
空串＋reasoning 5891 字＋finish length —— 旧链只认 reasoning_content，
5891 字被当空丢弃）。

★★★ R376 重锚（2026-10-20）: R327 当时让 reasoning **顶替答案**
（`ok=True, text=reasoning`）。生产实测证明那是**错的**——
nightbench 10 单 9 挂，`why` 全是「LLM 响应非 JSON: We need answer...」，
而真因是「推理把 max_tokens 吃光、正文一个字没写」。用推理冒充答案
⇒ 降级与成功不可区分 ⇒ 真正的失败原因被掩盖。

新语义（本文件现在锁的）:
1. content 非空 ⇒ 用 content（老路不变）。
2. content 空＋reasoning 有 ⇒ **ok=False / kind="reasoning_only"**，
   并把 finish_reason 与推理字数透出（诊断用），**不冒充答案**。
3. 双空 ⇒ ok=False「返回内容为空」（纪律不变）。

根因修法见 test_r377_reasoning_budget.py（max_tokens 可配 +
reasoning_effort=none 压制推理）。
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
    """★★★ R376 重锚: reasoning **不许**顶替答案。

    旧断言 `r.ok and r.text == "RS-DRAFT"` 锁的是「推理冒充答案」，
    而生产 10 单 9 挂的真因正是这个冒充 —— 下游拿到英文散文判非 JSON，
    真正的「token 被推理吃光」被掩盖。
    """
    c = _client(monkeypatch, _body("", reasoning="RS-DRAFT"))
    r = c.complete("hi", max_tokens=10)
    assert r.ok is False, "推理被当成答案返回了（降级与成功不可区分）"
    assert r.meta.get("kind") == "reasoning_only", r.meta
    assert r.meta.get("finish_reason") == "length", r.meta
    assert r.meta.get("reasoning_chars") == len("RS-DRAFT"), r.meta
    assert "推理" in r.error, r.error


def test_r327_both_empty_still_error(monkeypatch):
    c = _client(monkeypatch, _body("", reasoning=""))
    r = c.complete("hi", max_tokens=10)
    assert not r.ok and "为空" in r.error


def test_r327_cron_wires_draft_tokens():
    src = open(os.path.join(ROOT, "scripts",
                            "dwc_evo_round_cron.py"),
               encoding="utf-8").read()
    assert '"--draft-tokens", type=int, default=2000' in src
    assert "max_tokens=_a.draft_tokens" in src
