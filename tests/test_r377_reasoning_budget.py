# -*- coding: utf-8 -*-
"""R377 · 推理预算可配置（真修「任务未完成」的根因，不只如实报错）。

★★★ 现场（2026-10-20 nightbench 10 单 9 挂 + 探针实测）:
  · 失败任务推理 5500+ 字，`max_tokens` 硬编码 **1600** ⇒ finish=length
    ⇒ content 完全为空（推理把预算吃光，JSON 一个字没写）。
  · 端点支持压制推理（实测 `reasoning_effort="none"` / `thinking:{type:
    "disabled"}` ⇒ reasoning=0，content 干净）。
  · `max_tokens` 在 task_exec 里**写死两处 1600**，与 client 的
    「显式参数 > env > 文件」口径完全脱节 ⇒ 换个模型/端点就没法调。

★★ 判据（本轮锁的是「可配」+「不许再写死」）:
  ① `config/llm.json` 可配 `max_tokens` / `reasoning_effort`
  ② 环境变量 `DWC_LLM_MAX_TOKENS` / `DWC_LLM_REASONING_EFFORT` 可覆盖
  ③ task_exec 不再出现字面量 1600（改从 client 取）
  ④ 显式传参仍然最高优先（旧口径不破）
  ⑤ `reasoning_effort` 未配置 ⇒ 不发该字段（不猜端点支持什么）
"""
from __future__ import annotations

import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.llm import client as C  # noqa: E402


def _fake_resp(body: dict):
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


def _capture(monkeypatch, body=None):
    """装上 urlopen 桩，返回 (client, 捕获的请求 body 列表)。"""
    monkeypatch.setenv("DWC_LLM_RETRIES", "0")
    body = body or {"choices": [{"message": {"role": "assistant",
                                             "content": '{"a":1}'},
                                 "finish_reason": "stop"}]}
    seen = []

    def _uo(req, timeout=None):
        seen.append(json.loads(req.data.decode("utf-8")))
        return _fake_resp(body)

    monkeypatch.setattr(C.urllib.request, "urlopen", _uo)
    return seen


# ─────────────────────── ① 配置可读


def test_default_max_tokens_is_configurable(monkeypatch):
    """★★★ `max_tokens` 必须能从 config/llm.json 读（不再写死 1600）。"""
    monkeypatch.delenv("DWC_LLM_MAX_TOKENS", raising=False)
    cl = C.LLMClient(base_url="http://fake/v1", api_key="k", model="m",
                     timeout=5)
    assert hasattr(cl, "max_tokens"), "LLMClient 没有 max_tokens 属性"
    assert cl.max_tokens >= 1600, (
        "默认 max_tokens 太小（%s）—— 推理模型会吃光预算" % cl.max_tokens)


def test_max_tokens_env_override(monkeypatch):
    """★ 环境变量可覆盖（CI/临时调参）。"""
    monkeypatch.setenv("DWC_LLM_MAX_TOKENS", "4096")
    cl = C.LLMClient(base_url="http://fake/v1", api_key="k", model="m",
                     timeout=5)
    assert cl.max_tokens == 4096


def test_explicit_max_tokens_wins(monkeypatch):
    """★ 显式传参 > env（与 base/key/model 同一口径）。"""
    monkeypatch.setenv("DWC_LLM_MAX_TOKENS", "4096")
    cl = C.LLMClient(base_url="http://fake/v1", api_key="k", model="m",
                     timeout=5, max_tokens=999)
    assert cl.max_tokens == 999


def test_reasoning_effort_configurable(monkeypatch):
    """★★ `reasoning_effort` 可配（端点实测支持 none ⇒ 关推理）。"""
    monkeypatch.setenv("DWC_LLM_REASONING_EFFORT", "none")
    cl = C.LLMClient(base_url="http://fake/v1", api_key="k", model="m",
                     timeout=5)
    assert cl.reasoning_effort == "none"


def test_reasoning_effort_absent_by_default(monkeypatch):
    """★★ 未配置 ⇒ 不发该字段（不猜端点支持什么，避免 400）。

    ★ 必须隔离真实 config/llm.json —— 仓库配置**故意**配了 none（修事故），
      不隔离就等于「断言生产配置没配」，测试会随配置变化假红。
    """
    monkeypatch.delenv("DWC_LLM_REASONING_EFFORT", raising=False)
    monkeypatch.setattr(C, "_load_file_config", lambda: {})
    cl = C.LLMClient(base_url="http://fake/v1", api_key="k", model="m",
                     timeout=5)
    assert not cl.reasoning_effort, (
        "未配置却给了默认值 %r —— 会对不支持的端点发无效字段"
        % (cl.reasoning_effort,))


# ─────────────────────── ② 请求体真的带上


