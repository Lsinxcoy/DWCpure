"""P2 · atomic write tests."""
from __future__ import annotations

import json
import os

import pytest

from dwc.foundation.atomic_io import write_json_atomic, write_text_atomic


def test_write_text_atomic_replaces(tmp_path):
    p = tmp_path / "a.txt"
    write_text_atomic(str(p), "one")
    write_text_atomic(str(p), "two")
    assert p.read_text(encoding="utf-8") == "two"


def test_write_json_atomic(tmp_path):
    p = tmp_path / "a.json"
    write_json_atomic(str(p), {"a": 1}, indent=1)
    assert json.loads(p.read_text(encoding="utf-8")) == {"a": 1}


def test_failure_keeps_original_and_cleans_tmp(tmp_path, monkeypatch):
    p = tmp_path / "a.txt"
    write_text_atomic(str(p), "old")

    def boom(*a, **k):
        raise OSError("replace failed")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(OSError):
        write_text_atomic(str(p), "new")
    assert p.read_text(encoding="utf-8") == "old"
    assert not [x for x in os.listdir(tmp_path) if x.startswith(".dwc-tmp-")]
