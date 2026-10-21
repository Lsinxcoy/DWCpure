# -*- coding: utf-8 -*-
"""R409 · evidence.jsonl 的一条坏行不许炸掉整个漂移看板。

★★★ 现场（2026-10-21 09:1x，全量回归 4 红）：
    `config/anchors/evidence.jsonl` 第 107 行是半截尾巴
    （`压根没跑这个函数 'word_count'", "n_failed": ...`），
    `drift_signals()` 里 `[json.loads(l) for l in open(ev)]` 直接抛
    JSONDecodeError ⇒ `dwc_anchor_drift_watch` 退出码 2 ⇒
    test_r198 / test_r199 / test_r202 四个健康探针全红。

    台账是 append-only：历史坏行清不掉，也不能让一行坏数据把
    整个健康看板打挂（这正是"探针自己变成故障源"）。

★ 修法：逐行 try/except，坏行跳过；数据侧也清掉了那条坏行。
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.harness.anchor_drift import drift_signals  # noqa: E402


def _mk(tmp_path, lines):
    d = tmp_path / "config" / "anchors"
    d.mkdir(parents=True)
    (d / "evidence.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (d / "dev.json").write_text(json.dumps({"items": []}), encoding="utf-8")
    return str(tmp_path)


def test_bad_line_does_not_crash(tmp_path):
    """★★★ 一条半截 JSON ⇒ 不抛异常，好行照常统计。"""
    root = _mk(tmp_path, [
        json.dumps({"task_id": "a", "split": "dev", "success": True}),
        '压根没跑这个函数 \'word_count\', "n_failed": "2"',   # 半截尾巴
        json.dumps({"task_id": "a", "split": "dev", "success": False}),
    ])
    sig = drift_signals(root)          # 不许抛
    assert isinstance(sig, dict)
    # dev 两行有效（1 成功 1 失败）⇒ 通过率 0.5
    assert abs(float(sig.get("dev_pass_rate", -1)) - 0.5) < 1e-9, sig


def test_clean_file_unchanged(tmp_path):
    """★★ 全好行 ⇒ 结果与旧行为一致（零破坏）。"""
    root = _mk(tmp_path, [
        json.dumps({"task_id": "b", "split": "dev", "success": True}),
        json.dumps({"task_id": "b", "split": "dev", "success": True}),
    ])
    sig = drift_signals(root)
    assert abs(float(sig.get("dev_pass_rate", -1)) - 1.0) < 1e-9, sig