def test_max_tokens_sent_in_request(monkeypatch):
    """★★★ 请求体里的 max_tokens 必须用配置值，不是硬编码。"""
    monkeypatch.setenv("DWC_LLM_MAX_TOKENS", "4096")
    seen = _capture(monkeypatch)
    cl = C.LLMClient(base_url="http://fake/v1", api_key="k", model="m",
                     timeout=5)
    cl.complete("x", json_mode=True)
    assert seen[-1]["max_tokens"] == 4096, (
        "请求体 max_tokens=%s（应为 4096）" % seen[-1].get("max_tokens"))


def test_reasoning_effort_sent_when_configured(monkeypatch):
    """★★ 配了 reasoning_effort ⇒ 请求体带该字段。"""
    monkeypatch.setenv("DWC_LLM_REASONING_EFFORT", "none")
    seen = _capture(monkeypatch)
    cl = C.LLMClient(base_url="http://fake/v1", api_key="k", model="m",
                     timeout=5)
    cl.complete("x")
    assert seen[-1].get("reasoning_effort") == "none", seen[-1]


def test_reasoning_effort_not_sent_when_unset(monkeypatch):
    """★★ 未配 ⇒ 请求体不含该字段（旧行为不破）。

    ★ 同上：隔离真实 config（仓库故意配了 none）。
    """
    monkeypatch.delenv("DWC_LLM_REASONING_EFFORT", raising=False)
    monkeypatch.setattr(C, "_load_file_config", lambda: {})
    seen = _capture(monkeypatch)
    cl = C.LLMClient(base_url="http://fake/v1", api_key="k", model="m",
                     timeout=5)
    cl.complete("x")
    assert "reasoning_effort" not in seen[-1], seen[-1]


def test_explicit_max_tokens_overrides_call_default(monkeypatch):
    """★ 调用点显式传 max_tokens 仍最高优先。"""
    monkeypatch.setenv("DWC_LLM_MAX_TOKENS", "4096")
    seen = _capture(monkeypatch)
    cl = C.LLMClient(base_url="http://fake/v1", api_key="k", model="m",
                     timeout=5)
    cl.complete("x", max_tokens=777)
    assert seen[-1]["max_tokens"] == 777


# ─────────────────────── ③ task_exec 不许再写死


def test_task_exec_has_no_hardcoded_1600():
    """★★★ task_exec 里不许出现字面量 1600 —— 那是本次事故的硬编码源。"""
    p = os.path.join(ROOT, "src", "dwc", "llm", "task_exec.py")
    src = open(p, encoding="utf-8").read()
    assert "max_tokens=1600" not in src, (
        "task_exec 仍在硬编码 max_tokens=1600 —— 换模型就没法调")


# ─────────────────────── ④ 配置文件里的键真的被读到（防静默丢弃）


def test_file_config_whitelist_covers_new_keys():
    """★★★ `_load_file_config()` 的白名单必须包含新增键。

    本次事故的真凶之一：config/llm.json 里写了 max_tokens 与
    reasoning_effort，但白名单只有 4 个键 ⇒ **静默丢弃** ⇒ 排障时看到
    的是「配了没用」而不是「没配」。白名单是显式枚举，加字段必须同轮改。
    """
    got = C._load_file_config()
    assert isinstance(got, dict), "配置读取必须返回 dict"
    src = open(C.__file__, encoding="utf-8").read()
    i = src.index("_KEYS = (")
    block = src[i:i + 300]
    assert "max_tokens" in block, "白名单漏了 max_tokens（会被静默丢弃）"
    assert "reasoning_effort" in block, (
        "白名单漏了 reasoning_effort（会被静默丢弃）")


def test_file_config_keys_are_honored(monkeypatch, tmp_path):
    """★★ 真写一份临时 llm.json ⇒ 键必须被读进 client。

    ★ R审计-P0 · 测试环境自足: 仓库**只提交** config/llm.example.json
      （llm.json 是 .gitignore 的本地真实配置, 任何机器上都不保证存在）。
      原来硬读 config/llm.json ⇒ 新克隆仓库必红。改用 example 模板。
    """
    import io as _io
    src_cfg = os.path.join(ROOT, "config", "llm.example.json")
    if not os.path.exists(src_cfg):
        pytest.skip("仓库缺 config/llm.example.json —— 配置模板未提交")
    cfg = tmp_path / "llm.json"
    cfg.write_text(_io.open(src_cfg, encoding="utf-8").read(),
                   encoding="utf-8")
    data = json.loads(cfg.read_text(encoding="utf-8"))
    assert "max_tokens" in data, (
        "仓库 config/llm.example.json 缺 max_tokens —— 本轮修法没落地到模板")
    assert "reasoning_effort" in data, (
        "仓库 config/llm.example.json 缺 reasoning_effort —— 推理仍会吃光预算")
