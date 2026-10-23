# -*- coding: utf-8 -*-
"""R119 · 选项3 — dep 字节粒度修正: 触发源回归换代判决（not 字节哈希）。

背景（R115 实测）: 加兼容 kwarg（ε/split_mode）改 judge 源字节 ⇒ fp 变
⇒ 旧档被标 deprecated — 但行为等价（843 全绿支撑）, 且 E2 对拍判决是
incumbent_holds（**从未换代**）。字节粒度过度保守: 每次兼容扩展都误弃。
修正（稿④§⑥ 字面「换评估器只抹依赖记录」）: deprecated_by_evaluator
触发源 = 换代判决（challenger_duel regime_change）; 无判决 ⇒ 漂移档
保持 active + rows.drift 标注（事实可见, 不静默不误弃）。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from dep_scan import scan, split_fingerprint  # noqa: E402
from dwc.foundation.inheritance import judge_fingerprint  # noqa: E402

JUDGE_PATH = os.path.join(ROOT, "src", "dwc", "organs", "judge.py")


def _mk(td, fn, ec):
    json.dump({"inheritance": {"evaluation_config": ec}},
              open(os.path.join(td, fn), "w"))


def test_drift_without_regime_stays_active():
    """★ 核心: 字节漂移但无换代判决 ⇒ active + drift 标注（不误弃）。"""
    cur = judge_fingerprint(JUDGE_PATH)
    with tempfile.TemporaryDirectory() as td:
        # sfp=cur ⇒ split 分支不触发（隔离测 drift 语义）
        _mk(td, "knowledge3_a.json", {"judge_fingerprint": "00000000",
                                      "split_fingerprint": cur})
        rep = scan(td, cur, cur, regime_change=False)
        row = rep["rows"][0]
        assert row["status"] == "active"
        assert row["drift"] is True
        assert "无换代判决" in row["why"]
        assert rep["counts"]["deprecated_by_evaluator"] == 0
        # ★ 换代判决 ⇒ 同一份档立刻弃置（触发源=判决）
        rep2 = scan(td, cur, cur, regime_change=True)
        assert rep2["rows"][0]["status"] == "deprecated_by_evaluator"
        assert rep2["rows"][0]["drift"] is True


def test_real_archive_no_regime_no_evaluator_deprecation():
    """真 archive 扫描: E2 未换代 ⇒ deprecated_by_evaluator 必须 0
    （R115 那 2 档由兼容扩展造成的误弃在此修正后消失 — 漂移可见）。"""
    cur = judge_fingerprint(JUDGE_PATH)
    sfp = split_fingerprint(ROOT)
    rep = scan(os.path.join(ROOT, "archive"), cur, sfp, regime_change=False)
    c = rep["counts"]
    assert c["deprecated_by_evaluator"] == 0, "未换代不许有评估器弃置"
    assert set(c) == {"active", "deprecated_by_evaluator",
                      "deprecated_by_split_change", "pre_depz_legacy"}
    # 对账（count == rows）
    for k in c:
        assert c[k] == sum(1 for r in rep["rows"] if r["status"] == k), k
    # 六段档里的漂移档全部 active（含 R113-R116 的 judge fp≠当前档）
    six = [r for r in rep["rows"]
           if r["status"] != "pre_depz_legacy"]
    assert all(r["status"] in ("active", "deprecated_by_split_change")
               for r in six)
    # 拆分前档（无 split_fingerprint 的 R113-R116）进 split 栏（第二触发源
    # 是**独立于换代**的真实触发: 拆分确实发生了 — R117）
    assert c["deprecated_by_split_change"] >= 1


def test_main_reads_duel_regime():
    """dep_scan.main 从换代账本末条读判决（R120 后: ledger 非 duel.json）。"""
    from dep_scan import read_last_regime
    ledger = os.path.join(ROOT, "archive", "epoch_ledger.jsonl")
    # 账本存在且末条为 incumbent_holds ⇒ False（现判决=从未换代）
    assert os.path.exists(ledger), "R120 常态化账本应在位"
    assert read_last_regime(ledger) is False
    # main 端到端跑
    outp = os.path.join(ROOT, "docs", "dep_scan.json")
    r = subprocess.run([sys.executable,
                        os.path.join(ROOT, "scripts", "dep_scan.py")],
                       capture_output=True, timeout=300, cwd=ROOT)
    assert r.returncode == 0, r.stderr.decode("utf-8", "replace")[-500:]
    d = json.load(open(outp, encoding="utf-8"))
    assert d["counts"]["deprecated_by_evaluator"] == 0
    assert d["current_split_fingerprint"] == split_fingerprint(ROOT)
