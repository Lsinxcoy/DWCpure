# -*- coding: utf-8 -*-
"""R376 · 推理模型 token 耗尽 ⇒ 不许把 reasoning 当答案（用户报「一直反馈
dwc任务未完成」的根因修复）。

★★★ 现场取证（2026-10-20 02:30-04:11 nightbench 10 单 9 挂）:
  why = 'LLM 响应非 JSON（容错提取后仍失败）: We need answer task: ...'
  ⇒ 判分侧拿到的是**英文推理散文**，不是模型输出。

★★ 真根因（三层，逐层实测）:
  ① 端点层（正常）: 原始 HTTP 里 `content` 与 `reasoning_content` 是
     **分离的两个键**，`content` 是干净 JSON（max_tokens 足够时）。
  ② 模型层（正常）: deepseek-v4.1-flash 是推理模型，长任务上推理会吃掉
     max_tokens（实测 max_tokens=300 时 content_len=0 / finish=length）。
  ③ **客户端层（真 bug）**: `complete()` 在 content 空时用
     `reasoning_content` 顶替正文并返回 **ok=True**；`complete_stream()`
     在 delta 里同样把 reasoning_content 当正文拼进 text。
     ⇒ 「降级」与「成功」不可区分 —— 违反本项目纪律。

★ 判据（本轮锁的是"可区分"而非"必须成功"）:
  · content 空 + reasoning 有 ⇒ ok=False 且 meta["kind"]=="reasoning_only"
    （**不静默当答案**），并把 finish_reason 透出（length 说明是 token 被吃）
  · content 有 ⇒ 行为不变（不许因修 bug 把好路径也判死）
  · 流式同理：delta 里 reasoning 不拼进正文；只有 reasoning 无 content
    ⇒ ok=False / kind=="reasoning_only"
  · 两条路径都要 `meta["finish_reason"]` 可见（排障要能一眼看出 length）
"""
from __future__ import annotations

import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.llm import client as C  # noqa: E402


def _whole(body: dict):
    """造一个 urlopen 返回体（整段 JSON）。"""
    raw = json.dumps(body).encode("utf-8")

    class _R:
        headers = {"Content-Type": "application/json"}

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return raw

    return _R()


def _mk(monkeypatch, body: dict):
    monkeypatch.setenv("DWC_LLM_RETRIES", "0")
    cl = C.LLMClient(base_url="http://fake/v1", api_key="k", model="m",
                     timeout=5)
    monkeypatch.setattr(C.urllib.request, "urlopen",
                        lambda *a, **k: _whole(body))
    return cl


def _resp(content, reasoning=None, finish="stop"):
    msg = {"role": "assistant", "content": content}
    if reasoning is not None:
        msg["reasoning_content"] = reasoning
    return {"choices": [{"message": msg, "finish_reason": finish}]}


# ─────────────────────────── ① complete(): 推理不能当答案


def test_reasoning_only_is_not_success(monkeypatch):
    """★★★ content 空 + reasoning 有 ⇒ 必须 ok=False。

    旧行为：text=reasoning、ok=True ⇒ 下游 _extract_json 拿到英文散文
    ⇒ 报"响应非 JSON"⇒ 用户看到「任务未完成」。真正的失败原因被掩盖。
    """
    cl = _mk(monkeypatch, _resp(
        "", "We need answer task. Need inspect files...", finish="length"))
    r = cl.complete("x", max_tokens=300, json_mode=True)
    assert r.ok is False, (
        "推理文本被当成答案返回了（ok=True）—— 降级与成功不可区分")
    assert r.meta.get("kind") == "reasoning_only", r.meta


def test_reasoning_only_exposes_finish_reason(monkeypatch):
    """★★ 必须透出 finish_reason：length = token 被推理吃光（排障关键）。"""
    cl = _mk(monkeypatch, _resp("", "long thinking...", finish="length"))
    r = cl.complete("x", max_tokens=300)
    assert r.meta.get("finish_reason") == "length", r.meta
    assert "reasoning" in str(r.error).lower() or "推理" in str(r.error), r.error


