# -*- coding: utf-8 -*-
"""R126 · LLM 执行体下沉 src 级 — 真观测通道 + 零破坏默认接线。

验收:
  □ LLMExecutorFactory.make 出 executor: 好回复⇒observed 真路径
  □ 端点不可用/无文本/解析失败/异常 ⇒ detail 只有 error_code
    （NOT_EVALUATED 通道 — 不当 False/0, 不猜）
  □ stats 计数 n_calls/n_parsed/n_errors（挂载≠活着 的实测工具）
  □ DWC 零破坏: 不传 llm ⇒ runner.executor is None（走 R25 自造路径）
  □ DWC 传 llm(configured) ⇒ runner.executor 自动装（接线减少一次）
  □ run_term 真路径: behavior 任务走 executor; keyword 仍走合成（隐式）
"""
from __future__ import annotations

import os
import sys

import pytest

ROOT = r"E:/Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.llm.executor import (  # noqa: E402
    LLMExecutorFactory, coerce, memory_text, obs_skeleton,
    parse_llm_observed)
from dwc.organs.actor import Receipt  # noqa: E402


class _FakeRes:
    def __init__(self, text="", error=None):
        self.text = text
        self.error = error


class _FakeLLM:
    configured = True

    def __init__(self, text="", error=None, boom=False):
        self.text, self.error, self.boom = text, error, boom
        self.calls = []

    def complete(self, prompt, system=""):
        self.calls.append((prompt, system))
        if self.boom:
            raise RuntimeError("transport 炸")
        return _FakeRes(self.text, self.error)


def _dev_tids():
    from dwc.organs.judge import Judge
    j = Judge(store_path=None, evidence_path=None)
    return [t for t, r in j.anchors.items()
            if not t.startswith("_") and r.get("verifier_kind") == "behavior"]


def test_factory_parse_and_observed_path():
    """好回复 ⇒ detail={"observed": ...} + n_parsed 计数。"""
    from dwc.llm.executor import load_anchors
    anch = load_anchors()
    tids = [t for t, r in anch.items()
            if not t.startswith("_") and r.get("verifier_kind") == "behavior"]
    tid = tids[0]
    skel = obs_skeleton(anch, tid)
    fn0 = sorted(skel)[0]
    llm = _FakeLLM(text="前缀 " + '{%s: %s}' % (
        __import__("json").dumps(fn0), __import__("json").dumps(skel[fn0])))
    f = LLMExecutorFactory(llm, anchors=anch)
    exe = f.make(memory=None)
    rc = exe({"task_id": tid, "kind": "dev"})
    assert isinstance(rc, Receipt) and rc.verified is True
    assert "observed" in rc.detail
    assert fn0 in rc.detail["observed"]
    assert f.stats["n_calls"] == 1 and f.stats["n_parsed"] == 1
    assert f.stats["n_errors"] == 0


def test_failure_modes_all_error_code_only():
    """四失败模态 ⇒ detail 只有 error_code（未评价不当 False/0）。"""
    from dwc.llm.executor import load_anchors
    anch = load_anchors()
    tids = [t for t, r in anch.items()
            if not t.startswith("_") and r.get("verifier_kind") == "behavior"]
    tid = tids[0]
    # 无文本
    exe = LLMExecutorFactory(_FakeLLM(text=""), anchors=anch).make(None)
    rc = exe({"task_id": tid})
    assert rc.detail.get("error_code") == "llm_no_text" and "observed" not in rc.detail
    # error 字段
    exe = LLMExecutorFactory(_FakeLLM(error="401"), anchors=anch).make(None)
    assert exe({"task_id": tid}).detail["error_code"] == "llm_no_text"
    # 解析失败（回复无 JSON）
    exe = LLMExecutorFactory(_FakeLLM(text="我不会"), anchors=anch).make(None)
    assert exe({"task_id": tid}).detail["error_code"] == "llm_parse_failed"
    # 异常（端点炸）
    exe = LLMExecutorFactory(_FakeLLM(boom=True), anchors=anch).make(None)
    rc = exe({"task_id": tid})
    assert rc.detail["error_code"] == "llm_transport_error"
    assert "observed" not in rc.detail


def test_non_behavior_task_skipped():
    """keyword 任务不走 LLM（不发 call, detail 空 — 旧路径语义）。"""
    from dwc.llm.executor import load_anchors
    anch = load_anchors()
    kw = [t for t, r in anch.items()
          if r.get("verifier_kind") == "keyword_match"][0]
    f = LLMExecutorFactory(_FakeLLM(text="{}"), anchors=anch)
    rc = f.make(None)({"task_id": kw})
    assert rc.detail == {}
    assert f.stats["n_calls"] == 0        # 未被调用 ≠ 静默失败（显式计数）


