# -*- coding: utf-8 -*-
"""R378 · nightbench 假通过（读旧报告）+ tid 同日重复。

★★★ 现场取证（2026-10-20 08:51 实跑）:
  跑批输出 `3/9 通过`，但 `var/dwc_reports/nb_1020_0{1..4}.json`
  的 mtime 是 **02:35–04:01**（昨晚那批），08:51 的报告一个都不存在。
  ⇒ `_wait_report` 立刻命中昨天的文件 ⇒ 判据验的是**昨天的答案**。
  而昨晚 4 单的 status 全是 `incomplete`（LLM 非 JSON）—— 判"通过"的
  write 类任务只是因为 `var/inbox_work/` 里残留文件满足 `contains`。

★★ 两个独立缺陷:
  ① `tid = "nb_%s_%02d" % (day, i)` 只有 月日 + 轮内序号 ⇒ **同一天
     第二次跑批必然撞名**（cron 02:30 + 手动重跑就会撞）。
  ② `_wait_report` 只看 `os.path.exists(p)`，不看这份报告是不是**本轮
     投单之后**写的 ⇒ 旧文件让"超时等待"瞬间变成"立刻拿到结果"。

★ 判据:
  · 同一进程内连续两次生成 tid 不得相同（即使同一天同一序号）
  · `_wait_report` 必须忽略 mtime 早于投单时刻的报告
  · 超时确实超时（旧报告不再能骗过它）
"""
from __future__ import annotations

import importlib.util
import io
import json
import os
import sys
import time

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))


