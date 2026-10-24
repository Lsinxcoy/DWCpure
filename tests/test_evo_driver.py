# -*- coding: utf-8 -*-
"""R审计-P2 · evo_driver 产物参数进化驱动器测试。

★★ 锁什么（R438 验收四条 + 两条额外护栏）:
  1. 产物存在: adjusted 后 config/context_policy.json 真的变了
  2. 消费者生效: 调整后 read_default_lines() 立即返回新值
  3. 可回滚: apply 失败大声（error 态），不假装成功
  4. 可区分: 台账三态（adjusted / skipped_no_signal / skipped_cooldown）
  5. 防抖: 24h 内同参数只调一次（防震荡）
  6. 不发明信号: 无压力（截断率低于阈值）⇒ 不调参
"""

from __future__ import annotations

import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.organs import evo_driver as D  # noqa: E402
from dwc.organs import evo_targets as ET  # noqa: E402


@pytest.fixture()
def driver(tmp_path, monkeypatch):
    """隔离驱动: 台账 + 产物都落在 tmp（不碰生产 var/config）。"""
    ledger = tmp_path / "evolution_ledger.jsonl"
    monkeypatch.setattr(ET, "ROOT", str(tmp_path))
    # 产物路径在 ROOT 下: config/context_policy.json
    (tmp_path / "config").mkdir(exist_ok=True)
    d = D.EvoParamDriver(ledger_path=str(ledger), now=lambda: 1000000.0)
    return d, tmp_path


def _pressure_reads(n_trunc: int, n_ok: int = 0):
    """构造窗口观测: n_trunc 次第一页截断 + n_ok 次正常。"""
    obs = []
    for _ in range(n_trunc):
        obs.append({"op": "read", "truncated": True, "n_lines": 500,
                    "offset": 0, "returned": 200})
    for _ in range(n_ok):
        obs.append({"op": "read", "truncated": False, "n_lines": 50,
                    "offset": 0, "returned": 50})
    return obs


def test_no_signal_skips(driver):
    """窗口无读取 ⇒ 无从判定 ⇒ skipped_no_signal（不发明信号）。"""
    d, tmp = driver
    rep = d.run()
    assert rep["decision"] == "skipped_no_signal"
    # 产物未被创建
    assert not (tmp / "config" / "context_policy.json").exists()


def test_low_pressure_skips(driver):
    """截断率低于阈值 ⇒ skipped（一次截断 + 一次正常 = 50% < 50% 边界??）"""
    d, tmp = driver
    for obs in _pressure_reads(n_trunc=1, n_ok=2):   # 1/3 = 33%
        d.observe_read(obs)
    rep = d.run()
    assert rep["decision"] == "skipped_no_signal"


def test_pressure_triggers_adjustment(driver):
    """★★★ 核心: 截断率 100% ⇒ adjusted，产物真的写盘且值变大。"""
    d, tmp = driver
    for obs in _pressure_reads(n_trunc=3):           # 3/3 = 100%
        d.observe_read(obs)
    rep = d.run()
    assert rep["decision"] == "adjusted", rep
    assert rep["after"] == 250                       # 默认 200 + 步进 50
    # 产物存在（验收 1）
    p = tmp / "config" / "context_policy.json"
    assert p.exists()
    data = json.loads(p.read_text(encoding="utf-8"))
    assert data["read_default_lines"] == 250


def test_consumer_sees_new_value(driver, monkeypatch):
    """★★★ 消费者生效（验收 2）: 调整后 task_exec 立即读到新值。"""
    d, tmp = driver
    import dwc.llm.task_exec as T
    # task_exec 的 _policy 读 ET.path_of → 我们已 monkeypatch ET.ROOT
    monkeypatch.setattr(T._policy, "__wrapped__", None) if False else None
    # 先让 task_exec 用当前 ET.ROOT 读（默认 200 → 无产物文件时）
    for obs in _pressure_reads(n_trunc=3):
        d.observe_read(obs)
    d.run()
    # 直接断言: 产物文件存在 ⇒ read_default_lines() 会经 _policy 读到 250
    # （_policy 的哈希缓存 key 由内容决定，产物变了必然重读）
    from dwc.llm.task_exec import read_default_lines
    got = read_default_lines()
    assert got == 250, got


def test_cooldown_blocks_second_adjust(driver):
    """★★ 防抖: 刚调过 ⇒ 第二次 run 跳过（不震荡）。"""
    d, tmp = driver
    for obs in _pressure_reads(n_trunc=3):
        d.observe_read(obs)
    rep1 = d.run()
    assert rep1["decision"] == "adjusted"
    for obs in _pressure_reads(n_trunc=3):           # 压力仍在
        d.observe_read(obs)
    rep2 = d.run()
    assert rep2["decision"] == "skipped_cooldown", rep2


def test_ledger_three_states(driver):
    """★★ 台账三态可区分（验收 4）: 每行 decision 明确。"""
    d, tmp = driver
    # 1) no signal
    r0 = d.run()
    # 2) adjusted
    for obs in _pressure_reads(n_trunc=3):
        d.observe_read(obs)
    r1 = d.run()
    # 3) cooldown
    for obs in _pressure_reads(n_trunc=3):
        d.observe_read(obs)
    r2 = d.run()
    lines = (tmp / "evolution_ledger.jsonl").read_text(
        encoding="utf-8").strip().splitlines()
    assert len(lines) == 3
    decisions = [json.loads(x)["decision"] for x in lines]
    assert decisions == ["skipped_no_signal", "adjusted", "skipped_cooldown"]
    assert r0["decision"] == "skipped_no_signal"
    assert r1["decision"] == "adjusted"
    assert r2["decision"] == "skipped_cooldown"


def test_rollback_restores(driver):
    """★★ 可回滚（验收 3）: adjusted 的备份可 restore 回默认。

    ★ 前提: 产物文件**已存在**时 apply 才建备份（首次创建没有原文件可备）。
      先 seed 初始产物再调参。
    """
    d, tmp = driver
    # seed 初始产物（模拟已有配置文件）
    p = tmp / "config" / "context_policy.json"
    p.write_text(json.dumps({"read_default_lines": 200, "search_limit": 60}),
                 encoding="utf-8")
    for obs in _pressure_reads(n_trunc=3):
        d.observe_read(obs)
    rep = d.run()
    assert rep["decision"] == "adjusted"
    assert rep["backup"], rep
    # 用备份回滚
    res = ET.rollback("context_mgmt", rep["backup"])
    assert res["outcome"] == "rolled_back"
    data = json.loads(p.read_text(encoding="utf-8"))
    assert data["read_default_lines"] == 200        # 回到默认


def test_offset_reads_not_pressure(driver):
    """★★ 信号口径: offset>0 的翻页截断**不算**压力（大文件正常翻页）。"""
    d, tmp = driver
    # 全是 offset>0 的截断（翻页）⇒ 第一页读取数为 0 ⇒ 无压力
    for _ in range(3):
        d.observe_read({"op": "read", "truncated": True, "n_lines": 900,
                        "offset": 200, "returned": 200})
    rep = d.run()
    assert rep["decision"] == "skipped_no_signal", rep


def test_max_value_cap(driver):
    """★★ 上限护栏: 调到 max_value 后不再超（不越白名单）。"""
    d, tmp = driver
    d.step = 5000                                   # 故意超大步进
    for obs in _pressure_reads(n_trunc=3):
        d.observe_read(obs)
    rep = d.run(max_value=2000)
    assert rep["decision"] == "adjusted"
    assert rep["after"] == 2000                     # 被 cap 在 2000