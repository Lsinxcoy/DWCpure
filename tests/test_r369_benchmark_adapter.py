# -*- coding: utf-8 -*-
"""★ Phase 2.1 · benchmark adapter smoke test（本地仓库，无网络/无 docker）。"""
import os
import subprocess
import sys
import tempfile

ROOT = "E:/Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import dwc_benchmark_adapter as BA

def _git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)

def _make_repo(tmp):
    repo = os.path.join(tmp, "repo")
    os.makedirs(repo)
    _git(repo, "init")
    _git(repo, "config", "user.email", "t@t.com")
    _git(repo, "config", "user.name", "t")
    # buggy source
    with open(os.path.join(repo, "calc.py"), "w", encoding="utf-8") as f:
        f.write("def add(a, b):\n    return a - b  # bug\n")
    with open(os.path.join(repo, "test_calc.py"), "w", encoding="utf-8") as f:
        f.write("from calc import add\n\ndef test_add():\n    assert add(2, 3) == 5\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "base")
    cp = _git(repo, "rev-parse", "HEAD")
    return repo, cp.stdout.strip()

def test_adapter_resolve_with_patch():
    with tempfile.TemporaryDirectory() as tmp:
        repo, commit = _make_repo(tmp)
        inst = BA.BenchInstance(
            instance_id="local-1", repo=repo, base_commit=commit,
            FAIL_TO_PASS=["test_calc.py::test_add"],
        )
        patch = "--- a/calc.py\n+++ b/calc.py\n@@ -1,2 +1,2 @@\n def add(a, b):\n-    return a - b  # bug\n+    return a + b\n"
        r = BA.evaluate_instance(inst, patch, os.path.join(tmp, "work"))
        assert r["resolved"] is True, r
        assert r["FAIL_TO_PASS"]["all_passed"] is True

def test_adapter_unresolved_without_patch():
    with tempfile.TemporaryDirectory() as tmp:
        repo, commit = _make_repo(tmp)
        inst = BA.BenchInstance(
            instance_id="local-2", repo=repo, base_commit=commit,
            FAIL_TO_PASS=["test_calc.py::test_add"],
        )
        r = BA.evaluate_instance(inst, "", os.path.join(tmp, "work"))
        assert r["resolved"] is False
        assert r["FAIL_TO_PASS"]["all_passed"] is False
