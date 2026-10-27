# -*- coding: utf-8 -*-
"""P2 · Workflow：内容哈希缓存 + 可恢复。"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
from dwc.llm.workflow import run_workflow, load_state      # noqa: E402


def _spec():
    return {"name": "demo", "steps": [
        {"id": "s1", "task": "first", "opts": {"a": 1}},
        {"id": "s2", "task": "second", "max_rounds": 3},
    ]}


def test_workflow_runs_and_resumes_unchanged(tmp_path):
    calls = []

    def runner(task, opts):
        calls.append((task, opts))
        return {"status": "done", "answer": task, "rounds": 1}

    rep = run_workflow(_spec(), runner=runner, run_id="W1",
                       base_dir=str(tmp_path))
    assert rep["status"] == "done" and rep["n_run"] == 2
    assert len(calls) == 2
    assert os.path.isfile(tmp_path / "workflows" / "W1" / "state.json")

    rep2 = run_workflow(_spec(), runner=runner, run_id="W1", resume=True,
                        base_dir=str(tmp_path))
    assert rep2["status"] == "done" and rep2["n_cached"] == 2
    assert rep2["n_run"] == 0 and len(calls) == 2


def test_workflow_reruns_only_changed_step(tmp_path):
    calls = []

    def runner(task, opts):
        calls.append(task)
        return {"status": "done", "answer": task}

    run_workflow(_spec(), runner=runner, run_id="W2", base_dir=str(tmp_path))
    calls.clear()
    spec = _spec()
    spec["steps"][1]["task"] = "second-changed"
    rep = run_workflow(spec, runner=runner, run_id="W2", resume=True,
                       base_dir=str(tmp_path))
    assert rep["n_cached"] == 1 and rep["n_run"] == 1
    assert calls == ["second-changed"]


def test_workflow_failure_is_visible_and_stops(tmp_path):
    def runner(task, opts):
        if task == "bad":
            raise RuntimeError("boom")
        return {"status": "done", "answer": task}

    spec = {"steps": [{"id": "s1", "task": "bad"},
                      {"id": "s2", "task": "never"}]}
    rep = run_workflow(spec, runner=runner, run_id="W3",
                       base_dir=str(tmp_path))
    assert rep["status"] == "failed"
    assert rep["n_run"] == 1
    st = load_state("W3", str(tmp_path))
    assert st["steps"]["s1"]["status"] == "failed"
    assert "s2" not in st["steps"]


def test_workflow_max_rounds_enters_opts(tmp_path):
    seen = {}

    def runner(task, opts):
        seen.update(opts)
        return {"status": "done", "answer": task}

    run_workflow({"steps": [{"id": "s1", "task": "x",
                             "max_rounds": 7}]},
                 runner=runner, run_id="W4", base_dir=str(tmp_path))
    assert seen.get("max_rounds") == 7


def test_workflow_rejects_empty_steps():
    try:
        run_workflow({"steps": []}, runner=lambda t, o: {})
    except ValueError as exc:
        assert "steps" in str(exc)
    else:
        raise AssertionError("空 steps 未拒绝")
