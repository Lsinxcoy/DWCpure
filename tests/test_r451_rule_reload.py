# -*- coding: utf-8 -*-
"""R451 · 规则热加载：改了盘上的 rules.json，跑着的进程要能看见。

为什么必须做：`Mutator` 只在 **import 时**加载一次（evolver.py:2970），
落地发生在另一个进程（04:00 cron）⇒ 落了等于没落，直到重启。
这是 RSI 回路的最后一米：改进物回到了磁盘，但没回到运行中的系统。

纪律：
  · 没变 ⇒ 返回 0，不做任何事（每 tick 都调，必须便宜）
  · 变了但没新键 ⇒ 也返回 0（规则只增不改；改内容不算新增）
  · 文件坏 ⇒ 返回 0 不抛（留痕由调用方做），且**不重试**直到下次变更
"""
from __future__ import annotations

import json
import os
import time

import pytest

from dwc.organs.evolver import Mutator

KEY = "E_TEST:r451:probe"


@pytest.fixture(autouse=True)
def _clean():
    _old = Mutator.LEARNED_PATH
    Mutator.RULES.pop(KEY, None)
    yield
    Mutator.RULES.pop(KEY, None)
    Mutator.LEARNED_PATH = _old        # 别把 tmp 路径漏给别的测试文件


def _write(path, learned):
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"learned": learned}, f)


def test_missing_file_is_quiet(tmp_path):
    Mutator.LEARNED_PATH = str(tmp_path / "nope.json")
    assert Mutator.reload_if_changed() == 0


def test_unchanged_file_does_nothing(tmp_path):
    p = str(tmp_path / "r.json")
    _write(p, {KEY: {"patch": {}}})
    Mutator.LEARNED_PATH = p
    assert Mutator.reload_if_changed() == 1
    assert Mutator.reload_if_changed() == 0      # 第二次没变


def test_new_rule_is_picked_up(tmp_path):
    p = str(tmp_path / "r.json")
    _write(p, {})
    Mutator.LEARNED_PATH = p
    Mutator.reload_if_changed()
    time.sleep(0.01)
    _write(p, {KEY: {"patch": {"x": 1}}})
    os.utime(p, (time.time() + 1, time.time() + 1))   # 保证 mtime 变
    assert Mutator.reload_if_changed() == 1
    assert KEY in Mutator.RULES


def test_same_content_new_mtime_adds_nothing(tmp_path):
    """内容没变只是 mtime 变了 ⇒ 0（规则只增不改，别谎报"加载了 N 条"）。"""
    p = str(tmp_path / "r.json")
    _write(p, {KEY: {"patch": {}}})
    Mutator.LEARNED_PATH = p
    assert Mutator.reload_if_changed() == 1
    os.utime(p, (time.time() + 5, time.time() + 5))
    assert Mutator.reload_if_changed() == 0


def test_broken_json_does_not_raise(tmp_path):
    p = str(tmp_path / "r.json")
    with open(p, "w", encoding="utf-8") as f:
        f.write("{not json")
    Mutator.LEARNED_PATH = p
    assert Mutator.reload_if_changed() == 0
