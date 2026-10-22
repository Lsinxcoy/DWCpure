# -*- coding: utf-8 -*-
"""R422 · 重试额度必须**每次调用**重置（不是整个进程一次性）。

★★★ 现场（2026-10-21 23:41–23:48，端点连续 502）：
    `_attempts` 只在**成功**路径归零（client.py 文末 n_ok 分支），
    失败后停在 2 ⇒ 之后每次调用 `_attempts < retries` 恒假
    ⇒ **整个进程只有第一单重试过**，后面 12 单零重试、零动作、直接判死。

    日志证据：23:41:26 起连续 14 条 `LLM 失败: HTTP 502: Bad Gateway`，
    其中只有第一条真走了退避（n_retry_used=2），其余全是单发即死。

★ 修法：入口处 `if not _retry: self._attempts = 0`；
  递归重试传 `_retry=True`（否则递归会无限重置计数）。
"""
import io
import os
import sys
import urllib.error

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from dwc.llm import client as CL  # noqa: E402


def _always_502(monkeypatch):
    state = {"n": 0}

    def fake(req, timeout=None):
        state["n"] += 1
        raise urllib.error.HTTPError(
            req.full_url, 502, "Bad Gateway", {}, io.BytesIO(b""))

    monkeypatch.setattr(CL.urllib.request, "urlopen", fake)
    monkeypatch.setattr("time.sleep", lambda *_: None)   # 不真睡
    return state


def test_retry_budget_resets_between_calls(monkeypatch):
    """★★★ 核心：连续两次失败调用，**各自**都要有 3 发（初+2重试）。"""
    state = _always_502(monkeypatch)
    c = CL.LLMClient()
    r1 = c.complete("ping", max_tokens=16)
    n1 = state["n"]
    r2 = c.complete("ping", max_tokens=16)
    n2 = state["n"] - n1
    assert not r1.ok and not r2.ok
    assert n1 == 3, "第一次应 3 发（初+2重试），实际 %d" % n1
    assert n2 == 3, (
        "第二次也只该有 3 发；实际 %d —— 重试额度没有按调用重置" % n2)


def test_third_call_still_has_budget(monkeypatch):
    """★★ 第三次调用同样有额度（防止"用一次就永久失效"）。"""
    state = _always_502(monkeypatch)
    c = CL.LLMClient()
    for _ in range(3):
        c.complete("ping", max_tokens=16)
    assert state["n"] == 9, "3 次调用 × 3 发 = 9，实际 %d" % state["n"]


def test_4xx_still_no_retry(monkeypatch):
    """★★ 4xx 仍不重试（R36 语义不能被这次改动带坏）。"""
    state = {"n": 0}

    def fake(req, timeout=None):
        state["n"] += 1
        raise urllib.error.HTTPError(
            req.full_url, 404, "Not Found", {}, io.BytesIO(b""))

    monkeypatch.setattr(CL.urllib.request, "urlopen", fake)
    monkeypatch.setattr("time.sleep", lambda *_: None)
    c = CL.LLMClient()
    c.complete("ping", max_tokens=16)
    c.complete("ping", max_tokens=16)
    assert state["n"] == 2, "4xx 两次调用各 1 发，实际 %d" % state["n"]


def test_recursive_retry_does_not_reset_counter(monkeypatch):
    """★★ 递归重试不得重置计数（否则会无限重试）。"""
    state = _always_502(monkeypatch)
    c = CL.LLMClient()
    c.complete("ping", max_tokens=16)
    assert state["n"] == 3, "递归必须收敛在 3 发，实际 %d" % state["n"]


# ══════════════ 基础设施故障必须与模型失败可区分 ══════════════

class _FailLLM:
    """永远失败的假 LLM（带 meta，用来区分 infra / 模型失败）。"""
    configured = True

    def __init__(self, meta, error="HTTP 502: Bad Gateway"):
        self.meta = meta
        self.error = error

    def complete(self, *a, **kw):
        from types import SimpleNamespace
        return SimpleNamespace(ok=False, error=self.error, meta=self.meta,
                               text="")

    def complete_stream(self, *a, **kw):
        return self.complete(*a, **kw)


def test_http_502_marked_as_infra(monkeypatch):
    """★★★ 端点 502 ⇒ why 带 `[infra]`（bench 据此重投/剔除）。"""
    monkeypatch.setenv("DWC_LLM_NATIVE_TOOLS", "0")
    from dwc.llm import task_exec as T
    rep = T.execute_user_task("随便问一句", llm=_FailLLM({"http_code": 502}),
                              task_id="T_R422_infra", max_rounds=2)
    assert rep["status"] == "incomplete"
    assert "[infra]" in rep["why"], rep["why"]


def test_transport_error_marked_as_infra(monkeypatch):
    """★★ 传输超时同样算 infra（不是模型答错）。"""
    monkeypatch.setenv("DWC_LLM_NATIVE_TOOLS", "0")
    from dwc.llm import task_exec as T
    rep = T.execute_user_task(
        "随便问一句",
        llm=_FailLLM({"kind": "transport"}, error="TimeoutError: timed out"),
        task_id="T_R422_transport", max_rounds=2)
    assert "[infra]" in rep["why"], rep["why"]


def test_model_parse_failure_not_marked_as_infra(monkeypatch):
    """★★★ 反面：模型输出解析失败**不是** infra（否则会被无限重投掩盖）。"""
    monkeypatch.setenv("DWC_LLM_NATIVE_TOOLS", "0")
    from dwc.llm import task_exec as T
    rep = T.execute_user_task(
        "随便问一句",
        llm=_FailLLM({"kind": "parse"}, error="响应非 JSON"),
        task_id="T_R422_parse", max_rounds=2)
    assert "[infra]" not in rep["why"], rep["why"]
