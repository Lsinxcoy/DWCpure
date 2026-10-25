# -*- coding: utf-8 -*-
"""R440 · P0-b 输出压缩 + 原文落盘。

为什么：DWC 现在到处是裸切片 `[:4000]` / `[:6000]` —— **截断即丢失**。
模型想看得更细只能重读一遍，而重读本身又是一次工具调用（更贵、更慢）。

改法：超限时把原文写到 `var/tool_raw/<sha1>.txt`，并把路径放进提示里；
未超限时**一个字都不改**，也不落盘（否则每次输出都变成文件）。
"""
from __future__ import annotations

import io
import os

from dwc.llm import tool_raw as T


def test_short_text_unchanged_and_nothing_written(tmp_path, monkeypatch):
    monkeypatch.setenv("DWC_TOOL_RAW_DIR", str(tmp_path))
    s = "short output"
    assert T.clip(s, limit=100) == s
    assert list(tmp_path.iterdir()) == [], "未超限不许落盘"


def test_long_text_keeps_head_and_tail(tmp_path, monkeypatch):
    monkeypatch.setenv("DWC_TOOL_RAW_DIR", str(tmp_path))
    s = "A" * 5000 + "TAILMARK" + "B" * 5000
    out = T.clip(s, limit=2000)
    assert out.startswith("A" * 100), "头部必须保留"
    assert "TAILMARK" in out or out.endswith("B" * 50), "尾部必须保留"
    assert len(out) < len(s), "必须真的变短"


def test_long_text_hint_contains_readable_path(tmp_path, monkeypatch):
    monkeypatch.setenv("DWC_TOOL_RAW_DIR", str(tmp_path))
    s = "X" * 20000
    out = T.clip(s, limit=2000)
    # 提示里必须有路径，且该路径读回 == 原文
    assert str(tmp_path) in out, "提示里必须出现可读路径"
    files = list(tmp_path.glob("*.txt"))
    assert len(files) == 1
    assert io.open(files[0], encoding="utf-8").read() == s


def test_same_content_dedups_path(tmp_path, monkeypatch):
    monkeypatch.setenv("DWC_TOOL_RAW_DIR", str(tmp_path))
    s = "Y" * 20000
    T.clip(s, limit=2000)
    T.clip(s, limit=2000)
    assert len(list(tmp_path.glob("*.txt"))) == 1, "同内容必须去重"


def test_persist_failure_still_truncates_without_raising(tmp_path, monkeypatch):
    """落盘失败 ⇒ 仍截断，但提示必须说清"原文没保存"（不许假装有路径）。"""
    monkeypatch.setenv("DWC_TOOL_RAW_DIR", str(tmp_path))
    # 把目标目录变成一个文件 ⇒ makedirs/写入必然失败
    (tmp_path / "blocker").write_text("x", encoding="utf-8")
    monkeypatch.setenv("DWC_TOOL_RAW_DIR", str(tmp_path / "blocker" / "sub"))
    s = "Z" * 20000
    out = T.clip(s, limit=2000)
    assert len(out) < len(s)
    assert "未保存" in out or "失败" in out


def test_clip_is_idempotent_on_short_input(tmp_path, monkeypatch):
    monkeypatch.setenv("DWC_TOOL_RAW_DIR", str(tmp_path))
    s = "hello"
    assert T.clip(T.clip(s, limit=100), limit=100) == s


def test_raw_dir_honors_dwc_var_dir(tmp_path, monkeypatch):
    monkeypatch.delenv("DWC_TOOL_RAW_DIR", raising=False)
    monkeypatch.setenv("DWC_VAR_DIR", str(tmp_path))
    assert T.raw_dir() == os.path.join(str(tmp_path), T.RAW_REL)