def test_legacy_reasoning_key_also_not_success(monkeypatch):
    """★ R327 的 `reasoning`（opencode/MiMo 键名）同样不许顶替答案。"""
    body = {"choices": [{"message": {"role": "assistant", "content": "",
                                     "reasoning": "thinking..."},
                         "finish_reason": "length"}]}
    cl = _mk(monkeypatch, body)
    r = cl.complete("x", max_tokens=300)
    assert r.ok is False, "reasoning 键被当成答案（R327 路径漏修）"
    assert r.meta.get("kind") == "reasoning_only", r.meta


def test_normal_content_still_ok(monkeypatch):
    """★★ 回归保护：content 有内容时行为完全不变。"""
    cl = _mk(monkeypatch, _resp('{"answer":"ok"}', "thinking...", "stop"))
    r = cl.complete("x", max_tokens=1600, json_mode=True)
    assert r.ok is True
    assert r.text == '{"answer":"ok"}'
    assert json.loads(r.text)["answer"] == "ok"
    assert r.meta.get("finish_reason") == "stop", r.meta


def test_content_plus_reasoning_never_concatenated(monkeypatch):
    """★★ 有 content 时不得把 reasoning 拼进去（否则 JSON 被污染）。"""
    cl = _mk(monkeypatch, _resp('{"a":1}', "We need think...", "stop"))
    r = cl.complete("x")
    assert r.text == '{"a":1}', "正文被推理污染: %r" % r.text
    assert "We need" not in r.text


def test_empty_both_still_reports_empty(monkeypatch):
    """★ 两者都空 ⇒ 仍报 empty（旧语义不破）。"""
    cl = _mk(monkeypatch, _resp("", None, "stop"))
    r = cl.complete("x")
    assert r.ok is False and r.meta.get("kind") == "empty", r.meta


# ─────────────────────────── ② complete_stream(): 同上


class _SSE:
    """把 delta 列表包成 SSE 行流。"""

    def __init__(self, deltas, finish="stop"):
        lines = []
        for d in deltas:
            lines.append(("data: " + json.dumps(
                {"choices": [{"delta": d}]}) + "\n").encode("utf-8"))
        lines.append(("data: " + json.dumps(
            {"choices": [{"delta": {}, "finish_reason": finish}]}) + "\n"
        ).encode("utf-8"))
        lines.append(b"data: [DONE]\n")
        self._lines = lines
        self.headers = {"Content-Type": "text/event-stream"}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def __iter__(self):
        return iter(self._lines)


def _mk_stream(monkeypatch, deltas, finish="stop"):
    monkeypatch.setenv("DWC_LLM_RETRIES", "0")
    cl = C.LLMClient(base_url="http://fake/v1", api_key="k", model="m",
                     timeout=5)
    monkeypatch.setattr(C.urllib.request, "urlopen",
                        lambda *a, **k: _SSE(deltas, finish))
    return cl


def test_stream_reasoning_not_concatenated(monkeypatch):
    """★★★ 流式里 reasoning delta 不得进正文（旧代码 `if not piece:
    piece = delta.get("reasoning_content")` 直接拼接）。"""
    got = []
    cl = _mk_stream(monkeypatch, [
        {"reasoning_content": "We need "},
        {"reasoning_content": "think..."},
        {"content": '{"answer":'},
        {"content": '"ok"}'},
    ])
    r = cl.complete_stream("x", max_tokens=1600, on_delta=got.append)
    assert r.ok is True
    assert r.text == '{"answer":"ok"}', "正文被推理污染: %r" % r.text
    assert "".join(got) == '{"answer":"ok"}', (
        "on_delta 把推理当正文推给调用方了: %r" % ("".join(got),))


def test_stream_reasoning_only_is_not_success(monkeypatch):
    """★★ 流式只有 reasoning ⇒ ok=False / kind=reasoning_only。"""
    cl = _mk_stream(monkeypatch, [{"reasoning_content": "We need think..."}],
                    finish="length")
    r = cl.complete_stream("x", max_tokens=300)
    assert r.ok is False, "流式把推理当答案（ok=True）"
    assert r.meta.get("kind") == "reasoning_only", r.meta
    assert r.meta.get("finish_reason") == "length", r.meta


def test_stream_normal_still_ok(monkeypatch):
    """★★ 回归保护：正常流式行为不变。"""
    got = []
    cl = _mk_stream(monkeypatch, [{"content": "你"}, {"content": "好"}])
    r = cl.complete_stream("x", on_delta=got.append)
    assert r.ok and r.text == "你好" and got == ["你", "好"]
    assert r.meta.get("streamed") is True
