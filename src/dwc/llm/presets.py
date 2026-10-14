# -*- coding: utf-8 -*-
"""R267b · 便捷厂商路由预设（用户建议：像 Hermes/OpenClaw 一样，选厂商→填 key→选模型）。

★ 设计 (G1/DWC-AUTO): **只声明事实** (base_url/可选模型/单测门)，不 wheat- tickets。
★ 仅 OpenAI 兼容协议 (chat/completions) 的厂商进入 presets；
  /responses / /messages 协议厂商不在 (OpenCode Go 的 gpt-/grok-/muse-spark/mux 系 liệt, MiniMax/Qwen messages 系)。
★ 这是可扩展注册表: 提供了 ProviderPreset 哨兵，后续用户可 config/presets.yaml 覆盖 (未实现 — R73: 无设计不发明)。
"""
from __future__ import annotations
from typing import Dict, List, Optional

DEFAULT_TIMEOUT = "60"

# (name) -> base_url, common models, needs_session_header, sends_custom_ua
PRESETS: Dict[str, dict] = {
    # ★ OpenCode Go (chat/completions only; responses/messages models excluded by design)
    "opencode-go": {
        "base_url": "https://opencode.ai/inference/go/v1",
        "models": ["cat-jam-free", "deepseek-v4-flash", "deepseek-v4-pro",
                   "deepseek-v4.1-flash", "glm-5.3-flash", "glm-5.2", "glm-5.3",
                   "kimi-k2.6", "kimi-k2.7-code", "longcat-2.0",
                   "mimo-v2.6-flash", "mimo-v2.6-pro", "hy3", "hy4-preview",
                   "space-bunny", "longcat-2.5-preview-free",
                   "step-5-preview-free"],
        "session_header": True,         # x-opencode-session
        "custom_ua": "Divine-Wisdom-Core/1.0 (+dwccore)",
        "needs_key": True,
        "protocol": "openai-chat",
    },
    # ★ OpenAI
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "models": ["gpt-4o-mini", "gpt-4o", "gpt-4.1-mini", "gpt-4.1", "o4-mini", "o3-mini"],
        "session_header": False,
        "custom_ua": None,
        "needs_key": True,
        "protocol": "openai-chat",
    },
    # ★ Moonshot / Kimi
    "moonshot": {
        "base_url": "https://api.moonshot.cn/v1",
        "models": ["moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k"],
        "session_header": False,
        "custom_ua": None,
        "needs_key": True,
        "protocol": "openai-chat",
    },
    # ★ MiniMax (openai-compatible)
    "minimax-openai": {
        "base_url": "https://api.minimax.io/v1",
        "models": ["MiniMax-Text-01", "abab6.5s-chat"],
        "session_header": False,
        "custom_ua": None,
        "needs_key": True,
        "protocol": "openai-chat",
    },
    # ★ DeepSeek
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "models": ["deepseek-chat", "deepseek-reasoner"],
        "session_header": False,
        "custom_ua": None,
        "needs_key": True,
        "protocol": "openai-chat",
    },
    # ★ Ollama (no key)
    "ollama": {
        "base_url": "http://localhost:11434/v1",
        "models": ["llama3.1", "qwen2.5", "deepseek-r1"],
        "session_header": False,
        "custom_ua": None,
        "needs_key": False,
        "protocol": "openai-chat",
    },
}


def list_presets() -> List[str]:
    return sorted(PRESETS.keys())


def get_preset(name: str) -> Optional[dict]:
    return PRESETS.get(name.strip().lower())


def preset_choices() -> List[str]:
    return [f"{n}  {p['base_url']}" for n, p in sorted(PRESETS.items())]


def preset_model_choices(name: str) -> List[str]:
    p = get_preset(name)
    return list(p["models"]) if p else []
