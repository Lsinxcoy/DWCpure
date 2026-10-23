# -*- coding: utf-8 -*-
"""R198 · anchor 漂移观察面。

落地边界（R198 答用户的裁决）: **只观察 + 记账 + 列建议; 不自动换代**。
  · 换代权在系统外 — G10 grounded 双条件②（base 在 agent 外, GAI §2.2 逐字）
    + judge.py 逐字 "agent 仍不可改判分, 换代只能走 epoch 点界流程"
  · 单调性 — 守门人 2606.14249 "只增不改" ⇒ epoch 只能前进, 换代必须加任务
"""
from __future__ import annotations

import json
import os
import re
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.harness.anchor_drift import (EPOCH_LEDGER, SUGGESTION_RULES,  # noqa: E402
                                      drift_signals, epoch_of,
                                      read_epochs, record_epoch)


def test_drift_signals_from_real_products():
    """★★★ 信号全部来自既有产物（evidence.jsonl + dev.json）— 实测一次。"""
    sig = drift_signals(ROOT)
    # ★ R199 后: epoch=2（rung3 加题已记账 — R198 机制首次真实使用）
    #   出厂口径（无账本⇒1）的覆盖在 test_r198_epoch_ledger... 与 tmp_path 测试
    assert sig["epoch"] == 2, sig["epoch"]
    assert sig["n_dev"] >= 1, "e2e 跑过 ⇒ dev 证据在场"
    assert sig["dev_pass_rate"] is not None
    assert 0.0 <= sig["dev_pass_rate"] <= 1.0
    # ★★ R287-E 后事实: 007/008/009（rung1）落地 ⇒ rung_mix {1:13, 3:3}，
    #   rung_monotone 信号**仍消解**（信号亮→行动→信号灭 = R198 闭环）。
    #   意图是"非单调"，rung1 数动态取 —— 下次 anchor+1 不炸。
    _rung1 = sum(1 for k, a in json.load(
        open(os.path.join(ROOT, "config", "anchors", "dev.json"),
             encoding="utf-8")).items()
        if not k.startswith("_") and a.get("verifier_rung") == 1)
    assert sig["rung_mix"] == {"1": _rung1, "3": 3}, sig["rung_mix"]
    assert "rung_monotone" not in sig["suggestions"], (
        "rung 已有 3 档却还亮 rung_monotone ⇒ 规则实现错了")


def test_suggestion_rules_all_implemented():
    """★★★ 防幻影规则: SUGGESTION_RULES 的每个键都能被 _suggestions 产出。"""
    src = open(os.path.join(ROOT, "src", "dwc", "harness",
                            "anchor_drift.py"), encoding="utf-8").read()
    for key in SUGGESTION_RULES:
        assert '"%s"' % key in src, "规则 %r 登记了但函数里没有 ⇒ 幻影" % key


def test_no_auto_epoch_in_module():
    """★★★ 换代权在系统外 — 本模块不许出现"自动改锚点文件"路径。"""
    src = open(os.path.join(ROOT, "src", "dwc", "harness",
                            "anchor_drift.py"), encoding="utf-8").read()
    # ★ 只查**代码区**（剥掉模块 docstring — 说明文字里允许出现 dev.json 字样,
    #   判据是"有没有真的去写它", 不是"有没有提到它"; 同 A1/grep 逮 docstring 的坑）
    code = re.sub(r'"""[\s\S]*?"""', '""', src)   # 剥掉所有 docstring
    # ★ 精确判法: 禁的是**写动作**（读 dev.json 合法 — _rung_mix 要读它算难度
    #   结构; 判据是"会不会改", 不是"会不会提" — 同 grep 逮 docstring 的坑）
    for banned in ("shutil.copy", "os.replace", "write_text",
                   'open(p, "w"', "open(p, 'w'"):
        assert banned not in code, (
            "anchor_drift 出现 %r ⇒ 可能自己在改锚点文件（G10/grounded② 禁）" % banned)
    # 唯一的追加写出口必须是 epoch 账本 — 函数级判: 只查**含追加写的那个函数**
    # （`_rung_mix` 的 p=dev.json 是只读路径, 不该被这条误伤）
    fns = re.split(r"\ndef ", code)
    writers = [f for f in fns
               if "open(" in f and '"a"' in f]
    assert len(writers) == 1, "含追加写的函数不止一个: %d" % len(writers)
    fn = writers[0]
    p_assigns = [l for l in fn.splitlines() if l.strip().startswith("p = ")]
    assert p_assigns and all("EPOCH_LEDGER" in l for l in p_assigns), (
        "追加写目标不是 EPOCH_LEDGER: %r" % p_assigns)


