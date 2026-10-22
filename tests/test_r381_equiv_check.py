# -*- coding: utf-8 -*-
"""R381 · 判据不许验"写法"（等价形式必须算对）。

★★★ 现场取证（2026-10-20 第 0 步实验）:
  `rf01` 问「DWC 一行安装命令中，PowerShell 需要 TrimStart 的字符码是
  什么？只答字符码。」判据是 `{"type":"contains","target":"0xfeff"}`。
  模型答 **`65279`** —— `65279 == 0xFEFF` 是同一个字符码，**答对了**，
  却被判 ✗。

  ⇒ 判据验的是"写法"不是"答案"。这类判据缺陷会**系统性低估通过率**，
    而且伪装成"能力不足"（看起来像模型答错）。

★ 判据（本轮锁的）:
  · `contains_equiv` 任一等价形式命中即通过（大小写不敏感）
  · `rf01` 的判据必须包含十进制 `65279`
  · 不相干的答案不许被放行（不能修成恒真）
"""
from __future__ import annotations

import importlib.util
import json
import os

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_b2():
    p = os.path.join(ROOT, "scripts", "dwc_bench2.py")
    spec = importlib.util.spec_from_file_location("dwc_bench2_r381", p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.fixture()
def B2():
    return _load_b2()


# ─────────────────────── ① contains_equiv 语义


def test_equiv_accepts_decimal_form(B2):
    """★★★ 65279 必须算对（== 0xFEFF，现场判死的真因）。"""
    ck = {"type": "contains_equiv", "target": ["0xfeff", "65279"]}
    ok, how = B2.verify(ck, "65279")
    assert ok is True, "十进制 65279 被判 ✗ —— 判据验的是写法不是答案"


def test_equiv_accepts_hex_form(B2):
    """★★ 十六进制原形当然要算对。"""
    ck = {"type": "contains_equiv", "target": ["0xfeff", "65279"]}
    ok, _ = B2.verify(ck, "0xFEFF")
    assert ok is True


def test_equiv_case_insensitive(B2):
    """★★ 大小写不敏感（0xFEFF / 0xfeff 是同一个）。"""
    ck = {"type": "contains_equiv", "target": ["0xfeff", "65279"]}
    assert B2.verify(ck, "0xFEFF")[0] is True
    assert B2.verify(ck, "0XFEFF")[0] is True


def test_equiv_accepts_answer_inside_sentence(B2):
    """★★ 答案嵌在句子里也要算对（模型常带解释）。"""
    ck = {"type": "contains_equiv", "target": ["0xfeff", "65279"]}
    ok, _ = B2.verify(ck, "需要 TrimStart 的字符码是 65279（即 0xFEFF）")
    assert ok is True


def test_equiv_rejects_wrong_answer(B2):
    """★★★ 不许修成恒真 —— 错答案必须仍判 ✗。"""
    ck = {"type": "contains_equiv", "target": ["0xfeff", "65279"]}
    for bad in ("47", "65280", "0xfe00", "不知道", ""):
        ok, _ = B2.verify(ck, bad)
        assert ok is False, "错答案 %r 被放行了（判据被修成恒真）" % bad


# ─────────────────────── ② 任务定义锁


def test_rf01_check_accepts_decimal():
    """★★★ rf01 的判据必须含十进制 65279（否则仍会误判）。"""
    found = None
    for line in open(os.path.join(ROOT, "config", "eval_tasks.jsonl"),
                     encoding="utf-8"):
        if not line.strip():
            continue
        t = json.loads(line)
        if t["id"] == "rf01":
            found = t
            break
    assert found is not None, "找不到 rf01"
    ck = found["check"]
    assert ck["type"] == "contains_equiv", (
        "rf01 判据仍是 %r —— 十进制答案会被判死" % ck.get("type"))
    assert "65279" in ck["target"], "缺十进制 65279"
    assert "0xfeff" in [x.lower() for x in ck["target"]], "缺十六进制原形"


def test_all_eval_checks_are_valid_types():
    """★★ 全池判据类型必须是 verify() 支持的（防写了不支持的 type）。"""
    supported = {"contains", "regex", "contains_any", "contains_all",
                 "contains_equiv", "first_key", "rc_and_contains",
                 "file_contains", "file_contains_all", "file_lines"}
    bad = []
    for line in open(os.path.join(ROOT, "config", "eval_tasks.jsonl"),
                     encoding="utf-8"):
        if not line.strip():
            continue
        t = json.loads(line)
        ty = (t.get("check") or {}).get("type")
        if ty not in supported:
            bad.append((t["id"], ty))
    assert not bad, "未知判据类型: %r" % bad


def test_eval_jsonl_all_parse():
    """★★ 全池 JSONL 必须可解析（改判据时防手滑）。"""
    n = 0
    for line in open(os.path.join(ROOT, "config", "eval_tasks.jsonl"),
                     encoding="utf-8"):
        if line.strip():
            json.loads(line)
            n += 1
    assert n == 52, "任务数变了: %d（应为 52）" % n
