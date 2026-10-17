# -*- coding: utf-8 -*-
"""R309-③ · 双副本自检：E:↔.dwc 白名单 md5，异则告警不拦执行。"""
import hashlib
import importlib.util
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = r"E:/Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "src"))


def _load_agent():
    spec = importlib.util.spec_from_file_location(
        "agent_under_test",
        os.path.join(ROOT, "scripts", "dwc_agent.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _w(path, text):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def test_selfcheck_warns_on_stale(tmp_path):
    A = _load_agent()
    a = tmp_path / "a.py"
    b = tmp_path / "b.py"
    _w(str(a), "v1")
    _w(str(b), "v2")
    warn = A.startup_selfcheck([(str(a), str(b))])
    assert "异" in warn and "b.py" in warn, warn


def test_selfcheck_ok_when_same(tmp_path):
    A = _load_agent()
    a = tmp_path / "a.py"
    b = tmp_path / "b.py"
    _w(str(a), "same")
    _w(str(b), "same")
    assert A.startup_selfcheck([(str(a), str(b))]) == ""


def test_selfcheck_missing_is_warn_not_raise(tmp_path):
    A = _load_agent()
    warn = A.startup_selfcheck([(str(tmp_path / "nope.py"),
                                 str(tmp_path / "nope2.py"))])
    assert "缺" in warn, warn
