"""SEC-01 · command allowlist tests."""
from __future__ import annotations

import pytest

from dwc.llm import exec_policy as P


@pytest.mark.parametrize("cmd", [
    ["python", "-c", "import os; os.remove('x')"],
    ["python", "-c", "print(1)"],
    ["python", "scripts/gate.py"],
    ["powershell", "-Command", "Remove-Item x"],
    ["cmd", "/c", "del x"],
    ["bash", "-c", "rm -rf x"],
    ["definitely_not_a_command"],
])
def test_denied(cmd):
    d = P.check(cmd, cwd=".")
    assert d.allowed is False
    assert d.requires_approval is False


@pytest.mark.parametrize("cmd", [
    ["python", "-m", "pytest", "tests/test_x.py"],
    ["pytest", "tests/test_x.py"],
    ["git", "status"],
    ["git", "diff"],
    ["ruff", "check", "src"],
    ["echo", "hi"],
    ["find", ".", "-name", "*.py"],
])
def test_allowed(cmd):
    assert P.check(cmd, cwd=".").allowed is True


@pytest.mark.parametrize("cmd", [
    ["rm", "x"],
    ["git", "push"],
    ["curl", "http://x"],
])
def test_approval_required(cmd):
    d = P.check(cmd, cwd=".")
    assert d.allowed is False
    assert d.requires_approval is True
    assert d.ask


def test_tool_private_python_c_allowed():
    d = P.check(["python", "-c", "print(1)"], cwd=".", from_tool=True)
    assert d.allowed is True
