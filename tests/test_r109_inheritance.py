# -*- coding: utf-8 -*-
"""R109 · 稿①执行 — 六段继承产物（综述 §7 原文格式）。

验收（稿① §⑧ 字面）:
  □ 六段构造 + 写入即校验（缺段/坏段 raise 探针 ≥5）
  □ parent_gen 链连续（断链红）
  □ 段2/段3 非法形态（纯叙述/无 exec_form）被拒
  □ 现有 legacy 档零改动（读取兼容 — 无键=legacy 分支）
  □ 三层验证不变 · 一档一提交一知识档
"""
from __future__ import annotations

import json
import os
import sys

import pytest

ROOT = r"E:/Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.foundation.inheritance import (  # noqa: E402
    InheritanceError, attach_inheritance, build_inheritance,
    load_latest_gen, truth_fingerprint, validate_inheritance)


def _ok(**over):
    base = dict(
        gen=109, parent_gen=108, at="2026-10-09T12:00:00+08:00",
        parent_state={"commits": 114},
        proposed_change={"kind": "patch", "exec_form": "diff ...",
                         "files": ["src/x.py"]},
        motivating_evidence={"refs": [{"type": "test",
                                       "ref": "tests/t.py::test_x",
                                       "claim": "806 passed"}],
                             "numbers": {"pytest": 806}},
        evaluation_config={"truth_source": "config/anchors/dev.json",
                           "truth_sha8": "abcd1234",
                           "judge_frozen": True},
        acceptance_decision={"gate": "pytest+gate+e2e",
                             "verdict": "accepted", "evidence_ref": "rc=0"},
    )
    base.update(over)
    return base


def test_build_and_validate_ok():
    """六段齐 + 四属性过 ⇒ 构造通过（构造即校验）。"""
    inh = build_inheritance(**_ok())
    assert inh["gen"] == 109 and inh["parent_gen"] == 108
    assert inh["subsequent_use"]["status"] == "pending"
    assert "gap_note" in inh["subsequent_use"]   # 断供如实（R106 缺口挂账）


def test_probe_missing_segment_raises():
    """探针① 缺段 ⇒ raise（七判据之一）。"""
    bad = _ok()
    del bad["motivating_evidence"]
    with pytest.raises(InheritanceError, match="六段缺"):
        validate_inheritance({"gen": 1, "at": "2026-10-09T00:00:00", "parent_gen": 0,
                              "supersedes": None, **bad})


def test_probe_pure_narrative_change_raises():
    """探针② 段2 纯叙述（kind 无/exec 空）⇒ 拒（Hyra 属性）。"""
    with pytest.raises(InheritanceError, match="kind"):
        build_inheritance(**_ok(proposed_change={"kind": "essay",
                                                 "exec_form": "d"}))
    with pytest.raises(InheritanceError, match="exec_form"):
        build_inheritance(**_ok(proposed_change={"kind": "patch",
                                                 "exec_form": "  "}))


def test_probe_unciteable_evidence_raises():
    """探针③ 段3 无 refs / 坏 type ⇒ 拒（ARA 属性）。"""
    with pytest.raises(InheritanceError, match="refs"):
        build_inheritance(**_ok(motivating_evidence={"refs": []}))
    with pytest.raises(InheritanceError, match="type"):
        build_inheritance(**_ok(motivating_evidence={
            "refs": [{"type": "story", "ref": "x", "claim": "y"}]}))


def test_probe_bad_fingerprint_and_verdict_and_status():
    """探针④⑤⑥ 段4 指纹坏 / 段5 verdict 非法 / 段6 无 gap_note ⇒ 各 raise。"""
    with pytest.raises(InheritanceError, match="truth_sha8"):
        build_inheritance(**_ok(evaluation_config={
            "truth_source": "s", "truth_sha8": "XYZ", "judge_frozen": True}))
    with pytest.raises(InheritanceError, match="verdict"):
        build_inheritance(**_ok(acceptance_decision={"verdict": "maybe"}))
    with pytest.raises(InheritanceError, match="gap_note"):
        build_inheritance(**_ok(subsequent_use={"status": "pending"}))


def test_chain_and_attach(tmp_path):
    """链: load_latest_gen 读父档 gen; attach 只扩不破（重复挂=raise）。"""
    d = str(tmp_path)
    assert load_latest_gen(d) is None           # 空目录 ⇒ 首档 None
    rec = {"round": "R108"}
    inh = build_inheritance(**_ok(parent_gen=load_latest_gen(d)))
    rec2 = attach_inheritance(rec, inh)
    assert rec2["inheritance"]["gen"] == 109
    with open(os.path.join(d, "knowledge3_R108_x.json"), "w",
              encoding="utf-8") as f:
        json.dump(rec2, f, ensure_ascii=False)
    assert load_latest_gen(d) == 109            # 下轮 parent_gen 链源
    with pytest.raises(InheritanceError, match="supersedes"):
        attach_inheritance(rec2, inh)            # 已带 ⇒ 不原地改


def test_legacy_reads_broken_and_fingerprint():
    """legacy 107 档零改动: 无 inheritance 键读取方按键分支; 指纹 8 位 hex。"""
    legacy = json.load(open(os.path.join(ROOT, "archive",
                                         "knowledge3_R107_transfer.json"),
                            encoding="utf-8"))
    assert "inheritance" not in legacy           # 旧档不被改（只扩不破）
    fp = truth_fingerprint(os.path.join(ROOT, "config", "anchors", "dev.json"))
    assert len(fp) == 8 and all(c in "0123456789abcdef" for c in fp)
    # 档损坏 ⇒ 大声 raise（G7 不静默）
    import io
    bad = os.path.join(ROOT, "archive", "knowledge3_broken.json")
    io.open(bad, "w").write("{oops")
    try:
        with pytest.raises(InheritanceError, match="损坏"):
            load_latest_gen(os.path.join(ROOT, "archive"))
    finally:
        os.remove(bad)
