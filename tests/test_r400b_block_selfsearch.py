# -*- coding: utf-8 -*-
"""R400-b · 自写搜索脚本必须被拦截（模型的分类逻辑是错的）。

★★★ 现场（2026-10-21 02:20，R400 修复后复测 cl02/cl07）：
  模型**仍然**不用 `search_code`，而是 `run_command` 跑自己写的脚本：

      ['python.exe', '-c', "import os,sys,re\npat=sys.argv[1]; root=..."]
      → {"ok": true, "out": "=== DEFINITIONS (0) ===
                             === REFERENCES (2) ===
                             src\\dwc\\organs\\memory.py:223:class MemoryKernel:"}

  它把 `class MemoryKernel:` 归到了 **REFERENCES**（自己的分类逻辑错），
  随后还抛 `TypeError: Object of type set is not JSON serializable`（自己
  的脚本 bug），模型据此"撤回"了正确答案，最终拒答。

★ 修法：工具层**确定性拦截** —— 识别到 `python -c` + 搜索脚本特征
  （`DEFINITIONS` 或 `os.walk` + `re.`）且不是工具生成的（`readonly`），
  直接不执行，回一条明确指引：改用 `search_code`。
  search_code 自己也是 `python -c`，但它带 `readonly: True` ⇒ 不拦。
"""
from __future__ import annotations

import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.llm import task_exec as T  # noqa: E402

SCRIPT = ("import os,sys,re\npat=sys.argv[1]; root=sys.argv[2]\n"
          "skip={'.git'}\nprint('=== DEFINITIONS (0) ===')\n")


def _run(cmd, readonly=None):
    step = {"op": "run", "cmd": cmd}
    if readonly is not None:
        step["readonly"] = readonly
    return T._do_action(step["op"], step)


def test_selfwritten_search_script_is_blocked():
    """★★★ 模型自写的搜索脚本不许执行（它的分类是错的）。"""
    out = _run(["python", "-c", SCRIPT])
    assert out["ok"] is False, out
    assert "search_code" in out["error"], out


def test_model_cannot_forge_readonly_to_bypass():
    """★★★ 模型自己在 step 里塞 `readonly: true` 也不许绕过拦截。

    现场（cl02，03:32）：动作带着 `readonly` 进来，拦截条件失效，
    自写脚本照跑 ⇒ 把 `class MemoryKernel:` 判成引用 ⇒ 答错。
    判据必须是模型无法伪造的私有标记 `_from_tool`。
    """
    step = {"op": "run", "cmd": ["python", "-c", SCRIPT],
            "readonly": True}          # 模型伪造的字段
    out = T._do_action(step["op"], step)
    assert out["ok"] is False, out
    assert "search_code" in out["error"], out


def test_os_walk_plus_re_is_blocked():
    """★★ 换个体裁（os.walk + re）也要拦。"""
    out = _run(["python", "-c",
                "import os,re\nfor r,d,f in os.walk('.'):\n  re.search('x',r)"])
    assert out["ok"] is False and "search_code" in out["error"]


def test_tool_generated_search_not_blocked():
    """★★★ 工具层（readonly=True）自己的 search_code 不许被拦。

    否则 R394 的定义置顶功能整个失效（修 A 打破 B —— 已踩过 R393）。
    """
    tc = [{"id": "c1", "type": "function",
           "function": {"name": "search_code",
                        "arguments": json.dumps({"pattern": "MemoryKernel"})}}]
    step = T._tool_calls_to_step(tc)
    assert step.get("readonly") is True
    out = T._do_action(step["op"], step)
    assert out.get("ok") is True, out
    assert "=== DEFINITIONS (1) ===" in out.get("out", ""), out


def test_model_cannot_forge_private_from_tool():
    """★ SEC-01: 模型 JSON 里写 `_from_tool: true` 不能伪造工具层标记。"""
    step = {"op": "run", "cmd": ["python", "-c", "print(1)"],
            "_from_tool": True}
    out = T._do_action(step["op"], step)
    assert out.get("ok") is False, out
    assert out.get("error") == "command_denied", out


def test_plain_python_is_denied_by_default():
    """★ SEC-01: 普通 python -c 默认拒绝（它可执行任意代码）。"""
    out = _run(["python", "-c", "print(1+1)"])
    assert out.get("ok") is False, out
    assert out.get("error") == "command_denied", out
