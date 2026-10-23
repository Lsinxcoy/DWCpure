# -*- coding: utf-8 -*-
"""R226 · 多模态: 读图链 + client images content 数组。"""
from __future__ import annotations

import base64
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
from dwc.llm import task_exec as TE                             # noqa: E402
from dwc.llm import client as C                                 # noqa: E402


def _fake_client():
    cl = C.LLMClient.__new__(C.LLMClient)
    cl.configured = True
    cl._model = "fake-model"
    cl.n_calls = 0
    cl._base = "http://fake.test/v1"
    cl._key = "k"
    cl._attempts = 1
    cl.retries = 0
    cl.n_retries = 0
    cl.n_fail = 0
    cl.n_ok = 0
    cl.timeout = 60
    cl._probe = None
    return cl


class _Resp:
    def read(self):
        return json.dumps({"choices": [
            {"message": {"content": '{"ok": true}'}}]}).encode()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_read_image_returns_path_not_garbage():
    """★★ 读图: .png 走 image_path 分支（不按文本读二进制）。"""
    os.makedirs(TE.WORK, exist_ok=True)
    img = os.path.join(TE.WORK, "__r226_test.png")
    with open(img, "wb") as fh:
        fh.write(b"\x89PNG_fake")
    try:
        obs = TE._do_action("read", {"path": img})
    finally:
        os.remove(img)
    assert obs["ok"] and obs["image_path"].endswith("__r226_test.png")
    assert "content" not in obs, "图片按文本读了 — 上下文污染"


def test_client_builds_multimodal_content(monkeypatch, tmp_path):
    """★★★ client.images: OpenAI content 数组形态真构造 — 拦 HTTP 验 body。"""
    img = tmp_path / "b.png"
    img.write_bytes(b"\x89PNG_data")
    b64 = base64.b64encode(img.read_bytes()).decode()
    captured = {}

    def _fake_urlopen(req, timeout=60):
        captured["body"] = json.loads(req.data.decode())
        return _Resp()

    cl = _fake_client()
    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen)
    cl.complete("看这张图", images=[str(img)])
    content = captured["body"]["messages"][-1]["content"]
    assert isinstance(content, list), "没走 content 数组形态"
    types = [p["type"] for p in content]
    assert "text" in types and "image_url" in types
    url = [p for p in content if p["type"] == "image_url"][0]
    assert "data:image/png;base64," in url["image_url"]["url"]
    assert b64[:20] in url["image_url"]["url"]


def test_no_images_keeps_string_prompt(monkeypatch):
    """★ 无图时 content 仍是纯字符串（零破坏）。"""
    captured = {}

    def _fake_urlopen(req, timeout=60):
        captured["body"] = json.loads(req.data.decode())
        return _Resp()

    cl = _fake_client()
    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen)
    cl.complete("纯文本")
    assert captured["body"]["messages"][-1]["content"] == "纯文本"
