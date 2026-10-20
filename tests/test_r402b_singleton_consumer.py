# -*- coding: utf-8 -*-
"""R402-b · 只有 pid 文件登记的那个进程才许消费收件箱。"""
from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import dwc_agent as A  # noqa: E402


@pytest.fixture
def pidfile(tmp_path, monkeypatch):
    p = tmp_path / "agent.pid"
    monkeypatch.setattr(A, "PID", str(p))
    return p


def test_holder_is_true(pidfile):
    pidfile.write_text(str(os.getpid()), encoding="utf-8")
    assert A._is_singleton_holder() is True


def test_non_holder_is_false(pidfile):
    """★★★ 别的 pid 登记在册 ⇒ 本进程只许待命（不许抢单）。"""
    pidfile.write_text("999999", encoding="utf-8")
    assert A._is_singleton_holder() is False


def test_missing_pidfile_allows(pidfile):
    """★★ pid 文件读不到 ⇒ 不阻止（宁可跑，不要静默停摆）。"""
    assert A._is_singleton_holder() is True
