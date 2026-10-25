"""PERF-01/OPS-01 · FTS 不重复 rebuild + SQLite 并发写。"""
from __future__ import annotations

import sqlite3
import threading

from dwc.organs.memory import MemoryKernel, MemoryKind


class _ConnSpy:
    def __init__(self, conn, calls):
        self._conn = conn
        self._calls = calls

    def execute(self, sql, *a, **k):
        if "VALUES('rebuild')" in str(sql):
            self._calls.append(str(sql))
        return self._conn.execute(sql, *a, **k)

    def __getattr__(self, name):
        return getattr(self._conn, name)


def _spy_connect(monkeypatch, calls):
    orig = sqlite3.connect

    def fake(*a, **k):
        return _ConnSpy(orig(*a, **k), calls)

    monkeypatch.setattr("dwc.organs.memory.sqlite3.connect", fake)


def test_fts_not_rebuilt_when_in_sync(tmp_path, monkeypatch):
    db = str(tmp_path / "m.sqlite")
    calls = []
    _spy_connect(monkeypatch, calls)
    m = MemoryKernel(db)
    m.remember(MemoryKind.TRACE, {"task": "t", "action": "a"})
    m.close()
    assert len(calls) == 1      # 新库只做一次迁移 rebuild
    m2 = MemoryKernel(db)
    m2.close()
    assert len(calls) == 1      # 第二次初始化不再 rebuild


def test_fts_rebuilds_when_out_of_sync(tmp_path, monkeypatch):
    db = str(tmp_path / "m.sqlite")
    m = MemoryKernel(db)
    m.remember(MemoryKind.TRACE, {"task": "t", "action": "a"})
    m.close()
    # 模拟老库：迁移标记归零 ⇒ 启动时 rebuild 一次
    c = sqlite3.connect(db)
    c.execute("PRAGMA user_version=0")
    c.commit()
    c.close()
    calls = []
    _spy_connect(monkeypatch, calls)
    m2 = MemoryKernel(db)
    m2.close()
    assert len(calls) == 1


def test_concurrent_writes(tmp_path):
    m = MemoryKernel(str(tmp_path / "m.sqlite"))
    errs = []

    def worker(i):
        try:
            for j in range(20):
                m.remember(MemoryKind.TRACE, {"task": "t%d" % i, "action": str(j)})
        except Exception as e:      # noqa: BLE001
            errs.append(e)

    ts = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    assert not errs, errs
    n = m._conn.execute("SELECT COUNT(*) FROM memory_node").fetchone()[0]
    assert n == 200
    m.close()
