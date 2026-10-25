"""SEC-02 · actor/candidates AST guard tests."""
from __future__ import annotations

import pytest

from dwc.organs.actor import ActorError, PureFunctionExecutor
from dwc.organs.candidates import CandidateGenerator


@pytest.mark.parametrize("bad", [
    "import os\ndef f(n):\n    return os.getcwd()",
    "def f(n):\n    return open('x').read()",
    "def f(n):\n    return ().__class__",
    "def f(n):\n    while True:\n        pass",
])
def test_actor_rejects_unsafe_source(bad):
    with pytest.raises(ActorError):
        PureFunctionExecutor("f", source=bad)


def test_actor_reference_still_runs():
    ex = PureFunctionExecutor("sum_first_n")
    receipt = ex({"args": "3"})
    assert receipt.ok is True
    assert receipt.detail["value"] == 6


@pytest.mark.parametrize("bad", [
    "import os\ndef f(n):\n    return os.getcwd()",
    "def f(n):\n    return open('x').read()",
])
def test_candidate_baseline_rejects_unsafe_source(bad):
    assert CandidateGenerator._baseline_reproduces(
        [{"fn": "f", "args": 1, "actual": 1}], bad, "f") is None
