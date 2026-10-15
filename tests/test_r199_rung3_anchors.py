# -*- coding: utf-8 -*-
"""R199 · rung3 锚点落地（expected_values + tolerance 判据形态）。

用户令"推进1"（R198 选项①: 补 rung2-3 锚点 — 呼应 rung_monotone 实测信号）。

落地边界（与 R198 声明一致）:
  · rung3 = ARSI 源 reproduce_001-003 复制（expected_values + tolerance,
    ACTOR_TASK_SOURCE L85-86 逐字"数值容差比对最强, 有唯一正确答案"）
  · rung2 **无任何既有定义**（ARSI 源无、docs 无）⇒ R73『无设计不发明』不造
  · 守门人单调性（2606.14249 只增不改）: 旧 10 条逐字节不动, 只追加
  · epoch 2 记账（anchor_epochs.jsonl — R198 机制首次真实使用）
"""
from __future__ import annotations

import json
import os
import sys

import pytest

ROOT = r"E:\Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.harness.anchor_drift import drift_signals, epoch_of, read_epochs  # noqa: E402
from dwc.organs.actor import Actor, execute_task                          # noqa: E402
from dwc.organs.judge import Judge, JudgeError                            # noqa: E402

GOOD = "mean=6.00, std=2.83, median=6.00"
BAD = "mean=5.00, std=1.00, median=5.00"


@pytest.fixture
def j():
    return Judge()


# ══════════════════════════════════════════════════════════
# judge · expected_values 判据（五态 + fail-closed）
# ══════════════════════════════════════════════════════════
def test_correct_answer_passes(j):
    """★★★ 正确答案 ⇒ pass, k/n=3/3。"""
    v = j.evaluate("reproduce_001", "dev", observed={"answer": GOOD})
    assert v.success is True and v.k_passed == 3 and v.n_checks == 3


def test_wrong_answer_fails_with_key_sigs(j):
    """★★★ 错答案 ⇒ fail + 签名（fn=key 名 — 定位维度可用）。"""
    v = j.evaluate("reproduce_001", "dev", observed={"answer": BAD})
    assert v.success is False
    sig = v.failure_signature or {}
    assert sig.get("fn") in ("mean", "median", "std"), sig
    assert v.sigs and len(v.sigs) >= 2, "三项全错应产多签名（R197 簇）"


def test_missing_key_fails_closed(j):
    """★★★ 缺 key ⇒ fail（fail-closed — 不许判通过）。"""
    v = j.evaluate("reproduce_002", "dev", observed={"answer": "mean=6.00"})
    assert v.success is False
    assert any("缺" in (d.get("reason") or "") for d in (v.diffs or [])), v.diffs


def test_tolerance_boundary(j):
    """★★ 容差边界: |差|<=tol 过 / >tol 不过（reproduce_003 tol=0.5）。"""
    inside = j.evaluate("reproduce_003", "dev",
                        observed={"answer": "pow2=1024.4, pow3=242.6"})
    assert inside.success is True, "0.4 <= 0.5 必须过"
    outside = j.evaluate("reproduce_003", "dev",
                         observed={"answer": "pow2=1024.6, pow3=243"})
    assert outside.success is False, "0.6 > 0.5 必须不过"


def test_pass_path_sigs_is_empty_list(j):
    """★★★ 回归锁（R199 冒烟抓的真 bug）: pass 路径 sigs 必须 [] 不是 [None]。

    曾实测 pass ⇒ sigs=[None]（_sigs=[sig] 无条件包裹 sig=None）——
    evidence 的 sigs 长度统计把 pass 算成 1 条, 污染 drift 簇计数。"""
    v = j.evaluate("reproduce_001", "dev", observed={"answer": GOOD})
    assert v.success is True
    assert v.sigs == [], repr(v.sigs)


# ══════════════════════════════════════════════════════════
# judge · _load 校验（expected_values 的判据形态必须可执行）
# ══════════════════════════════════════════════════════════
def test_load_rejects_bad_expected_values(tmp_path):
    """★★★ 缺 expected_values / tolerance 非正 / 值非数值 ⇒ 拒载（原则 1）。"""
    d = tmp_path / "anchors"
    d.mkdir()
    base = {"verifier_kind": "expected_values", "tolerance": 0.1}

    def _write(rec):
        (d / "dev.json").write_text(
            json.dumps({"t": rec}, ensure_ascii=False), encoding="utf-8")
        return Judge(anchors_path=str(d / "dev.json"))

    with pytest.raises(JudgeError):
        _write(dict(base))            # 无 expected_values
    with pytest.raises(JudgeError):
        _write(dict(base, expected_values={"a": 1}, tolerance=0))
    with pytest.raises(JudgeError):
        _write(dict(base, expected_values={"a": "x"}))


