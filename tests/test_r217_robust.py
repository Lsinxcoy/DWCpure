# -*- coding: utf-8 -*-
"""R217 · 鲁棒包: LLM JSON 容错 + 铁律首批仪表（G3/G10 真判）。"""
from __future__ import annotations

import io
import os
import sys

ROOT = r"E:\Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "src"))
from dwc.llm import task_exec as TE                             # noqa: E402
from dwc.foundation import iron_runtime as IR                   # noqa: E402


def test_extract_json_four_shapes():
    """★★★ bench 最大失败单点 llm_format 的容错锁: 四形态全提取 + 空 None。"""
    assert TE._extract_json('{"op":"final","answer":"x"}')["op"] == "final"
    assert TE._extract_json('```json\n{"op":"read","path":"a"}\n```'
                            )["op"] == "read"
    assert TE._extract_json('{"op":"run","cmd":["ls"]}\n好的，我来运行。'
                            )["op"] == "run"
    assert TE._extract_json('前言\n{"op":"write","path":"b"}'
                            )["op"] == "write"
    assert TE._extract_json("") is None
    assert TE._extract_json("完全不是JSON") is None


def test_g3_freeze_instrumented(monkeypatch, tmp_path):
    """★★★ G3 真判（旧 not_instrumented why='frozen 无设置方'已过时 — R208
    后有设置方）: frozen 在场 + 落地 stages ⇒ block; 无冻结 ⇒ pass。"""
    frozen = tmp_path / "frozen"
    monkeypatch.setattr(IR, "FROZEN_PATH", str(frozen))

    class Rep:
        stages = [{"stage": "apply"}]
    # 冻结在场 + 落地 stages ⇒ block（主权被绕过）
    frozen.write_text("x", encoding="utf-8")
    ir = IR.evaluate_for_term(Rep(), certification_limit_present=True)
    ids = {c["id"]: c for c in ir["checked"]}
    assert "G3" in ids and ids["G3"]["verdict"] == "block", ids.get("G3")
    assert "G3" in ir["block"]
    # 无冻结 ⇒ pass（无冻结对象）
    frozen.unlink()
    ir2 = IR.evaluate_for_term(Rep(), certification_limit_present=True)
    ids2 = {c["id"]: c for c in ir2["checked"]}
    assert ids2["G3"]["verdict"] == "pass", ids2.get("G3")


def test_g10_sealed_sha_audit(monkeypatch, tmp_path):
    """★★★ G10 真判: sealed sha 与知识档基准一致 ⇒ pass; 篡改 ⇒ warn 留痕
    （新增锚合法故不 block — 变化必须现形可审）。"""
    sealed = tmp_path / "dev.json"
    sealed.write_text('{"t": 1}', encoding="utf-8")
    sha = IR._sha8(str(sealed))
    monkeypatch.setattr(IR, "SEALED_DEV", str(sealed))
    monkeypatch.setattr(IR, "_last_truth_sha8", lambda: sha)

    class Rep:
        stages = []
    ir = IR.evaluate_for_term(Rep(), certification_limit_present=True)
    ids = {c["id"]: c for c in ir["checked"]}
    assert ids["G10"]["verdict"] == "pass", ids.get("G10")
    sealed.write_text('{"t": 2}', encoding="utf-8")     # 篡改
    ir2 = IR.evaluate_for_term(Rep(), certification_limit_present=True)
    ids2 = {c["id"]: c for c in ir2["checked"]}
    assert ids2["G10"]["verdict"] == "warn" and "G10" in ir2["warn"]
    assert ids2["G10"]["sha_now"] != ids2["G10"]["sha_ledger"]


def test_g10_baseline_comes_from_knowledge_record():
    """★★ 基准外部锚: _last_truth_sha8 来自最新 knowledge3 档（在 git 里 —
    改档=进 git 历史可审计; Layer 22: 首版查错 epoch 账本——那是换代记录）。"""
    base = IR._last_truth_sha8()
    assert len(base) == 8, "基准缺失/异常: %r" % base
