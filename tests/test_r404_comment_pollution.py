# -*- coding: utf-8 -*-
"""R404 · 注释里不许出现**不存在的 .py 文件名**（搜索污染守卫）。

★★★ 这个坑犯了三次：
  ① R400-d：助手在 `task_exec.py` 注释里写了 `class MemoryKernel:`
     ⇒ 模型 `search_code` 命中注释 ⇒ 答出不存在的 `一个不存在的内核文件名`
  ② R404：助手在注释里写「模型猜 `一个不存在的路由文件名`（不存在）」
     ⇒ 模型把 `一个不存在的路由文件名` 当答案 ⇒ **cl01 + cl08 两单同时答错**
     （cl01 明明已经拿到 `DEFINITIONS (1) → task_exec.py:1145`）
  ③ R425：假文件名藏进**测试的 docstring**（不是 `#` 注释）——
     `search_code` 照样扫到，cl08 连续几轮都答那个不存在的名字。
     **测试自身成了污染源。**

  根因是同一个：**agent 的搜索工具会读注释和文档字符串**，
  里面的"假文件名"和真文件一样会被检索出来，而且往往排在真实定义旁边。

★ 守卫规则：
  · `src/` `scripts/` —— **注释行**里凡出现 `xxx.py`，该文件名必须真实存在；
  · `tests/` —— **docstring** 里凡出现 `xxx.py`，同样必须真实存在。
    （只查 docstring，不查正文：测试正文里的 `mod.py` / `b.py` 是 tmp 目录
     里的 fixture 名，不会冒充"仓库里的文件"，查全文会误伤一片。）
  · 要举例请用中文描述，或在测试里用字符串拼接（`"task_" + "router.py"`）。
"""
from __future__ import annotations

import ast
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIRS = [os.path.join(ROOT, "src"), os.path.join(ROOT, "scripts")]
TEST_DIR = os.path.join(ROOT, "tests")
#: `src/` `scripts/` 只查注释行；`tests/` 查 **docstring** ——
#: R425 现场：假文件名藏在测试的 docstring 里（不是 `#` 注释），
#: agent 的 search_code 照样扫到，cl08 因此一直答那个不存在的名字。
#: 测试正文里的 `mod.py` / `b.py` 是 tmp 目录的 fixture 名，不查（会误伤）。

#: 只关心注释行（`#` 开头）
_COMMENT = re.compile(r"^\s*#")
_PYNAME = re.compile(r"[\w./\\-]+\.py\b")
#: 明显是编造的名字（不会被误当答案）—— 不查，否则测试里的 fixture 名全中
_FAKE_MARK = re.compile(r"(zzz|xxx|no_?such|nonexist|fake|dummy|__test)", re.I)


def _plausible(name: str) -> bool:
    """像"仓库里真有的文件"的名字才查（`a.py`/`mod.py`/`xxx.py` 放过）。"""
    stem = name[:-3]
    return (len(stem) >= 6 and not _FAKE_MARK.search(name)
            and bool(re.fullmatch(r"[a-z0-9_]+", stem)))


def _repo_py_basenames() -> set:
    names = set()
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames
                       if d not in ("__pycache__", ".git", ".cache",
                                    "node_modules", "venv", "var", "docs")]
        for fn in filenames:
            if fn.endswith(".py"):
                names.add(fn)
    return names


def _docstrings(path):
    """返回 [(起始行号, docstring)]，覆盖模块/类/函数。"""
    try:
        src = open(path, encoding="utf-8", errors="replace").read()
        tree = ast.parse(src)
    except (OSError, SyntaxError):
        return []
    out = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef,
                             ast.FunctionDef, ast.AsyncFunctionDef)):
            doc = ast.get_docstring(node)
            if doc:
                out.append((getattr(node, "lineno", 1), doc))
    return out


def _check(rel, lineno, text, real, bad):
    for m in _PYNAME.finditer(text):
        name = os.path.basename(m.group(0).replace("\\", "/"))
        if name not in real and _plausible(name):
            bad.append("%s:%d  %s" % (rel, lineno, m.group(0)))


def test_comments_do_not_mention_nonexistent_py_files():
    """★★★ 注释里提到的 .py 必须真实存在（否则会污染 agent 的搜索）。"""
    real = _repo_py_basenames()
    bad = []
    # ① src/ scripts/ —— 注释行
    for base in SRC_DIRS:
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [d for d in dirnames
                           if d not in ("__pycache__", ".git")]
            for fn in filenames:
                if not fn.endswith(".py"):
                    continue
                path = os.path.join(dirpath, fn)
                rel = os.path.relpath(path, ROOT)
                try:
                    lines = open(path, encoding="utf-8",
                                 errors="replace").read().splitlines()
                except OSError:
                    continue
                for i, ln in enumerate(lines, 1):
                    if _COMMENT.match(ln):
                        _check(rel, i, ln, real, bad)
    # ② tests/ —— docstring（正文里的 fixture 名合法，不查）
    for dirpath, dirnames, filenames in os.walk(TEST_DIR):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for fn in filenames:
            if not fn.endswith(".py"):
                continue
            path = os.path.join(dirpath, fn)
            rel = os.path.relpath(path, ROOT)
            for lineno, doc in _docstrings(path):
                for off, ln in enumerate(doc.splitlines()):
                    _check(rel, lineno + off, ln, real, bad)
    assert not bad, (
        "注释/docstring 里出现了**不存在**的 .py 文件名"
        "（会被 search_code 检索到，导致 agent 答出不存在的文件）：\n  "
        + "\n  ".join(bad[:20]))


#: search_code 会扫这些后缀（含 .md —— 所以 docs 里的历史记录也算污染）
_SEARCHABLE = (".py", ".md", ".json", ".yaml", ".yml", ".jsonl", ".toml")


def test_known_poison_name_absent_everywhere():
    """★★★ R425 回归锁：cl08 那个假文件名不许再出现在任何可被检索的文本里。

    现场：它曾出现在**本目录某个测试的 docstring** 里，agent `search_code`
    命中后把它当成"仓库里真的提到过"，cl08 连续几轮都答那个不存在的名字。
    """
    poison = "task_" + "router.py"          # ★ 拼接，本文件不许有字面量
    hits = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames
                       if d not in (".git", ".cache", "var", "archive",
                                    "node_modules", "__pycache__", ".venv",
                                    "venv", "build", "dist")]
        for fn in filenames:
            if not fn.endswith(_SEARCHABLE):
                continue
            p = os.path.join(dirpath, fn)
            try:
                txt = open(p, encoding="utf-8", errors="replace").read()
            except OSError:
                continue
            if poison in txt:
                hits.append(os.path.relpath(p, ROOT))
    assert not hits, (
        "cl08 的假文件名仍在可检索文本里（会污染 search_code，"
        "让 agent 把它当成真实存在的文件）：\n  " + "\n  ".join(hits[:20]))
