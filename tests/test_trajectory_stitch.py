"""DWC-AUTO · M3.3 trajectory stitching: real steps only, no fabrication."""
from __future__ import annotations

from dwc.harness.trajectory_stitch import stitch


def test_stitch_two_real_trajectories():
    a = {"steps": [{"op": "read", "target": "a.py", "ok": True,
                    "obs_ref": "h1"}]}
    b = {"steps": [{"op": "run", "target": "pytest", "ok": True,
                    "obs_ref": "h2"}]}
    out = stitch(a, b)
    assert out["stitched"] is True
    assert out["n_steps"] == 2
    assert [x["source"] for x in out["steps"]] == ["primary", "secondary"]
    assert out["link"]["relation"] == "follows"
    assert out["evidence_refs"] == ["h1", "h2"]


def test_single_sided_does_not_stitch():
    out = stitch({"steps": []}, {"steps": [{"op": "run", "ok": True}]})
    assert out["stitched"] is False
    assert out["steps"] == []
