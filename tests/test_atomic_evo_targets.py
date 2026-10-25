# -*- coding: utf-8 -*-
"""evo_targets 原子落盘与回滚安全测试；所有写入均在 tmp_path。"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.organs import evo_targets as ET  # noqa: E402


@pytest.fixture()
def sandbox(tmp_path, monkeypatch):
    monkeypatch.setattr(ET, "ROOT", str(tmp_path))
    return tmp_path


def test_rollback_first_creation_removes_file(sandbox):
    out = ET.apply("context_mgmt", {"read_default_lines": 300})
    assert out["created"] is True
    assert out["backup"] == ""

    restored = ET.rollback("context_mgmt", out["backup"])

    target = sandbox / "config" / "context_policy.json"
    assert restored["outcome"] == "rolled_back"
    assert restored["removed"] is True
    assert not target.exists()
    assert ET.read("context_mgmt")["read_default_lines"] == 200


def test_concurrent_processes_do_not_lose_updates(sandbox):
    """两个真实进程同时加 1，读改写锁必须保留两次更新。"""
    target = sandbox / "config" / "context_policy.json"
    target.parent.mkdir()
    target.write_text(json.dumps({"read_default_lines": 200}), encoding="utf-8")
    worker = r'''
import os, sys
sys.path.insert(0, os.path.join(sys.argv[1], "src"))
from dwc.organs import evo_targets as ET
ET.ROOT = sys.argv[2]
value = ET.update("context_mgmt", lambda current: {"read_default_lines": current["read_default_lines"] + 1})
'''
    commands = [[sys.executable, "-c", worker, ROOT, str(sandbox)]
                for _ in range(2)]
    with ThreadPoolExecutor(max_workers=2) as pool:
        processes = list(pool.map(
            lambda cmd: subprocess.run(cmd, capture_output=True, text=True,
                                       timeout=30, check=False), commands))
    assert [p.returncode for p in processes] == [0, 0], [
        (p.stdout, p.stderr) for p in processes]
    assert json.loads(target.read_text(encoding="utf-8"))[
        "read_default_lines"] == 202
