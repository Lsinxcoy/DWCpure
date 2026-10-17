# -*- coding: utf-8 -*-
"""R303-⑤ Coordinator：规则拆活+Kanban台账。串行先行，绝不硬拆。"""
from dwc.llm.coordinator import plan, run_plan


def test_split_and():
    blocks = plan("查A且查B")
    assert len(blocks) == 2 and all(b["dep"] == [] for b in blocks)


def test_split_seq():
    blocks = plan("先查A再查B")
    assert len(blocks) == 2 and blocks[1]["dep"] == [0]


def test_single_no_split():
    blocks = plan("查A")
    assert len(blocks) == 1 and blocks[0]["dep"] == []


def test_cap_three():
    blocks = plan("查A且查B且查C且查D")
    assert len(blocks) == 3


def test_run_plan_kanban(tmp_path):
    log = tmp_path / "kanban.jsonl"
    calls = []
    blocks = plan("查A且查B")
    out = run_plan(blocks, str(log), emit=lambda b: calls.append(b["sub"]))
    assert out == ["done", "done"] and calls == ["查A", "查B"]
    lines = open(str(log), encoding="utf-8").read().strip().split("\n")
    assert len(lines) == 4  # 每块 queued+done 两行
