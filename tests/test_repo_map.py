# -*- coding: utf-8 -*-
"""P1 · RepoMap：只读、紧凑、可重建。"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
from dwc.llm.repo_map import build                           # noqa: E402


def test_repo_map_lists_key_layout(tmp_path):
    (tmp_path / "README.md").write_text("x\n", encoding="utf-8")
    (tmp_path / "src" / "dwc" / "llm").mkdir(parents=True)
    (tmp_path / "src" / "dwc" / "llm" / "a.py").write_text("x\n",
                                                           encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "b.py").write_text("x\n", encoding="utf-8")
    out = build(str(tmp_path), max_chars=900)
    assert "仓库地图" in out
    assert "README.md" in out
    assert "src/dwc" in out
    assert "tests/" in out
    assert len(out) <= 900


def test_repo_map_skips_venv_and_var(tmp_path):
    (tmp_path / ".venv" / "x").mkdir(parents=True)
    (tmp_path / "var" / "secret").mkdir(parents=True)
    (tmp_path / "src").mkdir()
    out = build(str(tmp_path), max_chars=900)
    assert ".venv" not in out
    assert "var" not in out


def test_repo_map_never_reads_file_contents(tmp_path):
    (tmp_path / "src" / "dwc").mkdir(parents=True)
    (tmp_path / "src" / "dwc" / "secret.py").write_text(
        "API_KEY='SHOULD_NOT_APPEAR'\n", encoding="utf-8")
    out = build(str(tmp_path), max_chars=900)
    assert "SHOULD_NOT_APPEAR" not in out
