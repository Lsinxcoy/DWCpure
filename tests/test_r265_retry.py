# -*- coding: utf-8 -*-
"""R265 · 5xx/429 网关瞬时重试锁（2026-10-14 用户实测: "流式失败且回退
失败: HTTP 502: Bad Gateway" 16.2s 任务判死）。

根因（代码级）: R36 只重试**传输异常**, `except HTTPError` 分支一发就
return ⇒ 瞬时 502 零韧性: 流式挂 502 → 回退 complete 又 502 → incomplete。
修: 5xx/429 走重试+退避（0.5·2^n 封顶 3s）, retries 默认 1→2（总 3 发）;
4xx 立即返回（key 错重试必然再失败）。
"""
import io
import sys
import urllib.error
import os

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from dwc.llm import client as CL  # noqa: E402


def _ok_response(text="recovered"):
    import json
    class R:
        def read(self):
            return json.dumps(
                {"choices": [{"message": {"content": text}}]}).encode()
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False
    return R()


def _raise_502_then_ok(remaining_fail):
    """前 remaining_fail 发 502, 之后成功。"""
    state = {"n": 0}
    def fake(req, timeout=None):
        state["n"] += 1
        if state["n"] <= remaining_fail:
            raise urllib.error.HTTPError(
                req.full_url, 502, "Bad Gateway", {}, io.BytesIO(b""))
        return _ok_response()
    return fake, state


def test_502_retries_then_recovers(monkeypatch):
    """★★★ 瞬时 502: 前两发 502 → 第三发救回（不判死）。"""
    fake, state = _raise_502_then_ok(2)
    monkeypatch.setattr(CL.urllib.request, "urlopen", fake)
    c = CL.LLMClient()
    r = c.complete("ping", max_tokens=16)
    assert r.ok and r.text == "recovered", r.error
    assert state["n"] == 3, "应 3 发（初+2重试）: %s" % state["n"]
    assert c.n_retries >= 2, c.n_retries


def test_404_no_retry(monkeypatch):
    """★★ 4xx 立即返回（请求错, 重试必然再失败 — R36 语义保留）。"""
    state = {"n": 0}
    def fake(req, timeout=None):
        state["n"] += 1
        raise urllib.error.HTTPError(
            req.full_url, 404, "Not Found", {}, io.BytesIO(b""))
    monkeypatch.setattr(CL.urllib.request, "urlopen", fake)
    c = CL.LLMClient()
    r = c.complete("ping", max_tokens=16)
    assert not r.ok and "HTTP 404" in r.error
    assert state["n"] == 1, "4xx 不该重试: %s" % state["n"]


def test_retries_default_two():
    """★ retries 默认 2（总 3 发 — 抗两个退避窗口）。可被 env 覆盖。"""
    c = CL.LLMClient()
    assert c.retries == 2, c.retries


def test_http_error_branch_has_5xx_gate_in_source():
    """★ 源锁: HTTPError 分支必须有 5xx/429 重试门（防回退到一发就 return）。"""
    src = io.open(CL.__file__.replace(".pyc", ".py"), encoding="utf-8").read()
    assert 'e.code in (429, 500, 502, 503, 504)' in src
