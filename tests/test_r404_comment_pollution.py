# -*- coding: utf-8 -*-
"""R404 · 注释里不许出现**不存在的 .py 文件名**（搜索污染守卫）。

★★★ 这个坑犯了两次：
  ① R400-d：助手在 `task_exec.py` 注释里写了 `class MemoryKernel:`
     ⇒ 模型 `search_code` 命中注释 ⇒ 答出不存在的 `一个不存在的内核文件名`
  ② R404：助手在注释里写「模型猜 `一个不存在的路由文件名`（不存在）」
     ⇒ 模型把 `一个不存在的路由文件名` 当答案 ⇒ **cl01 + cl08 两单同时答错**
     （cl01 明明已经拿到 `DEFINITIONS (1) → task_exec.py:1145`）

  根因是同一个：**agent 的搜索工具会读注释**，注释里的"假文件名"
  和真文件一样会被检索出来，而且往往排在真实定义旁边。

★ 守卫规则：`src/` 与 `scripts/` 的**注释行**里，凡出现 `xxx.py`，
  该文件名必须在仓库里真实存在。要举例请用中文描述或 `xxx_*.py`。
"""
from __future__ import annotations

import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCAN_DIRS = [os.path.join(ROOT, "src"), os.path.join(ROOT, "scripts")]

#: 只关心注释行（`#` 开头）；文档字符串不在此列（正文说明难免提到文件名）
_COMMENT = re.compile(r"^\s*#")
_PYNAME = re.compile(r"[\w./\\-]+\.py\b")


def _repo_py_basenames() -> set:
    names = set()
    for base in SCAN_DIRS:
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [d for d in dirnames
                           if d not in ("__pycache__", ".git")]
            for fn in filenames:
                if fn.endswith(".py"):
                    names.add(fn)
    return names


def test_comments_do_not_mention_nonexistent_py_files():
    """★★★ 注释里提到的 .py 必须真实存在（否则会污染 agent 的搜索）。"""
    real = _repo_py_basenames()
    bad = []
    for base in SCAN_DIRS:
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [d for d in dirnames
                           if d not in ("__pycache__", ".git")]
            for fn in filenames:
                if not fn.endswith(".py"):
                    continue
                path = os.path.join(dirpath, fn)
                try:
                    lines = open(path, encoding="utf-8",
                                 errors="replace").read().splitlines()
                except OSError:
                    continue
                for i, ln in enumerate(lines, 1):
                    if not _COMMENT.match(ln):
                        continue
                    for m in _PYNAME.finditer(ln):
                        name = os.path.basename(
                            m.group(0).replace("\\", "/"))
                        if name not in real:
                            bad.append("%s:%d  %s"
                                       % (os.path.relpath(path, ROOT), i,
                                          m.group(0)))
    assert not bad, (
        "注释里出现了**不存在**的 .py 文件名（会被 search_code 检索到，"
        "导致 agent 答出不存在的文件）：\n  " + "\n  ".join(bad[:20]))
