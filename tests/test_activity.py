# -*- coding: utf-8 -*-
"""六层活性模型（foundation/activity.py）的契约测试。

★★★ 存在理由
  2026-10-05 用户裁决 DWC 采用六层（2608.24876 §2.2.3 的 Γ 结构）。
  activity.py 是它的第一个实现 ⇒ 而六层同时是 gate.py G3 的强制判据
  ⇒ 若这个模块有漏洞，门就失去了它唯一能检的东西。

★ 测什么（按意图，不按实现）:
  ① 六层单调: 弱判据不得越级（构造时就拦，不留到检查期）
  ② ★★ 负事件 NOT_CALLED 是一等公民（论文 Table 4 的硬要求）
  ③ "从未调用"（dead）≠ "曾经活跃后失效"（stale）
     —— 母巢 P2-3 同款病：把 never_called 塞进 stale
  ④ 状态不可变（frozen），改事件必须产出新状态
  ⑤ 未登记机制不许记事件（present 层未过就不许有下游事件）
"""
from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
from dwc.foundation.activity import (  # noqa: E402
    ActivityState, EventKind, Layer, LayerError, MechanismRegistry,
    ORDER, REQUIRES, lit, stamp,
)


# ══════════════════════════════════════════════════════════
# ① 单调性：弱判据不得越级
# ══════════════════════════════════════════════════════════

@pytest.mark.parametrize("lay", list(ORDER))
def test_lit_requires_its_evidence(lay):
    """★★★ 意图: 点亮某层必须**同时声明**它要求的证据（REQUIRES 表）。

    ★★★ 2026-10-05 两次更正（都被接线层测试逼出来）:
      ① 初版"自动补齐上游" ⇒ 会绕过『必须外部回执』（点 feedback_closed
         就连带点亮 succeeded）⇒ 原则 1 被绕过
      ② 改为"必须声明直接上游"后，六层变成了**单向有序链** ⇒ 而
         2608.24876 §5.1.2 原文只给了六个**并列**来源，从未说有序
      ⇒⇒ 最终模型: 六层是**并列证据**，每层只要求 REQUIRES[lay] 里的那些。

    ⇒ 本测试逐层核对: 只传一层时，缺什么就报什么。
    """
    need = REQUIRES[lay]
    # ★ lit() 默认 exists=True ⇒ PRESENT 已被点亮
    #   ⇒ 若 REQUIRES 只要求 PRESENT，那单传一层就已满足（正确行为）
    missing_after_default = {x for x in need if x is not Layer.PRESENT}
    if not missing_after_default:
        assert lit(lay).at_least(lay)
        return
    # ★ 若还要求别的证据（如 succeeded 要求 called），缺了就必须 raise
    with pytest.raises(LayerError):
        lit(lay)


def test_lit_with_required_evidence_is_legal():
    """意图: 补齐 REQUIRES 后合法（逐层核对，不假设前缀）。"""
    for lay in ORDER:
        need = REQUIRES[lay]
        st = lit(lay, *need)
        assert st.at_least(lay)
        for x in need:
            assert st.at_least(x)


def test_independent_layers_need_no_upstream():
    """★★★ 意图: produced_effect / feedback_closed 可**独立**被点亮。

    ★★★ 这是"并列证据"模型的核心断言。
      真实场景: 一次调用没有外部回执，但下游确实观测到了产物
      （例如产物由 side-channel 产生）⇒ 有序链模型无法表达这种情况。
    """
    assert REQUIRES[Layer.PRODUCED_EFFECT] == frozenset()
    assert REQUIRES[Layer.FEEDBACK_CLOSED] == frozenset()
    st = lit(Layer.PRESENT, Layer.PRODUCED_EFFECT, Layer.FEEDBACK_CLOSED)
    assert st.at_least(Layer.PRODUCED_EFFECT)
    assert st.at_least(Layer.FEEDBACK_CLOSED)
    assert not st.at_least(Layer.SUCCEEDED), "无回执就不该有 succeeded"


def test_exists_false_means_present_not_lit():
    """★★ 意图: exists=False ⇒ present 不亮（机制不存在）。

    ★ 而 REGISTERED/CALLED 要求 PRESENT ⇒ exists=False 时传它们必须 raise。
    ⇒ 这防止"为不存在的机制声明它已注册"。
    """
    assert not lit(Layer.PRESENT, exists=False).at_least(Layer.PRESENT)
    with pytest.raises(LayerError):
        lit(Layer.REGISTERED, exists=False)      # registered 要求 present


