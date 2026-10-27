# -*- coding: utf-8 -*-
"""P1 · apply_patch：精确 old→new，不整文件重写。"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
from dwc.llm import task_exec as TE                             # noqa: E402


def _work(tmp_path, monkeypatch):
    monkeypatch.setattr(TE, "ROOT", str(tmp_path))
    monkeypatch.setattr(TE, "WORK", str(tmp_path / "var" / "inbox_work"))
    p = tmp_path / "var" / "inbox_work" / "x.txt"
    p.parent.mkdir(parents=True)
    p.write_text("alpha\nbeta\ngamma\n", encoding="utf-8")
    return p


def test_apply_patch_replaces_exactly_once(tmp_path, monkeypatch):
    p = _work(tmp_path, monkeypatch)
    out = TE._do_action("apply_patch", {
        "path": "var/inbox_work/x.txt", "old": "beta", "new": "BETA"})
    assert out["ok"] and out["replacements"] == 1
    assert p.read_text(encoding="utf-8") == "alpha\nBETA\ngamma\n"


def test_apply_patch_requires_replace_all_for_multiple_hits(tmp_path, monkeypatch):
    p = _work(tmp_path, monkeypatch)
    p.write_text("x x x\n", encoding="utf-8")
    out = TE._do_action("apply_patch", {
        "path": "var/inbox_work/x.txt", "old": "x", "new": "y"})
    assert not out["ok"] and "replace_all" in out["error"]
    assert p.read_text(encoding="utf-8") == "x x x\n"


def test_apply_patch_replace_all(tmp_path, monkeypatch):
    p = _work(tmp_path, monkeypatch)
    p.write_text("x x x\n", encoding="utf-8")
    out = TE._do_action("apply_patch", {
        "path": "var/inbox_work/x.txt", "old": "x", "new": "y",
        "replace_all": True})
    assert out["ok"] and out["replacements"] == 3
    assert p.read_text(encoding="utf-8") == "y y y\n"


def test_apply_patch_missing_old_is_rejected(tmp_path, monkeypatch):
    _work(tmp_path, monkeypatch)
    out = TE._do_action("apply_patch", {
        "path": "var/inbox_work/x.txt", "old": "nope", "new": "x"})
    assert not out["ok"] and "未命中" in out["error"]


def test_apply_patch_is_registered_as_native_tool():
    names = [t["function"]["name"] for t in TE.TASK_TOOLS]
    assert "apply_patch" in names
    assert TE._TOOL_TO_OP["apply_patch"][0] == "apply_patch"


def test_apply_patch_passes_step_judge():
    from dwc.llm.step_judge import judge_step, validate_step
    step = {"op": "apply_patch", "path": "var/inbox_work/x.txt",
            "old": "a", "new": "b"}
    verdict, why, rule = judge_step(step, [])
    assert verdict != "noisy", (verdict, why, rule)
    assert validate_step(step) is None
