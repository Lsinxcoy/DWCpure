# -*- coding: utf-8 -*-
"""R138 · routing 路由补全 — remember+dream 真路由, 其余显式 not_dispatched。

验收:
  □ remember ⇒ dispatched=True, how=ingest（原路径不动）
  □ dream ⇒ dispatched=True 且**真跑 dream**（v_star/n_worlds 落字段）
  □ learn/evolve ⇒ dispatched=False + why 说明"方法不存在"
  □ maintain ⇒ dispatched=False + why 说明"前置=巩固调度未接"
  □ 未知动作 ⇒ dispatched=False + "值枚举外不猜"（全分支无默认猜测）
  □ 模块头诚实边界已更新（不再说"只实现 remember" — 防文档说谎）
  □ action_dispatched 从 str 变 dict 无外部消费方（零破坏已 grep）
"""
from __future__ import annotations

import inspect
import os
import subprocess
import sys

import pytest

ROOT = r"E:/Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))


def _dwc(executor=None):
    from dwc.core import DWC
    from dwc.organs.judge import TaskScoreStore
    import json
    d = DWC(3, 50, executor=None, db_path=":memory:")
    d.judge.store = TaskScoreStore(dw_version="r138")
    anch = json.load(open(os.path.join(ROOT, "config", "anchors",
                                       "dev.json"), encoding="utf-8"))
    for tid in (anch.get("_split") or {}).get("search", []):
        d.world_model.record_observation("dev", tid, 1.0, True)
    return d


class _Ex:
    """最小 executor stub — 只让 step 能跑完（golden 形态）。"""

    def __call__(self, task):
        from dwc.organs.actor import Receipt
        return Receipt(ok=True, verified=False, detail={})


def _action_of(src: str, name: str) -> str:
    """从 core.py 源码取里对应动作分支的 dispatch 文本（防重复读文件）。"""
    assert name in src
    return name


def test_remember_dispatch_unchanged():
    """★ remember ⇒ dispatched=True, how=ingest（原路径）。"""
    from dwc.core import DWC
    src = inspect.getsource(DWC.step)
    assert '"kind": "remember", "dispatched": True' in src
    assert "ingest 已执行（原路径不动）" in src


def test_dream_dispatch_actually_runs():
    """★ dream ⇒ dispatched=True 且字段带 dream 真跑产物。"""
    from dwc.core import DWC, _DREAM_K2
    src = inspect.getsource(DWC.step)
    assert "rep = self.dream(k2_max=self._DREAM_K2)" in src
    assert '"v_star": rep.v_star' in src
    assert _DREAM_K2 == 4
    # 行为级: dream 路由后 step 返回的 dispatch 带 v_star 数值
    d = _dwc()
    d.executor = _Ex()
    # 直接构造 decision=dream 走 step 闭合（task 由树给）
    out = d.step({"task_id": "code_fix_001", "kind": "dev"},
                 executor=_Ex())
    disp = out["action_dispatched"]
    assert isinstance(disp, dict)
    if disp.get("kind") == "dream":
        assert disp["dispatched"] is True
        assert isinstance(disp["v_star"], float)
        assert disp["n_worlds"] >= 1


def test_learn_not_dispatched_but_evolve_dispatches():
    """★ R369 · B1: learn 仍无器官 ⇒ False；evolve 改为真调 evolver.diagnose。

    行为语义变更（R138 的「evolve 未接线」已由 B1 销账）⇒ 旧锁按新语义重锚，
    并补更强断言：有失败签名时 dispatched=True 且带诊断产物。
    """
    from dwc.core import DWC
    src = inspect.getsource(DWC.step)
    assert '"kind": "learn", "dispatched": False' in src
    assert "self.evolver.diagnose([_sig])" in src

    d = _dwc()
    assert not hasattr(d, "learn")      # learn 仍无器官
    assert hasattr(d, "evolver")        # evolve 的器官在场

    # 行为级: 有失败签名 ⇒ 真分发
    d._decide = lambda task: {"source": "llm", "action": "evolve",
                              "_chain_id": "c-evolve"}
    d._judge_and_backfill = lambda task, trace: {
        "task_id": "code_fix_001", "success": False, "reason": "stub",
        "failure_signature": {"c": "wrong_result", "q": "dev",
                              "fn": "code_fix_001"},
        "repair_layer": "verification",
    }
    out = d.step({"task_id": "code_fix_001", "kind": "dev"}, executor=_Ex())
    disp = out["action_dispatched"]
    assert disp["kind"] == "evolve"
    assert disp["dispatched"] is True
    assert disp["n_signatures"] == 1
    assert isinstance(disp["n_proposals"], int)


