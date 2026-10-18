# -*- coding: utf-8 -*-
"""★ R333 · state inheritance 启动接线 + 版本化（load_archive 真正闭合）。"""
import hashlib
import importlib.util
import json
import os
import sys
import tempfile

ROOT = "E:/Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "src"))


def _load():
    spec = importlib.util.spec_from_file_location(
        "evolver_r333", os.path.join(ROOT, "src", "dwc", "organs", "evolver.py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_r333_bootstrap_empty():
    mod = _load()
    M = mod.Mutator
    # 无文件 ⇒ 0，不报错
    with tempfile.TemporaryDirectory() as d:
        M.LEARNED_PATH = os.path.join(d, "rules.json")
        M.ARCHIVE_PATH = os.path.join(d, "archive.json")
        M.RULES.clear()
        M.ARCHIVE.clear()
        r = M.bootstrap_state()
        assert r == {"learned_loaded": 0, "archive_loaded": 0}


def test_r333_persist_versioned_roundtrip():
    mod = _load()
    M = mod.Mutator
    with tempfile.TemporaryDirectory() as d:
        M.LEARNED_PATH = os.path.join(d, "rules.json")
        M.ARCHIVE_PATH = os.path.join(d, "archive.json")
        M.RULES.clear()
        M.ARCHIVE.clear()
        M.RULES["k"] = {"component": "skill", "target": "x",
                         "patch": "p", "rationale": "r"}
        pr = M.persist_learned()
        assert pr["version"] == "R333"
        assert isinstance(pr["content_hash"], str) and len(pr["content_hash"]) == 12
        # reload
        M.RULES.clear()
        n = M.load_learned()
        assert n == 1
        assert "k" in M.RULES
        # 文件含 _version/_content_hash
        with open(M.LEARNED_PATH, encoding="utf-8") as f:
            data = json.load(f)
        assert data["_version"] == "R333"
        assert data["_content_hash"] == pr["content_hash"]

        M.archive_candidate("a", {"v": 1})
        pa = M.persist_archive()
        assert pa["version"] == "R333"
        M.ARCHIVE.clear()
        na = M.load_archive()
        assert na == 1
        assert M.select_parent("a")["v"] == 1
        with open(M.ARCHIVE_PATH, encoding="utf-8") as f:
            da = json.load(f)
        assert da["_version"] == "R333"
