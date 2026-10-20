# -*- coding: utf-8 -*-
"""R386 · qa_mode 必须允许**只读命令**（grep/ls 不是写操作）。

★★★ 现场取证（2026-10-20 R384 原生工具首测，cl01）:
  "execute_user_task 定义在哪个文件？" 被判 qa_mode ⇒ `step_judge` 的
  R301-D 硬约束只许 `read`/`ask`/`web_read`，`run` 一律 R5 拦截。
  而 `search_code` 工具转成 `run(grep ...)` ⇒ **每轮都被 R5 拦截**：

      {"round":1,"phase":"obs","op":"run","target":"R5_blocked",
       "obs":"R5 拦截未执行"}   ×4 轮
      → 最终答「未能确认 execute_user_task 的具体定义文件」

  ⇒ 结果：**code-locate 类 3/10 = 30%**，而 grep 明明能一行定位
    （实测 `grep -rn "def execute_user_task" .` →
     `src/dwc/llm/task_exec.py:914`）。

★ 根因：`qa_mode` 的本意是「只读、不许改状态」，却被实现成
  「不许用命令」。**grep 是只读的**，拦它等于把"查证"这件事本身禁了。

★ 判据（本轮锁的）:
  · qa_mode 下只读命令（grep/ls/find/cat/head/tail/wc/stat/tree）放行
  · qa_mode 下**写/改状态**命令（write/run 里的 rm/mv/cp/git push…）仍拦
  · 非 qa_mode 行为完全不变（回归保护）
"""
from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.llm import step_judge as SJ  # noqa: E402


def _run(cmd):
    return {"op": "run", "cmd": cmd}


# ─────────────────────── ① 只读命令必须放行


@pytest.mark.parametrize("cmd", [
    ["grep", "-rn", "def execute_user_task", "."],
    ["grep", "-rn", "--include=*.py", "class MemoryKernel", "src"],
    ["ls", "-la", "src/dwc"],
    ["find", ".", "-name", "*.py"],
    ["cat", "README.md"],
    ["head", "-50", "README.md"],
    ["tail", "-20", "README.md"],
    ["wc", "-l", "README.md"],
    ["stat", "README.md"],
])
def test_qa_mode_allows_readonly_commands(cmd):
    """★★★ qa 问答里 grep/ls/find 必须放行（它们是只读的）。

    现场：cl01 被 R5 连拦 4 轮，最终答不出 —— 而 grep 一行就能定位。
    """
    verdict, why, rule = SJ.judge_step(_run(cmd), [], qa_mode=True)
    assert rule != "R5", (
        "只读命令 %r 被 R5 拦截（qa 的本意是只读，不是禁用命令）: %s"
        % (cmd[:2], why))


# ─────────────────────── ② 写/改状态命令仍要拦


@pytest.mark.parametrize("cmd", [
    ["rm", "-rf", "x"],
    ["mv", "a", "b"],
    ["cp", "a", "b"],
    ["git", "push"],
    ["git", "commit", "-m", "x"],
    ["pip", "install", "x"],
    ["curl", "http://x"],
    ["python", "-c", "open('a','w').write('x')"],
])
def test_qa_mode_still_blocks_mutating_commands(cmd):
    """★★★ 写/改状态命令在 qa 下仍必须拦（不许把 qa 变成万能）。"""
    verdict, why, rule = SJ.judge_step(_run(cmd), [], qa_mode=True)
    assert rule == "R5", (
        "改状态命令 %r 被放行了 —— qa 变成了万能执行: %s" % (cmd[:2], why))


# ─────────────────────── ③ 回归保护


def test_non_qa_mode_unaffected():
    """★★★ 非 qa 模式下 grep 照常放行（行为不变）。"""
    verdict, why, rule = SJ.judge_step(
        _run(["grep", "-rn", "x", "."]), [], qa_mode=False)
    assert rule != "R5", why


def test_qa_mode_write_op_still_blocked():
    """★★ qa 下 write op 仍拦（只有 read/ask/web_read + 只读 run）。"""
    verdict, why, rule = SJ.judge_step(
        {"op": "write", "path": "var/inbox_work/x.txt", "content": "y"},
        [], qa_mode=True)
    assert rule == "R5", why


def test_readonly_whitelist_exists():
    """★★ 必须有显式的只读命令白名单（不许靠猜）。"""
    assert hasattr(SJ, "READONLY_CMDS"), "缺 READONLY_CMDS 白名单"
    assert "grep" in SJ.READONLY_CMDS
    assert "ls" in SJ.READONLY_CMDS
