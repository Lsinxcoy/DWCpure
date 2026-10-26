"""启动维护默认 dry-run：不得在无人要求时 archive。"""
from __future__ import annotations

import importlib.util
import os

from dwc.organs.memory import MemoryKernel, MemoryKind


def _agent_module():
    spec = importlib.util.spec_from_file_location(
        "dwc_agent_maintain_test", "scripts/dwc_agent.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_startup_maintain_is_dry_run_by_default(tmp_path, monkeypatch):
    A = _agent_module()
    A.ROOT = str(tmp_path)
    logs = []
    A._log = lambda ev: logs.append(ev)
    monkeypatch.delenv("DWC_MAINTAIN_ON_START", raising=False)
    m = MemoryKernel(str(tmp_path / "m.db"))
    nid = m.remember(MemoryKind.TRACE, {"task": "t", "action": "a"})
    A._maybe_maintain(m)
    assert m.get(nid).archived_at is None
    assert any(e.get("event") == "memory_maintain_skipped"
               and e.get("why") == "startup_dry_run" for e in logs)
    m.close()


def test_startup_maintain_opt_in_env(tmp_path, monkeypatch):
    A = _agent_module()
    A.ROOT = str(tmp_path)
    logs = []
    A._log = lambda ev: logs.append(ev)
    monkeypatch.setenv("DWC_MAINTAIN_ON_START", "1")
    m = MemoryKernel(str(tmp_path / "m.db"))
    m.remember(MemoryKind.TRACE, {"task": "t", "action": "a"})
    A._maybe_maintain(m)
    # 单条未召回 trace 应 held，不归档；关键是走到了真维护分支
    assert any(e.get("event") in ("memory_maintain", "memory_maintain_empty")
               for e in logs)
    m.close()
