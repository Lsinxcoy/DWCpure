import hashlib

import pytest

from dwc.harness.probe_compose import (
    ComposeError,
    ProbeProtocol,
    ProbeResult,
    ProbeRun,
    compose_candidates,
    run_probe,
)


def _protocol():
    return ProbeProtocol(
        protocol_id="probe-1", split="dev", task_ids=("task-1",),
        model_id="model-a", environment_hash="env-a",
    )


def _result(**extra):
    return ProbeResult(
        candidate_hash=hashlib.sha256(b"candidate").hexdigest(),
        protocol_id="probe-1", split="dev", task_id="task-1",
        model_id="model-a", environment_hash="env-a",
        behavior="changed", delivered=True, passed=False,
        adopted=False, verified=True,
        **extra,
    )


def test_probe_fields_are_independent_not_a_success_hierarchy():
    result = _result()
    assert result.behavior == "changed"
    assert result.delivered and not result.passed
    assert result.verified and not result.adopted


def test_probe_binds_exact_hash_protocol_and_execution_identity():
    probe = run_probe(_protocol(), b"candidate", [_result()], base_rollouts=[{"task_id": "task-1"}])
    assert probe.status == "observed"
    with pytest.raises(ComposeError, match="hash"):
        run_probe(_protocol(), b"other", [_result()], base_rollouts=[{}])
    with pytest.raises(ComposeError, match="validation"):
        run_probe(ProbeProtocol("bad", "validation", ("task-1",), "model-a", "env-a"), b"candidate", [])


def test_compose_keep_current_is_decided_by_real_diff_not_claim(tmp_path):
    base = tmp_path / "base"
    base.mkdir()
    (base / "config.txt").write_text("same")
    unchanged = tmp_path / "unchanged"
    unchanged.mkdir()
    (unchanged / "config.txt").write_text("same")
    changed = tmp_path / "changed"
    changed.mkdir()
    (changed / "config.txt").write_text("different")
    keep = compose_candidates(base, [{"label": "keep", "claimed_decision": "KEEP_CURRENT", "root": unchanged}], probe_runner=lambda root: {"static_valid": True, "probe": "done"})
    assert keep.decision == "KEEP_CURRENT"
    assert not keep.kept
    assert keep.requires_reprobe is False
    actual = compose_candidates(base, [{"label": "change", "claimed_decision": "KEEP_CURRENT", "root": changed}], probe_runner=lambda root: {"static_valid": True, "probe": "done"})
    assert actual.kept
    assert actual.decision == "COMPOSED"
    assert actual.requires_reprobe is False
    assert actual.probe_result == {"static_valid": True, "probe": "done"}


def test_changed_composition_requires_real_reprobe_and_base_remains(tmp_path):
    base = tmp_path / "base"
    changed = tmp_path / "changed"
    base.mkdir()
    changed.mkdir()
    (base / "a").write_text("a")
    (changed / "a").write_text("b")
    result = compose_candidates(base, [{"label": "b", "root": changed}])
    assert result.status == "needs_reprobe"
    assert result.requires_reprobe
    assert result.final_pool == ("base", "composed")
    assert (base / "a").read_text() == "a"
    with pytest.raises(ComposeError, match="reprobe"):
        compose_candidates(base, [{"label": "b", "root": changed}], probe_runner=lambda root: (_ for _ in ()).throw(RuntimeError("infra")))


def test_compose_rejects_duplicate_labels_and_validation_evidence(tmp_path):
    base = tmp_path / "base"
    base.mkdir()
    with pytest.raises(ComposeError, match="duplicate"):
        compose_candidates(base, [{"label": "x"}, {"label": "x"}])
    with pytest.raises(ComposeError, match="validation"):
        compose_candidates(base, [{"label": "x", "evidence": {"split": "validation"}}])