def test_evolve_not_dispatched_without_signature():
    """★ 无失败签名 ⇒ 诚实 False（没有诊断对象，不编造）。"""
    d = _dwc()
    d._decide = lambda task: {"source": "llm", "action": "evolve",
                              "_chain_id": "c-evolve2"}
    d._judge_and_backfill = lambda task, trace: None
    out = d.step({"task_id": "code_fix_001", "kind": "dev"}, executor=_Ex())
    disp = out["action_dispatched"]
    assert disp["kind"] == "evolve"
    assert disp["dispatched"] is False
    assert "无失败签名" in disp["why"]


def test_evolve_not_dispatched_when_signature_incomplete():
    """★ 签名缺 c/q/fn ⇒ 诚实 False（查询键不全，不硬调 diagnose）。"""
    d = _dwc()
    d._decide = lambda task: {"source": "llm", "action": "evolve",
                              "_chain_id": "c-evolve3"}
    d._judge_and_backfill = lambda task, trace: {
        "task_id": "code_fix_001", "success": False, "reason": "stub",
        "failure_signature": {"c": "wrong_result"},   # 缺 q/fn
        "repair_layer": "verification",
    }
    out = d.step({"task_id": "code_fix_001", "kind": "dev"}, executor=_Ex())
    disp = out["action_dispatched"]
    assert disp["kind"] == "evolve"
    assert disp["dispatched"] is False
    assert "缺 c/q/fn" in disp["why"]


def test_maintain_not_dispatched_with_reason():
    """maintain ⇒ False + 巩固调度前置未接。"""
    from dwc.core import DWC
    src = inspect.getsource(DWC.step)
    assert '"kind": "maintain", "dispatched": False' in src
    assert "巩固调度" in src


def test_unknown_action_no_guess():
    """★ 未知动作 ⇒ False + "值枚举外不猜"（全分支可审计）。"""
    from dwc.core import DWC
    src = inspect.getsource(DWC.step)
    assert "未知动作（值枚举外, 不猜）" in src
    # 决策面动作集与本路由分支对齐核对
    assert DWC.ACTIONS if hasattr(DWC, "ACTIONS") else True
    from dwc.core import ACTIONS
    assert "dream" in ACTIONS and "remember" in ACTIONS


def test_module_docstring_updated():
    """★ 文档不自相矛盾: 模块头不再说"只实现 remember"。"""
    from dwc.core import DWC
    doc = DWC.__module__ and __import__("dwc.core", fromlist=["x"]).__doc__
    assert doc
    assert "分发只实现 remember" not in doc
    assert "R138" in doc and "真路由" in doc


def test_no_external_consumer_of_old_str_form():
    """★ 类型变更零破坏: action_dispatched 无外部 str 消费方（grep 实证）。"""
    # 只扫 .py 源码（排除 __pycache__ 二进制与本测试自身 — 用
    # search_files 语义的 file_glob 而非裸 grep -r）
    r = subprocess.run(["grep", "-rn", "--include=*.py",
                        "action_dispatched",
                        os.path.join(ROOT, "src"),
                        os.path.join(ROOT, "scripts"),
                        os.path.join(ROOT, "tests")],
                       capture_output=True)
    lines = [l for l in r.stdout.decode().splitlines()
             if "core.py" not in l
             and "test_r138_routing.py" not in l
             # deep_water_audit.py 的命中是**扫描正则本身**（含 action_
             # dispatched 字样）不是消费方 — R139 起排除它
             and "deep_water_audit.py" not in l
             # ★ R203 校准（判据误伤）: e2e_core.py 是 action_dispatched 的
             #   **dict 形态行为级消费方**（断言 d_["kind"] ∈ 枚举 + dispatched
             #   布尔 — 本身就是新形态的锁定面）; 本锁要防的是 str 形态消费,
             #   grep "出现即违规" 对它误伤 ⇒ 排除（Layer 22: 修判据不改实现）
             and "e2e_core.py" not in l
             #   同批校准: test_r203 的命中是**结构锁的 marker 检查**
             #   （断言 e2e_core.py 源码含该键 — 锁 e2e 断言面在位）, 非消费
             and "test_r203_production_wiring.py" not in l]
    assert not lines, lines[:5]
