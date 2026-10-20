# -*- coding: utf-8 -*-
"""R395 · 一条半行不该让整个系统起不来（生产 store 已实际损坏过）。

★★★ 现场（2026-10-20 21:12，全量 pytest）：
    59 failed, 37 errors —— 全部同一个异常：

        json.decoder.JSONDecodeError: Extra data: line 1 column 2 (char 1)
        src/dwc/organs/judge.py:668  TaskScoreStore.__init__
        → 每次构造 Loop() 都崩

  根因：`config/anchors/task_scores.jsonl` 第 46 行是**半行**：

        …"recorded_at": "2026-10-20T21:1        ← 第 46 行
        7:51"}                                  ← 第 47 行（尾巴）

  一条记录被写成两行（`io.open(path,"a")` 是带缓冲的文本流，
  `f.write` 不保证一次落盘；多进程/中断就会写半行）。

★ 两条纪律：
  ① **读**：坏行跳过 + **计数 + 大声报**（不许静默吞，也不许整库崩）
  ② **写**：单次 `os.write` 到 O_APPEND fd（小写入原子追加，不再写半行）
"""
from __future__ import annotations

import io
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.organs import judge as J  # noqa: E402


def _valid_line(task_id="t1", score=1.0):
    return json.dumps({
        "task_id": task_id, "group_id": "g", "round_index": 1,
        "split": "dev", "wm_version": "", "dw_version": "abc",
        "score": score, "n_assertions": 1, "rung": 1,
        "evidence_ref": "e#1", "recorded_at": "2026-10-20T21:00:00"})


# ───────────────────── ① 读：坏行不许让整库崩


def test_corrupt_line_does_not_crash_load(tmp_path):
    """★★★ 核心：半行 + 好行混排 ⇒ 能装载好行，不抛异常。"""
    p = tmp_path / "scores.jsonl"
    p.write_text(_valid_line("a") + "\n" + '7:51"}' + "\n"
                 + _valid_line("b") + "\n", encoding="utf-8")
    store = J.TaskScoreStore(path=str(p), evidence_path=str(tmp_path / "e.jsonl"))
    assert [x.task_id for x in store._points] == ["a", "b"]


def test_corrupt_line_is_counted_not_silent(tmp_path, capsys):
    """★★★ 坏行必须**计数并打警告**（不许静默吞 —— G7 静默门）。"""
    p = tmp_path / "scores.jsonl"
    p.write_text(_valid_line("a") + "\n" + '{"broken": ' + "\n",
                 encoding="utf-8")
    store = J.TaskScoreStore(path=str(p), evidence_path=str(tmp_path / "e.jsonl"))
    assert getattr(store, "n_corrupt", 0) == 1, store.n_corrupt
    err = capsys.readouterr().err
    assert "坏行" in err, err


def test_evidence_corrupt_line_tolerated(tmp_path):
    """★★ evidence.jsonl 同样要容忍坏行。"""
    ev = tmp_path / "e.jsonl"
    ev.write_text(json.dumps({"_ref": "e#1", "ok": True}) + "\n"
                  + '{"_ref": "e#2"' + "\n", encoding="utf-8")
    sp = tmp_path / "s.jsonl"
    sp.write_text("", encoding="utf-8")
    store = J.TaskScoreStore(path=str(sp), evidence_path=str(ev))
    assert "e#1" in store._evidence
    assert getattr(store, "n_corrupt", 0) == 1


# ───────────────────── ② 写：必须原子（不产生半行）


def test_append_line_is_single_write():
    """★★★ `_append_line` 必须存在且用 os.write（不是文本流缓冲）。"""
    import inspect
    src = inspect.getsource(J._append_line)
    assert "os.write" in src, src
    # ★ 只查"调用"不查文档字符串里的提及
    assert "with io.open" not in src, "仍在用带缓冲的文本流（会写半行）"


def test_append_line_roundtrip(tmp_path):
    """★★ 追加的内容必须可被逐行解析（含中文）。"""
    p = str(tmp_path / "x.jsonl")
    for i in range(5):
        J._append_line(p, json.dumps({"i": i, "msg": "中文内容"}, ensure_ascii=False))
    lines = io.open(p, encoding="utf-8").read().splitlines()
    assert len(lines) == 5
    for i, l in enumerate(lines):
        assert json.loads(l)["i"] == i


def test_record_uses_atomic_append(tmp_path):
    """★★ 生产写入路径（record/_store_evidence）不许再用 io.open(...,"a")。"""
    import inspect
    src = inspect.getsource(J.TaskScoreStore.record)
    assert "_append_line" in src, src
    src2 = inspect.getsource(J.TaskScoreStore._store_evidence)
    assert "_append_line" in src2, src2


# ───────────────────── ③ 生产文件已修复


def test_production_store_is_valid_now():
    """★★★ 生产 store 必须每行都是合法 JSON（本轮已实际损坏过）。"""
    p = os.path.join(ROOT, "config", "anchors", "task_scores.jsonl")
    if not os.path.exists(p):
        pytest.skip("生产 store 不存在")
    bad = []
    for i, l in enumerate(io.open(p, encoding="utf-8"), 1):
        if not l.strip():
            continue
        try:
            json.loads(l)
        except Exception:                              # noqa: BLE001
            bad.append(i)
    assert not bad, "生产 store 仍有坏行: %r" % bad[:5]
