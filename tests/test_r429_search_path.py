# -*- coding: utf-8 -*-
"""R429 · 检索路径写错时必须**大声报错**，不能静默 0/0。

★★★ 现场（rf05，2026-10-22 12:53，池 A）：
    模型三次 `search_code("MemoryKernel", <path>)` 全部返回
        === DEFINITIONS (0) ===
        === REFERENCES (0) ===
    于是它断定"目标符号在 DWC 仓库源码中未被检索到"，最后只敢说
    "最可能的类名是 MemoryKernel，但这是推测而非取证结论" ⇒
    R389 判 guess-credit-blocked，整单失败。

    而 `class MemoryKernel` 就在 `src/dwc/organs/memory.py:223`。
    复现后确认两个陷阱都会**静默**返回 0/0：

      path='src/dwc/organs/memory.py'   ← 传成**文件**，os.walk 什么都不遍历
      path='organs'                     ← 相对路径不存在，os.walk 也不报错

★ 规则：**0 命中 ≠ 符号不存在。** 路径错必须与符号不存在可区分，
  否则模型会基于"空结果"编出一个看似严谨的否定结论。
"""
from __future__ import annotations

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.llm import task_exec as T  # noqa: E402


def _run(pat, path):
    cmd = T._search_to_python(pat, path)
    r = subprocess.run(cmd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", cwd=ROOT)
    return r.returncode, (r.stdout or "")


def test_file_path_searches_that_file():
    """★★★ 传文件路径时应当搜这个文件，而不是静默 0/0。"""
    rc, out = _run("MemoryKernel", "src/dwc/organs/memory.py")
    assert rc == 0
    assert "class MemoryKernel" in out, out[:200]
    assert "DEFINITIONS (0)" not in out


def test_missing_path_reports_loudly():
    """★★★ 路径不存在必须报 PATH NOT FOUND（而不是 0 命中）。"""
    rc, out = _run("MemoryKernel", "organs")
    assert rc == 3, "路径不存在必须是非零退出，实际 %s" % rc
    assert "PATH NOT FOUND" in out, out[:200]
    assert "符号不存在" in out          # 明确告诉模型这是路径问题


def test_dir_path_still_works():
    """★★ 正常目录路径不许被改坏。"""
    rc, out = _run("MemoryKernel", "src/dwc/organs")
    assert rc == 0
    assert "class MemoryKernel" in out


def test_skip_dirs_respected_on_file_walk():
    """★★ 跳过表对目录遍历仍生效（别把 venv/.git 扫进来）。"""
    script = T._search_to_python("x", ".")[2]
    assert "'venv'" in script and "'.git'" in script
