# -*- coding: utf-8 -*-
"""★ N3 · C1 parent 选择器 + archive 落盘（R324 后半截）。

锁：
1. select_parent 默认 latest（最后追加版本）。
2. select_parent(strategy="first") 最早版本。
3. 空 archive ⇒ None（诚实缺席）。
4. persist_archive → load_archive 跨进程 roundtrip。
5. promote_archived：无 parent ⇒ no_parent；有 ⇒ landed + RULES 入库 + persist。
6. promote_archived 幂等：第二次 ⇒ already_landed。
"""
import importlib.util
import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))


def _load():
    spec = importlib.util.spec_from_file_location(
        "evolver_n3", os.path.join(ROOT, "src", "dwc", "organs", "evolver.py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_n3_select_latest_and_first():
    mod = _load()
    M = mod.Mutator
    M.ARCHIVE.clear()
    M.archive_candidate("k", {"v": 1})
    M.archive_candidate("k", {"v": 2})
    M.archive_candidate("k", {"v": 3})
    assert M.select_parent("k")["v"] == 3
    assert M.select_parent("k", strategy="first")["v"] == 1


def test_n3_select_empty():
    mod = _load()
    M = mod.Mutator
    M.ARCHIVE.clear()
    assert M.select_parent("nope") is None


def test_n3_persist_roundtrip(tmp_path):
    mod = _load()
    M = mod.Mutator
    M.ARCHIVE.clear()
    M.archive_candidate("k", {"v": 7})
    orig = M.ARCHIVE_PATH
    M.ARCHIVE_PATH = str(tmp_path / "archive.json")
    try:
        M.persist_archive()
        M.ARCHIVE.clear()
        assert M.select_parent("k") is None
        n = M.load_archive()
        assert n == 1
        assert M.select_parent("k")["v"] == 7
    finally:
        M.ARCHIVE_PATH = orig
        M.ARCHIVE.clear()


def test_n3_promote_no_parent():
    mod = _load()
    M = mod.Mutator
    M.ARCHIVE.clear()
    M.RULES.pop("k", None)
    assert M.promote_archived("k")["outcome"] == "no_parent"


def test_n3_promote_lands_and_idempotent(tmp_path):
    mod = _load()
    M = mod.Mutator
    M.ARCHIVE.clear()
    M.RULES.pop("k", None)
    M.archive_candidate("k", {"component": "skill", "target": "x",
                             "patch": "p", "rationale": "r"})
    orig_learned = M.LEARNED_PATH
    orig_archive = M.ARCHIVE_PATH
    M.LEARNED_PATH = str(tmp_path / "rules.json")
    M.ARCHIVE_PATH = str(tmp_path / "archive.json")
    try:
        r1 = M.promote_archived("k")
        assert r1["outcome"] == "landed"
        assert "k" in M.RULES
        r2 = M.promote_archived("k")
        assert r2["outcome"] == "already_landed"
    finally:
        M.LEARNED_PATH = orig_learned
        M.ARCHIVE_PATH = orig_archive
        M.RULES.pop("k", None)
        M.ARCHIVE.clear()
