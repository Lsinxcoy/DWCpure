"""DWC-AUTO · M1.4 task trajectory: hash refs, no raw payloads, no fake steps."""
from __future__ import annotations

import json
import os
from types import SimpleNamespace

from dwc.llm import task_exec as TE
from dwc.llm.task_trajectory import record_task_trajectory


def test_records_hashes_not_raw_payloads(tmp_path):
    result = {
        "task_id": "T/../evil",
        "status": "done",
        "rounds": 2,
        "answer": "SECRET_ANSWER",
        "actions_log": [{
            "round": 1, "phase": "obs", "op": "read", "target": "a.py",
            "args": "SECRET_ARGS", "obs": "SECRET_OBS", "ok": True,
        }],
    }
    meta = record_task_trajectory(result, var_dir=str(tmp_path))
    assert meta["trajectory_status"] == "recorded"
    assert meta["trajectory_steps"] == 1
    assert os.path.exists(meta["trajectory_path"])
    text = open(meta["trajectory_path"], encoding="utf-8").read()
    assert "SECRET_" not in text
    rec = json.loads(text.splitlines()[0])
    step = rec["steps"][0]
    assert step["args_ref"].startswith("sha256:")
    assert step["obs_ref"].startswith("sha256:")
    assert step["args_chars"] == len("SECRET_ARGS")
    assert rec["n_bad_steps"] == 0


def test_bad_step_is_counted_not_silently_dropped(tmp_path):
    result = {"task_id": "T_bad", "status": "done",
              "actions_log": [None, {"op": "read", "ok": True}]}
    meta = record_task_trajectory(result, var_dir=str(tmp_path))
    rec = json.loads(open(meta["trajectory_path"], encoding="utf-8")
                     .read().splitlines()[0])
    assert rec["n_bad_steps"] == 1
    assert rec["steps"][0]["bad"] == "not_a_dict"


def test_empty_actions_log_is_zero_steps(tmp_path):
    meta = record_task_trajectory(
        {"task_id": "T_empty", "status": "done", "actions_log": []},
        var_dir=str(tmp_path))
    assert meta["trajectory_steps"] == 0
    rec = json.loads(open(meta["trajectory_path"], encoding="utf-8")
                     .read().splitlines()[0])
    assert rec["steps"] == []


class _FinalLLM:
    configured = True

    def complete(self, *a, **k):
        return SimpleNamespace(ok=True, error=None, text=json.dumps({
            "analysis": "done", "op": "final", "answer": "已完成",
        }, ensure_ascii=False))


def test_execute_user_task_records_trajectory():
    rep = TE.execute_user_task("轨迹集成测试", llm=_FinalLLM(),
                               task_id="T_traj_integration")
    assert rep["trajectory_status"] == "recorded"
    assert rep["trajectory_steps"] >= 1
    assert os.path.exists(rep["trajectory_path"])
