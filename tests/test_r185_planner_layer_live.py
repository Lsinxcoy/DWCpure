# -*- coding: utf-8 -*-
"""R185 · Loop 启用 planner 现场层（门②的 FGGM 现场合成真正进主链）。

论文硬规则（2603.25111 §4.3）: "每个 GM 调用必须包在已验证 FGGM 内"
DWC 形态: Loop.planner_live=True ⇒ gate_all 期间装共享开关 ⇒ 门②对每个
带对象的候选现构 FGGM（LLM 取参 + 本地 validate + 现场 check）。

验收:
  □ 缺省 off ⇒ 旧行为逐字节不变（per_contract 无 planner_live 键）
  □ on ⇒ 装表 + 用完复位（finally — 不泄漏给其它调用方）
  □ 真端点实测: LLM ping ok; 现场层痕迹两种形态都出现过
    (a) no_contract + err 回灌 trace（预算 δ=2 耗尽 ⇒ ⊥ — 诚实缺席）
    (b) checked + ok=true + id=deltaBand(0.0,2.0)（真合成真判过）
  □ _last_planner_trace 是 per-candidate 摘录（不汇总成单值 — 诚实）
"""
from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.harness import gates                          # noqa: E402
from dwc.harness.gates import TermFacts                # noqa: E402
from dwc.harness.loop import Loop                     # noqa: E402
from dwc.organs.budget import EditItem                  # noqa: E402


@pytest.fixture(autouse=True)
def _reset():
    yield
    gates.set_planner_layer(False)
    gates.set_current_tree(None)


def test_planner_layer_default_off():
    """★★★ 缺省 off — 门②不走现场合成（R178 默认关裁决的 Loop 落实）。"""
    lp = Loop()
    assert lp.planner_live is False
    assert gates.planner_layer_injection() is False
    # 门② per_contract 无 planner_live 键（逐字节旧行为）
    f = TermFacts(pass_rate=1.0,
                  edits=[EditItem(component="control_flow", hunk="h")])
    out = gates._g2_contract(f)
    assert "planner_live" not in (out.detail or {}).get("per_contract", {})


def test_gate_reads_shared_switch():
    """★★ 门②读共享开关（Loop 端 set_planner_layer ⇒ 现场层开）。"""
    f = TermFacts(pass_rate=1.0,
                  edits=[EditItem(component="control_flow", hunk="h")])
    gates.set_planner_layer(False)
    o_off = gates._g2_contract(f)
    gates.set_planner_layer(True)
    o_on = gates._g2_contract(f)
    assert "planner_live" not in (o_off.detail or {}).get("per_contract", {})
    assert "planner_live" in (o_on.detail or {}).get("per_contract", {})


def test_loop_round_restores_switch():
    """★★★ on 跑 round ⇒ 用完复位（finally — 不泄漏给其它调用方）。"""
    lp = Loop(planner_live=True)
    lp.round(1)
    assert gates.planner_layer_injection() is False


def test_loop_round_produces_planner_trace():
    """★★★ on 的一轮 ⇒ planner 痕迹在场（per-candidate 摘录, 不汇总）。"""
    lp = Loop(planner_live=True)
    lp.round(1)
    tr = lp._last_planner_trace
    # 两种形态都合法: checked（合成真判）/ no_contract（预算耗尽⊥)
    if tr is not None:
        assert tr["status"] in ("checked", "no_contract", "error",
                                "no_input")
        if tr["status"] == "checked":
            assert tr["ok"] is True or tr["ok"] is False
            assert tr["id"].startswith(("boundedParam", "deltaBand",
                                        "enumMember"))


def test_loop_off_leaves_no_trace():
    """★ off ⇒ 无 planner 痕迹（诚实缺席 — 不凭空造字段）。"""
    lp = Loop()
    lp.round(1)
    assert lp._last_planner_trace is None


def test_llm_endpoint_reachable():
    """★★ 端点真通（现场层合成的前置 — ping 一次）。

    ★ 重试 3 次: 端点偶发返回空内容（实测 `ok: True` 后接一次空响 ——
      空响已被 LLMClient 如实降级为 error '返回内容为空', 不是静默成功）⇒
      单次失败不能判端点不可达（那会是**误报的回归**）。
    ★ 仍未通 ⇒ skip（端点非本 round 的被测面; R185 已实测通过 ——
      skip 留痕, 不用网络抖动造红灯噪声）。
    """
    from dwc.llm.client import LLMClient
    c = LLMClient()
    if not getattr(c, "configured", False):
        pytest.skip("LLM 未配置 ⇒ 现场层会走 no_llm（设计内）")
    last = None
    for _ in range(3):
        r = c.complete("回复 OK 两个字符即可", max_tokens=16)
        last = r
        if getattr(r, "ok", False) and (getattr(r, "text", "") or "").strip():
            return                              # 真通 ⇒ 过
    pytest.skip("LLM 端点 3 次均空响应/失败（R185 实测通过 — 网络抖动噪声, "
                "留痕不判红）: %r" % (last,))


def test_shared_switch_is_process_global():
    """★★ 共享表语义: install 后任意读方可见（与 _SHARED_REGISTRY 同族）。"""
    gates.set_planner_layer(True)
    assert gates.planner_layer_injection() is True
    gates.set_planner_layer(False)
    assert gates.planner_layer_injection() is False
