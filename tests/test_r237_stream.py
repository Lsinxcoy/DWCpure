# -*- coding: utf-8 -*-
"""R237 · 流式 + 乱码修：SSE delta 回调 / 回退 / answer 状态机 / ANSI 降级。"""
from __future__ import annotations

import io
import json
import os
import sys
import urllib.error
from types import SimpleNamespace

ROOT = r"E:\Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from dwc.llm import client as C                                # noqa: E402
from dwc.llm import task_exec as TE                            # noqa: E402
import dwc_chat as CH                                          # noqa: E402


class _FakeResp:
    """伪 SSE 响应（逐行迭代 — 模拟 OpenAI chunk 流）。"""
    def __init__(self, chunks, ctype="text/event-stream"):
        self.headers = {"Content-Type": ctype}
        lines = []
        for i, t in enumerate(chunks):
            lines.append(("data: %s\n" % json.dumps(
                {"choices": [{"delta": {"content": t}}]})).encode("utf-8"))
            lines.append(b"id: %d\n\n" % i)
        lines.append(b"data: [DONE]\n\n")
        self._lines = lines

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def __iter__(self):
        return iter(self._lines)


def _client(monkeypatch, chunks, ctype="text/event-stream"):
    monkeypatch.setenv("DWC_LLM_RETRIES", "0")
    cl = C.LLMClient(base_url="http://fake/v1", api_key="k", model="m",
                     timeout=5)
    monkeypatch.setattr(C.urllib.request, "urlopen",
                        lambda *a, **k: _FakeResp(chunks, ctype))
    return cl


def test_stream_deltas_and_result(monkeypatch):
    """★★★ 流式锁: 每 delta 回调 + 整段拼合 + meta.streamed=True。"""
    got = []
    cl = _client(monkeypatch, ["你", "好", "，", "世界"])
    r = cl.complete_stream("x", max_tokens=64, on_delta=got.append)
    assert r.ok and r.text == "你好，世界"
    assert got == ["你", "好", "，", "世界"]
    assert r.meta.get("streamed") is True and r.meta.get("n_chunks") == 4


def test_stream_falls_back_on_non_sse(monkeypatch):
    """★★ 非 SSE 响应 ⇒ 自动回退整段 complete（meta.stream_fallback=True
    — 用不用流看得见, 不静默）。"""
    cl = _client(monkeypatch, [], ctype="application/json")
    # urlopen 先被流式用（非SSE触发 ValueError）, 回退 complete 再次 urlopen
    # — 二次调用需返回整段 JSON 响应
    calls = {"n": 0}
    body = json.dumps({"choices": [{"message": {"content": "整段答案"}}]}).encode()

    class _Whole:
        headers = {"Content-Type": "application/json"}
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return body
        def __iter__(self): return iter([])

    def _uo(*a, **k):
        calls["n"] += 1
        if calls["n"] == 1:                 # 流式请求 → 非 SSE ctype
            return _FakeResp([], ctype="application/json")
        return _Whole()                     # 回退整段
    monkeypatch.setattr(C.urllib.request, "urlopen", _uo)
    r = cl.complete_stream("x", max_tokens=64)
    assert r.ok and r.text == "整段答案"
    assert r.meta.get("stream_fallback") is True


def test_token_events_reach_progress(monkeypatch):
    """★★★ task_exec 流接线: 有 progress 的调用走 complete_stream,
    每 delta 发 token 事件（final 轮流式输出的数据源）。

    ★ R384 重锚：流式只存在于 **JSON 路径**。原生 tool calling 走非流式
      （tool_calls 要解析 delta 分片，端点按整段返回），这是明确取舍：
      正确性（真调工具）> 逐字动画。
      故本条显式关掉原生工具来测流式接线；下面再锁"原生模式下不流式
      但仍有 round 事件"的新语义。
    """
    monkeypatch.setenv("DWC_LLM_NATIVE_TOOLS", "0")
    events = []
    class _LLM:
        configured = True
        def complete_stream(self, *a, on_delta=None, **k):
            for t in ("答", "案"):
                on_delta(t)
                events.append(t)
            return SimpleNamespace(ok=True, error=None,
                text='{"analysis": "完", "op": "final", "answer": "答案"}')
        def complete(self, *a, **k):
            raise AssertionError("有 progress 时必须走流式")
    rep = TE.execute_user_task("t", llm=_LLM(), progress=events.append)
    kinds = [e["ev"] if isinstance(e, dict) else e for e in events]
    assert rep["status"] == "done"
    toks = [e for e in events if isinstance(e, dict) and e["ev"] == "token"]
    assert len(toks) == 2 and toks[0]["t"] == "答", toks
    # 无 progress ⇒ 不要求流式（零破坏）
    class _LLM2:
        configured = True
        def complete(self, *a, **k):
            return SimpleNamespace(ok=True, error=None,
                text='{"analysis": "x", "op": "final", "answer": "y"}')
    assert TE.execute_user_task("t", llm=_LLM2())["status"] == "done"


def test_native_tools_mode_is_not_streaming_but_reports_rounds(monkeypatch):
    """★★★ R384 新语义：原生工具模式**不走流式**，但 round 事件照发。

    取舍理由：tool_calls 需按整段解析，流式分片会拆坏参数。
    正确性（真调工具，全池零动作 94%→0%）> 逐字动画。
    """
    monkeypatch.setenv("DWC_LLM_NATIVE_TOOLS", "1")
    events = []

    class _LLM:
        configured = True

        def complete(self, *a, **k):
            return SimpleNamespace(
                ok=True, error=None, text="",
                meta={"tool_calls": [{"id": "c", "type": "function",
                                      "function": {
                                          "name": "final_answer",
                                          "arguments": '{"answer": "原生答案"}'}}],
                      "finish_reason": "tool_calls"})

        def complete_stream(self, *a, **k):
            raise AssertionError("原生工具模式不该走流式")

    rep = TE.execute_user_task("t", llm=_LLM(), progress=events.append)
    assert rep["status"] == "done"
    assert "原生答案" in str(rep.get("answer") or "")
    rounds = [e for e in events if isinstance(e, dict) and e["ev"] == "round"]
    assert rounds, "原生模式也要发 round 事件（否则前端没进度）"
    toks = [e for e in events if isinstance(e, dict) and e["ev"] == "token"]
    assert not toks, "原生模式不该发 token 事件（非流式）"


def test_answer_state_machine():
    """★★★ answer 状态机（测 _AnswerStream 真码）: JSON 前缀不打,
    answer 值逐字打, 转义 \n 还原, 闭合即止。"""
    import io as _io
    st = CH._AnswerStream()
    buf = _io.StringIO()
    for piece in ('{"analysis":"收", "op":"final", "ans',
                  'wer":"第一行\\n第二', '行"}'):
        st.feed(piece, out=buf)
    assert buf.getvalue() == "第一行\n第二行", repr(buf.getvalue())
    assert st.in_ans is False and st.streamed is False
    # 无 answer 键的帧: 只留尾部缓存, 不打印
    buf2 = _io.StringIO()
    st2 = CH._AnswerStream()
    st2.feed('{"analysis": "中间轮", "op": "read"}', out=buf2)
    assert buf2.getvalue() == ""
