# -*- coding: utf-8 -*-
"""R458 · 函数类任务的做法来源：成功时把模型自述的 method 写成 skill。

守五件事：
  1. prompt 要求 `_method`（否则模型永远不会说"怎么算的"）
  2. `_method` 能被解析出来；没有就是空串（不猜）
  3. executor 把 method 带进 detail
  4. 观测里带 `★method`（判分前就要有，判分后才决定写不写）
  5. **只有判分通过**才写 skill；失败/空做法一律不写
"""
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if os.path.join(_ROOT, "src") not in sys.path:
    sys.path.insert(0, os.path.join(_ROOT, "src"))

from dwc.harness.run_term import TermReport, TermRunner       # noqa: E402
from dwc.llm.executor import (LLMExecutorFactory, build_observed_prompt,  # noqa: E402
                              parse_method)
from dwc.organs import skill_writer as SW                     # noqa: E402
from dwc.organs.memory import MemoryKernel                    # noqa: E402


# ── 1. prompt ─────────────────────────────────────────────────────────
def test_prompt_asks_for_method():
    p = build_observed_prompt("t1", {"f": [[[1], None]]}, "")
    assert "_method" in p


# ── 2. 解析 ───────────────────────────────────────────────────────────
def test_parse_method_from_json():
    raw = '{"f": [[[1], 2]], "_method": "用等差数列求和公式"}'
    assert parse_method(raw) == "用等差数列求和公式"


def test_parse_method_missing_returns_empty():
    assert parse_method('{"f": [[[1], 2]]}') == ""
    assert parse_method("") == ""
    assert parse_method("完全不是 JSON") == ""


# ── 3. executor 带 method ─────────────────────────────────────────────
class _Res:
    def __init__(self, text):
        self.text = text
        self.error = None


class _FakeLLM:
    def __init__(self, text):
        self.text = text

    def complete(self, prompt, system=None):
        return _Res(self.text)


def test_executor_carries_method_in_detail():
    anchors = {"t1": {"verifier_kind": "behavior",
                      "checks": [{"fn": "f", "args": [1], "expected": 2}]}}
    fac = LLMExecutorFactory(
        _FakeLLM('{"f": [[[1], 2]], "_method": "直接加一"}'), anchors=anchors)
    rc = fac.make(memory=None)({"task_id": "t1"})
    assert rc.detail["observed"] == {"f": [[[1], 2]]}
    assert rc.detail["method"] == "直接加一"


# ── 4. 观测带 ★method ────────────────────────────────────────────────
class _FakeJudge:
    def __init__(self, anchors):
        self.anchors = anchors

    def score(self, split, obs):
        return {"pass_rate": 1.0, "details": []}


class _Rc:
    def __init__(self, tid):
        self.detail = {"observed": {tid: []}, "method": "先乘后加"}


def test_observations_carry_method():
    anchors = {"t1": {"verifier_kind": "behavior", "checks": []}}
    tr = TermRunner(db_path=":memory:", judge=_FakeJudge(anchors),
                    executor=lambda t: _Rc(t["task_id"]))
    out = tr._build_observations(
        TermReport(term_id="T", chain_id="C", started_at=0.0, task="t1"))
    assert out["t1"]["★method"] == "先乘后加"


# ── 5. 只有通过才写 skill ────────────────────────────────────────────
def test_from_term_writes_only_on_pass(tmp_path):
    mem = MemoryKernel(db_path=str(tmp_path / "m.db"))
    assert SW.from_term(mem, "t1", "实现 f", "先乘后加", passed=False) is None
    assert SW.from_term(mem, "t1", "实现 f", "", passed=True) is None
    nid = SW.from_term(mem, "t1", "实现 f", "先乘后加再取整", passed=True)
    assert nid
    assert SW.skill_count(mem) == 1


def test_term_skill_payload_is_d6_complete(tmp_path):
    mem = MemoryKernel(db_path=str(tmp_path / "m.db"))
    SW.from_term(mem, "t1", "实现 f：输入 x 返回 x+1", "直接加一", passed=True)
    row = mem._conn.execute(
        "SELECT payload FROM memory_node WHERE kind='skill'").fetchone()
    d = json.loads(row[0])
    for k in ("scene", "method", "boundary",
              "invalid_conditions", "recovery_strategies"):
        assert d.get(k), "缺 D6 字段 %s" % k
    assert d["m_source"] == "llm_self_report", "自述来源必须可辨"
    assert d["task_id"] == "t1"


def test_term_skill_is_recallable_by_its_own_prompt(tmp_path):
    """写进去的做法，下次同一道题必须召得回来。"""
    from dwc.llm.executor import memory_text
    mem = MemoryKernel(db_path=str(tmp_path / "m.db"))
    prompt = "实现 fresh_range_sum 函数：输入 [a, b] 列表，返回 a 到 b（含）的整数和"
    SW.from_term(mem, "fresh_range_sum", prompt, "先定位边界，再用 range(a,b+1) 求和", passed=True)
    assert "range(a,b+1)" in memory_text(mem, prompt)
