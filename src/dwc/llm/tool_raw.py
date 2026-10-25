# -*- coding: utf-8 -*-
"""R440 · P0-b · 输出压缩 + 原文落盘。

★★★ 定位（G1）: **DWC-AUTO** —— 自我强化的观测层：截断可以，但**不许丢信息**。

为什么要有这个模块
------------------
DWC 现在到处是裸切片（`[:4000]` / `[:6000]`）—— **截断即丢失**。
模型想看更细只能重读一遍，而重读又是一次工具调用（更贵、更慢）。

三条纪律
--------
1. **未超限 ⇒ 一个字都不改，也不落盘**（否则每次输出都变成文件）。
2. **超限 ⇒ 头 + 尾 + 可读路径**；同内容按 sha1 去重。
3. **落盘失败 ⇒ 仍截断，但提示必须说清"原文没保存"** ——
   不许假装有路径（那是幻影声明）。
"""
from __future__ import annotations

import hashlib
import io
import os
import sys
from typing import Optional

#: 原文目录名（落在 var/ 下）
RAW_REL = "tool_raw"


def _root() -> str:
    """仓库根（src/dwc/llm/tool_raw.py → 上四层）。"""
    return os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))))


def raw_dir() -> str:
    """原文目录。测试靠 `DWC_TOOL_RAW_DIR` 或 `DWC_VAR_DIR` 指到 tmp。"""
    p = os.environ.get("DWC_TOOL_RAW_DIR", "").strip()
    if p:
        return p
    var = os.environ.get("DWC_VAR_DIR", "").strip()
    if var:
        return os.path.join(var, RAW_REL)
    return os.path.join(_root(), "var", RAW_REL)


def persist(text: str) -> Optional[str]:
    """把原文写盘，返回绝对路径；失败返回 None（stderr 留痕，不抛）。

    原子写：先写 `.tmp` 再 `os.replace`，避免半截文件被读到。
    去重：同名（sha1 前 16 位）已存在 ⇒ 直接复用，不重复写。
    """
    body = str(text or "")
    digest = hashlib.sha1(body.encode("utf-8", "replace")).hexdigest()[:16]
    d = raw_dir()
    path = os.path.join(d, digest + ".txt")
    if os.path.isfile(path):
        return path
    try:
        os.makedirs(d, exist_ok=True)
        tmp = path + ".tmp"
        with io.open(tmp, "w", encoding="utf-8", newline="\n") as f:
            f.write(body)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
        return path
    except OSError as e:      # noqa: BLE001 — 旁路失败只留痕
        sys.stderr.write("原文落盘失败: %r\n" % (e,))
        return None


def clip(text: object, *, limit: int, head_ratio: float = 0.6) -> str:
    """按 `limit` 截断；超限时保留头尾并把原文路径写进提示。"""
    t = str(text or "")
    if limit <= 0 or len(t) <= limit:
        return t
    head_n = max(1, int(limit * max(0.0, min(1.0, head_ratio))))
    tail_n = max(1, limit - head_n)
    dropped = len(t) - head_n - tail_n
    path = persist(t)
    if path:
        hint = ("\n…[truncated %d chars; full: %s. "
                "Read only a targeted range if more detail is needed.]\n"
                % (dropped, path))
    else:
        hint = ("\n…[truncated %d chars; 原文保存失败（本行不提供路径）]\n"
                % (dropped,))
    return t[:head_n] + hint + t[-tail_n:]
