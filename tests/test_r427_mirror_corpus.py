# -*- coding: utf-8 -*-
"""R427 · 外部仓库镜像不是本仓库的语料（`docs/repos/` 必须跳过）。

★★★ 现场（cl08，2026-10-22 11:48 复跑）：
    R425 清掉了测试 docstring 里的假文件名，R426 修好了 `search_code` 被丢，
    模型**这次真的搜了 4 轮**，仍然答那个不存在的路由文件名。

    根因：`docs/repos/_all.json` 是**外部仓库镜像**（3.4MB README 转储），
    里面写着「M11 task_router」（那是 SYNTHEX 的组件名，不是本仓库的文件）。
    `search_code` 把 `docs/` 当语料索引 ⇒ 模型搜到这条 ⇒ 答出
    `src/dwc/harness/<那个名字>.py`。

★ 规则：**外部仓库的文本不能当本仓库的证据。**
  `docs/repos/` 整目录从检索语料里剔除（含 R417 的文件名存在性判断、
  R420 的裸名解析 —— 否则镜像里的文件名会被当成"仓库里真有"）。
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.llm import task_exec as T  # noqa: E402


def test_mirror_dir_is_in_skip_list():
    """★★★ `repos` 必须在检索跳过表里。"""
    assert "repos" in T._REPO_SKIP_DIRS


def test_repo_text_excludes_mirror_dump():
    """★★★ 拼出来的仓库语料里不许有镜像转储的内容。

    `AGENT_HIVE_ACCESS_PLAN` 只出现在 `docs/repos/_all.json`（外部仓库 README），
    本仓库源码里没有 —— 它出现在语料里就说明镜像被索引了。
    """
    T._REPO_TEXT_CACHE = None          # 强制重建（不吃旧缓存）
    text = T._repo_text()
    assert "AGENT_HIVE_ACCESS_PLAN" not in text
    assert "MOTHERNODE_REPORT_MINING_MAP" not in text


def test_mirror_files_not_in_repo_file_list():
    """★★ R417 的"文件名存在性"判断也不许把镜像里的文件当本仓库文件。"""
    files = T._repo_files()
    bad = [f for f in files if "docs/repos" in f.replace("\\", "/")]
    assert not bad, "镜像文件被当成仓库文件：%s" % bad[:5]


def test_search_script_uses_shared_skip_list():
    """★★★ 生成的搜索/查找脚本必须用**同一份** skip 表。

    现场：`_REPO_SKIP_DIRS` 改了，但 `_SEARCH_PY` / `_FIND_PY` 里
    各抄了一份字面量 —— 改常量对实际检索毫无影响（两处漂移）。
    """
    for cmd in (T._search_to_python("x", "."),
                T._find_to_python(["find", ".", "-name", "x.py"])):
        script = cmd[2]
        assert "'repos'" in script, "脚本里没有共享 skip 表：%s" % script[:120]
