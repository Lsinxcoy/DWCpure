# -*- coding: utf-8 -*-
"""R289 · credit 落盘持久化（内存→jsonl，重启不丢）契约测试。

★★★ 存在理由
  _feed_credit 只记内存 ledger —— daemon 重启台账清零（缺席≠0 变真 0）。
  落盘是 append-only 台账语义的物理保证：只追加新增、启动载回、
  坏即大声（不静默丢账）。
"""
from __future__ import annotations

import json
import os
import sys

import pytest  # noqa: F401

ROOT = r"E:/Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.organs.credit import CreditEntry, CreditLedger  # noqa: E402


def _entry(t=1, edit="code_fix_007"):
    return CreditEntry(t=t, edit=edit, layer="assets", hunk=edit,
                       dimension="D7", delta_s=1.0, delta_c=0.0, adopted=1)


def test_flush_appends_only_new(tmp_path):
    """★★ 只追加新增：flush 两次不翻倍（append-only 物理保证）。"""
    p = str(tmp_path / "credit_ledger.jsonl")
    lg = CreditLedger()
    lg.record(_entry())
    assert lg.flush(p) == 1
    lg.record(_entry(edit="code_fix_008"))
    assert lg.flush(p) == 1                    # 只追加第 2 笔
    lines = open(p, encoding="utf-8").readlines()
    assert len(lines) == 2, lines
    assert json.loads(lines[1])["edit"] == "code_fix_008"


def test_load_recovers_entries(tmp_path):
    """★★ 启动载回：flush→新实例 load→对数（重启不丢）。"""
    p = str(tmp_path / "credit_ledger.jsonl")
    lg = CreditLedger()
    lg.record(_entry())
    lg.record(_entry(edit="code_fix_008"))
    lg.flush(p)
    lg2 = CreditLedger()
    assert lg2.load(p) == 2
    assert [e.edit for e in lg2.entries()] == ["code_fix_007", "code_fix_008"]
    assert lg2.flush(p) == 0                  # 载回后无新增 ⇒ 零追加


def test_load_missing_file_is_empty_not_crash(tmp_path):
    """★★ 文件缺席 ⇒ 空台账不炸（首轮无文件是常态）。"""
    lg = CreditLedger()
    assert lg.load(str(tmp_path / "nope.jsonl")) == 0
    assert lg.entries() == []


def test_load_bad_line_raises_loud(tmp_path):
    """★★★ 坏行大声炸（raises 配额 — 账坏了不许静默跳过，宁可停）。"""
    p = str(tmp_path / "credit_ledger.jsonl")
    open(p, "w", encoding="utf-8").write('{"t": 1, "edit": "x"}\nNOT_JSON\n')
    lg = CreditLedger()
    with pytest.raises(Exception):
        lg.load(p)


def test_load_compat_r276_envelope(tmp_path):
    """★★ 兼容 R276-③ 信封 {round, task, entry}（同文件两写盘路径，读侧兼容）。"""
    p = str(tmp_path / "credit_ledger.jsonl")
    open(p, "w", encoding="utf-8").write(json.dumps(
        {"round": 1, "task": "code_fix_003",
         "entry": {"t": 1, "edit": "e", "layer": "assets", "hunk": "e",
                   "dimension": "D7", "delta_s": 1.0, "delta_c": 0.0,
                   "adopted": 1}}, ensure_ascii=False) + "\n")
    lg = CreditLedger()
    assert lg.load(p) == 1
    assert lg.entries()[0].edit == "e"


def test_flush_returns_zero_when_empty(tmp_path):
    """★ 空台账 flush ⇒ 0 且不建文件（无账不假装有）。"""
    p = str(tmp_path / "credit_ledger.jsonl")
    lg = CreditLedger()
    assert lg.flush(p) == 0
    assert not os.path.exists(p)


def test_term_runner_persists_credit_to_disk(tmp_path):
    """★★★ 生产接线：真 db 路径 ⇒ 轮尾落盘，重启载回（R289 消 1◐）。"""
    import sys as _sys
    _sys.path.insert(0, os.path.join(ROOT, "src"))
    from dwc.harness.run_term import TermRunner
    from dwc.organs.judge import Judge
    db = str(tmp_path / "prod.sqlite")
    tr = TermRunner(judge=Judge(), db_path=db)
    assert tr.credit_path is not None and tr.credit_path.endswith(
        "credit_ledger.jsonl")
    tr.run_term("t", n_steps=1)
    assert os.path.exists(tr.credit_path), "轮尾应落盘"
    n_disk = len(open(tr.credit_path, encoding="utf-8").readlines())
    # 重启载回（新实例同路径 ⇒ 笔数一致，不翻倍）
    tr2 = TermRunner(judge=Judge(), db_path=db)
    assert len(tr2.credit_ledger.entries()) == n_disk


def test_memory_db_has_no_credit_path():
    """★ :memory: ⇒ 无落盘路径（内存语义不变，现有测试零影响）。"""
    import sys as _sys
    _sys.path.insert(0, os.path.join(ROOT, "src"))
    from dwc.harness.run_term import TermRunner
    from dwc.organs.judge import Judge
    tr = TermRunner(judge=Judge(), db_path=":memory:")
    assert tr.credit_path is None
