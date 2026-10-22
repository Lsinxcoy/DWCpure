# -*- coding: utf-8 -*-
"""R430 · 检索词过泛时给出"更长标识符"候选（rf08）。

★★★ 现场（rf08，池 B + 单独复跑 0/2）：
    问："DWC 记忆修订的新节点用哪个保留键链回旧节点？只答键名。"
    模型搜 `prev` ⇒ 77 条引用、0 条定义 ⇒ 它把 `prev` 当答案。
    正确答案是 `_rev_prev`（`previous_error` 之类的泛命中把它淹了）。

★ 关键区分：**0 条定义 + 大量引用** = 这个词只是某个更长标识符的一部分。
  工具应该把"包含它的标识符"按出现次数列出来 —— 这些候选全部来自
  **模型自己搜到的行**，所以不是"给答案"，判据/闸/评分一律不变。
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


def test_broad_term_lists_longer_identifiers():
    """★★★ 搜 `prev`（0 定义、大量引用）必须列出 `_rev_prev` 这类候选。"""
    rc, out = _run("prev", "src")
    assert rc == 0
    assert "DEFINITIONS (0)" in out
    assert "候选更长标识符" in out, out[-400:]
    assert "_rev_prev" in out, "正确键必须出现在候选里：%s" % out[-400:]
    assert "很可能只是" in out


def test_exact_symbol_does_not_get_candidate_noise():
    """★★ 有定义时不该再刷候选块（那是噪声，会稀释真正的定义）。"""
    rc, out = _run("MemoryKernel", "src")
    assert rc == 0
    assert "class MemoryKernel" in out
    assert "候选更长标识符" not in out


def test_candidates_are_sorted_by_count():
    """★★ 候选按出现次数降序 —— 模型先看到最相关的。"""
    rc, out = _run("prev", "src")
    lines = [l for l in out.splitlines() if l.strip().endswith("x%d") or "  x" in l]
    counts = []
    for l in lines:
        tail = l.rsplit("x", 1)[-1]
        if tail.isdigit():
            counts.append(int(tail))
    assert counts == sorted(counts, reverse=True), counts
    assert len(counts) <= 8
