# -*- coding: utf-8 -*-
"""R117 · ⑥ HCE 拆分执行 — dev 8+2 / 标签隐藏 / D_val 终评 / dep 第二触发源。

验收（设计稿⑥ §⑦ 写死清单）:
  □ _split 分层规则复算（机械规则可复核）
  □ legacy 默认零破坏（val 任务照判 — 现行为不动）
  □ search 模式: D_val success=None + reason 标签隐藏（不当 0/1）
  □ select 模式: D_val 真判; 短名单必含 current; 平票回落 val_tie_fallback
  □ dep_scan: 四栏 + split_fingerprint 函数 + 拆分前档分栏
  □ gap_search_vs_val 报表出数（hidden_ok + val_judged 断言）
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

ROOT = r"E:/Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from dwc.organs.judge import Judge, JudgeError  # noqa: E402
from dwc.organs.replay import (  # noqa: E402
    ReplayError, select_with_val_fallback, shortlist_candidates)

DEV = json.load(open(os.path.join(ROOT, "config", "anchors", "dev.json"),
                     encoding="utf-8"))


def test_split_rule_recomputes():
    """★ 机械规则复算: 分层(verifier_kind) + 层内字典序末位 = 落盘 val。"""
    sp = DEV["_split"]
    ids = sorted(k for k in DEV if not k.startswith("_"))
    from collections import defaultdict
    groups = defaultdict(list)
    for k in ids:
        groups[DEV[k]["verifier_kind"]].append(k)
    expect_val = sorted(v[-1] for v in
                        (sorted(m) for m in groups.values()))
    assert sorted(sp["val"]) == expect_val, "规则复算 ≠ 落盘"
    assert set(sp["search"]) | set(sp["val"]) == set(ids)
    assert set(sp["search"]) & set(sp["val"]) == set()
    assert len(sp["search"]) == 8 and len(sp["val"]) == 2


def test_legacy_zero_regression():
    """legacy 默认: val 任务照判（830 全量的行为基座, 这里锁拆分面）。"""
    j = Judge()
    assert j.d_val == set(DEV["_split"]["val"])  # 加载正确
    v = j.evaluate("code_fix_006", observed=None)   # 默认 legacy
    assert v.success is None and "observed 为 None" in v.reason


def test_search_mode_hides_val_labels():
    """★ search 模式: D_val ⇒ None+标签隐藏（不当 0/1）; search 集照判。"""
    j = Judge()
    # val 任务 — 隐藏（observed 给了正确 golden 也不许出 True）
    golden = DEV["code_fix_006"]
    v_hidden = j.evaluate("code_fix_006",
                          observed={"_probe": 1}, split_mode="search")
    assert v_hidden.success is None
    assert "标签隐藏" in v_hidden.reason and v_hidden.missing == "d_val_hidden"
    # search 任务 — 正常判
    v_legit = j.evaluate("code_fix_001",
                         observed={"_probe": 1}, split_mode="search")
    assert v_legit.success is False          # 错观测判 False = 真在判
    # 非法 split_mode ⇒ raise
    with pytest.raises(JudgeError, match="split_mode"):
        j.evaluate("code_fix_001", observed={}, split_mode="hedge")


def test_select_mode_judges_val():
    """select 模式: D_val 真判（终评信号源）。"""
    j = Judge()
    v = j.evaluate("reasoning_004", observed=None, split_mode="select")
    assert "observed 为 None" in v.reason    # 无隐藏分支 — 正常判分路径
    assert v.missing != "d_val_hidden"


def test_shortlist_and_fallback_chain():
    """★ 终评链: 短名单必含 current + 三分回落语义。"""
    vs = {"a": 0.9, "b": 0.8, "c": 0.7}
    # 短名单 top-2 不含 current(c) ⇒ 强制并入（§2.7 前提不豁免）
    assert shortlist_candidates(vs, current="c", k=2) == ["a", "b", "c"]
    assert shortlist_candidates(vs, current="a", k=2) == ["a", "b"]
    with pytest.raises(ReplayError, match="必含 current"):
        shortlist_candidates({"a": 1.0}, current="zz", k=2)
    with pytest.raises(ReplayError, match="K 须"):
        shortlist_candidates(vs, current="a", k=0)
    # 终评: v_val 有明确胜者 ⇒ 只用 val 信号
    r = select_with_val_fallback({"a": 0.6, "c": 0.5}, vs, current="c")
    assert r["m_star"] == "a" and r["source"] == "val"
    # v_val 平票 ⇒ 回落 v_search + 诚实标记（不装终评有分辨力）
    r2 = select_with_val_fallback({"a": 0.5, "c": 0.5}, vs, current="c")
    assert r2["source"] == "val_tie_fallback" and r2["tie"] is True
    assert r2["m_star"] == "a"          # 回落 argmax v_search
    # v_val 空 ⇒ 回落 + 不装数
    r3 = select_with_val_fallback({}, vs, current="c")
    assert r3["source"] == "val_empty_fallback"


def test_dep_scan_split_fingerprint_and_four_buckets():
    """dep(z) 第二触发源: split_fingerprint 函数 + 四栏在位。"""
    from dep_scan import scan, split_fingerprint
    cur = split_fingerprint(ROOT)
    assert cur and len(cur) == 8        # dev.json 已有 _split
    # 档判定树: 换代优先 > 拆分 > active（造三份假档验证, 临时目录）
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        def mk(fn, ec):
            json.dump({"inheritance": {"evaluation_config": ec}},
                      open(os.path.join(td, fn), "w"))
        # scan 只认 knowledge3_*.json 前缀（历史档形态约定）
        mk("knowledge3_k1.json", {"judge_fingerprint": cur,      # 指纹同+split同
                                  "split_fingerprint": cur})
        mk("knowledge3_k2.json", {"judge_fingerprint": "00000000",  # 换代
                                  "split_fingerprint": cur})
        mk("knowledge3_k3.json", {"judge_fingerprint": cur,      # 拆分前档(无sfp)
                                  "epoch_id": 1})
        rep = scan(td, cur, cur)
        st = {r["file"]: r["status"] for r in rep["rows"]}
        assert st["knowledge3_k1.json"] == "active"
        assert st["knowledge3_k2.json"] == "deprecated_by_evaluator"  # 换代优先
        assert st["knowledge3_k3.json"] == "deprecated_by_split_change"
        assert rep["counts"]["active"] == 1
        # 拆分未启用(cur_split=None) ⇒ split 栏全 0 如实
        rep2 = scan(td, cur, None)
        assert rep2["counts"]["deprecated_by_split_change"] == 0


def test_gap_report_runs():
    """报表真跑: 隐藏生效 + val 终评真判 + gap 字段出数。"""
    outp = os.path.join(ROOT, "docs", "hce_split_report.json")
    r = subprocess.run([sys.executable,
                        os.path.join(ROOT, "scripts",
                                     "hce_split_report.py")],
                       capture_output=True, timeout=600, cwd=ROOT)
    assert r.returncode == 0, r.stderr.decode("utf-8", "replace")[-600:]
    d = json.load(open(outp, encoding="utf-8"))
    assert d["checks"] == {"hidden_ok": True, "val_judged_in_select": True}
    assert d["gap_search_vs_val"] is not None
    assert d["split"]["val"] == DEV["_split"]["val"]
