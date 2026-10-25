"""DWC-AUTO · M1.5 contrast: paired evidence only, no invented causality."""
from __future__ import annotations

from dwc.harness.contrast import compare


def test_first_divergence_and_verification():
    failure = {"steps": [
        {"op": "read", "target": "a.py", "ok": True, "obs_ref": "h1"},
        {"op": "run", "target": "pytest -q", "ok": False, "obs_ref": "h2"},
    ]}
    success = {"steps": [
        {"op": "read", "target": "a.py", "ok": True, "obs_ref": "h1"},
        {"op": "run", "target": "pytest -q", "ok": True, "obs_ref": "h3"},
    ]}
    out = compare(failure, success)
    assert out["comparable"] is True
    assert out["divergence_index"] == 1
    assert out["changed_action"]["failure"]["ok"] is False
    assert out["changed_action"]["success"]["ok"] is True
    assert out["verification"][0]["op"] == "run"
    assert out["confidence"] == 0.8


def test_single_sided_does_not_claim_causality():
    out = compare({"steps": []}, {"steps": [{"op": "run", "ok": True}]})
    assert out["comparable"] is False
    assert out["confidence"] == 0.0
    assert out["changed_action"] is None


def test_same_steps_do_not_invent_divergence():
    same = {"steps": [{"op": "read", "target": "a.py", "ok": True}]}
    out = compare(same, same)
    assert out["comparable"] is True
    assert out["divergence_index"] is None
    assert out["confidence"] == 0.2
