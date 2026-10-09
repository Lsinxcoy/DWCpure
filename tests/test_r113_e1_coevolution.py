# -*- coding: utf-8 -*-
"""R113 · E1（裁决②执行轮·记录与约束层）— 判据分层 + 档依赖字段 + epoch 合同 + dep(z)。

验收（设计稿④ §⑧ E1 字面）:
  □ 判据声明字面 = 稿 §④（judge.py 含分层重述关键词）
  □ dep(z) 破坏测试: 换指纹 ⇒ 该档进 deprecated 栏, 其余不动
  □ 段内改评估器 ⇒ raise 探针（EpochGuard 牙齿）
  □ 本级零评估器换代（纯记录/约束 — 行为不回退由全量三层兜底）
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

from dwc.foundation.epoch_guard import (  # noqa: E402
    EpochViolation, EvaluatorEpochGuard)
from dwc.foundation.inheritance import (  # noqa: E402
    InheritanceError, build_inheritance, judge_fingerprint, validate_inheritance)


def _ok(**over):
    base = dict(
        gen=113, parent_gen=112, at="2026-10-09T14:00:00+08:00",
        parent_state={"commits": 118},
        proposed_change={"kind": "patch", "exec_form": "diff ...",
                         "files": ["src/x.py"]},
        motivating_evidence={"refs": [{"type": "test",
                                       "ref": "tests/t.py::test_x",
                                       "claim": "ok"}]},
        evaluation_config={"truth_source": "config/anchors/dev.json",
                           "truth_sha8": "abcd1234",
                           "judge_frozen": True,
                           "judge_fingerprint": "beef0001",   # E1 新增
                           "split_fingerprint": "5a5a1111",  # R117
                           "epoch_id": None,                   # E1 新增
                           "epoch_note": "epoch 合同 E2 生效"},
        acceptance_decision={"gate": "3x", "verdict": "accepted",
                             "evidence_ref": "rc=0"})
    base.update(over)
    return base


def test_judge_declaration_reshaped_verbatim():
    """★ 稿 §④ 判据声明字面: 分层重述进 judge.py（E1 字面验收）。"""
    src = open(os.path.join(ROOT, "src", "dwc", "organs", "judge.py"),
               encoding="utf-8").read()
    for key in ("判据分层（E1 重述", "锚与判分执行", "验收门外部化",
                "评估策略层", "平票在位者", "RQGM 2606.26294",
                "Recuris 2608.24876", "用户裁决: 做"):
        assert key in src, "判据声明缺 %r（稿 §④ 逐字）" % key
    # 旧窄判据被收窄说明替代（不许完全丢失原依据）
    assert "作用域收窄" in src


def test_evaluation_config_requires_dependency_fields():
    """★ 稿 §⑥ 依赖声明: judge_fingerprint 必填 8hex; epoch_id None 必带 note。"""
    inh = build_inheritance(**_ok())
    ec = inh["evaluation_config"]
    assert ec["judge_fingerprint"] == "beef0001"
    assert ec["epoch_id"] is None and ec["epoch_note"]
    # 走 build（构造即校验）— 手搓残缺六段会先撞"六段缺"而非目标判据
    bad = _ok()
    bad["evaluation_config"] = dict(_ok()["evaluation_config"],
                                    judge_fingerprint="XYZ")
    with pytest.raises(InheritanceError, match="judge_fingerprint"):
        build_inheritance(**bad)
    bad2 = _ok()
    bad2["evaluation_config"] = {
        k: v for k, v in _ok()["evaluation_config"].items()
        if k != "epoch_note"}
    with pytest.raises(InheritanceError, match="epoch_note"):
        build_inheritance(**bad2)


def test_epoch_guard_freeze_and_boundary():
    """段内冻结 raise + 点界换代记录（G7 不许无痕）。"""
    g = EvaluatorEpochGuard(3, "aaaa1111")
    g.check("aaaa1111")                       # 一致 ⇒ 过
    with pytest.raises(EpochViolation, match="段内评估器变更被拒"):
        g.check("bbbb2222")                   # 段内改动 ⇒ 牙齿
    with pytest.raises(EpochViolation, match="reason"):
        g.close_epoch("bbbb2222", reason="")  # 无痕换代 ⇒ 拒
    with pytest.raises(EpochViolation, match="在位者相同"):
        g.close_epoch("aaaa1111", reason="x")  # 同指纹非换代 ⇒ 拒
    new_id = g.close_epoch("bbbb2222", reason="challenger 赢对拍")
    assert new_id == 4 and g.judge_fingerprint == "bbbb2222"
    assert len(g.transitions) == 1 and g.to_dict()["n_transitions"] == 1


def test_dep_scan_buckets(tmp_path):
    """★ dep(z) 破坏: 换指纹 ⇒ 该档进 deprecated 栏, 其余栏不动; 只读不改档。"""
    from dep_scan import scan
    # 造三形态: active(当前fp) / 换代(旧fp) / legacy(无字段)
    import io
    cur = judge_fingerprint(os.path.join(ROOT, "src", "dwc", "organs",
                                         "judge.py"))
    d = str(tmp_path)
    mk = lambda name, fp: io.open(os.path.join(d, name), "w",                # noqa: E731
                                  encoding="utf-8").write(json.dumps(
        {"round": name, "inheritance": {
            "gen": 1, "at": "2026-10-09T00:00:00", "parent_gen": None,
            "supersedes": None, "parent_state": {}, "proposed_change": {},
            "motivating_evidence": {}, "acceptance_decision": {},
            "subsequent_use": {"status": "pending", "gap_note": "x"},
            "evaluation_config": {"truth_source": "s", "truth_sha8": "abcd1234",
                                  "judge_frozen": True,
                                  "judge_fingerprint": fp,
                                  "split_fingerprint": "5a5a1111",
                                  "epoch_id": 1}}}))
    mk("knowledge3_a.json", cur)
    mk("knowledge3_b.json", "0ld00000")
    io.open(os.path.join(d, "knowledge3_c.json"), "w").write("[1,2]")
    io.open(os.path.join(d, "knowledge3_l.json"), "w").write('{"round":"old"}')
    before = open(os.path.join(d, "knowledge3_a.json"), encoding="utf-8").read()
    # ★ R119 新语义: 无换代判决 ⇒ 字节漂移(b)不弃置, 保持 active+drift
    rep = scan(d, cur)
    c = rep["counts"]
    assert c["active"] == 2 and c["deprecated_by_evaluator"] == 0
    # list 档被 scan 的 isinstance dict 跳过（inheritance 同款）⇒ legacy 只剩无字段 dict 档
    assert c["pre_depz_legacy"] == 1
    st = {r["file"]: r["status"] for r in rep["rows"]}
    assert st["knowledge3_a.json"] == "active"
    assert st["knowledge3_b.json"] == "active"
    assert next(r for r in rep["rows"]
                if r["file"] == "knowledge3_b.json")["drift"] is True
    # ★ 换代判决发生 ⇒ b 立刻弃置（触发源=判决 not 字节哈希）
    rep_r = scan(d, cur, regime_change=True)
    st_r = {r["file"]: r["status"] for r in rep_r["rows"]}
    assert st_r["knowledge3_b.json"] == "deprecated_by_evaluator"
    assert rep_r["counts"]["deprecated_by_evaluator"] == 1
    # 只读: active 档字节未变
    assert open(os.path.join(d, "knowledge3_a.json"),
                encoding="utf-8").read() == before


def test_dep_scan_script_runs():
    """脚本可跑 + 分栏输出 + 换代前 deprecated=0 不装数。"""
    outp = os.path.join(ROOT, "docs", "dep_scan.json")
    r = subprocess.run([sys.executable,
                        os.path.join(ROOT, "scripts", "dep_scan.py")],
                       capture_output=True, timeout=180, cwd=ROOT)
    assert r.returncode == 0, r.stderr.decode("utf-8", "replace")[-500:]
    rep = json.load(open(outp, encoding="utf-8"))
    assert set(rep["counts"]) == {"active", "deprecated_by_evaluator",
                                  "deprecated_by_split_change",
                                  "pre_depz_legacy"}
    # ★ 计数与 rows 对账（不锁死 0 — 任何 judge 源改动（如 R115 加 ε kwarg）
    #   都会让旧档进 deprecated: 字节粒度的保守正确性; 行为等价由全量绿支撑,
    #   是否恢复 active=用户裁。R115 实测 deprecated=2(R113/R114 档) 即此机制)
    rows = rep["rows"]
    for k in ("active", "deprecated_by_evaluator",
              "deprecated_by_split_change", "pre_depz_legacy"):
        n_rows = sum(1 for r in rows if r["status"] == k)
        assert rep["counts"][k] == n_rows, (k, rep["counts"][k], n_rows)
    assert "不装数" in rep["note"]
    assert "HCE" in rep["split_change"]
