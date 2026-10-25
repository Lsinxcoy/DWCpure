# -*- coding: utf-8 -*-
"""R439 · P0-a 成本记账（token / cached / 三档计价 / 落盘）。

纪律（来自 v2 计划 §2）：
  · 无 usage ⇒ None，**不猜 0**（降级与成功必须可区分）
  · 模型不在价目表 ⇒ cost_usd=None，但 tokens 照记（不许拿别的模型价格兜底）
  · 落盘失败不许掀翻 LLM 调用
"""
from __future__ import annotations

import io
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from dwc.llm import cost as C


# ---------------------------------------------------------------- parse_usage

def test_parse_usage_missing_returns_none():
    """没有 usage 字段 ⇒ None（不是 0 —— 0 会被当成"免费"）。"""
    assert C.parse_usage({}) is None
    assert C.parse_usage({"choices": []}) is None
    assert C.parse_usage(None) is None


def test_parse_usage_reads_cached_tokens():
    """cached 在 prompt_tokens_details 里（OpenAI 兼容形态）。"""
    u = C.parse_usage({
        "prompt_tokens": 1200,
        "completion_tokens": 300,
        "prompt_tokens_details": {"cached_tokens": 900},
    })
    assert u is not None
    assert (u.prompt_tokens, u.completion_tokens, u.cached_tokens) == (1200, 300, 900)


def test_parse_usage_without_details_defaults_cached_zero():
    """没有 details ⇒ cached=0（这是"确实没命中"，不是"不知道"）。"""
    u = C.parse_usage({"prompt_tokens": 10, "completion_tokens": 2})
    assert u is not None and u.cached_tokens == 0


def test_parse_usage_malformed_returns_none():
    """畸形/负数 ⇒ None（不许把坏数据当成本）。"""
    for bad in ({"prompt_tokens": "x", "completion_tokens": 1},
                {"prompt_tokens": -5, "completion_tokens": 1},
                {"prompt_tokens": 1},                       # 缺 completion
                {"prompt_tokens": 1, "completion_tokens": 2,
                 "prompt_tokens_details": "nope"}):
        assert C.parse_usage(bad) is None, bad


# ---------------------------------------------------------------- cost_usd

PRICING = {"m1": {"input": 1.0, "cached_input": 0.1, "output": 10.0}}


def test_cost_unknown_model_returns_none_not_zero():
    """模型不在价目表 ⇒ None。★ 0 会让"未知"看起来像"免费"。"""
    u = C.Usage(prompt_tokens=100, completion_tokens=10)
    assert C.cost_usd("nope", u, PRICING) is None
    assert C.cost_usd("m1", u, {}) is None


def test_cost_prices_cached_separately():
    """缓存输入与未缓存输入**分开计价**（两篇论文都用三档）。"""
    # 1200 prompt，其中 900 cached；300 completion
    u = C.Usage(prompt_tokens=1200, completion_tokens=300, cached_tokens=900)
    got = C.cost_usd("m1", u, PRICING)
    want = (300 * 1.0 + 900 * 0.1 + 300 * 10.0) / 1_000_000.0
    assert got == pytest.approx(want)


def test_cost_never_negative_when_cached_exceeds_prompt():
    """坏数据（cached > prompt）⇒ 按 prompt 封顶，不出负数成本。"""
    u = C.Usage(prompt_tokens=10, completion_tokens=1, cached_tokens=99)
    got = C.cost_usd("m1", u, PRICING)
    assert got is not None and got >= 0


# ---------------------------------------------------------------- 落盘

def test_usage_log_honors_env_override(tmp_path, monkeypatch):
    p = tmp_path / "u.jsonl"
    monkeypatch.setenv("DWC_USAGE_PATH", str(p))
    assert C.usage_log_path() == str(p)


def test_usage_log_appends_jsonl(tmp_path, monkeypatch):
    p = tmp_path / "u.jsonl"
    monkeypatch.setenv("DWC_USAGE_PATH", str(p))
    u = C.Usage(prompt_tokens=5, completion_tokens=1, cached_tokens=0)
    C.record(model="m1", usage=u, cost=0.5, tag="t1")
    C.record(model="m1", usage=u, cost=None, tag="t2")
    rows = [json.loads(l) for l in io.open(p, encoding="utf-8") if l.strip()]
    assert len(rows) == 2
    assert rows[0]["prompt_tokens"] == 5 and rows[0]["cost_usd"] == 0.5
    assert rows[0]["tag"] == "t1"
    assert rows[1]["cost_usd"] is None      # ★ None 保留，不写成 0


def test_record_swallows_write_error_without_raising(tmp_path, monkeypatch):
    """落盘失败不许掀翻 LLM 调用（但必须留痕到 stderr）。

    ★ 用**已存在的目录**当文件路径 ⇒ 真的 open 失败（IsADirectoryError）。
      指向不存在的目录不算，因为实现会 makedirs 成功。
    """
    monkeypatch.setenv("DWC_USAGE_PATH", str(tmp_path))
    u = C.Usage(prompt_tokens=1, completion_tokens=1)
    C.record(model="m1", usage=u, cost=None)   # 不抛
    assert tmp_path.is_dir()                   # 也没把它删掉


def test_load_pricing_missing_returns_empty(tmp_path):
    assert C.load_pricing(str(tmp_path / "nope.json")) == {}


def test_load_pricing_reads_dict(tmp_path):
    p = tmp_path / "llm.json"
    p.write_text(json.dumps({"model": "m1", "pricing": PRICING}),
                 encoding="utf-8")
    assert C.load_pricing(str(p)) == PRICING


def test_load_pricing_ignores_non_dict_pricing(tmp_path):
    p = tmp_path / "llm.json"
    p.write_text(json.dumps({"pricing": "nope"}), encoding="utf-8")
    assert C.load_pricing(str(p)) == {}


# ---------------------------------------------------------------- 客户端接线

def test_client_meta_carries_usage(monkeypatch):
    """★ 端到端：HTTP 响应里的 usage 必须进 LLMResult.meta。"""
    from dwc.llm import LLMClient

    class H(BaseHTTPRequestHandler):
        def do_POST(self):
            self.rfile.read(int(self.headers.get("Content-Length", 0)))
            body = json.dumps({
                "choices": [{"message": {"content": "ok"},
                             "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 11, "completion_tokens": 3,
                          "prompt_tokens_details": {"cached_tokens": 7}},
            }).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        c = LLMClient(base_url="http://127.0.0.1:%d/v1" % srv.server_address[1],
                      api_key="k", model="m1", timeout=8)
        r = c.complete("x")
        assert r.ok is True
        assert r.meta.get("usage") == {"prompt_tokens": 11,
                                       "completion_tokens": 3,
                                       "cached_tokens": 7}, r.meta
    finally:
        srv.shutdown()


def test_client_without_usage_meta_has_no_usage_key(monkeypatch):
    """服务端不回 usage ⇒ meta 里**没有** usage 键（不是 0）。"""
    from dwc.llm import LLMClient

    class H(BaseHTTPRequestHandler):
        def do_POST(self):
            self.rfile.read(int(self.headers.get("Content-Length", 0)))
            body = json.dumps({"choices": [{"message": {"content": "ok"},
                                            "finish_reason": "stop"}]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        c = LLMClient(base_url="http://127.0.0.1:%d/v1" % srv.server_address[1],
                      api_key="k", model="m1", timeout=8)
        r = c.complete("x")
        assert r.ok is True
        assert "usage" not in r.meta
    finally:
        srv.shutdown()