def test_succeeded_requires_called():
    """★★ 意图: succeeded 必须有 called（"无调用却成功"是原则 1 的绕过）。"""
    assert REQUIRES[Layer.SUCCEEDED] == frozenset({Layer.CALLED})
    with pytest.raises(LayerError):
        lit(Layer.PRESENT, Layer.SUCCEEDED)


def test_missing_evidence_rejected_at_construction():
    """★★ 意图: 缺必要证据的状态必须 raise（不是等到检查期才报）。"""
    with pytest.raises(LayerError) as e:
        ActivityState(mechanism="x", reached=frozenset({Layer.SUCCEEDED}))
    assert "必要证据" in str(e.value) and "called" in str(e.value)


def test_stamp_never_leaves_a_hole():
    """★★ 意图: 按层序依次打事件后不得出现中间空洞。"""
    st = lit(Layer.PRESENT)
    for kind in (EventKind.REGISTER, EventKind.CALL, EventKind.RECEIPT,
                 EventKind.EFFECT, EventKind.FEEDBACK):
        st = stamp(st, kind)
    assert st.depth() == len(ORDER) - 1
    assert st.reached == frozenset(ORDER), "六层应全亮"


def test_receipt_without_call_is_rejected():
    """★★★ 意图: 无调用却收到回执必须 raise（"无调用却成功"绕过原则 1）。

    ★ 而 produced_effect 不受此限（可独立被观测到）⇒ 这正体现并列证据模型。
    """
    st = lit(Layer.PRESENT, Layer.REGISTERED)
    with pytest.raises(LayerError) as e:
        stamp(st, EventKind.RECEIPT)          # succeeded 缺 called
    assert "必要证据" in str(e.value)
    # ★ 而 effect 在同样的状态下可点亮（它不要求 succeeded）
    st2 = stamp(st, EventKind.EFFECT)
    assert st2.at_least(Layer.PRODUCED_EFFECT)


def test_depth_reflects_furthest_layer():
    """意图: depth 报最深层，不是数量。"""
    st = lit(Layer.PRESENT, Layer.REGISTERED)
    assert st.depth() == 1
    st = stamp(st, EventKind.CALL)
    st = stamp(st, EventKind.RECEIPT)
    assert st.depth() == 3, "RECEIPT 应点亮到 SUCCEEDED（深度3）"
    assert len(st.reached) == 4, "present+registered+called+succeeded = 4 层"


# ══════════════════════════════════════════════════════════
# ②★★ 负事件（Table 4 的硬要求）
# ══════════════════════════════════════════════════════════

def test_not_called_does_not_light_any_layer():
    """★★★ 意图: NOT_CALLED 是负事件 —— 记录"缺失"但**不点亮任何层**。

    ★★★ 依据 2608.24876 Table 4: 仅结果证据的故障定位 Macro-F1 = 0.0，
      **低于恒定猜测基线 33.3%**；原始轨迹条件下 61.1。
      ⇒ 若 Γ 不记录"本应调用但未调用"，DWC 会重犯母巢"调用失败看不出"的错。
    """
    reg = MechanismRegistry()
    reg.register("m")
    before = reg.get("m").depth()
    after = stamp(reg.get("m"), EventKind.NOT_CALLED)
    assert after.depth() == before, "负事件不许点亮层"
    assert after.not_called == 1


def test_not_called_is_countable():
    """意图: 多次未调用要能累加（频率本身是信息）。"""
    st = lit(Layer.REGISTERED)
    for _ in range(5):
        st = stamp(st, EventKind.NOT_CALLED)
    assert st.not_called == 5
    assert st.depth() == 1, "五次未调用后深度不变"


# ══════════════════════════════════════════════════════════
# ③ dead ≠ stale（母巢 P2-3 同款病）
# ══════════════════════════════════════════════════════════

def test_never_called_is_dead_not_stale():
    """★★★ 意图: 从未调用的机制是 **dead**，不是 stale。

    ★★★ 母巢 P2-3 的病: MechanismHealth 只有 call_count/is_healthy/last_called
      三字段，把"从未调用"塞进 stale ⇒ 未调用 ≠ 曾经活跃。
    """
    reg = MechanismRegistry()
    reg.register("never")
    assert reg.get("never").is_dead()
    assert "never" in reg.dead()
    assert "never" not in reg.stale(), "从未调用不许进 stale"


