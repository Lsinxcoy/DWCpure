"""DWC-AUTO · M1.3 skill kind filter: factual/chat not injected as procedure."""
from __future__ import annotations

from dwc.llm.executor import memory_text
from dwc.organs.memory import MemoryKernel, MemoryKind


def _skill(mem, scene, method, kind=None):
    payload = {
        "scene": scene, "method": method,
        "boundary": "success_pattern:test",
        "invalid_conditions": "不适用时不要用",
        "recovery_strategies": "失败后重新诊断",
    }
    if kind:
        payload["skill_kind"] = kind
    return mem.remember(MemoryKind.SKILL, payload)


def test_factual_skill_is_not_injected(tmp_path):
    mem = MemoryKernel(str(tmp_path / "m.db"))
    scene = "修复 factorial 函数的无限递归"
    _skill(mem, scene, "阶乘定义为 n! = n×(n-1)!；5! = 120", "factual")
    assert memory_text(mem, scene) == ""
    assert "阶乘" in memory_text(mem, scene, include_factual=True)


def test_chat_skill_is_not_injected(tmp_path):
    mem = MemoryKernel(str(tmp_path / "m.db"))
    scene = "你现在拥有跨任务上下文记忆了吗"
    _skill(mem, scene, "部分具备，但要区分两种记忆；建议把结论写入文件。",
           "chat")
    assert memory_text(mem, scene) == ""


def test_legacy_factual_is_classified_on_the_fly(tmp_path):
    mem = MemoryKernel(str(tmp_path / "m.db"))
    scene = "修复 sum_first_n 的边界错误"
    _skill(mem, scene, "sum_first_n(n)=n(n+1)/2；21×22/2=231")
    assert memory_text(mem, scene) == ""


def test_procedural_skill_still_recalled(tmp_path):
    mem = MemoryKernel(str(tmp_path / "m.db"))
    scene = "定位代码符号"
    _skill(mem, scene, "先搜索定义，再读取文件，最后运行测试验证")
    got = memory_text(mem, scene)
    assert got and "先搜索定义" in got