def _load_nb():
    """按路径加载 nightbench（scripts 下同名模块可能与别处遮蔽）。"""
    p = os.path.join(ROOT, "scripts", "dwc_nightbench.py")
    spec = importlib.util.spec_from_file_location("dwc_nightbench_r378", p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


NB = _load_nb()


# ─────────────────────────── ① tid 必须唯一


def test_tid_unique_within_same_day():
    """★★★ 同一天连续生成 3 个 tid 必须互不相同。

    旧实现 `nb_{MMDD}_{i:02d}`：同一天第二次跑批 i 又从 1 开始 ⇒ 撞名。
    """
    a = NB.make_tid(1)
    time.sleep(1.1)          # 让秒级时间戳变化（真实现应含时分秒）
    b = NB.make_tid(1)
    assert a != b, (
        "同一天同一序号生成了相同 tid（%r）—— 会读到上一批的报告" % a)


def test_tid_is_filename_safe():
    """★ tid 直接当文件名用 ⇒ 不许含路径分隔符/空格/冒号。"""
    t = NB.make_tid(3)
    for bad in ("/", "\\", ":", " ", ".."):
        assert bad not in t, "tid 含非法字符 %r: %r" % (bad, t)


# ─────────────────────────── ② 旧报告不许当本轮结果


def test_wait_report_ignores_stale_file(tmp_path, monkeypatch):
    """★★★ mtime 早于投单时刻的报告必须被忽略。

    现场：08:51 跑批读到 02:35 的报告 ⇒ 判"通过"。
    """
    monkeypatch.setattr(NB, "REPORTS", str(tmp_path))
    tid = "nb_test_stale"
    p = tmp_path / ("%s.json" % tid)
    p.write_text(json.dumps({"status": "incomplete", "answer": None}),
                 encoding="utf-8")
    # 把 mtime 拨到 1 小时前
    old = time.time() - 3600
    os.utime(str(p), (old, old))

    got = NB._wait_report(tid, timeout_min=0.02, since=time.time())
    assert got == {}, (
        "读到了旧报告（mtime 比投单时刻早 1 小时）—— 判据验的是昨天的答案")


def test_wait_report_accepts_fresh_file(tmp_path, monkeypatch):
    """★★ 本轮新写的报告必须正常读到（不许修过头）。"""
    monkeypatch.setattr(NB, "REPORTS", str(tmp_path))
    tid = "nb_test_fresh"
    since = time.time()
    p = tmp_path / ("%s.json" % tid)
    p.write_text(json.dumps({"status": "done", "answer": "ok"}),
                 encoding="utf-8")

    got = NB._wait_report(tid, timeout_min=0.5, since=since)
    assert got.get("answer") == "ok", got


def test_wait_report_since_none_keeps_old_behavior(tmp_path, monkeypatch):
    """★ 不传 since ⇒ 保持旧语义（兼容既有调用/测试）。"""
    monkeypatch.setattr(NB, "REPORTS", str(tmp_path))
    tid = "nb_test_compat"
    p = tmp_path / ("%s.json" % tid)
    p.write_text(json.dumps({"answer": "legacy"}), encoding="utf-8")
    old = time.time() - 3600
    os.utime(str(p), (old, old))

    got = NB._wait_report(tid, timeout_min=0.02)
    assert got.get("answer") == "legacy", got


# ─────────────────────────── ③ 调用点真的传了 since


def test_main_passes_since_to_wait_report():
    """★★★ 源码级锁：main 里 `_wait_report` 必须带 `since=`。

    只修函数不修调用点 = 白修（本次 bug 正是"函数没错、调用点漏了上下文"）。
    """
    src = io.open(os.path.join(ROOT, "scripts", "dwc_nightbench.py"),
                  encoding="utf-8").read()
    assert "_wait_report(tid, args.wait_min, since=" in src, (
        "main 调用 _wait_report 没传 since ⇒ 旧报告仍会被当成结果")


# ─────────────────────────── ④ 文件类判据不许吃旧文件


def _load_b2():
    p = os.path.join(ROOT, "scripts", "dwc_bench2.py")
    spec = importlib.util.spec_from_file_location("dwc_bench2_r378", p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_verify_file_contains_rejects_stale_file(tmp_path, monkeypatch):
    """★★★ 旧文件不许满足 file_contains（现场：wr08 用 6 天前的文件判 ✓）。"""
    B2 = _load_b2()
    f = tmp_path / "hello.txt"
    f.write_text("EVAL_WRITE_OK", encoding="utf-8")
    old = time.time() - 528591
    os.utime(str(f), (old, old))
    ck = {"type": "file_contains", "path": str(f), "target": "EVAL_WRITE_OK"}

    ok, how = B2.verify(ck, "", since=time.time())
    assert ok is False, "旧文件被判通过 —— 验的是历史残留，不是本轮产出"
    assert "stale" in how, how


def test_verify_file_contains_accepts_fresh_file(tmp_path):
    """★★ 本轮新写的文件必须正常通过（不许修过头）。"""
    B2 = _load_b2()
    f = tmp_path / "hello.txt"
    f.write_text("EVAL_WRITE_OK", encoding="utf-8")
    ck = {"type": "file_contains", "path": str(f), "target": "EVAL_WRITE_OK"}

    ok, how = B2.verify(ck, "", since=time.time() - 5)
    assert ok is True, how


def test_verify_file_contains_since_none_compat(tmp_path):
    """★ 不传 since ⇒ 旧语义不变（兼容既有调用/测试）。"""
    B2 = _load_b2()
    f = tmp_path / "hello.txt"
    f.write_text("EVAL_WRITE_OK", encoding="utf-8")
    old = time.time() - 999999
    os.utime(str(f), (old, old))
    ck = {"type": "file_contains", "path": str(f), "target": "EVAL_WRITE_OK"}

    ok, _ = B2.verify(ck, "")
    assert ok is True


def test_nightbench_passes_since_to_verify():
    """★★★ 源码级锁：main 里 `B2.verify` 必须带 `since=`。"""
    src = io.open(os.path.join(ROOT, "scripts", "dwc_nightbench.py"),
                  encoding="utf-8").read()
    assert "since=_t_push)" in src, (
        "main 调用 B2.verify 没传 since ⇒ 旧文件仍能假通过")