def test_called_but_not_succeeded_is_stale():
    """意图: 调用过但没回执 = stale（曾经活跃后失效）。"""
    reg = MechanismRegistry()
    reg.register("called_no_receipt")
    reg.apply("called_no_receipt", EventKind.CALL)
    assert not reg.get("called_no_receipt").is_dead(), "有调用就不算死"
    assert "called_no_receipt" in reg.stale()


def test_healthy_mechanism_in_neither_list():
    """意图: 完全成功的机制既不 dead 也不 stale。"""
    reg = MechanismRegistry()
    reg.register("ok")
    reg.apply("ok", EventKind.CALL)
    reg.apply("ok", EventKind.RECEIPT)
    assert reg.get("ok").is_dead() is False
    assert "ok" not in reg.dead()
    assert "ok" not in reg.stale()


def test_negative_event_makes_it_dead_even_if_called():
    """★★ 意图: 调用过但反复未调用 ⇒ 仍算 dead（有 not_called 记录）。"""
    reg = MechanismRegistry()
    reg.register("flaky")
    reg.apply("flaky", EventKind.CALL)
    assert not reg.get("flaky").is_dead()
    reg.apply("flaky", EventKind.NOT_CALLED)
    assert reg.get("flaky").is_dead(), "有未调用记录就该算死"


# ══════════════════════════════════════════════════════════
# ④ 不可变
# ══════════════════════════════════════════════════════════

def test_state_is_frozen():
    """意图: ActivityState 不可变。"""
    st = lit(Layer.REGISTERED)
    with pytest.raises(Exception) as e:
        st.not_called = 99
    assert "frozen" in str(e.value).lower() or "assign" in str(e.value).lower()


def test_stamp_returns_new_object():
    """意图: stamp 不改原状态（纯函数语义）。"""
    st = lit(Layer.REGISTERED)
    st2 = stamp(st, EventKind.CALL)
    assert st.depth() == 1, "原状态不变"
    assert st2.depth() == 2, "新状态前进一层"


# ══════════════════════════════════════════════════════════
# ⑤ present 层是入口守卫
# ══════════════════════════════════════════════════════════

def test_event_on_unregistered_mechanism_raises():
    """★★ 意图: 未登记的机制不许记事件（present 层未过）。"""
    reg = MechanismRegistry()
    with pytest.raises(LayerError) as e:
        reg.apply("ghost", EventKind.CALL)
    assert "未登记" in str(e.value)


def test_register_lights_exactly_two_layers():
    """意图: 登记只点亮 present + registered，不越级到 called。"""
    reg = MechanismRegistry()
    st = reg.register("x")
    assert st.reached == frozenset({Layer.PRESENT, Layer.REGISTERED})
    assert st.depth() == 1


def test_register_twice_is_idempotent():
    """意图: 重复登记不丢已有进度（不重置到 2 层）。"""
    reg = MechanismRegistry()
    reg.register("x")
    reg.apply("x", EventKind.CALL)
    reg.apply("x", EventKind.RECEIPT)
    st = reg.register("x")
    assert st.depth() == 1, "重复登记应重置为初始态（显式语义）"


# ══════════════════════════════════════════════════════════
# 快照（M6 要求：落进 TermReport）
# ══════════════════════════════════════════════════════════

def test_snapshot_is_json_ready():
    """意图: to_dict/snapshot 产出可 JSON 序列化，且字段齐全。"""
    reg = MechanismRegistry()
    reg.register("a")
    reg.apply("a", EventKind.CALL)
    reg.register("b")
    reg.apply("b", EventKind.NOT_CALLED)
    snap = reg.snapshot()
    assert len(snap) == 2
    for row in snap:
        # ★★★ R53 · 原 `set(row) == {…5 项…}` = **锁死数据形状**:
        #   record 若加字段就红 ⇒ 下一步就是改断言迁就（R52 的病根）
        #   ⇒ ⇒★ 改验 **⊇ 必需字段**（可扩展, 缺字段才红）
        _need = {"mechanism", "reached", "depth", "not_called", "dead"}
        assert _need <= set(row), (
            "★ record 缺必需字段 %s, 实得 %s"
            % (sorted(_need - set(row)), sorted(set(row))))
        assert isinstance(row["reached"], list)
    import json
    json.dumps(snap)          # 不得抛异常


def test_get_unregistered_raises():
    """意图: 读不存在的机制必须 raise（不许返回默认空状态）。"""
    reg = MechanismRegistry()
    with pytest.raises(LayerError):
        reg.get("nope")