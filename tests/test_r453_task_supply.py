# -*- coding: utf-8 -*-
"""R453 · 任务供给：L1 参数扰动 / L2 fresh 接入 / L3 新函数族。

为什么做：池子只有 16 题、最近 30 个 term 全 1.0 ⇒ 没有失败 ⇒ 没有信号。
进化不是"学得不够"，是"没东西可学"。

纪律：
  · L1 的期望值只能来自 refimpl（已验证），算不出就不生成
  · L1 必须是**真扰动**：新 args 与原 args 不同
  · L2 只搬 fresh.json 现成的题，不改判分口径
  · L3 必须两份独立实现**逐输入一致**才收；不一致就不收（fail-closed）
  · 生成是确定性的：同 seed ⇒ 同题（可复现、可审计）
"""
from __future__ import annotations

import json
import os

import pytest

from dwc.organs import refimpl as R
from dwc.organs import task_supply as S

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEV = os.path.join(ROOT, "config", "anchors", "dev.json")
FRESH = os.path.join(ROOT, "config", "anchors", "fresh.json")


def _dev():
    with open(DEV, encoding="utf-8") as f:
        return json.load(f)


# ── L1 ──────────────────────────────────────────────────────────

def test_l1_generates_self_consistent_checks():
    d = _dev()
    tasks = S.perturb("code_fix_001", d["code_fix_001"], seed=7, n=3)
    assert len(tasks) == 3
    for t in tasks:
        assert t["split"] == "supply" and t["level"] == 1
        assert t["anchor"]["checks"], "没有检查的新题等于没判据"
        for c in t["anchor"]["checks"]:
            assert R.compute(c["fn"], c["args"]) == c["expected"]


def test_l1_args_really_differ_from_original():
    a = _dev()["code_fix_001"]
    old = {c["args"] for c in a["checks"]}
    tasks = S.perturb("code_fix_001", a, seed=11, n=3)
    new = {c["args"] for t in tasks for c in t["anchor"]["checks"]}
    assert new - old, "参数没变 ⇒ 这不是新题，是同一题"


def test_l1_is_deterministic():
    """同 seed ⇒ 同题（created_ts 是生成时刻，不参与内容比较）。"""
    a = _dev()["code_fix_004"]
    x = S.perturb("code_fix_004", a, seed=42, n=2)
    y = S.perturb("code_fix_004", a, seed=42, n=2)
    for t in x + y:
        t.pop("created_ts", None)
    assert json.dumps(x, sort_keys=True) == json.dumps(y, sort_keys=True)


def test_l1_unknown_fn_generates_nothing():
    a = {"prompt": "x", "checks": [{"fn": "no_such_fn", "args": "1", "expected": "1"}]}
    assert S.perturb("t", a, seed=1, n=3) == []


# ── L2 ──────────────────────────────────────────────────────────

def test_l2_admits_all_fresh_tasks():
    tasks = S.from_fresh(FRESH)
    assert len(tasks) == 5
    for t in tasks:
        assert t["level"] == 2 and t["split"] == "supply"
        assert t["anchor"]["checks"]


def test_l2_keeps_original_expected_values():
    with open(FRESH, encoding="utf-8") as f:
        f = json.load(f)
    tasks = {t["task_id"]: t for t in S.from_fresh(FRESH)}
    for tid, a in f.items():
        if tid.startswith("_"):
            continue
        assert tasks[tid]["anchor"]["checks"] == a["checks"]


# ── 队列 ────────────────────────────────────────────────────────

def test_admit_is_idempotent(tmp_path):
    p = str(tmp_path / "q.jsonl")
    a = _dev()["code_fix_003"]
    tasks = S.perturb("code_fix_003", a, seed=3, n=2)
    assert S.admit(tasks, p) == 2
    assert S.admit(tasks, p) == 0          # 同一批再来一次 ⇒ 0
    assert len(S.load_queue(p)) == 2


def test_load_queue_missing_file_is_empty(tmp_path):
    assert S.load_queue(str(tmp_path / "nope.jsonl")) == []


# ── 饱和判据 ────────────────────────────────────────────────────

def test_saturation_detects_all_pass():
    terms = [{"pass_rate": 1.0} for _ in range(30)]
    r = S.saturation(terms)
    assert r["saturated"] is True
    assert r["mean"] == 1.0


def test_saturation_false_when_mixed():
    terms = [{"pass_rate": 1.0}] * 20 + [{"pass_rate": 0.5}] * 10
    assert S.saturation(terms)["saturated"] is False


def test_saturation_empty_is_not_saturated():
    """没有数据 ≠ 饱和（不许凭空样本升难度）。"""
    r = S.saturation([])
    assert r["saturated"] is False and r["n"] == 0


# ── L3 ──────────────────────────────────────────────────────────

_SPEC = json.dumps({"fn": "triple", "prompt": "返回三倍",
                    "impl": "def triple(x):\n    return x * 3"})
_IMPL2 = "def triple(x):\n    return x + x + x"


def _llm(spec=_SPEC, impl=_IMPL2):
    seq = [spec, impl]
    def _f(_p):
        return seq.pop(0) if seq else ""
    return _f


def test_l3_independent_impls_agree_yields_task():
    t = S.generate_family(_llm(), runner=lambda c, f, x: (True, x * 3))
    assert t is not None
    assert t["level"] == 3 and t["verified_by"] == "two_impl_agree"
    assert len(t["anchor"]["checks"]) >= 3
    for c in t["anchor"]["checks"]:
        assert c["expected"] == repr(eval(c["args"]) * 3)


def test_l3_second_call_gets_prompt_not_first_impl():
    """★ 第二份必须只看题面 —— 给了第一份就是抄。"""
    seen = []
    def _f(p):
        seen.append(p)
        return _SPEC if len(seen) == 1 else _IMPL2
    S.generate_family(_f, runner=lambda c, f, x: (True, x * 3))
    assert len(seen) == 2
    assert "返回三倍" in seen[1]
    assert "return x * 3" not in seen[1]


_IMPL_A = json.loads(_SPEC)["impl"]


def test_l3_disagreement_is_rejected():
    """★ 按**代码**区分两份实现（runner 是 A/B 交替调的，按调用计数会错）。"""
    def runner(code, fn, x):
        return (True, x * 3) if code == _IMPL_A else (True, x * 4)
    assert S.generate_family(_llm(), runner=runner) is None


def test_l3_runner_failure_is_rejected():
    assert S.generate_family(_llm(), runner=lambda c, f, x: (False, None)) is None


def test_l3_missing_second_impl_is_rejected():
    assert S.generate_family(_llm(impl="我不知道"), runner=lambda c, f, x: (True, 1)) is None


def test_l3_non_json_spec_is_rejected():
    assert S.generate_family(_llm(spec="随便说点什么"),
                             runner=lambda c, f, x: (True, 1)) is None


def test_l3_too_few_agreements_is_rejected():
    def runner(code, fn, x):
        if x in (3, 5):                       # 只有两个输入两边一致
            return (True, 0)
        return (True, 0) if code == _IMPL_A else (True, 9)
    assert S.generate_family(_llm(), runner=runner, min_agree=3) is None


def test_l3_real_sandbox_runs():
    """★ 不注入 runner 时走真沙箱：证明接线不是假的。"""
    t = S.generate_family(_llm())
    assert t is not None and len(t["anchor"]["checks"]) >= 3
