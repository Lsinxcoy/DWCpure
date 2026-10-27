# -*- coding: utf-8 -*-
"""P2/P3 · SkillReview：真实轨迹 → proposal → 审批 → active。"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
from dwc.organs import skill_review as SR                    # noqa: E402
from dwc.organs import skill_store as SS                     # noqa: E402


def _result(status="done", actions=None):
    return {"status": status, "answer": "ok",
            "actions_log": actions if actions is not None else [
                {"op": "write", "ok": True, "target": "var/inbox_work/x.md"},
                {"op": "run", "ok": True, "target": "pytest -q"},
            ]}


def test_propose_requires_verified_actions(tmp_path, monkeypatch):
    monkeypatch.setenv("DWC_VAR_DIR", str(tmp_path))
    assert SR.propose_from_result({"status": "done", "actions_log": []},
                                  task="t")["why"] == "no_verified_actions"
    assert SR.propose_from_result(_result(status="incomplete"),
                                  task="t")["why"] == "not_done"


def test_propose_creates_pending_without_active_skill(tmp_path, monkeypatch):
    monkeypatch.setenv("DWC_VAR_DIR", str(tmp_path))
    monkeypatch.setattr(SS, "SKILLS_DIR", str(tmp_path / "skills"))
    rep = SR.propose_from_result(_result(), task="写一个报告并运行测试")
    assert rep["ok"]
    p = rep["proposal"]
    assert p["status"] == "pending"
    assert "write" in p["skill_md"] and "run/test" in p["skill_md"]
    assert not os.path.exists(SS.path_of(p["name"]))


def test_approve_preview_then_apply(tmp_path, monkeypatch):
    monkeypatch.setenv("DWC_VAR_DIR", str(tmp_path))
    monkeypatch.setattr(SS, "SKILLS_DIR", str(tmp_path / "skills"))
    p = SR.propose_from_result(_result(), task="写一个报告并运行测试")["proposal"]
    prev = SR.approve(p["id"], apply=False)
    assert prev["ok"] and prev["apply"] is False
    assert not os.path.exists(SS.path_of(p["name"]))
    got = SR.approve(p["id"], apply=True)
    assert got["ok"] and got["apply"] is True
    assert os.path.isfile(SS.path_of(p["name"]))
    assert got["proposal"]["status"] == "approved"


def test_reject_and_list(tmp_path, monkeypatch):
    monkeypatch.setenv("DWC_VAR_DIR", str(tmp_path))
    p = SR.propose_from_result(_result(), task="t")["proposal"]
    assert SR.reject(p["id"], "not useful")["proposal"]["status"] == "rejected"
    assert SR.list_proposals("pending") == []
    assert len(SR.list_proposals("rejected")) == 1
