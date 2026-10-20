# -*- coding: utf-8 -*-
"""R393 · 工具层生成的只读命令必须自带 `readonly` 标记（否则被 R5 全拦）。

★★★ 现场（2026-10-20 19:57 全池，R391 上线后）：
  code-locate 两单全灭，`actions_log` 清一色：

      {"op": "run", "target": "R5_blocked", "ok": false}  × 3~4

  agent 其实调了工具，但**每个动作都被 R5 拦掉**，最后只能瞎猜：

      cl01 答 "定义在 src/dwc/harness/task_router.py"（错，真在 task_exec.py）
      cl02 答 "src/dwc/foundation/memory_kernel.py"（对，但靠猜）

★ 根因（R391 的回归）：`find` 转成 `python -c <os.walk 脚本>` 后，
  首 token 是 `python.exe` —— **不在 `READONLY_CMDS` 白名单**
  ⇒ `_is_readonly_run()` 判 False ⇒ qa_mode 的 R5 硬约束直接拦。

★ 修法：工具层（list_dir / search_code / find_files）构造的 step
  自带 `readonly: True` —— 它们**不是模型手写的 shell 串**，
  安全性由工具层保证（参数是结构化字段，不是拼字符串）。
  `run_command` **不带**该标记（模型手写命令仍走白名单判定）。
"""
from __future__ import annotations

import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.llm import task_exec as T  # noqa: E402
from dwc.llm import step_judge as SJ  # noqa: E402


def _tc(name, args):
    return [{"id": "c1", "type": "function",
             "function": {"name": name, "arguments": json.dumps(args)}}]


# ───────────────────── ① 工具层 step 必须带 readonly


@pytest.mark.parametrize("name,args", [
    ("list_dir", {"path": "src"}),
    ("search_code", {"pattern": "def execute_user_task"}),
    ("find_files", {"pattern": "*.py", "path": "src"}),
])
def test_tool_steps_marked_readonly(name, args):
    """★★★ 三个只读工具生成的 step 必须带 `readonly: True`。"""
    step = T._tool_calls_to_step(_tc(name, args))
    assert step is not None, name
    assert step.get("readonly") is True, (name, step)


def test_run_command_is_not_marked_readonly():
    """★★★ `run_command` 不许自带 readonly（模型手写命令要走白名单判定）。

    否则模型可以借 run_command 绕过 qa_mode 的写保护。
    """
    step = T._tool_calls_to_step(_tc("run_command", {"cmd": "rm -rf x"}))
    assert not step.get("readonly"), step


# ───────────────────── ② qa_mode 下不许再拦


@pytest.mark.parametrize("name,args", [
    ("list_dir", {"path": "src"}),
    ("search_code", {"pattern": "MemoryKernel"}),
    ("find_files", {"pattern": "*.py", "path": "src"}),
])
def test_readonly_tools_pass_qa_mode(name, args):
    """★★★ qa_mode 下这三个工具必须放行（现场全被 R5 拦）。"""
    step = T._tool_calls_to_step(_tc(name, args))
    verdict, why, rule = SJ.judge_step(step, [], qa_mode=True)
    assert rule != "R5", "%s 在 qa_mode 下被 R5 拦了: %s" % (name, why)


def test_run_command_still_blocked_in_qa_mode():
    """★★ 模型手写的改状态命令在 qa 下仍拦（不许借 run_command 绕过）。"""
    step = T._tool_calls_to_step(_tc("run_command", {"cmd": "rm -rf var"}))
    verdict, why, rule = SJ.judge_step(step, [], qa_mode=True)
    assert rule == "R5", why


def test_find_files_end_to_end_in_qa_mode():
    """★★★ 端到端：qa_mode 下 find_files 必须真执行并返回结果。

    旧链路：转成 python -c ⇒ head=python.exe ⇒ 不在白名单 ⇒ R5_blocked。
    """
    step = T._tool_calls_to_step(_tc("find_files",
                                     {"pattern": "task_exec.py", "path": "src"}))
    verdict, why, rule = SJ.judge_step(step, [], qa_mode=True)
    assert rule != "R5", why
    obs = T._do_action(step["op"], step)
    assert obs.get("ok") is True, obs
    assert "task_exec.py" in str(obs.get("out") or "")
