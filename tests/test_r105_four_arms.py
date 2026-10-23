# -*- coding: utf-8 -*-
"""R105 · 记忆带失败对照臂（Evo-memory 表3: 带失败记忆 vs 只技能）。

判据:
  · skills_only 臂 = 真判分**确定性提炼**期望行为（skill_hint, 无实得失败）
    —— 非编造（fn/args/expected 全来自 judge diffs）
  · 四臂同 prompt 骨架（none/guidance/replay/skills_only, 只差记忆块）
  · 首版正则 fn(args) 括号形式 0 命中 ⇒ fallback 失败 hint（教训锁定）
"""
from __future__ import annotations

import os
import sys
from types import SimpleNamespace

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.experiments.mem_guidance_vs_replay import (  # noqa: E402
    ARMS, build_prompt, _memory_from_verdict)


def _v():
    return SimpleNamespace(
        failure_signature={"c": "E_OFF_BY_ONE", "q": "range"},
        diffs=[{"ok": False, "fn": "sum_first_n", "args": "3",
                "expected": "6", "actual": "3"},
               {"ok": False, "fn": "sum_first_n", "args": "5",
                "expected": "15", "actual": "10"}],
        reason="x")


def test_four_arms_enum():
    assert ARMS == ("none", "guidance", "replay", "skills_only")
    import pytest
    with pytest.raises(ValueError, match="未知臂"):
        build_prompt("made_up", "t", "material")


def test_skill_hint_extracts_expectation_not_failure():
    """★ 教训锁: 实际格式 fn/args 粘连 — skill_hint 必须命中且无失败细节。"""
    mem = _memory_from_verdict("code_fix_001", _v())
    sh = mem["skill_hint"]
    assert "期望产出 6" in sh and "期望产出 15" in sh, \
        "正则必须匹配粘连格式（fn(args) 括号形式会 0 命中）"
    assert "实得" not in sh and "上次实测失败" not in sh, \
        "skills_only 臂不许带失败实得"
    # guidance 臂照旧带失败细节（对照的干净性）
    assert "上次实测失败" in mem["fix_hint"]


def test_skills_only_prompt_block():
    """skills_only prompt: 只含期望技能块, 无失败叙述; guidance 有失败叙述。"""
    mem = _memory_from_verdict("code_fix_001", _v())
    pb = build_prompt("skills_only", "t", "def f(): ...", memo_items=[mem])
    assert "只含期望行为" in pb
    assert "上次实测失败" not in pb
    pg = build_prompt("guidance", "t", "def f(): ...", memo_items=[mem])
    assert "上次实测失败" in pg
    # none 臂零记忆块（对照下界）
    pn = build_prompt("none", "t", "def f(): ...", memo_items=[mem])
    assert "过往" not in pn

def test_arm_material_assignment_not_degraded():
    """★ 回归锁: skills_only 必须与 guidance 同批条目（首版落 else ⇒ memo_n=0
    ⇒ 臂降级为 none — pass 与 none 完全一致的自检铁证教训）。"""
    # 源码级锁: 臂分配分支必须含 skills_only（跑真 LLM 前的静态防回退）
    src_path = os.path.join(ROOT, "src", "dwc", "experiments",
                            "mem_guidance_vs_replay.py")
    src = open(src_path, encoding="utf-8").read()
    assert 'arm in ("guidance", "skills_only")' in src, \
        "★ skills_only 臂分配必须与 guidance 同批（落 else = 降级 none）"
