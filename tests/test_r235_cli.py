# -*- coding: utf-8 -*-
"""R235 · dwc 专属命令：console_scripts 注册 / 路由 / 单实现委托。"""
from __future__ import annotations

import os
import subprocess
import sys

ROOT = r"E:\Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "src"))
from dwc import cli_main as C                                 # noqa: E402


def test_console_scripts_registered():
    """★★★ dwc 命令已注册（venv 内可直接运行 — 头部 agent 同款形态）。"""
    exe = os.path.join(os.path.dirname(sys.executable), "dwc.exe")
    sh = os.path.join(os.path.dirname(sys.executable), "dwc")
    assert os.path.exists(exe) or os.path.exists(sh), \
        "dwc 命令未注册 — pip install -e . 跑了吗"
    r = subprocess.run([exe if os.path.exists(exe) else sh, "help"],
                       capture_output=True, text=True, timeout=60,
                       encoding="utf-8", errors="replace")
    assert r.returncode == 0 and "专属命令" in r.stdout


def test_router_single_implementation(capsys):
    """★★ 路由只做路由: 未知命令报错; status 委托 dwc_cli(→agent_rpc 单实现)。"""
    rc = C.main(["bogus_cmd"])
    assert rc == 1 and "未知子命令" in capsys.readouterr().out
    # 未知之外的路由分发正确（status 走 RPC 单实现 — 真跑一次只读指令）
    rc2 = C.main(["status"])
    assert rc2 == 0


def test_no_arg_defaults_to_chat(monkeypatch):
    """★★ 无参 = chat REPL（opencode/claude 惯例）— 打桩子进程验证路由。"""
    seen = {}

    def _fake_run(name, args):
        seen["name"] = name
        seen["args"] = list(args)
        return 0
    monkeypatch.setattr(C, "_run_script", _fake_run)
    assert C.main([]) == 0
    assert seen["name"] == "dwc_chat.py" and seen["args"] == []
    # ask 单发路由
    C.main(["ask", "去重 排序"])
    assert seen["name"] == "dwc_chat.py" and seen["args"] == ["-c", "去重 排序"]


def test_pyproject_entry_point_declared():
    """★★ 声明即实测: pyproject 的 console_scripts 指向存在的入口。"""
    import importlib
    m = importlib.import_module("dwc.cli_main")
    assert callable(m.main)
    txt = open(os.path.join(ROOT, "pyproject.toml"), encoding="utf-8").read()
    assert 'dwc = "dwc.cli_main:main"' in txt
