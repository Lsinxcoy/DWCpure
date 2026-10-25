from pathlib import Path

from dwc.harness.run_identity import RunIdentity, RunMarkerStore, content_fingerprint


def test_complete_marker_written_only_after_normal_return(tmp_path):
    store = RunMarkerStore(tmp_path)
    identity = RunIdentity(run_id="r1", task_id="t1", protocol_id="p1",
                           component_hash="c1", artifact_fingerprint="a1",
                           solver_id="s", model_id="m", evaluator_version="e")
    def interrupted():
        raise RuntimeError("stop")
    assert store.run(identity, interrupted) is None
    assert not store.marker_path(identity).exists()
    assert store.run(identity, lambda: "answer") == "answer"
    assert store.resume(identity, tmp_path) is None


def test_resume_requires_marker_all_identity_hashes_and_artifact(tmp_path):
    artifact = tmp_path / "answer.txt"
    artifact.write_text("answer")
    identity = RunIdentity(run_id="r1", task_id="t1", protocol_id="p1",
                           component_hash="c1", artifact_fingerprint=content_fingerprint(artifact),
                           solver_id="s", model_id="m", evaluator_version="e")
    store = RunMarkerStore(tmp_path / "runs")
    store.run(identity, lambda: "done")
    assert store.resume(identity, artifact) == "done"
    artifact.write_text("tampered")
    assert store.resume(identity, artifact) is None
    changed = RunIdentity(**{**identity.__dict__, "model_id": "m2"})
    assert store.resume(changed, artifact) is None


def test_content_fingerprint_uses_bytes_not_mtime(tmp_path):
    path = tmp_path / "context.txt"
    path.write_text("one")
    before = content_fingerprint(path)
    stat = path.stat()
    path.write_text("two")
    path.touch()
    import os
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    assert content_fingerprint(path) != before


def test_answer_file_without_marker_is_not_reused(tmp_path):
    artifact = tmp_path / "answer.txt"
    artifact.write_text("answer")
    identity = RunIdentity("r", "t", "p", "c", content_fingerprint(artifact), "s", "m", "e")
    assert RunMarkerStore(tmp_path / "runs").resume(identity, artifact) is None
