# -*- coding: utf-8 -*-
"""R456 · 让 term 用真模型作答（不再拿参考答案给自己判分）。

守四件事：
  1. term 报告带 task 字段（判分面要知道"这轮判的是哪道题"）
  2. 注入 executor 时**只跑当前题**（全量判 = 每 term 6~20 次调用，成本不可控，
     且别的题的结果会混进本 term 的分数）
  3. 当前题不在 anchors 里 ⇒ 回退全量（向后兼容：测试/自由文本调用不变）
  4. 自检模式（无模型）的 term 不许进饱和判据（否则 1.0 又是假的）
"""
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
for _p in (os.path.join(_ROOT, "src"), os.path.join(_ROOT, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from dwc.harness.run_term import TermReport, TermRunner  # noqa: E402


class FakeJudge:
    """只提供 _build_observations 需要的两样东西。"""

    def __init__(self, anchors):
        self.anchors = anchors

    def score(self, split, obs):
        return {"pass_rate": 1.0, "details": []}


class Rc:
    def __init__(self, tid):
        self.detail = {"observed": {tid: []}}


def _runner(tids):
    calls = []

    def exe(task):
        calls.append(task["task_id"])
        return Rc(task["task_id"])

    anchors = {t: {"verifier_kind": "behavior", "checks": []} for t in tids}
    tr = TermRunner(db_path=":memory:", judge=FakeJudge(anchors), executor=exe)
    return tr, calls


def _rep(task):
    return TermReport(term_id="T", chain_id="C", started_at=0.0, task=task)


def test_term_report_carries_task():
    """run_term 必须把题记进报告 —— 判分面不能靠猜。"""
    rep = TermRunner().run_term("hello_task", n_steps=1)
    assert rep.task == "hello_task"


def test_observations_only_current_task():
    tr, calls = _runner(["a", "b", "c"])
    out = tr._build_observations(_rep("b"))
    assert calls == ["b"], "只许跑当前题，实际跑了 %r" % (calls,)
    assert list(out) == ["b"]


def test_observations_fallback_when_task_not_an_anchor():
    """自由文本 / 测试里传的不是题号 ⇒ 保持旧的全量行为。"""
    tr, calls = _runner(["a", "b"])
    tr._build_observations(_rep("自由文本"))
    assert calls == ["a", "b"]


def test_seed_recent_ignores_selfcheck_rows(tmp_path):
    """★ 自检 term（无模型，跑参考答案）的 1.0 不许当饱和证据。"""
    import dwc_agent as A

    p = tmp_path / "log.jsonl"
    rows = [
        {"agent_term": 1, "task": "x", "pass_rate": 1.0},                 # 旧行：无 mode
        {"agent_term": 2, "task": "x", "pass_rate": 1.0, "mode": "selfcheck"},
        {"agent_term": 3, "task": "x", "pass_rate": 0.5, "mode": "llm"},
    ]
    p.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    assert A._seed_recent(str(p)) == [0.5]


def test_seed_recent_keeps_llm_rows(tmp_path):
    import dwc_agent as A

    p = tmp_path / "log.jsonl"
    rows = [{"agent_term": i, "task": "x", "pass_rate": v, "mode": "llm"}
            for i, v in enumerate([1.0, 0.0, 0.5], start=1)]
    p.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    assert A._seed_recent(str(p)) == [1.0, 0.0, 0.5]
