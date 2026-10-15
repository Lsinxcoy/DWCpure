# -*- coding: utf-8 -*-
"""★★★ R285 · R3 浮点铁律规则（deterministic prompt 形态，无需 baseline）。

★ 依据：2606.14249 Definition 2（modified prompt template 是原文认可的
  edit 形态）——改 prompt 不碰源码 ⇒ 不需要 baseline_source。
★ 红线：diffs 必须来自 judge._diff 真调（手拼即编造）；铁律句里的真值
  必须逐字来自 diffs/anchor，不许手写数字。
"""
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(_HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.organs.candidates import CandidateGenerator
from dwc.organs.judge import Judge

_diff = Judge._diff


def _diffs_007():
    """★ 真调 _diff：anchor 007 真 checks＋调用记录形态 observed。

    ★ observed 真形态（judge behavior 口径）：{fn: [[args, actual], ...]}
      —— 传错形态（dict 套 dict）会得"压根没调这个入参"，那是我的输入错，
      不是 _diff 错（已踩一次）。
    """
    golden = {"verifier_kind": "behavior",
              "checks": [{"fn": "average", "args": "[0.1, 0.2]",
                           "expected": "0.15000000000000002"}]}
    observed = {"average": [[[0.1, 0.2], "0.15"]]}
    ds = _diff(golden, observed)
    bad = [d for d in ds if not d.get("ok")]
    assert bad, "前置：真 _diff 必须产出失败条目，否则测试无意义"
    return bad


class TestR3:
    def test_r3_fires_without_baseline(self):
        cg = CandidateGenerator()
        r = cg.generate({"c": "E_VALUE", "q": "wrong_magnitude",
                         "fn": "average"},
                        diffs=_diffs_007(), baseline_source="",
                        fn_name="average")
        assert r["n"] >= 1, "R3 无 baseline 也必须产候选：%s" % r.get("why")
        assert any(c.rule.startswith("R3_") for c in r["candidates"])

    def test_r3_patch_quotes_truth_verbatim(self):
        cg = CandidateGenerator()
        r = cg.generate({"c": "E_VALUE", "q": "wrong_magnitude",
                         "fn": "average"},
                        diffs=_diffs_007(), baseline_source="",
                        fn_name="average")
        c3 = [c for c in r["candidates"] if c.rule.startswith("R3_")][0]
        assert "0.15000000000000002" in c3.patch  # 真值逐字来自 diffs
        assert c3.source == "deterministic"
        assert c3.component == "prompt" and c3.dimension == "D7"
        assert len(c3.grounding) >= 1  # 纪律②：每条必带 grounding

    def test_r3_silent_on_unrelated(self):
        """★ 非浮点截断类 diffs ⇒ R3 不产（不硬凑，纪律③）。"""
        cg = CandidateGenerator()
        r = cg.generate({"c": "E_X", "q": "q", "fn": "f"},
                        diffs=[{"fn": "f", "args": "1", "expected": "a",
                                "actual": "b", "ok": False}],
                        baseline_source="", fn_name="f")
        assert not any(c.rule.startswith("R3_") for c in
                       r.get("candidates", []))

    def test_r3_bool_never_triggers(self):
        """★ bool 不许进 float 口径（True==1.0 是陷阱，必须拒）。"""
        cg = CandidateGenerator()
        r = cg.generate({"c": "E_X", "q": "q", "fn": "f"},
                        diffs=[{"fn": "f", "args": "1", "expected": True,
                                "actual": 1, "ok": False}],
                        baseline_source="", fn_name="f")
        assert not any(c.rule.startswith("R3_") for c in
                       r.get("candidates", []))

    def test_r3_rejects_empty_diffs_loud(self):
        """★ 纪律①：无 diffs ⇒ 显式 empty（n=0＋why 非空），不静默 []。"""
        cg = CandidateGenerator()
        r = cg.generate({"c": "E_X", "q": "q", "fn": "f"}, diffs=[],
                        baseline_source="", fn_name="f")
        assert r["n"] == 0 and r["candidates"] == []
        assert "纪律①" in r["why"]


def test_candidate_without_grounding_is_rejected():
    """★ 真行为：无 grounding 的 Candidate 构造即抛（纪律②硬门）。

    ★ raises 配额：1/6≈17%（纪律 floor 5%）。
    """
    from dwc.organs.candidates import Candidate, CandidateError
    with pytest.raises(CandidateError, match="grounding"):
        Candidate(patch="p", source="deterministic", rule="R",
                  target="f", grounding=[])
