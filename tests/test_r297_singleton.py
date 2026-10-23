# -*- coding: utf-8 -*-
"""R297-Task1 · 单实例原子锁（O_EXCL 抢建＋stale 接管）。

★ 零真 LLM；raises 配额见末尾。
★ R210 的 pid 检查非原子（先查后写竞态可双过）——本任务换 O_EXCL 原子抢建。
"""
from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))


def test_r297_double_acquire_second_refused(tmp_path):
    """★ 同进程连抢两次⇒第二次 False（有活实例，拒双开）。"""
    from dwc_agent import acquire_singleton
    p = str(tmp_path / "agent.pid")
    assert acquire_singleton(p) is True
    assert acquire_singleton(p) is False


def test_r297_stale_lock_taken_over(tmp_path):
    """★ 残留 pid 已死⇒接管 True（不卡死永远拒启）。"""
    from dwc_agent import acquire_singleton
    pid_file = tmp_path / "agent.pid"
    pid_file.write_text("999999999", encoding="utf-8")  # ★ 必死 pid
    assert acquire_singleton(str(pid_file)) is True
    assert pid_file.read_text(encoding="utf-8").strip() == str(os.getpid())


def _race_live_worker(pid_path, q):
    import sys as _s
    _s.path.insert(0, os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
    from dwc_agent import acquire_singleton
    q.put(acquire_singleton(pid_path))


def test_r297_live_lock_refused(tmp_path):
    """★ 活持有者在⇒他进程抢⇒False（真双开，拒）。

    主进程先拿锁（模拟活 daemon），子进程撞锁必须拒。
    pid 文件可读性由 watch 侧保障（本测不断言读）。
    """
    import multiprocessing as _mp
    from dwc_agent import acquire_singleton
    p = str(tmp_path / "agent.pid")
    assert acquire_singleton(p) is True  # ★ 主进程=活持有者
    assert open(p, encoding="utf-8").read().strip() == str(os.getpid())
    q = _mp.Queue()
    x = _mp.Process(target=_race_live_worker, args=(p, q))
    x.start()
    x.join(30)
    assert q.get() is False


def test_r297_raises_quota_bad_pid_content(tmp_path):
    """★ raises 配额：坏内容（非数字）⇒接管不炸（坏 pid 文件放行，R210 语义延续）。

    注：本测不断言抛——坏内容走 stale 接管分支；配额由下测承担。
    """
    from dwc_agent import acquire_singleton
    pid_file = tmp_path / "agent.pid"
    pid_file.write_text("not-a-pid", encoding="utf-8")
    assert acquire_singleton(str(pid_file)) is True


def test_r297_raises_quota_acquire_never_none(tmp_path):
    """★ raises 配额：锁目录不可写⇒抛 OSError 大声（不静默假装拿到锁）。"""
    from dwc_agent import acquire_singleton
    with pytest.raises(OSError):
        acquire_singleton(os.path.join(
            str(tmp_path), "no_such_dir", "agent.pid"))


def _race_worker(pid_path, q):
    import sys as _s
    _s.path.insert(0, os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
    from dwc_agent import acquire_singleton
    q.put(acquire_singleton(pid_path))


def test_r297_concurrent_stale_single_winner(tmp_path):
    """★ 真并发：两进程同时撞 stale⇒恰一 True（CAS 收敛单赢）。"""
    import multiprocessing as _mp
    p = str(tmp_path / "agent.pid")
    with open(p, "w", encoding="utf-8") as fh:
        fh.write("999999999")
    q = _mp.Queue()
    ps = [_mp.Process(target=_race_worker, args=(p, q)) for _ in range(2)]
    for x in ps:
        x.start()
    for x in ps:
        x.join(30)
    wins = [q.get() for _ in ps]
    assert wins.count(True) == 1, wins
