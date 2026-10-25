# -*- coding: utf-8 -*-
"""R391 · `find` 必须转成 Python 实现（Windows 的 find.exe 语法不同）。

★★★ 现场（2026-10-20 全池 52 单）：
  code-locate 只有 2/10 = 20%，7 单 incomplete 里多数是
  **反复跑同一条命令直到复读熔断**：

      nb_1020_185347_28: 复读熔断 run ['find','src/dwc','-type','f','-name','*.py']
      nb_1020_185728_32: 复读熔断 run ['ls;','find','.','-iname','README*']

  实测该命令：

      _do_action("run", {"cmd": ["find","src/dwc","-type","f","-name","*.py"]})
      → ok=False  rc=2  err="FIND: 参数格式不正确"

★ 根因：Windows 的 `C:\\Windows\\System32\\find.exe` **先于** Git Bash 的
  GNU find 命中（它只支持 `find "字符串" 文件`），GNU 写法一律 rc=2。
  模型不知道，就重试到熔断。

★ 修法：`find` 一律转成等价的 Python os.walk 实现（不依赖 PATH），
  并新增 `find_files` 原生工具；系统提示明确"不要用 find"。
"""
from __future__ import annotations

import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.llm import task_exec as T  # noqa: E402


def _tc(name, args):
    return [{"id": "c1", "type": "function",
             "function": {"name": name, "arguments": json.dumps(args)}}]


# ───────────────────── ① find 转 Python


def test_find_is_rewritten_to_python():
    """★★★ `find PATH -type f -name PAT` 必须变成 python -c 调用。"""
    argv = T._argv_of("find src/dwc -type f -name *.py")
    assert argv[0].lower().endswith(("python.exe", "python", "python3")), argv
    assert "-c" in argv
    assert "src/dwc" in argv and "*.py" in argv


def test_find_iname_sets_ignore_case():
    """★★ `-iname` ⇒ ignore_case=1。"""
    argv = T._argv_of("find . -iname README*")
    assert argv[-1] == "1", argv
    argv2 = T._argv_of("find . -name README*")
    assert argv2[-1] == "0", argv2


def test_find_actually_runs_and_finds_files():
    """★★★ 端到端：转出来的命令必须**真能跑通**并返回文件路径。

    这是修 bug 的核心证据 —— 旧实现在 Windows 上 rc=2。
    """
    step = T._tool_calls_to_step(_tc("find_files", {"pattern": "task_exec.py",
                                                    "path": "src"}))
    assert step and step["op"] == "run", step
    obs = T._do_action(step["op"], step)
    assert obs.get("ok") is True, obs
    out = str(obs.get("out") or "")
    assert "task_exec.py" in out, out[:300]


def test_find_files_ignore_case():
    """★★ find_files(ignore_case=True) 要能大小写不敏感命中。"""
    step = T._tool_calls_to_step(_tc("find_files", {
        "pattern": "TASK_EXEC.PY", "path": "src", "ignore_case": True}))
    obs = T._do_action(step["op"], step)
    assert obs.get("ok") is True, obs
    assert "task_exec.py" in str(obs.get("out") or "")


def test_find_files_is_a_declared_tool():
    """★★ `find_files` 必须出现在 TASK_TOOLS 里（否则模型看不见）。"""
    names = [t["function"]["name"] for t in T.TASK_TOOLS]
    assert "find_files" in names, names
    assert "search_code" in names, names


def test_run_command_with_find_also_rewritten():
    """★★ 模型直接 `run_command("find ...")` 也要被改写（不能只有工具路径修）。"""
    step = T._tool_calls_to_step(_tc("run_command",
                                     {"cmd": "find src -name *.py"}))
    assert step["cmd"][0].lower().endswith(("python.exe", "python", "python3")), step


# ───────────────────── ② 系统提示必须教对策略


def test_system_prompt_tells_search_code_first():
    """★★★ 系统提示必须明确"定位先 search_code，不要逐层 ls"。

    现场：模型反复 `ls -la .` 11 轮零进展 ⇒ 复读熔断。
    """
    import inspect
    src = inspect.getsource(T._execute_user_task_impl)
    assert "search_code" in src, "系统提示没提 search_code"
    assert "不要用 list_dir" in src or "不要用 list_dir / ls" in src, \
        "系统提示没禁止逐层 ls"
    assert "find_files" in src, "系统提示没提 find_files"


def test_system_prompt_warns_about_windows_find():
    """★★ 系统提示必须警告 Windows 的 find.exe（否则模型还会踩）。"""
    import inspect
    src = inspect.getsource(T._execute_user_task_impl)
    assert "find.exe" in src, "没警告 Windows find.exe"
