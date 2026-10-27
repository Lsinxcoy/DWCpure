# -*- coding: utf-8 -*-
"""RepoMap · 只读仓库地图（P1）。

★★★ 定位（G1 定位门）: **DWC-AUTO** —— 任务执行层的只读上下文，不是记忆底座。
★★★ TRUTH_SOURCE（G2）: 无判定面；只列目录/文件名/计数，不读正文、不产评分。

目的：让模型先看到“仓库长什么样”，少做逐层 `ls`。
只读、可重建、不写任何文件；跳过 .git/.venv/node_modules/var 等。
"""
from __future__ import annotations

import os
from typing import Iterable

from dwc.foundation.paths import find_root

_SKIP = {".git", ".venv", ".venv-audit", "node_modules", "__pycache__",
         ".pytest_cache", "var", "archive", "dist", "build", ".mypy_cache",
         ".ruff_cache", "site-packages"}


def _count_files(root: str, limit: int = 20000) -> int:
    n = 0
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if d not in _SKIP and not d.startswith(".")]
        n += len(fns)
        if n >= limit:
            return n
    return n


def _subdirs(root: str) -> list[str]:
    try:
        return sorted(
            d for d in os.listdir(root)
            if os.path.isdir(os.path.join(root, d))
            and d not in _SKIP and not d.startswith("."))
    except OSError:
        return []


def build(root: str | None = None, *, max_chars: int = 900) -> str:
    base = root or find_root()
    lines = ["仓库地图（只读；文件名为代表，不是全文）"]
    tops = _subdirs(base)
    if tops:
        lines.append("顶层目录: " + ", ".join(tops[:14]))
    key = [f for f in ("README.md", "pyproject.toml", "requirements.txt",
                       "setup.py", "Makefile", "AGENTS.md")
           if os.path.isfile(os.path.join(base, f))]
    if key:
        lines.append("关键文件: " + ", ".join(key))
    src = os.path.join(base, "src", "dwc")
    if os.path.isdir(src):
        subs = _subdirs(src)
        lines.append("src/dwc 子目录: " + ", ".join(subs[:14]))
        py = 0
        for dp, dns, fns in os.walk(src):
            dns[:] = [d for d in dns if d not in _SKIP]
            py += sum(1 for f in fns if f.endswith(".py"))
        lines.append("src/dwc: %d 个 .py" % py)
    for d in ("tests", "scripts", "docs", "config"):
        p = os.path.join(base, d)
        if os.path.isdir(p):
            lines.append("%s/: %d 个文件" % (d, _count_files(p, 5000)))
    out = "\n".join(lines)
    return out[:max_chars]