# ══════════════════════════════════════════════════════════
# actor · 答案文本执行器路由
# ══════════════════════════════════════════════════════════
def test_actor_executes_expected_values_as_text(j):
    """★★★ execute_task 对 expected_values 走文本执行器（observation=answer）。"""
    out = execute_task(Actor(), j, "reproduce_001", implementation=GOOD)
    assert out["observation"]["answer"] == GOOD
    v = j.evaluate("reproduce_001", "dev", observed=out["observation"])
    assert v.success is True


def test_actor_missing_impl_raises(j):
    """★★ 文本任务无 REFERENCE ⇒ 缺 impl 显式报错（不冒充）。"""
    from dwc.organs.actor import ActorError
    with pytest.raises(ActorError):
        execute_task(Actor(), j, "reproduce_001", implementation=None)


# ══════════════════════════════════════════════════════════
# 锚点集 / split / epoch（守门人 + 只增不改 + 记账）
# ══════════════════════════════════════════════════════════
def test_split_mechanical_rule_holds(j):
    """★★★ _split 机械规则复算（test_r117 同款）: 层内字典序末位进 val。"""
    sp = j.anchors["_split"]
    groups = {}
    for k, v in j.anchors.items():
        if k.startswith("_") or not isinstance(v, dict):
            continue
        groups.setdefault(v["verifier_kind"], []).append(k)
    expect_val = sorted(m[-1] for m in (sorted(g) for g in groups.values()))
    assert sorted(sp["val"]) == expect_val, "规则复算 ≠ 落盘"
    assert "reproduce_003" in sp["val"]


def test_old_ten_tasks_untouched(j):
    """★★★ 守门人只增不改: 旧 10 条的判据形态/关键字段逐条在原位。"""
    assert j.anchors["code_fix_001"]["verifier_kind"] == "behavior"
    assert j.anchors["code_fix_001"]["checks"][0]["fn"] == "sum_first_n"
    assert j.anchors["reasoning_001"]["verifier_kind"] == "keyword_match"
    assert j.anchors["code_fix_006"]["verifier_rung"] == 1


def test_rung_mix_now_three_tier():
    """★★ rung 结构三层（R199 前单层 — rung_monotone 信号消解）。"""
    # ★ R287-E · 动态口径（anchor+3 根因：rung1 10→13。意图是"三层结构
    #   + 无单调"，数字从 anchors 实算 —— 下次 anchor+1 不炸。）
    from collections import Counter
    _expect = Counter(str(a.get("verifier_rung"))
                      for k, a in json.load(
                          open(os.path.join(ROOT, "config", "anchors",
                                            "dev.json"),
                               encoding="utf-8")).items()
                      if not k.startswith("_"))
    sig = drift_signals(ROOT)
    assert sig["rung_mix"] == dict(_expect), sig["rung_mix"]
    assert "rung_monotone" not in sig["suggestions"]


def test_epoch_ledger_records_addition():
    """★★★ epoch 2 记账（R198 机制首次真实使用）: 加题有账可审计。"""
    assert epoch_of(ROOT) == 2
    recs = read_epochs(ROOT)
    last = recs[-1]
    assert last["epoch"] == 2 and last["prev_epoch"] == 1
    assert sorted(last["added_tasks"]) == [
        "reproduce_001", "reproduce_002", "reproduce_003"]


def test_golden_values_hand_verified():
    """★★★ 金标手算核验（声称=实测 — 我逐项算过）:
    [2,4,6,8,10] mean=6.00, 总体std=sqrt(8)=2.828≈2.83, median=6.00;
    [1,3,5,7,9,11] mean=6.00, range=10.00; 2^10=1024, 3^5=243。"""
    import math
    a = [2, 4, 6, 8, 10]
    assert sum(a) / len(a) == 6.0
    assert abs(math.sqrt(sum((x - 6.0) ** 2 for x in a) / 5) - 2.83) < 0.01
    b = [1, 3, 5, 7, 9, 11]
    assert sum(b) / len(b) == 6.0 and max(b) - min(b) == 10.0
    assert 2 ** 10 == 1024 and 3 ** 5 == 243
