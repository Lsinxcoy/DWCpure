"""SEC-04 · path guard tests."""
from __future__ import annotations

import os

import pytest

from dwc.llm import task_exec as TE


def _roots(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    work = repo / "var" / "inbox_work"
    work.mkdir(parents=True)
    monkeypatch.setattr(TE, "ROOT", str(repo))
    monkeypatch.setattr(TE, "WORK", str(work))
    return repo, work


def test_relative_read_inside(tmp_path, monkeypatch):
    repo, _ = _roots(tmp_path, monkeypatch)
    (repo / "a.txt").write_text("x", encoding="utf-8")
    assert TE._guard_path("a.txt", write=False) == str(repo / "a.txt")


def test_same_prefix_outside_denied(tmp_path, monkeypatch):
    repo, _ = _roots(tmp_path, monkeypatch)
    (tmp_path / "repo_evil").mkdir()
    (tmp_path / "repo_evil" / "x").write_text("x", encoding="utf-8")
    with pytest.raises(TE.TaskExecError):
        TE._guard_path("../repo_evil/x", write=False)


def test_write_outside_work_denied(tmp_path, monkeypatch):
    repo, _ = _roots(tmp_path, monkeypatch)
    with pytest.raises(TE.TaskExecError):
        TE._guard_path("../outside.txt", write=True)


def test_symlink_denied(tmp_path, monkeypatch):
    repo, _ = _roots(tmp_path, monkeypatch)
    target = tmp_path / "outside.txt"
    target.write_text("secret", encoding="utf-8")
    link = repo / "link.txt"
    try:
        os.symlink(target, link)
    except (OSError, NotImplementedError):
        pytest.skip("Windows 无符号链接权限")
    with pytest.raises(TE.TaskExecError):
        TE._guard_path("link.txt", write=False)
