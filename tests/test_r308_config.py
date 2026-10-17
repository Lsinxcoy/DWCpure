# -*- coding: utf-8 -*-
"""R308-③ · 配置三层：出厂默认 → 显式参数 → 环境变量 → config/llm.json，
每层来源可审计（只记层名不记值，凭证永不进日志）。"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(_HERE), "src"))


def test_explicit_beats_env(monkeypatch):
    from dwc.llm.client import LLMClient
    monkeypatch.setenv("DWC_LLM_MODEL", "env-model")
    monkeypatch.setenv("DWC_LLM_BASE_URL", "http://env")
    monkeypatch.setenv("DWC_LLM_API_KEY", "env-key")
    c = LLMClient(model="explicit-model")
    assert c._model == "explicit-model"
    assert c.sources["model"] == "explicit"
    assert c.sources["base_url"] == "env"


def test_env_beats_file(monkeypatch):
    from dwc.llm import client as C
    from dwc.llm.client import LLMClient
    monkeypatch.setenv("DWC_LLM_MODEL", "env-model")
    monkeypatch.setenv("DWC_LLM_TIMEOUT", "11")
    c = LLMClient()
    assert c._model == "env-model"
    assert c.sources["model"] == "env"
    assert c.timeout == 11.0
    assert c.sources["timeout"] == "env"


def test_factory_defaults_no_leak(monkeypatch):
    from dwc.llm import client as C
    from dwc.llm.client import LLMClient, LLMResult
    for k in ("DWC_LLM_BASE_URL", "DWC_LLM_API_KEY", "DWC_LLM_MODEL",
              "DWC_LLM_TIMEOUT", "DWC_LLM_RETRIES"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(C, "_load_file_config", lambda: {})
    c = LLMClient()
    assert c.timeout == 30.0 and c.retries == 2
    assert c.sources["timeout"] == "factory"
    assert c.sources["retries"] == "factory"
    assert c.configured is False
    r = LLMResult(ok=False, source="not_configured", error="no key")
    assert "rc-" not in str(r)
    assert set(c.sources.values()) <= {"explicit", "env", "file", "factory"}
