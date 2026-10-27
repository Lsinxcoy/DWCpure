# -*- coding: utf-8 -*-
"""P1 · TaskGraph：持久任务节点/状态/依赖。"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
from dwc.llm.task_graph import TaskGraph                     # noqa: E402
from dwc.llm import task_exec as TE                          # noqa: E402


def test_graph_create_update_reload(tmp_path, monkeypatch):
    monkeypatch.setenv("DWC_VAR_DIR", str(tmp_path))
    g = TaskGraph("T1")
    a = g.create("读源码", description="先定位")
    b = g.create("写产物", owner="agent")
    assert a["id"] == "T1" and b["id"] == "T2"
    g.update("T1", status="completed", owner="agent")
    g.update("T2", add_blocked_by=["T1"])
    assert g.list()["nodes"][0]["status"] == "completed"
    assert g.list()["nodes"][1]["blockedBy"] == ["T1"]

    g2 = TaskGraph("T1")
    assert g2.list()["nodes"][0]["owner"] == "agent"
    assert "T2" in g2.summary() and "blockedBy=T1" in g2.summary()


def test_graph_invalid_status_and_unknown_id(tmp_path, monkeypatch):
    monkeypatch.setenv("DWC_VAR_DIR", str(tmp_path))
    g = TaskGraph("T2")
    g.create("x")
    for kwargs in ({"status": "bogus"},):
        try:
            g.update("T1", **kwargs)
        except ValueError as exc:
            assert "status" in str(exc)
        else:
            raise AssertionError("非法 status 未拒绝")
    try:
        g.update("T999", status="completed")
    except ValueError as exc:
        assert "未知 id" in str(exc)
    else:
        raise AssertionError("未知 id 未拒绝")


def test_graph_deleted_hidden_by_default(tmp_path, monkeypatch):
    monkeypatch.setenv("DWC_VAR_DIR", str(tmp_path))
    g = TaskGraph("T3")
    g.create("x")
    g.update("T1", status="deleted")
    assert g.list()["nodes"] == []
    assert len(g.list(include_deleted=True)["nodes"]) == 1


def test_task_actions_write_persistent_graph(tmp_path, monkeypatch):
    monkeypatch.setenv("DWC_VAR_DIR", str(tmp_path))
    out = TE._do_action("task_create", {
        "subject": "定位文件", "_task_id": "T_act"})
    assert out["ok"] and out["node"]["id"] == "T1"
    out2 = TE._do_action("task_update", {
        "id": "T1", "status": "in_progress", "_task_id": "T_act"})
    assert out2["ok"] and out2["node"]["status"] == "in_progress"
    out3 = TE._do_action("task_list", {"_task_id": "T_act"})
    assert out3["ok"] and out3["graph"]["nodes"][0]["status"] == "in_progress"
    assert os.path.isfile(out3["path"])


def test_task_actions_are_registered_and_judged():
    names = [t["function"]["name"] for t in TE.TASK_TOOLS]
    for n in ("task_create", "task_update", "task_list"):
        assert n in names
        assert TE._TOOL_TO_OP[n][0] == n
    from dwc.llm.step_judge import judge_step
    verdict, why, rule = judge_step(
        {"op": "task_create", "subject": "x"}, [])
    assert verdict != "noisy", (verdict, why, rule)
