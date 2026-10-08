# -*- coding: utf-8 -*-
"""R76 批1 · EL 采样接线测试（A core.step / B run_term · 提案 docs/proposal_consuming_organ6.html）。

★★★ 为什么这份测试重要
  这是 ⑥ 探索组件五轮来**第一个运行流消费方** —— 测试锁的不是算法
  （test_el_sched 已锁式2），是**接线契约**:
  ① A/B 共用同一台 EL 状态机（提案硬约束: 分裂=调度语义废）
  ② B 是**叠加式**（原 tasks 不动, 只加 el_selected — 零破坏承诺）
  ③ 节律=观测变化才推进（没变不空转）
  ④ 无观测保底=接线前行为（acts[0] / insufficient）
★ 破坏面预设: B 改替换 ⇒ 叠加红; 实例分裂 ⇒ 同实例红。
"""
from __future__ import annotations

import os
import sys

import pytest

ROOT = r"E:/Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.core import DWC  # noqa: E402
from dwc.organs.el_sched import (  # noqa: E402
    STATUS_INSUFFICIENT, ELScheduler,
)
from dwc.harness.run_term import TermRunner  # noqa: E402


def _ok_executor(task):
    from dwc.organs.actor import Receipt
    return Receipt(ok=True, detail={"echo": task.get("task_id")},
                   verified=True)


def _dwc():
    return DWC(3, 50, executor=_ok_executor)


# ══════════════════════════════════════════════════════════
# 硬约束①: 一个 agent 一台状态机（A/B 同实例）
# ══════════════════════════════════════════════════════════

def test_single_el_instance_shared_by_a_and_b():
    """★★ 提案批1 硬约束: step 与 runner 拿到**同一个** ELScheduler。"""
    d = _dwc()
    assert isinstance(d.el, ELScheduler)
    assert d.runner.el_scheduler is d.el, \
        "★ A（core._el_pick）与 B（run_term）必须共用一台状态机"


# ══════════════════════════════════════════════════════════
# 接点 A: core.step 缺省取任务
# ══════════════════════════════════════════════════════════

def test_step_default_unobserved_takes_first_act():
    """★ 无观测 ⇒ insufficient ⇒ acts[0] —— **与接线前行为一致**（保底）。"""
    d = _dwc()
    d.world_model.seed("main", "基线")
    out = d.step()
    # seed 后唯一候选 = root（未揭示）
    assert out["decision"]  # 执行成功走通
    assert d.el.index == 1 and d.el.generation == 1   # 无观测不推进


def test_step_advances_only_on_new_observations():
    """★★ 节律 + 推进: 有观测且过 τ ⇒ 游标 +1 选下一候选; 观测没变不再推进。"""
    d = _dwc()
    wm = d.world_model
    wm.seed("main", "基线")
    wm.expand("main", "root", node_id="a", action="act-A",
              provenance="observed")
    wm.expand("main", "root", node_id="b", action="act-B",
              provenance="observed")
    # 灌观测: root 过 ⇒ 池通过率 1.0 > τ=0.75 ⇒ 推进
    wm.record_observation("main", "root", 1.0, True)
    acts = wm.legal_actions()
    assert [a["node"] for a in acts] == ["a", "b"]    # root 已揭示, 叶子 a/b
    d.step()                                          # 观测变化 ⇒ 判一次
    assert d.el.index == 2, "p̂>τ ⇒ 同代推进 index 1→2"
    picked1 = d._el_pick(acts)
    assert picked1["node"] == "b"                     # acts[(2-1)%2]=b
    # ★ 节律: 观测计数没变 ⇒ 不再推进（连续调用不空转）
    n_before = d.el.index
    d._el_pick(acts)
    d._el_pick(acts)
    assert d.el.index == n_before, "★ Σn_obs 未变 ⇒ 不重复判定"


def test_step_explicit_task_path_untouched():
    """显式 task 路径不走 EL（接线只动缺省取任务）。"""
    d = _dwc()
    out = d.step({"task_id": "t1", "kind": "manual"})
    assert out["decision"]


