"""DWC-AUTO · M1 skill quality metadata: procedural vs factual vs chat."""
from __future__ import annotations

import json

from dwc.organs.memory import MemoryKernel
from dwc.organs.skill_writer import classify_skill_kind, from_term, lesson_to_payload


def test_classify_procedural():
    assert classify_skill_kind(
        "定位代码符号", "先搜索定义，再读取文件，最后运行测试验证"
    ) == "procedural"


def test_classify_factual():
    assert classify_skill_kind(
        "阶乘", "阶乘定义为 n! = n×(n-1)!；5! = 120"
    ) == "factual"


def test_classify_chat():
    text = ("你可以考虑先看文档，我认为这样比较好，建议把相关章节都读一遍，"
            "然后再决定是否修改，总结一下就是多读多看。")
    assert classify_skill_kind("一般建议", text) == "chat"


def test_classify_question_answer_is_chat():
    assert classify_skill_kind(
        "你现在拥有跨任务上下文记忆了吗",
        "部分具备。每次接单都会加载配置，也会读取文件；建议把结论写入文件。",
    ) == "chat"


def test_from_term_payload_carries_kind(tmp_path):
    mem = MemoryKernel(str(tmp_path / "m.db"))
    nid = from_term(
        mem, "定位符号", "定位代码符号",
        "先搜索定义，再读取文件，最后运行测试验证", passed=True, quality=1.0,
    )
    assert nid
    node = mem.get(nid)
    payload = node.payload if isinstance(node.payload, dict) \
        else json.loads(node.payload)
    assert payload["skill_kind"] == "procedural"


def test_lesson_payload_carries_kind():
    p = lesson_to_payload({
        "fail_mode": "success_pattern:code",
        "task": "定位代码符号",
        "detail": "先搜索定义，再读取文件，最后运行测试验证",
    })
    assert p and p["skill_kind"] == "procedural"
