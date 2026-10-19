# -*- coding: utf-8 -*-
"""R141 · routing 器官侧盘点 — π/U 陈旧自陈修正（evolver 早已实现）。

验收:
  □ 事实底座: evolver.Evolver 类存在且 core.py 实例化 self.evolver
  □ Quintet 构建: π/V 有真值（不再 None）; U 标"已实现但未接本盘点"
  □ to_dict 双列表: unimplemented（None 字段）+ partial（含"未接"字样）
  □ core.py step 分发: evolve 的 why 从"方法不存在"改为"器官已实现但未接线"
  □ 盘点 note 同步（不残留 R138 的误导文字）
  □ 端到端: TermRunner 跑一轮后 rep.quintet 无 None 的 π/V/U
"""
from __future__ import annotations

import inspect
import os
import sys

ROOT = r"E:/Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))


def test_evolver_really_exists():
    """★ 事实底座: Evolver 类 + core 实例化（R138/R141 纠偏的实测依据）。"""
    from dwc.organs.evolver import Evolver
    from dwc.core import DWC
    src = inspect.getsource(DWC.__init__)
    assert "self.evolver = Evolver()" in src
    d = DWC(3, 50, executor=None, db_path=":memory:")
    assert d.evolver is not None
    # π 角色契约: 变异器编排（失败签名→提案→过门→待判分）
    doc = Evolver.__doc__ or ""
    assert "变异器" in doc and "不判分" in doc


def test_select_winner_exists_for_U():
    """★ U 评估面: select_winner 已实现（evolver.py L449）。"""
    from dwc.organs.evolver import select_winner
    assert callable(select_winner)
    doc = select_winner.__doc__ or ""
    assert "赢家" in doc and "judge 产出" in doc


def test_quintet_dict_has_partial_list():
    """★ to_dict 双列表: unimplemented + partial（未接线≠未实现）。"""
    from dwc.harness.run_term import Quintet
    q = Quintet(pi="evolver（已实现）", V="judge（已实现）", m="m",
                U="select_winner · 已实现但未接", rho="rho")
    d = q.to_dict()
    assert d["unimplemented"] == []
    assert d["partial"] == ["U"]
    # 全 None 时 unimplemented 全列、partial 空（原语义不破坏）
    q2 = Quintet()
    d2 = q2.to_dict()
    assert d2["unimplemented"] == ["pi", "V", "U"] and d2["partial"] == []


def test_quintet_build_uses_real_roles():
    """★ build 现场: π/V/U 三字符串都非 None（evolver 已注入时）。"""
    from dwc.harness import run_term as rt
    src = inspect.getsource(rt.TermRunner.run) if hasattr(
        rt.TermRunner, "run") else ""
    # 定位 build quintet 段（函数名以模块源为准）
    mod_src = inspect.getsource(rt)
    assert 'pi=("dwc.organs.evolver.Evolver' in mod_src
    assert "已实现" in mod_src


def test_core_dispatch_why_corrected():
    """★ R369: evolve 已从「器官已实现但未接线」升级为真分发。

    旧锁守的是「why 不能说方法不存在」；现在再进一步——
    不能再说「未接线」，且必须真调 evolver.diagnose（B1 销账）。
    """
    from dwc.core import DWC
    src = inspect.getsource(DWC.step)
    assert "self.evolver.diagnose([_sig])" in src
    assert "step 分发未接线" not in src          # 旧缺口文字必须消失
    # 旧误导文字必须消失
    assert "方法不存在（DWC 未实现 evolve 器" not in src


def test_audit_note_mentions_evolver_implemented():
    """盘点 note 同步: evolve 缺口是接线不是实现。"""
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    import subprocess, json
    subprocess.run([sys.executable,
                    os.path.join(ROOT, "scripts", "deep_water_audit.py")],
                   capture_output=True, timeout=300, cwd=ROOT)
    d = json.load(open(os.path.join(ROOT, "docs",
                                    "deep_water_audit.json"),
                       encoding="utf-8"))
    r = [o for o in d["items"] if o["id"] == "routing"][0]
    assert "R141 补充" in r["doc_note"]
    assert "evolver.py L1683 Evolver" in r["doc_note"]


def test_end_to_end_quintet_no_none():
    """端到端: TermRunner 跑一轮 ⇒ quintet 的 π/V/U 非 None。"""
    from dwc.harness.run_term import TermRunner
    tr = TermRunner(db_path=":memory:")
    rep = tr.run_term("demo task", n_steps=1)   # 真实签名
    q = rep.quintet
    for k in ("pi", "V", "U"):
        assert q[k] is not None, (k, q[k])
    assert q["unimplemented"] == []
    assert q["partial"] == ["U"]     # U 仍"未接本盘点"（如实）