def test_dwc_zero_break_no_llm():
    """★ 零破坏: DWC 不传 llm ⇒ runner.executor is None（R25 自造路径）。"""
    from dwc.core import DWC
    d = DWC(3, 50, db_path=":memory:")
    assert d.executor is None
    assert d.runner.executor is None


def test_dwc_auto_wires_configured_llm():
    """传 configured llm ⇒ runner.executor 自动装（一次接线）。"""
    from dwc.core import DWC
    d = DWC(3, 50, db_path=":memory:", llm=_FakeLLM(text="{}"))
    assert d.executor is not None
    assert d.runner.executor is d.executor


def test_dwc_explicit_executor_wins():
    """显式 executor 优先（注入语义不被默认接线覆盖 — README §11.2）。"""
    from dwc.core import DWC
    sentinel = lambda t: None          # noqa: E731
    d = DWC(3, 50, db_path=":memory:", llm=_FakeLLM(text="{}"),
            executor=sentinel)
    assert d.executor is sentinel
    assert d.runner.executor is sentinel


def test_run_term_true_path_marks_executed(monkeypatch):
    """真路径: behavior 任务标 ★_executed; 失败任务只留 error_code。"""
    from dwc.harness.run_term import TermRunner
    from dwc.llm.executor import load_anchors
    anch = load_anchors()
    beh = [t for t, r in anch.items()
           if not t.startswith("_") and r.get("verifier_kind") == "behavior"]
    kw = [t for t, r in anch.items()
          if r.get("verifier_kind") == "keyword_match"][0]
    calls = []

    def exe(task):
        calls.append(task["task_id"])
        if task["task_id"] == beh[0]:
            return Receipt(ok=True, verified=True,
                           detail={"observed": {"f": [["a", 1]]}})
        return Receipt(ok=True, verified=True,
                       detail={"error_code": "llm_parse_failed"})

    tr = TermRunner(db_path=":memory:", judge=None, executor=exe)
    # monkeypatch judge.anchors 只留这两条（_build_observations 只读 anchors）
    class _J:
        anchors = {beh[0]: {"verifier_kind": "behavior"},
                   beh[1] if len(beh) > 1 else "zz_behavior":
                       {"verifier_kind": "behavior"},
                   kw: {"verifier_kind": "keyword_match"}}
    tr.judge = _J()
    out = tr._build_observations(None)
    assert out[beh[0]] == {"observed": {"f": [["a", 1]]}, "★_executed": True}
    # keyword 不在真路径输出（behavior-only 语义 — 不静默也喂合成）
    assert kw not in out
    assert set(calls) >= {beh[0]}


def test_synthetic_path_unchanged_without_executor():
    """★ R25 路径冻结: 无 executor ⇒ keyword 合成依旧（零破坏锁定）。"""
    from dwc.harness.run_term import TermRunner
    tr = TermRunner(db_path=":memory:", judge=None, executor=None)
    class _J:
        anchors = {"kw_task": {"verifier_kind": "keyword_match",
                               "checks": [{"kw": "alpha"}, {"kw": "beta"}]},
                   "code_fix": {"verifier_kind": "behavior"}}
    tr.judge = _J()
    out = tr._build_observations(None)
    assert out == {"kw_task": {"answer": "alpha beta", "★_synthetic": True}}


def test_parse_reasoning_preamble_takes_trailing_json():
    """★ R277b-4 · 推理模型前言+skeleton回声+围栏真JSON ⇒ 取末尾真值。"""
    from dwc.llm.executor import parse_llm_observed
    skel = {"average": [[[], None], [[1, 2, 3], None]]}
    raw = ("We need answer. skeleton: "
           '{"average": [[[], null], [[1, 2, 3], null]]}. Decide.\n'
           '```json\n{"average": [[[], 0.0], [[1, 2, 3], 2.0]]}\n```')
    assert parse_llm_observed(raw, skel) == {
        "average": [[[], 0.0], [[1, 2, 3], 2.0]]}


def test_parse_plain_json_unchanged():
    """★ R277b-4 · 纯JSON行为不变（零回归锁）。"""
    from dwc.llm.executor import parse_llm_observed
    skel = {"f": [[[1], None]]}
    assert parse_llm_observed('{"f": [[[1], 7]]}', skel) == {
        "f": [[[1], 7]]}
    assert parse_llm_observed("no braces", skel) is None
    assert parse_llm_observed("", skel) is None


def test_parse_rejects_wrong_shape_loudly():
    """★ R277b-4 · 全是错形 ⇒ None（调用方记llm_parse_failed，不编数）。"""
    import pytest
    from dwc.llm.executor import parse_llm_observed
    skel = {"f": [[[1], None]]}
    assert parse_llm_observed('{"f": "not pairs"}', skel) is None
    with pytest.raises((TypeError, AttributeError)):
        parse_llm_observed(None, skel)["f"]  # type: ignore