def test_monotonic_epoch_rejects_regression(tmp_path):
    """★★★ epoch 只能前进（换代不回退 — 与 direction 锁 3 同纪律）。"""
    rec = record_epoch(str(tmp_path), new_epoch=2, by="human",
                       why="test", added_tasks=["t1"])
    assert rec["prev_epoch"] == 1 and rec["epoch"] == 2
    with pytest.raises(ValueError):
        record_epoch(str(tmp_path), new_epoch=2, by="human",     # 同号 ⇒ 拒
                     why="test", added_tasks=["t2"])
    with pytest.raises(ValueError):
        record_epoch(str(tmp_path), new_epoch=1, by="human",     # 回退 ⇒ 拒
                     why="test", added_tasks=["t3"])


def test_epoch_record_requires_added_tasks(tmp_path):
    """★★★ 换代必须加任务（守门人单调性: 只增不改 — 空 = 没漂移, 不许记账）。"""
    with pytest.raises(ValueError):
        record_epoch(str(tmp_path), new_epoch=2, by="human",
                     why="只改号不动锚", added_tasks=[])
    assert read_epochs(str(tmp_path)) == [], "空 added_tasks 却记了账"


def test_epoch_ledger_bad_line_raises(tmp_path):
    """★ G7: 坏行 raise 不静默跳（账本拒绝猜）。"""
    p = tmp_path / "archive"
    p.mkdir()
    (p / EPOCH_LEDGER).write_text("{bad}\n", encoding="utf-8")
    with pytest.raises(ValueError):
        read_epochs(str(tmp_path))


def test_drift_signals_absent_evidence_is_none(tmp_path):
    """★★★ 缺席如实化: 无 dev 证据 ⇒ None（"没测过"≠"全错"）。"""
    sig = drift_signals(str(tmp_path))
    assert sig["epoch"] == 1, "无账本 ⇒ 出厂口径 epoch=1（R141）"
    assert sig["n_dev"] == 0 and sig["dev_pass_rate"] is None
    assert sig["val_pass_rate"] is None
    assert sig["suggestions"] == [], "没数据却给建议 ⇒ 无据触发"


def test_r198_rung_rule_still_fires(tmp_path):
    """★★ 合成夹具: rung 全 1 的锚点面 ⇒ rung_monotone 仍亮（规则覆盖保留）。

    ★ R199 动 dev.json 后, 真实面不再单调 ⇒ 真实断言翻转（见
      test_drift_signals_from_real_products）; 但规则本身必须仍有测试
      证明它会响（否则规则死了都没人知道 — 幻影规则防线上移）。"""
    import json
    anchor_dir = tmp_path / "config" / "anchors"
    anchor_dir.mkdir(parents=True)
    (anchor_dir / "dev.json").write_text(json.dumps({
        "t_a": {"verifier_kind": "behavior", "verifier_rung": 1},
        "t_b": {"verifier_kind": "keyword_match", "verifier_rung": 1},
    }, ensure_ascii=False), encoding="utf-8")
    sig = drift_signals(str(tmp_path))
    assert sig["rung_mix"] == {"1": 2}, sig["rung_mix"]
    assert "rung_monotone" in sig["suggestions"], "全 rung1 时规则必须亮"
