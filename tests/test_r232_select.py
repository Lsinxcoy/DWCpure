# -*- coding: utf-8 -*-
"""R232 · bench 预测式选择：确定性 / λ 两端极限 / dial 校验 / 记录面。"""
from __future__ import annotations

import io
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from dwc.organs.predictor import OutcomePredictor              # noqa: E402
from dwc.foundation import dial_config as D                    # noqa: E402
import pytest                                                   # noqa: E402


def _tasks(*ids):
    return [{"id": i, "task": "t", "verifier": "classes"} for i in ids]


def _pred(tmp_path, seq):
    p = OutcomePredictor(log_path=str(tmp_path / "p.jsonl"))
    for tid, ok in seq:
        p.observe("bench:" + tid, ok)
    return p


def test_selection_deterministic(tmp_path, monkeypatch):
    """★★★ 选择确定性锁: 同一预测状态两次选择序列完全一致（含平局按 ID 升序）。"""
    import dwc_bench as B
    p = _pred(tmp_path, [("a", True), ("a", True), ("b", False)])
    ts = _tasks("c", "a", "b")
    s1 = [t["id"] for t in B.bench_select(ts, 0.5, predictor=p)]
    s2 = [t["id"] for t in B.bench_select(list(ts), 0.5, predictor=p)]
    assert s1 == s2
    # 手算 score=p̂+0.5·unc（unc=1/(α+β), 先验 α=β=1 ⇒ unc=0.5）:
    # a(0.75+0.125=0.875) > c(0.5+0.25=0.75) > b(1/3+1/6=0.5)
    assert s1 == ["a", "c", "b"], s1


def test_lambda_extremes(tmp_path):
    """★★ λ 两端极限: λ=0 ⇒ 纯 p̂ 排序; λ 极大 ⇒ 纯不确定性排序。"""
    import dwc_bench as B
    # a 高成功率低不确定(多观测), z 全先验(高不确定)
    p = _pred(tmp_path, [("a", True)] * 10)
    ts = _tasks("z", "a")
    pure_util = [t["id"] for t in B.bench_select(ts, 0.0, predictor=p)]
    assert pure_util[0] == "a", pure_util          # λ=0: p̂=0.917 > 0.5
    pure_exp = [t["id"] for t in B.bench_select(ts, 100.0, predictor=p)]
    assert pure_exp[0] == "z", pure_exp            # λ大: unc(先验1.0) > unc(0.077)


def test_dial_validation(tmp_path):
    """★★ dial 校验锁: bench 段必填且合法（λ>=0, mode∈{auto,full}）。"""
    import yaml
    drift = yaml.safe_load(io.open(
        os.path.join(ROOT, "config", "drift.yaml"), encoding="utf-8"))
    drift["drift"]["bench"]["select_mode"] = "bogus"
    bad = tmp_path / "drift.yaml"
    bad.write_text(yaml.safe_dump(drift, allow_unicode=True), encoding="utf-8")
    with pytest.raises(D.DialError, match="select_mode"):
        D.load_drift(path=str(bad))


def test_bench_records_select_mode(tmp_path, monkeypatch):
    """★★ 记录面锁: --select predictor 跑 --only 单任务 ⇒ 结果文件带
    select_mode/λ（A/B 对照分析靠它分组 — 不记录=对照无法做）。"""
    import dwc_bench as B
    work = str(tmp_path)
    monkeypatch.setattr(B, "WORK", work)
    monkeypatch.setattr(B, "VAR", work)
    monkeypatch.setattr(B, "ROOT", ROOT)
    monkeypatch.setattr(B, "LLMClient", lambda: type("L", (), {
        "configured": False, "complete": lambda *a, **k: {
            "ok": False, "error": "unconfigured"}})())
    rc = B.main(["dwc_bench.py", "--only", "classes", "--timeout", "20",
                 "--select", "predictor"])
    assert rc == 0
    out = json.loads(io.open(os.path.join(work, "dwc_bench_results.json"),
                             encoding="utf-8").read())
    assert out["select_mode"] == "predictor" and out["select_lambda"] == 0.5