# ══════════════════════════════════════════════════════════
# 接点 B: run_term 任务源 el_selected（叠加式）
# ══════════════════════════════════════════════════════════

def _tr(with_el: bool):
    wm_world = None
    from dwc.organs.world_model import WorldModel
    wm_world = WorldModel(depth_limit=3, max_nodes=50)
    wm_world.seed("main", "基线")
    wm_world.expand("main", "root", node_id="a", action="act-A",
                    provenance="observed")
    wm_world.expand("main", "root", node_id="b", action="act-B",
                    provenance="observed")
    return TermRunner(world_model=wm_world,
                      el_scheduler=ELScheduler() if with_el else None)


def test_b_adds_el_selected_without_touching_tasks():
    """★★ 叠加式: tasks 原样（world_tree_action 全在）+ 顶部 el_selected。"""
    tr = _tr(with_el=True)
    rep = tr.run_term("t", n_steps=1)
    src = rep.next_task_source
    wta = [t for t in src["tasks"] if t["kind"] == "world_tree_action"]
    assert len(wta) == 2, "★ 原 tasks 不许被采样替换掉（叠加承诺）"
    el = src.get("el_selected")
    assert el is not None, "注入了 EL ⇒ 必须有标注"
    assert el["status"] == STATUS_INSUFFICIENT      # 无观测首判
    assert el["n_candidates"] == 2
    assert el["picked"]["node"] in {w["node"] for w in wta}
    assert "叠加标注" in el["why"]


def test_b_without_el_injection_has_no_field():
    """没注入 ⇒ 字段不出现（不假装采样过 — judge=None 同纪律）。"""
    tr = _tr(with_el=False)
    rep = tr.run_term("t", n_steps=1)
    assert "el_selected" not in rep.next_task_source


def test_b_pushes_index_when_pool_observed():
    """B 侧也吃池观测: 观测过 τ ⇒ el_selected.index 推进到 2。"""
    tr = _tr(with_el=True)
    tr.world_model.record_observation("main", "root", 1.0, True)
    rep = tr.run_term("t", n_steps=1)
    el = rep.next_task_source["el_selected"]
    assert el["status"] == "next_environment"
    assert el["index"] == 2
    assert el["picked"]["node"] == "b"


# ══════════════════════════════════════════════════════════
# 观测源: world_model.observed_rate / observed_count
# ══════════════════════════════════════════════════════════

def test_observed_rate_none_when_no_observations():
    """★ 无观测 ⇒ None（不冒充 0.0）; 有观测 ⇒ Σn_pass/Σn_obs（跨树聚合）。"""
    from dwc.organs.world_model import WorldModel
    wm = WorldModel(depth_limit=3, max_nodes=50)
    assert wm.observed_rate() is None
    assert wm.observed_count() == 0
    wm.seed("t1", "x")
    wm.seed("t2", "y")
    wm.record_observation("t1", "root", 1.0, True)
    wm.record_observation("t2", "root", 0.5, False)
    assert wm.observed_count() == 2
    assert wm.observed_rate() == pytest.approx(0.5)   # 1 pass / 2 obs


def test_decide_from_rate_core_equivalence():
    """速率口与序列口同核心: 同一 p̂ 下三段结果一致（拆分等价）。"""
    s1 = ELScheduler()
    s2 = ELScheduler()
    # 序列口: 灌 8 次全过 ⇒ p=1.0 ⇒ 推进
    for _ in range(8):
        s1.record(True)
    d_seq = s1.decide(n_envs=4)
    d_rate = s2.decide_from_rate(1.0, 4)
    assert d_seq.status == d_rate.status == "next_environment"
    assert (d_seq.generation, s1.index) == \
           (d_rate.generation, s2.index) == (1, 2)
    # None ⇒ 同 insufficient
    d_none = ELScheduler().decide_from_rate(None, 4)
    assert d_none.status == STATUS_INSUFFICIENT and d_none.pass_rate is None
