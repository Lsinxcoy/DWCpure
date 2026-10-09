# -*- coding: utf-8 -*-
"""R114 · M1 — 单点纪律升级（路径乙 attribution_plan）+ 四跑消融归因。

验收（设计稿③ §⑧ M1 字面）:
  □ 路径乙: 合法 plan 多改过 / 缺字段·成员重复·τ无注记 raise（同款严厉）
  □ 路径甲零破坏: 无 plan 单点照旧过, 无 plan 多处原消息 raise
  □ 四跑三读数出数 + τ 分流边界（|I|<τ additive / ≥τ interactive / 负 I 补偿）
  □ 恒等如实（structural-inevitability caveat 在位, 不冒充可加性发现）
  □ 六段档 attribution 可选段: 带则四件齐, 单点档不带合法
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

from dwc.organs.evolver import EvolverError, Proposal  # noqa: E402
from dwc.foundation.inheritance import (  # noqa: E402
    InheritanceError, build_inheritance)


def _proposal(**over):
    base = dict(proposal_id="p1", failure_signature={"c": "E", "q": "n",
                                                     "m": "m"},
                component="memory", target="organs/memory.py::remember",
                patch="+x = 1", rationale="证据链在",
                attribution_plan=None)
    base.update(over)
    return Proposal(**base)


PLAN_OK = {"members": ["seg_order", "prefer_revealable"],
           "ablation_budget": {"n_runs": 2, "cost_to_ledger": True},
           "tau": 0.2,
           "calibration_note": "初值=R105c 抖动量级, 待校准",
           "fork_rule": "<τ additive / ≥τ interactive（稿§④）"}


def test_path_b_valid_plan_multi_change_passes():
    """★ 路径乙: 带合法 plan 的**多处**形态提案放行（单点纪律升级为归因纪律）。"""
    p = _proposal(target="a.py, b.py", patch="@@ -1 +1 @@\n@@ -5 +5 @@\n",
                  attribution_plan=dict(PLAN_OK))
    assert p.attribution_plan["members"] == ["seg_order", "prefer_revealable"]


def test_path_b_bad_plan_raises_same_severity():
    """plan 缺字段/坏值 ⇒ 构造期 raise（与单点判据同款严厉）。"""
    for bad, pat in [
        ({**PLAN_OK, "members": ["only_one"]}, "members"),
        ({**PLAN_OK, "members": ["k", "k"]}, "重复键域"),
        ({**PLAN_OK, "ablation_budget": {"n_runs": 0,
                                         "cost_to_ledger": True}}, "n_runs"),
        ({**PLAN_OK, "ablation_budget": {"n_runs": 2,
                                         "cost_to_ledger": False}}, "成本"),
        ({**PLAN_OK, "tau": 0}, "tau"),
        ({**PLAN_OK, "calibration_note": " "}, "calibration_note"),
        ({k: v for k, v in PLAN_OK.items() if k != "fork_rule"}, "fork_rule"),
        ({**PLAN_OK, "members": "not-a-list"}, "members"),
    ]:
        with pytest.raises(EvolverError, match=pat):
            _proposal(target="a.py, b.py", patch="@@\n@@", attribution_plan=bad)


def test_path_甲_single_change_zero_regression():
    """路径甲零破坏: 无 plan 单点照旧过（全部现有提案的路径）。"""
    p = _proposal()
    assert p.attribution_plan is None and p.state == "draft"


def test_path_甲_multi_change_original_raise_kept():
    """无 plan 的多处提案 ⇒ 原消息 raise（升级不是废除 — 单点地基不松）。"""
    with pytest.raises(EvolverError, match="多个目标"):
        _proposal(target="a.py, b.py")
    with pytest.raises(EvolverError, match="多 hunk"):
        _proposal(patch="@@ -1 +1 @@\nx\n@@ -2 +2 @@\ny")
    with pytest.raises(EvolverError, match="patch 必填"):
        _proposal(patch=" ")


def test_read_effects_boundaries_and_compensation():
    """★ 三读数 + τ 分流边界（稿§④; τ=0.2 两侧 + 负交互补偿）。"""
    import ablation_attribution as aa
    # 可加: I = 0.5-0.3-0.4+0.2 = 0.0 < 0.2
    eff = aa.read_effects({"s0": 0.2, "sA": 0.3, "sB": 0.4, "sAB": 0.5})
    assert abs(eff["main_effect_A"] - 0.1) < 1e-9
    assert abs(eff["main_effect_B"] - 0.2) < 1e-9
    assert abs(eff["interaction_I"]) < 1e-9
    assert eff["split"] == "additive" and not eff["compensation_flag"]
    # 交互: I = 1.1-0.3-0.4+0.2 = 0.6 ≥ 0.2
    eff2 = aa.read_effects({"s0": 0.2, "sA": 0.3, "sB": 0.4, "sAB": 1.1})
    assert eff2["split"] == "interactive"
    # 补偿: I = 0.0-0.3-0.4+0.2 = -0.5 < -0.2
    eff3 = aa.read_effects({"s0": 0.2, "sA": 0.3, "sB": 0.4, "sAB": 0.0})
    assert eff3["split"] == "interactive" and eff3["compensation_flag"]
    assert "待校准" in eff["calibration_note"]
    # 键域不相交 + 四 pid 唯一（稿§⑦ 构造即断言）
    specs = aa.build_specs()
    assert len(specs) == 4 and len({s.pid for s in specs.values()}) == 4
    assert specs["sA"].seg_order == "delta"
    assert specs["sB"].prefer_revealable is False


def test_inheritance_attribution_optional_segment():
    """六段档 attribution 可选段: 带则四件齐（成员≥2/三读数/τ/分流/注记）。"""
    base = dict(
        gen=114, parent_gen=113, at="2026-10-09T15:00:00+08:00",
        parent_state={"commits": 119},
        proposed_change={"kind": "patch", "exec_form": "d", "files": ["f"]},
        motivating_evidence={"refs": [{"type": "test", "ref": "r", "claim": "c"}]},
        evaluation_config={"truth_source": "s", "truth_sha8": "abcd1234",
                           "judge_frozen": True, "judge_fingerprint": "beef0001",
                           "epoch_id": None, "epoch_note": "n"},
        acceptance_decision={"verdict": "accepted"})
    # 不带 attribution = 合法（单点档）
    build_inheritance(**base)
    # 带齐 = 合法
    build_inheritance(**base, attribution={
        "members": ["seg_order", "prefer_revealable"],
        "main_effect_A": 0.1, "main_effect_B": 0.0, "interaction_I": 0.05,
        "split": "additive", "tau": 0.2, "calibration_note": "待校准"})
    # 带了缺件 ⇒ raise
    for bad, pat in [
        ({"members": ["x"], "split": "additive", "tau": 0.2,
          "main_effect_A": 0, "main_effect_B": 0, "interaction_I": 0,
          "calibration_note": "n"}, "members"),
        ({"members": ["a", "b"], "split": "weird", "tau": 0.2,
          "main_effect_A": 0, "main_effect_B": 0, "interaction_I": 0,
          "calibration_note": "n"}, "split"),
        ({"members": ["a", "b"], "split": "additive", "tau": 0.2,
          "main_effect_A": 0, "main_effect_B": 0, "interaction_I": 0},
         "calibration_note"),
    ]:
        with pytest.raises(InheritanceError, match=pat):
            build_inheritance(**base, attribution=bad)


def test_ablation_script_runs_full():
    """脚本真跑: 四V槽/三读数/τ分流/恒等如实（M1 验收首条）。"""
    outp = os.path.join(ROOT, "docs", "ablation_attribution.json")
    r = subprocess.run([sys.executable,
                        os.path.join(ROOT, "scripts",
                                     "ablation_attribution.py")],
                       capture_output=True, timeout=600, cwd=ROOT)
    assert r.returncode == 0, r.stderr.decode("utf-8", "replace")[-700:]
    d = json.load(open(outp, encoding="utf-8"))
    assert set(d["v_by_slot"]) == {"s0", "sA", "sB", "sAB"}
    eff = d["effects"]
    assert eff["split"] in ("additive", "interactive")
    assert eff["tau"] == 0.2 and "待校准" in eff["calibration_note"]
    # 恒等 ⇒ 结构必然 caveat（不冒充可加性发现 — 稿§⑨①）
    cave = json.dumps(d["caveats"], ensure_ascii=False)
    if eff["identical_v"]:
        assert "结构必然" in cave and "不冒充" in cave
    # 四 spec 键域不相交（读回断言）
    keys = {k: set(v["keys"]) - {"w_delta"} for k, v in d["specs"].items()}
    assert "seg_order" in d["specs"]["sA"]["keys"]
    assert d["specs"]["sB"]["keys"]["prefer_revealable"] is False
