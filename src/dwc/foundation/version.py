"""dw_version —— TS2 的版本真源（git 真实状态, 不是自报字符串）。

★★ 为什么需要它（R71 实测）:
  run_term 的 T3 判据锁的是 dw_version before==after, 但全库 grep
  `dw_version =` **0 个赋值源**（两头都是默认 ""）⇒ T3 实际锁的是
  **两个空串相等 = 假锁**。
  ⇒ 本模块给一个**有出处**的版本: 仓库 .git 的 HEAD sha。
  ⇒ 仓库在 ⇒ 真 sha; 不在 ⇒ "nogit"（★ 明确的无版本标记 ——
    TS2「换版本即换坐标系」在 nogit 下退化为「都不可比」, 诚实可见）。

★ 纯文件读, 无 subprocess（core 是库, 不该为版本拉 git 进程）。
★ 定位声明 · **DWC-AUTO**（判据 G1 定位门 —— 服务审计与版本坐标系）。
"""
from __future__ import annotations

import os

#: 无 git 时的显式标记（不装 sha, 不编版本号）
NO_GIT = "nogit"


def _find_root(start: str | None = None) -> str | None:
    """从本文件所在目录逐级向上找含 .git 的目录。"""
    d = os.path.dirname(os.path.abspath(__file__)) if start is None else start
    while True:
        if os.path.isdir(os.path.join(d, ".git")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent


def dw_version(repo_root: str | None = None) -> str:
    """当前仓库的版本 = HEAD commit sha（40 位或短 sha; 无 git ⇒ nogit）。"""
    root = repo_root if repo_root is not None else _find_root()
    if root is None:
        return NO_GIT
    head = os.path.join(root, ".git", "HEAD")
    if not os.path.exists(head):
        return NO_GIT
    txt = open(head, encoding="utf-8").read().strip()
    if not txt.startswith("ref:"):
        # detached HEAD: HEAD 直接就是 sha
        return txt[:40] or NO_GIT
    ref = txt.split(":", 1)[1].strip()
    # loose ref: .git/refs/heads/master
    p = os.path.join(root, ".git", *ref.split("/"))
    if os.path.exists(p):
        sha = open(p, encoding="utf-8").read().strip()
        if sha:
            return sha[:40]
    # packed-refs: `<sha> <ref>` 逐行找
    pr = os.path.join(root, ".git", "packed-refs")
    if os.path.exists(pr):
        for line in open(pr, encoding="utf-8"):
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("^"):
                continue
            parts = line.split(" ", 1)
            if len(parts) == 2 and parts[1].strip() == ref:
                return parts[0][:40]
    return "unknown-ref"
