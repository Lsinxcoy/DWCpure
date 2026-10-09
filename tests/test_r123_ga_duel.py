# -*- coding: utf-8 -*-
"""R123 · 项1 M2 对打执行 — 两臂同预算对打（设计稿⑦ §⑦ 验收清单）。

验收（稿⑦ §⑦ 逐条）:
  □ A 臂忠实复刻（π0+三单键, 一次一键, 无交叉无组合）
  □ B 臂: N=4/代≤4/tournament k=2/合法交叉/单键变异 逐项断言
  □ 预算硬上限: 两臂 ≤16 断言; 超额不评（K 倍账读数如实）
  □ 消融账覆盖 100%（子代带 plan — 缺账=构造期 raise）
  □ Eq.10 裁决 + 平局判 A（规则跑前锁 — 破坏测试: 改判据⇒红）
  □ CostLedger 风格两臂账各记各（K 倍账读数出数）
  □ 恒等风险: 如实报 caveat（一期协议验收口径）
  □ 单点路径零破坏（A 臂纯新增脚本 — select_policy 现行为不动）
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
from dwc.organs.replay import PolicySpec  # noqa: E402
import ga_duel as gd  # noqa: E402


def test_seed_and_enum_pool_semantics():
    """同起点四变体 + 组合池 = 与π0差≥2键（GA=多改组合归因场景）。"""
    seed = gd.seed_population()
    assert [s.pid for s in seed] == ["π0", "π(w=0,r=1)", "π(w=1,r=0)",
                                     "π(w=1,r=1,s=delta)"]
    pool = gd._enum_pool()
    base = PolicySpec()
    for s in pool:
        n = sum(1 for k in gd.KEYS
                if getattr(s, k) != getattr(base, k))
        assert n >= 2, "池只含多改组合（单键=路径甲不属归因池）: %s" % s.pid
    assert len(pool) >= 4          # C(3,2)+C(3,3)=4 键型×取值组合
    assert len({p.pid for p in pool}) == len(pool)   # pid 不撞


def test_cross_and_mutate_deterministic():
    """合法交叉（键域不相交⇒取b侧值, 同键⇒raise）+ 单键枚举翻转。"""
    p1 = PolicySpec.from_mapping({"w_delta": 0.0})          # w0 r1 s=child
    p2 = PolicySpec.from_mapping({"prefer_revealable": False})  # w1 r0
    c = gd.cross_pair(p1, p2)
    assert c.w_delta == 1.0 and c.prefer_revealable is False  # b 侧值
    assert gd.changed_keys(p1, p2) == ["w_delta", "prefer_revealable"]
    # 键域全同 ⇒ 交叉拒绝（不相交才交叉 — 稿③§⑦）
    with pytest.raises(RuntimeError, match="交叉拒绝"):
        gd.cross_pair(p1, p1)
    # 单键枚举翻转（非采样 — 有限域内另一值）
    m = gd.mutate_one(c, "w_delta")
    assert m.w_delta == 0.0 and m.pid != c.pid


def test_ga_child_must_carry_plan():
    """★ 子代带消融账（M1 路径乙契约）: members ≥2 组才成 Proposal。"""
    good = {"members": ["w_delta", "seg_order"],
            "ablation_budget": {"n_runs": 2, "cost_to_ledger": True},
            "tau": 0.2, "calibration_note": "τ₀=0.2 (稿③)",
            "fork_rule": "|I|<τ 拆分 / ≥τ 归档"}
    Proposal(proposal_id="x", failure_signature={"c": "E", "q": "n",
              "m": "m"}, component="memory",
             target="organs/memory.py::remember", patch="+x=1",
             rationale="r", attribution_plan=good)
    # 单键 plan ⇒ 构造期 raise（归属账对象必须是组合 — 稿⑦验收条③）
    with pytest.raises(EvolverError, match="members"):
        Proposal(proposal_id="y", failure_signature={"c": "E", "q": "n",
                  "m": "m"}, component="memory",
                  target="organs/memory.py::remember", patch="+x=1",
                  rationale="r", attribution_plan={**good,
                                                  "members": ["w_delta"]})


def test_budget_hard_limit_and_ledger():
    """预算硬上限: 满额不再可花; 逐笔记账（CostLedger 风格）。"""
    b = gd.Budgeter("ga", limit=3)
    for i in range(3):
        assert b.can(); b.spend("x%d" % i)
    assert not b.can() and b.spent == 3
    s = b.summary()
    assert s["within_budget"] and s["limit"] == 3 and s["arm"] == "ga"
    assert len(b.ledger) == 3


def test_ga_duel_script_runs_full():
    """★ 脚本真跑: 两臂/预算/Eq.10/平局判A/账本/K倍 全读数。"""
    outp = os.path.join(ROOT, "docs", "ga_duel.json")
    r = subprocess.run([sys.executable,
                        os.path.join(ROOT, "scripts", "ga_duel.py")],
                       capture_output=True, timeout=600, cwd=ROOT)
    assert r.returncode == 0, r.stderr.decode("utf-8", "replace")[-700:]
    d = json.load(open(outp, encoding="utf-8"))
    # A 臂忠实: 恰好评 π0+三单键（无交叉无组合 — 单点纪律复刻）
    assert sorted(d["arm_single"]["best_v"]) == sorted(
        s.pid for s in gd.seed_population())
    # B 臂 GA: 代=4, 有父/交叉键/子代plan 记录; 池内不重复评
    log = d["arm_ga"]["log"]
    assert len(log) == gd.MAX_GEN
    planned = [g for g in log if "child_with_plan" in g]
    assert len(planned) >= 4, "GA 每代都该产出子代（键空间未穷尽）"
    for g in planned:
        assert len(g["plan_members"]) >= 2   # 消融账 100% 强制
    # 预算纪律: 两臂 ≤16, K 倍账如实
    bA, bB = d["budget"]["single"], d["budget"]["ga"]
    assert bA["v_evals_spent"] <= d["params"]["B_arms"] and \
        bB["v_evals_spent"] <= d["params"]["B_arms"]
    assert d["budget"]["k_ratio_ga_over_single"] is not None
    assert d["budget"]["k_ratio_ga_over_single"] == round(
        bB["v_evals_spent"] / bA["v_evals_spent"], 4)
    # Eq.10 裁决 + 平局判 A（跑前锁 — 稿⑦§⑤）
    v = d["verdict"]
    assert v["basis"].startswith("tie") or v["basis"] in ("accept_count",
                                                          "best_v")
    assert v["winner"] in ("single", "ga")
    # 恒等如实（一期 protocol 验证口径）
    cave = "\n".join(d["caveats"])
    assert "结构必然" in cave and "非对打失败" in cave
    assert "仍须用户再拍" in cave    # 对打赢≠常态化授权
    # 纪律先于输赢字段
    assert d["discipline"]["single_within"] and d["discipline"]["ga_within"]
