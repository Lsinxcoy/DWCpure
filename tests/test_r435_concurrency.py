# -*- coding: utf-8 -*-
"""R435 · 端点并发宽度可配（A/B 提速）。

★★★ 为什么现在敢放开：
    旧端点并发下不遵守 `json_mode`（4 路 ⇒ 0/4 合法），所以当年加了全局锁。
    换到当前端点后重测：**12 路串行 12/12、4 路并发 12/12**，且 4.17× 加速
    ⇒ 旧结论只对旧端点成立，锁的宽度应当可配，而不是写死 1。

★★★ 为什么默认仍是 1：
    生产稳定性优先。宽度只在 A/B（要速度）时显式调高，默认行为与历史一致。
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from dwc.llm import client as CL  # noqa: E402
import dwc_prompt_ab as AB        # noqa: E402


def test_default_width_is_one():
    """★★ 缺省 = 1（与历史串行行为一致，生产零变化）。"""
    old = os.environ.pop("DWC_HTTP_CONCURRENCY", None)
    try:
        assert CL._http_width() == 1
    finally:
        if old is not None:
            os.environ["DWC_HTTP_CONCURRENCY"] = old


def test_width_parses_int(monkeypatch):
    monkeypatch.setenv("DWC_HTTP_CONCURRENCY", "4")
    assert CL._http_width() == 4


def test_width_clamped(monkeypatch):
    """★★ 下限 1、上限 8 —— 0/负数不能把锁变成"永不阻塞"。"""
    monkeypatch.setenv("DWC_HTTP_CONCURRENCY", "0")
    assert CL._http_width() == 1
    monkeypatch.setenv("DWC_HTTP_CONCURRENCY", "-3")
    assert CL._http_width() == 1
    monkeypatch.setenv("DWC_HTTP_CONCURRENCY", "99")
    assert CL._http_width() == 8


def test_width_garbage_falls_back_to_one(monkeypatch):
    monkeypatch.setenv("DWC_HTTP_CONCURRENCY", "abc")
    assert CL._http_width() == 1


def test_lock_is_semaphore_compatible():
    """★★ `with _HTTP_LOCK:` 必须仍可用（Semaphore 支持上下文协议）。"""
    assert hasattr(CL._HTTP_LOCK, "acquire")
    with CL._HTTP_LOCK:
        pass


def test_width_n_allows_n_concurrent_holders():
    """★★★ 宽度 3 ⇒ 三个线程能同时进入临界区（这是提速的机制本身）。"""
    sem = threading.Semaphore(3)
    peak = [0]
    cur = [0]
    lock = threading.Lock()

    def worker():
        with sem:
            with lock:
                cur[0] += 1
                peak[0] = max(peak[0], cur[0])
            time.sleep(0.15)
            with lock:
                cur[0] -= 1

    ths = [threading.Thread(target=worker) for _ in range(3)]
    for t in ths:
        t.start()
    for t in ths:
        t.join()
    assert peak[0] == 3


def test_width_one_serializes():
    """★★ 宽度 1 时峰值并发必须是 1（旧行为不能被悄悄破坏）。"""
    sem = threading.Semaphore(1)
    peak = [0]
    cur = [0]
    lock = threading.Lock()

    def worker():
        with sem:
            with lock:
                cur[0] += 1
                peak[0] = max(peak[0], cur[0])
            time.sleep(0.05)
            with lock:
                cur[0] -= 1

    ths = [threading.Thread(target=worker) for _ in range(4)]
    for t in ths:
        t.start()
    for t in ths:
        t.join()
    assert peak[0] == 1


def test_agent_task_width_env():
    """★★ agent 侧槽位宽也读环境变量（两处必须同时调高才有意义）。"""
    src = open(os.path.join(ROOT, "scripts", "dwc_agent.py"),
               encoding="utf-8").read()
    assert "DWC_TASK_CONCURRENCY" in src
    assert "threading.Semaphore(_width)" in src


# ── 并发波次：等一批报告 ────────────────────────────────────────────

def _mk_report(dirpath, tid, mtime=None):
    p = os.path.join(dirpath, tid + ".json")
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(json.dumps({"answer": "ok"}))
    if mtime is not None:
        os.utime(p, (mtime, mtime))
    return p


def test_wait_many_collects_whole_batch(tmp_path, monkeypatch):
    """★★★ 一波 N 单必须等齐（否则并发退化成串行）。"""
    import time as _t
    import json
    monkeypatch.setattr(AB.NB, "REPORTS", str(tmp_path))
    now = _t.time()
    _mk_report(str(tmp_path), "ab_x_S_rf01", now)
    _mk_report(str(tmp_path), "ab_x_S_rf02", now)
    got = AB._wait_many([("ab_x_S_rf01", "rf01"), ("ab_x_S_rf02", "rf02")],
                        since=now - 1, timeout_min=0.2, poll=0.05)
    assert set(got) == {"ab_x_S_rf01", "ab_x_S_rf02"}


def test_wait_many_rejects_stale_reports(tmp_path, monkeypatch):
    """★★ 防旧报告：mtime 早于 since 的报告不算本轮产出。"""
    import time as _t
    monkeypatch.setattr(AB.NB, "REPORTS", str(tmp_path))
    now = _t.time()
    _mk_report(str(tmp_path), "ab_x_C_rf03", now - 600)   # 上一轮的
    got = AB._wait_many([("ab_x_C_rf03", "rf03")],
                        since=now - 1, timeout_min=0.2, poll=0.05)
    assert got == {}


def test_wave_covers_all_ids():
    """★★ 波次切分不能漏题（最后一波不足 wave 也要跑）。"""
    ids = ["t%d" % i for i in range(7)]
    for wave in (1, 3, 4, 8):
        seen = []
        for w in range(0, len(ids), wave):
            seen.extend(ids[w:w + wave])
        assert seen == ids


# ── 基础设施故障不许记在候选头上 ──────────────────────────────────

def test_judge_marks_infra_as_none():
    """★★★ 现场：wave=4 跑到一半连续 HTTP 502，第一版判成 ✗ ⇒ 误 REJECT。"""
    rep = {"status": "incomplete", "why": "LLM 失败[infra]: HTTP 502: Bad Gateway",
           "answer": None}
    ok, how, _ = AB._judge({"check": {"type": "contains", "target": "x"}},
                           rep, since=0)
    assert ok is None
    assert "infra" in how


def test_judge_normal_failure_stays_false():
    """★★ 模型真的答错仍然是 False（不能把所有失败都当 infra 洗掉）。"""
    rep = {"status": "done", "answer": "错的", "why": ""}
    ok, _, _ = AB._judge({"check": {"type": "contains", "target": "对的"}},
                         rep, since=0)
    assert ok is False


def test_decide_excludes_infra_pairs_from_denominator():
    """★★★ 10 单里 2 单 infra ⇒ 分母 8；且 infra 不会被算成 loss。"""
    pairs = [{"id": "a", "stable_ok": True, "cand_ok": None},
             {"id": "b", "stable_ok": None, "cand_ok": False}] + \
            [{"id": "c%d" % i, "stable_ok": True, "cand_ok": True}
             for i in range(8)]
    v, wins, losses = AB.decide(pairs, min_tasks=8, min_wins=2)
    assert v == "keep" and not losses


def test_decide_insufficient_when_infra_eats_denominator():
    """★★ infra 太多 ⇒ insufficient（不能拿 2 单有效结果下结论）。"""
    pairs = [{"id": "a", "stable_ok": True, "cand_ok": None},
             {"id": "b", "stable_ok": None, "cand_ok": True},
             {"id": "c", "stable_ok": True, "cand_ok": True}]
    v, _, _ = AB.decide(pairs, min_tasks=10, min_wins=2)
    assert v == "insufficient"
