# -*- coding: utf-8 -*-
"""R398 · 收件箱不许无限重取（一单被重跑 52 次的现场）。

★★★ 现场（2026-10-21 00:09，第二轮全池）：
  跑批卡死在 `nb_1020_232218_38`（analyze），会话日志 157KB：

      task_mode 出现 **52 次**（同一 task_id，每 30~60 秒一次）
      final 202 / run 180 / judge 179 / refcheck 102 / revision 89

  收件箱被这一单堵死，后续任务全部超时，整轮跑批作废。

★ 根因链：
  ① 长任务的 `running:<ts>` 标记**不刷新** ⇒ 15 分钟后被判 stale
  ② stale ⇒ `take_inbox()` 重取 ⇒ 再跑一遍
  ③ 重取的线程又写回旧标记 ⇒ 永远 stale ⇒ **无限重跑**

★ 修法：**硬上限**。同一 task_id 最多重取 `MAX_REPICK` 次，
  超了标记 `failed:too_many_attempts` 并停止重试（落盘，跨重启保持）。
  计数失败不阻断取单（不许因为计数把队列卡死）。
"""
from __future__ import annotations

import json
import os
import sys
import time

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import dwc_agent as A  # noqa: E402


@pytest.fixture
def env(tmp_path, monkeypatch):
    inbox = tmp_path / "inbox.jsonl"
    done = tmp_path / "done.json"
    att = tmp_path / "attempts.json"
    inbox.write_text(json.dumps({"id": "T1", "task": "x"}) + "\n",
                     encoding="utf-8")
    done.write_text(json.dumps({"T1": "running:%.0f" % (time.time() - 3600)}),
                    encoding="utf-8")
    monkeypatch.setattr(A, "INBOX", str(inbox))
    monkeypatch.setattr(A, "INBOX_DONE", str(done))
    monkeypatch.setattr(A, "ATTEMPTS", str(att))
    return inbox, done, att


def test_stale_task_is_retaken_once(env):
    """★★ 第 1 次 stale 重取允许（恢复崩溃的线程）。"""
    item = A.take_inbox()
    assert item and item["id"] == "T1"
    assert A._done_state()["T1"] == "stale_recovered"


def test_attempt_cap_stops_rerun(env):
    """★★★ 核心：超过 MAX_REPICK 次 ⇒ 不再返回该单，标记 failed。"""
    _, done, att = env
    # 模拟已被重取 MAX_REPICK 次
    att.write_text(json.dumps({"T1": A.MAX_REPICK}), encoding="utf-8")
    item = A.take_inbox()
    assert item is None, "超过上限仍在重取（会无限烧）"
    st = json.loads(done.read_text(encoding="utf-8"))
    assert st["T1"] == "failed:too_many_attempts", st


def test_attempt_cap_does_not_affect_fresh_running(env):
    """★★ 15 分钟内的 running 本来就跳过（上限不该改变这点）。"""
    _, done, _ = env
    done.write_text(json.dumps({"T1": "running:%.0f" % time.time()}),
                    encoding="utf-8")
    assert A.take_inbox() is None
    st = json.loads(done.read_text(encoding="utf-8"))
    assert st["T1"].startswith("running:"), "fresh running 被改写了"


def test_done_task_never_retaken(env):
    """★★ 已 done 的单永远不重取（与上限无关）。"""
    _, done, _ = env
    done.write_text(json.dumps({"T1": "done"}), encoding="utf-8")
    assert A.take_inbox() is None


def test_bump_attempt_is_persistent(tmp_path, monkeypatch):
    """★★ 重取计数落盘（重启不重置预算）。"""
    att = tmp_path / "a.json"
    monkeypatch.setattr(A, "ATTEMPTS", str(att))
    assert A._bump_attempt("TX") == 1
    assert A._bump_attempt("TX") == 2
    assert json.loads(att.read_text(encoding="utf-8"))["TX"] == 2


def test_bump_failure_does_not_block(tmp_path, monkeypatch):
    """★★ 计数写失败 ⇒ 返回 1（不许因为计数把队列卡死）。"""
    monkeypatch.setattr(A, "ATTEMPTS", str(tmp_path / "nodir" / "x" / "a.json"))
    assert A._bump_attempt("TY") == 1
