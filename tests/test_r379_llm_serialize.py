# -*- coding: utf-8 -*-
"""R379 · 并发调 LLM 必须串行化（端点并发下不遵守 json_mode）。

★★★ 现场取证（2026-10-20 09:00 生产跑批 + 对照实验）:
  · 串行（同一实例，4 个任务依次）  ⇒ **4/4 JSON**
  · 并发（各自独立实例，4 线程）    ⇒ **0/4 JSON**（含 finish=tool_calls、
    content 为空、自然语言散文）
  · 并发 + 各自独立 `x-opencode-session` ⇒ 仍 **0/4**
  · 并发 + **全局锁串行化**          ⇒ **4/4 JSON**

  ⇒ 根因不是 session 冲突，是**端点并发下不遵守 `response_format:
    json_object`**。而 DWC 的 `Semaphore(2)` 允许 2 单并发
    （`dwc_agent.py` 收件箱异步接单），所以生产上必然踩中。

★ 判据（锁的是「串行」这个行为，不是「能不能并发」）:
  · 多线程同时调 `complete()` ⇒ 真正打到 HTTP 的请求**互不重叠**
    （用 enter/exit 计数器检测重叠峰值必须 == 1）
  · 串行调用行为不变（不许因加锁改变结果）
  · 锁是**模块级**的（跨实例生效 —— 生产里每单 `LLMClient()` 新建）
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.llm import client as C  # noqa: E402


class _Resp:
    def __init__(self, body: dict):
        self._raw = json.dumps(body).encode("utf-8")
        self.headers = {"Content-Type": "application/json"}

    def read(self):
        return self._raw

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _ok_body(text='{"a":1}'):
    return {"choices": [{"message": {"role": "assistant", "content": text},
                         "finish_reason": "stop"}]}


@pytest.fixture(autouse=True)
def _reset_lock(monkeypatch):
    """每个测试复位全局锁状态（防相互污染）。"""
    monkeypatch.setenv("DWC_LLM_RETRIES", "0")
    monkeypatch.setattr(C, "_load_file_config", lambda: {})
    yield


def test_module_level_lock_exists():
    """★★★ 必须存在**模块级**互斥 —— 生产每单新建 LLMClient，
    实例级锁挡不住跨实例并发。

    ★ R435 重锚：`_HTTP_LOCK` 由 `Lock()` 改为 `Semaphore(DWC_HTTP_CONCURRENCY)`，
      **默认宽度 1 ⇒ 语义等价于锁**（下面用峰值并发=1 验证，不只看类型）。
    """
    assert hasattr(C, "_HTTP_LOCK"), "缺模块级 _HTTP_LOCK"
    import threading as _t
    assert isinstance(C._HTTP_LOCK, type(_t.Semaphore())), (
        "_HTTP_LOCK 必须是 threading.Semaphore，实得 %r" % (type(C._HTTP_LOCK),))
    assert int(getattr(C, "_HTTP_WIDTH", 0)) >= 1, "宽度必须 ≥1（0 会变成不阻塞）"
    # 默认宽度 1：拿到一次后第二次非阻塞获取必须失败（等价于旧 Lock）
    if int(C._HTTP_WIDTH) == 1:
        assert C._HTTP_LOCK.acquire(blocking=False) is True, "第一次获取应成功"
        assert C._HTTP_LOCK.acquire(blocking=False) is False, "宽度 1 却允许第二个持有者"
        C._HTTP_LOCK.release()


def test_concurrent_calls_do_not_overlap(monkeypatch):
    """★★★ 多线程调 complete() ⇒ 真实 HTTP 请求不得重叠。

    用 enter/exit 计数器测「同时在飞」的峰值；端点并发下不遵守
    json_mode，所以峰值必须 == 1。
    """
    state = {"now": 0, "peak": 0, "n": 0}
    guard = threading.Lock()

    def _uo(req, timeout=None):
        with guard:
            state["now"] += 1
            state["n"] += 1
            state["peak"] = max(state["peak"], state["now"])
        time.sleep(0.15)          # 模拟网络往返，放大重叠窗口
        with guard:
            state["now"] -= 1
        return _Resp(_ok_body())

    monkeypatch.setattr(C.urllib.request, "urlopen", _uo)

    def one():
        cl = C.LLMClient(base_url="http://fake/v1", api_key="k", model="m",
                         timeout=5)
        cl.complete("x", max_tokens=64)

    ths = [threading.Thread(target=one) for _ in range(4)]
    for t in ths:
        t.start()
    for t in ths:
        t.join()

    assert state["n"] == 4, "请求数不对: %s" % state
    assert state["peak"] == 1, (
        "并发请求重叠了（峰值 %d）—— 端点并发下不遵守 json_mode，"
        "生产实测 0/4 JSON" % state["peak"])


def test_serial_calls_still_work(monkeypatch):
    """★★ 回归保护：串行调用行为完全不变。"""
    monkeypatch.setattr(C.urllib.request, "urlopen",
                        lambda *a, **k: _Resp(_ok_body('{"b":2}')))
    cl = C.LLMClient(base_url="http://fake/v1", api_key="k", model="m",
                     timeout=5)
    r1 = cl.complete("x")
    r2 = cl.complete("y")
    assert r1.ok and r1.text == '{"b":2}'
    assert r2.ok and r2.text == '{"b":2}'


def test_lock_released_on_exception(monkeypatch):
    """★★★ 请求抛异常也必须放锁 —— 否则一次失败就永久死锁。"""
    def _boom(req, timeout=None):
        raise RuntimeError("network down")

    monkeypatch.setattr(C.urllib.request, "urlopen", _boom)
    cl = C.LLMClient(base_url="http://fake/v1", api_key="k", model="m",
                     timeout=5)
    r = cl.complete("x")
    assert r.ok is False

    # 锁必须已释放：换正常桩再调一次
    monkeypatch.setattr(C.urllib.request, "urlopen",
                        lambda *a, **k: _Resp(_ok_body('{"c":3}')))
    r2 = cl.complete("y")
    assert r2.ok is True, "异常后锁没释放 ⇒ 永久死锁"


def test_stream_also_serialized(monkeypatch):
    """★★ 流式同样要串行（生产 progress 路径走 complete_stream）。"""
    state = {"now": 0, "peak": 0}
    guard = threading.Lock()

    class _SSE:
        def __init__(self):
            self.headers = {"Content-Type": "text/event-stream"}

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def __iter__(self):
            return iter([('data: ' + json.dumps(
                {"choices": [{"delta": {"content": "ok"}}]}) + "\n").encode(),
                b"data: [DONE]\n"])

    def _uo(req, timeout=None):
        with guard:
            state["now"] += 1
            state["peak"] = max(state["peak"], state["now"])
        time.sleep(0.12)
        with guard:
            state["now"] -= 1
        return _SSE()

    monkeypatch.setattr(C.urllib.request, "urlopen", _uo)

    def one():
        cl = C.LLMClient(base_url="http://fake/v1", api_key="k", model="m",
                         timeout=5)
        cl.complete_stream("x", max_tokens=64)

    ths = [threading.Thread(target=one) for _ in range(3)]
    for t in ths:
        t.start()
    for t in ths:
        t.join()

    assert state["peak"] == 1, (
        "流式请求并发重叠（峰值 %d）" % state["peak"])
