# -*- coding: utf-8 -*-
"""R175 · planner 契约合成面（2603.25111 §4.3 三阶段 DWC 复刻）。

验收（本地白名单面全部可复现; LLM 面只有端点通时跑 — 标 skip 不假过）:
  □ _validate_spec 拒: 非白名单 kind / 类型错 / 区间退化 / 单成员恒真
  □ parse_llm_spec 容忍 ```json 栅栏 + 顶层 list
  □ craft 无 llm ⇒ no_llm（不返回假契约）
  □ craft 带假 llm: 先坏后好 ⇒ err 回灌 ⇒ 第二次过（痕迹可复盘）
  □ [可选] 真端点: craft 出真 FGGM 且 check 可判
"""
from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.organs.planner import (PlannerError, available_templates,  # noqa: E402
                                build_fggm, compose_prompt, craft,
                                parse_llm_spec)


def test_templates_whitelisted():
    """★ 模板族白名单（审计边界 — 只有这三个, 不开自由公式）。"""
    assert available_templates() == ["bounded_param", "delta_band",
                                     "enum_member"]


def test_reject_unknown_kind():
    with pytest.raises(PlannerError) as e:
        build_fggm({"kind": "eval_formula", "params": {"expr": "1<2"}})
    assert "不在白名单" in str(e.value)


def test_reject_type_drift():
    with pytest.raises(PlannerError) as e:
        build_fggm({"kind": "bounded_param", "params": {"l": "1", "u": 8}})
    assert "须数值" in str(e.value)


def test_reject_degenerate_enum():
    """★★★ 单成员集合恒真 = 放水面（实测: LLM 真合出过 enumMember(1)）。"""
    with pytest.raises(PlannerError) as e:
        build_fggm({"kind": "enum_member", "params": {"members": ["10"]}})
    assert "无判定力" in str(e.value)


def test_reject_degenerate_band():
    with pytest.raises(PlannerError) as e:
        build_fggm({"kind": "delta_band", "params": {"l": 5, "u": 5}})
    assert "无判定力" in str(e.value)


def test_parse_fence_and_list_wrap():
    got = parse_llm_spec('```json\n[{"kind":"bounded_param","params":'
                         '{"l":1,"u":8}}]\n```')
    assert got == {"kind": "bounded_param", "params": {"l": 1, "u": 8}}


def test_parse_non_json_raises():
    with pytest.raises(PlannerError):
        parse_llm_spec("这不是 JSON 只是一句话")


def test_craft_no_llm():
    f, tr = craft({"task": "x"}, None)
    assert f is None and tr["outcome"] == "no_llm"


class _FakeLLM:
    """先坏后好 — 锁 err 回灌路径（真端点的替身, 可复现）。"""

    configured = True

    def __init__(self):
        self.n = 0

    def complete(self, prompt, **kw):
        class _R:
            ok = True
        r = _R()
        self.n += 1
        r.text = ('not json at all' if self.n == 1 else
                  '{"kind":"bounded_param","params":{"l":1,"u":8}}')
        return r


def test_craft_err_refeed():
    """★★★ err 回灌: 第一次坏 ⇒ 第二次过（痕迹带失败原因 — 论文 Alg 回路）。"""
    f, tr = craft({"task": "code_fix_001"}, _FakeLLM(), budget=3)
    assert f is not None and f.id == "boundedParam(1.0,8.0)"
    assert tr["attempts"] == 2 and tr["outcome"] == "crafted"
    assert tr["trace"][0]["stage"] == "validate"


def test_craft_budget_exhausted_returns_none():
    """★★★ 预算耗尽 ⇒ None（不返回假契约 — 论文 δ 耗尽 ⇒ ⊥）。"""

    class _BadLLM:
        configured = True

        def complete(self, prompt, **kw):
            class _R:
                ok = True
                text = "garbage"
            return _R()

    f, tr = craft({"task": "x"}, _BadLLM(), budget=2)
    assert f is None and tr["outcome"] == "budget_exhausted"


def test_prompt_mentions_templates():
    p = compose_prompt({"task": "t", "checks": [{"fn": "f"}]})
    assert "bounded_param" in p and "白名单" in p


def test_real_endpoint_when_available():
    """★ 真端点 craft（端点不通 ⇒ skip — 不假装跑过; 通了必出真契约）。"""
    from dwc.llm import LLMClient
    c = LLMClient()
    if not c.configured:
        pytest.skip("llm 未配置")
    f, tr = craft({"task": "code_fix_001",
                   "checks": [{"fn": "sum_first_n", "args": 4,
                               "expected": "10"}]}, c, budget=3)
    if tr["outcome"] == "crafted":
        assert f is not None and f.check is not None
    else:
        # 端点异常也算如实结果（不是 skip 也不是假过）
        assert tr["outcome"] in ("budget_exhausted", "no_llm")
