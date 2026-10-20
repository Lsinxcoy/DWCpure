# -*- coding: utf-8 -*-
"""R401 · 收件箱状态必须原子写（非原子写 ⇒ 整个队列重跑）。

★★★ 现场（2026-10-21 03:05）：
  `T_r400d1_..._cl02` 一分钟内被跑了 **13 次**，报告被后一次覆盖
  （我先看到 ✓，两分钟后再看同一文件变成 ✗）。

★ 根因链：
  ① `open(INBOX_DONE, "w")` 是**先截断再写**
  ② 并发的 `_done_state()` 正好读到截断后的空/半截文件
  ③ `json.load` 抛异常 → `except: return {}` **静默吞**
  ④ 调用方看到 `{}` = "一条都没处理过" ⇒ 整个收件箱重跑一遍

  （这也是 R398 那单"重跑 52 次"的真正机制：不只是 stale 判定。）

★ 修法：
  ① 写：临时文件 + `fsync` + `os.replace`（同分区原子）
  ② 读：失败先重试 3 次；仍失败才空返回，**并打 stderr**（不许静默）
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import dwc_agent as A  # noqa: E402


@pytest.fixture
def state_file(tmp_path, monkeypatch):
    p = tmp_path / "done.json"
    p.write_text(json.dumps({"T0": "done"}), encoding="utf-8")
    monkeypatch.setattr(A, "INBOX_DONE", str(p))
    return p


def test_write_done_leaves_valid_json(state_file):
    """★★★ 写完之后文件必须是完整合法 JSON。"""
    A._write_done({"T1": "done", "T2": "running:1"})
    obj = json.loads(state_file.read_text(encoding="utf-8"))
    assert obj["T1"] == "done" and obj["T2"] == "running:1"


def test_write_done_leaves_no_tmp_file(state_file, tmp_path):
    """★★ 不许残留 .tmp（否则磁盘上会堆积垃圾）。"""
    A._write_done({"T1": "done"})
    leftovers = [f for f in os.listdir(str(tmp_path)) if ".tmp." in f]
    assert not leftovers, leftovers


def test_read_after_write_roundtrip(state_file):
    """★★ 写完立刻读，必须读到新值（os.replace 的可见性）。"""
    A._write_done({"T9": "done"})
    assert A._done_state()["T9"] == "done"


def test_empty_file_is_not_silently_empty(tmp_path, monkeypatch, capsys):
    """★★★ 空/坏文件不许**静默**返回 {} —— 必须打 stderr。

    静默返回 {} 正是"整个队列重跑"的开关。
    """
    p = tmp_path / "done.json"
    p.write_text("", encoding="utf-8")
    monkeypatch.setattr(A, "INBOX_DONE", str(p))
    assert A._done_state() == {}
    err = capsys.readouterr().err
    assert "INBOX_DONE" in err, err


def test_concurrent_read_never_sees_empty(state_file):
    """★★★ 并发读写压测：读方**永远**不该看到 {}（非原子写就会）。

    50 次写 × 50 次读同时跑；每次读到的必须是完整 dict（含 T0）。
    """
    stop = threading.Event()
    bad = []

    def writer():
        i = 0
        while not stop.is_set():
            i += 1
            A._write_done({"T0": "done", "n": i, "pad": "x" * 2000})

    def reader():
        while not stop.is_set():
            st = A._done_state()
            if not st:
                bad.append("empty")

    tw = threading.Thread(target=writer)
    trs = [threading.Thread(target=reader) for _ in range(4)]
    tw.start()
    for t in trs:
        t.start()
    time.sleep(1.0)
    stop.set()
    tw.join()
    for t in trs:
        t.join()
    assert not bad, "读方看到空状态 %d 次（会被判成'全都没处理'）" % len(bad)


def test_concurrent_updates_do_not_lose_keys(state_file):
    """★★★ 并发"读-改-写"不许丢键（现场：6 单投进去一条都没登记上）。

    20 个线程各自登记一个不同任务；结束后 20 个键必须**全在**。
    旧的 `st=_done_state(); st[k]=v; _write_done(st)` 会互相覆盖。
    """
    def add(i):
        A._update_done(lambda s: s.__setitem__("T%d" % i, "done"))

    ts = [threading.Thread(target=add, args=(i,)) for i in range(20)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    st = A._done_state()
    missing = [i for i in range(20) if "T%d" % i not in st]
    assert not missing, "丢失的键: %r（读-改-写没有串行化）" % missing
