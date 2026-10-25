import pytest

from dwc.harness.improvement_schedule import ScheduleError, run_improvement_schedule


def test_parallel_uses_frozen_base_and_canonical_ledger_order():
    seen = []
    def execute(base, step):
        seen.append((base, step["label"]))
        return {"checkpoint": "cp-" + step["label"], "cost": 1}

    result = run_improvement_schedule(
        "parallel", "original", [{"label": "z"}, {"label": "a"}], execute,
        execution_order=[1, 0],
    )
    assert seen == [("original", "a"), ("original", "z")]
    assert [row["label"] for row in result.ledger] == ["a", "z"]
    assert [row["sequence"] for row in result.ledger] == [0, 1]
    assert result.original_base == "original"
    assert set(result.final_pool) == {"original", "cp-a", "cp-z"}


def test_sequential_checkpoint_and_restore_never_lose_original_base():
    def execute(base, step):
        return {"checkpoint": step["label"] + "-cp", "cost": 2, "adopted": True}

    result = run_improvement_schedule("sequential", "original", [
        {"label": "one"}, {"label": "restore", "restore": "one-cp"}, {"label": "two"},
    ], execute)
    parents = {row["label"]: row["parent_checkpoint"] for row in result.ledger}
    assert parents == {"one": "original", "restore": "one-cp", "two": "one-cp"}
    assert result.current_checkpoint == "two-cp"
    assert result.checkpoints == ("one-cp", "two-cp")
    assert result.final_pool[0] == "original"


def test_resume_does_not_shift_slots_and_duplicate_label_fails_before_execution():
    calls = []
    result = run_improvement_schedule(
        "sequential", "original", [{"label": "a"}, {"label": "b"}],
        lambda base, step: calls.append(step["label"]) or {"checkpoint": step["label"], "cost": 1},
        completed=[{"label": "a", "sequence": 0, "parent_checkpoint": "original", "checkpoint": "a", "cost": 1, "status": "recorded"}],
    )
    assert calls == ["b"]
    assert [row["sequence"] for row in result.ledger] == [0, 1]
    with pytest.raises(ScheduleError, match="duplicate"):
        run_improvement_schedule("parallel", "base", [{"label": "a"}, {"label": "a"}], lambda *_: calls.append("bad"))
    assert calls == ["b"]


def test_mode_and_resume_integrity_are_validated():
    with pytest.raises(ScheduleError, match="mode"):
        run_improvement_schedule("tree", "base", [], lambda *_: {})
    with pytest.raises(ScheduleError, match="resume"):
        run_improvement_schedule("parallel", "base", [{"label": "a"}], lambda *_: {}, completed=[{"label": "other"}])
