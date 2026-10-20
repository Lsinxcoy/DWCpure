# -*- coding: utf-8 -*-
"""R405 · 噪声重写提示不许因为 `_confirmed` 是 set 就崩。

★★★ 现场（rv07，04:0x 全池）：
    模型执行 `scripts/gate.py` 被拦成噪声动作 → 构造"换条路重写"提示时
    `json.dumps({k: v for k, v in step.items() if k != "analysis"})`
    直接抛 `TypeError: Object of type set is not JSON serializable`
    —— 因为 `step["_confirmed"]` 是 **set**（人工授权词集合，见调用点
    `step = {**step, "_confirmed": _parse_confirmed(ctx), ...}`）。

    模型看到这条 TypeError，以为**命令本身失败**，于是放弃并答"未能证实"。

★ 修法：该处（以及 recent 回放）的 `json.dumps` 必须带 `default=str`。
"""
from __future__ import annotations

import json
import os
import sys
from types import SimpleNamespace

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.llm import task_exec as T  # noqa: E402


class _SameStepLLM:
    """每轮都返回**同一个** run 动作 ⇒ 触发 R1 重复/噪声判定。"""

    configured = True

    def __init__(self):
        self.prompts = []

    def complete(self, prompt, **kw):
        self.prompts.append(prompt)
        step = {"analysis": "跑 gate", "op": "run",
                "cmd": ["python", "scripts/gate.py"]}
        return SimpleNamespace(ok=True, error="", meta={},
                               text=json.dumps(step, ensure_ascii=False))

    def complete_stream(self, prompt, **kw):
        return self.complete(prompt, **kw)


@pytest.fixture(autouse=True)
def _json_path(monkeypatch):
    monkeypatch.setenv("DWC_LLM_NATIVE_TOOLS", "0")


def test_noise_prompt_survives_set_in_confirmed():
    """★★★ 带人工授权的 ctx ⇒ step 里有 set ⇒ 重写提示不许抛 TypeError。"""
    llm = _SameStepLLM()
    rep = T.execute_user_task(
        "跑 scripts/gate.py 看是否全绿",
        llm=llm, task_id="T_R405_a", max_rounds=5,
        ctx="人工授权: python")          # ← 让 _confirmed 变成非空 set
    blob = json.dumps(rep, ensure_ascii=False, default=str)
    assert "Object of type set is not JSON serializable" not in blob, blob[:600]
    assert "TypeError" not in blob, blob[:600]
    # 提示词里应该出现过"噪声动作"（说明确实走到了重写分支）
    assert any("噪声动作" in p for p in llm.prompts), \
        "没走到噪声重写分支，测试没覆盖到目标代码"
