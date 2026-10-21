# -*- coding: utf-8 -*-
"""R417 · 有取证也编文件名 ⇒ 打回。

★★★ 现场（cl08，R415 全池）：
    题：「DWC 的 CLI 入口路由文件叫什么？只答文件名。」
    动作：run python → find_files → read ×2（**有取证**）
    答案：`task_router.py（完整路径 src/dwc/harness/task_router.py …）`
    真相：该文件不存在；真实入口是 `src/dwc/cli_main.py`。

    R400-f 拦的是"零取证的文件名断言"，这一单**有取证**，所以漏了。
    文件名是否存在是**可判定事实**，不该靠模型自觉。

★ 设计边界（三条，防止误伤）：
  ① 只在"任务在问文件名"时启用 —— 写文件类任务会合法提到尚不存在的文件名；
  ② 答案里只要有一个文件真实存在就不拦（"提到多个文件"的正常答案）；
  ③ 只查基名（`src/dwc/cli_main.py` → `cli_main.py`），不要求路径完全一致。
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.llm.task_exec import _phantom_file_gate, _repo_files  # noqa: E402

#: 拼接构造，避免这个字符串本身被 search_code 搜到（自证预言）
FAKE = "task_" + "router.py"


def test_fake_filename_is_blocked():
    """★★★ 新行为：问文件名 + 答案的文件名全不存在 ⇒ 打回（cl08 复刻）。"""
    why = _phantom_file_gate(
        "DWC 的 CLI 入口路由文件叫什么？只答文件名。",
        "%s（完整路径 src/dwc/harness/%s，其中定义了入口路由函数）。"
        % (FAKE, FAKE))
    assert why, "编造的文件名没有被拦"
    assert FAKE in why
    assert "find_files" in why or "search_code" in why


def test_real_filename_passes():
    """★★ 反面：答真实存在的文件 ⇒ 放行（`cli_main.py` 在仓库里）。"""
    why = _phantom_file_gate("DWC 的 CLI 入口路由文件叫什么？只答文件名。",
                             "cli_main.py（src/dwc/cli_main.py）")
    assert why is None, why


def test_mixed_real_and_fake_passes():
    """★★ 边界：答案里同时有真有假 ⇒ 不拦（避免误伤多文件答案）。"""
    why = _phantom_file_gate("哪个文件是入口？",
                             "入口是 cli_main.py，不是 %s" % FAKE)
    assert why is None, why


def test_write_task_not_blocked():
    """★★ 边界：写文件类任务会合法提到尚不存在的文件名 ⇒ 不拦。"""
    why = _phantom_file_gate("在 var/inbox_work 写入 list.md，内容是三点",
                             "已写入 list.md")
    assert why is None, why


def test_non_file_question_not_blocked():
    """★★ 边界：不问文件名 ⇒ 不启用（普通回答里提到 .py 也不拦）。"""
    why = _phantom_file_gate("DWC 有几个器官？", "大约 7 个，见 x.py")
    assert why is None, why


def test_repo_files_index_is_real():
    """★ 索引自检：必须能查到真实文件，且查不到这个拼接出来的假名。"""
    files = _repo_files()
    assert "cli_main.py" in files, "索引里没有 cli_main.py —— 索引建错了"
    assert FAKE not in files, "假名不该在索引里"
