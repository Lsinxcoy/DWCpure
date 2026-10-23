# -*- coding: utf-8 -*-
"""接线层（foundation/wiring.py）的契约测试。

★★★ 这个模块的定位
  R15 写了 activity.py（六层的层与事件），R16 写了 causal_chain.py（链），
  两者**没有接起来** ⇒ 六层定义了却无任何真实数据流过。
  本模块就是那条接线 ⇒ 所以它的测试就是"六层真的被点亮了吗"的证据。

★ 测什么:
  ① 五环 → 六层的映射正确（表驱动，不是 if 链）
  ② ★★★ succeeded 只认**外部回执**（judge_verdict / tool_receipt）
     —— 自报、None、不在白名单，都不算
  ③ ★★★ 负事件走接线: 写链留痕但不点亮 called
  ④ 链是唯一真值源: 活性只是链的投影
  ⑤ 未登记机制不许记事件（present 层是入口守卫）
"""
from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
from dwc.foundation.activity import EventKind, Layer  # noqa: E402
from dwc.foundation.causal_chain import ChainError  # noqa: E402
from dwc.foundation import wiring as w  # noqa: E402


def full_chain(wire, mech="scorer", cid="CH1", receipt=True):
    """走完五环。★ receipt=True 时 trace 带真实外部回执。"""
    wire.register(mech)
    payload = ({"success": True, "success_source": "tool_receipt"}
               if receipt else {})
    wire.record(mech, cid, "decision", "D1", {"action": "x"},
                recorded_at="t0")
    wire.record(mech, cid, "turn", "T1", {}, upstream_id="D1",
                recorded_at="t1")
    wire.record(mech, cid, "trace", "TR1", payload, upstream_id="T1",
                recorded_at="t2")
    # ★★ experience 环**不自动**点亮 produced_effect（下游可观测产物
    #   必须显式声明被观测到）—— 否则 feedback_closed 会因缺上游而顺序错。
    wire.record(mech, cid, "experience", "E1", {"n_obs": 1},
                upstream_id="TR1", recorded_at="t3",
                effect_observed=True)
    wire.record(mech, cid, "change", "C1", {}, upstream_id="E1",
                recorded_at="t4")
    return wire


# ══════════════════════════════════════════════════════════
# ① 映射表
# ══════════════════════════════════════════════════════════

def test_stage_to_layers_table_is_complete():
    """意图: 五个 stage 全在映射表里（不漏）。"""
    from dwc.foundation.causal_chain import STAGES
    assert set(w.STAGE_TO_LAYERS) == set(STAGES), \
        "映射表与五环白名单不一致: %s vs %s" % (
            sorted(w.STAGE_TO_LAYERS), sorted(STAGES))


def test_present_has_no_event_by_design():
    """★★ 意图: PRESENT 没有对应事件（它由 register() 点亮，不是 Γ 事件）。

    ★★ 自检踩过这个坑: 映射表里 decision→PRESENT，而 _LAYER_TO_EVENT
      没有 PRESENT ⇒ 直接查表会 KeyError。
      ⇒ 这条测试锁住"PRESENT 走 .get() 跳过"这个设计。
    """
    assert Layer.PRESENT in w.STAGE_TO_LAYERS["decision"]
    assert Layer.PRESENT not in w._LAYER_TO_EVENT, \
        "PRESENT 不该有对应事件（它由 register 直接点亮）"
    # 而其余五个层都有
    for lay in (Layer.REGISTERED, Layer.CALLED, Layer.SUCCEEDED,
                Layer.PRODUCED_EFFECT, Layer.FEEDBACK_CLOSED):
        assert lay in w._LAYER_TO_EVENT, "%s 缺事件映射" % lay


def test_five_stages_light_expected_layers():
    """★★ 意图: 每环点亮对应的层。"""
    wire = w.ActivityWiring()
    wire.register("m")
    wire.record("m", "C", "decision", "D", {}, recorded_at="t")
    # ★ register() 已点亮 present+registered ⇒ decision 环不新增层
    assert wire.state("m").depth() == 1
    assert not wire.state("m").at_least(Layer.CALLED)
    wire.record("m", "C", "turn", "T", {}, upstream_id="D")
    assert wire.state("m").depth() == 1, "turn 不新增层（registered 已亮）"
    wire.record("m", "C", "trace", "TR", {}, upstream_id="T")
    s = wire.state("m")
    assert s.at_least(Layer.CALLED) and s.depth() == 2, "trace 点亮 called"


def test_full_chain_lights_all_six():
    """★★★ 核心: 走完五环 ⇒ 六层全亮（depth=5）。"""
    wire = full_chain(w.ActivityWiring())
    s = wire.state("scorer")
    assert s.depth() == 5, "应达第 6 层（depth=5），实为 %d" % s.depth()
    assert s.reached == frozenset(
        [Layer.PRESENT, Layer.REGISTERED, Layer.CALLED, Layer.SUCCEEDED,
         Layer.PRODUCED_EFFECT, Layer.FEEDBACK_CLOSED])


def test_full_chain_without_receipt_stops_before_succeeded():
    """★★ 意图: trace 环不带回执 ⇒ 只到 called（depth=2）。"""
    wire = full_chain(w.ActivityWiring(), receipt=False)
    s = wire.state("scorer")
    assert s.at_least(Layer.CALLED)
    assert not s.at_least(Layer.SUCCEEDED), \
        "没有外部回执却点亮 succeeded —— 违反原则 1"


# ══════════════════════════════════════════════════════════
# ②★★★ succeeded 只认外部回执
# ══════════════════════════════════════════════════════════

@pytest.mark.parametrize("src", ["self_reported", "internal_check",
                                  "model_says", "", None, "TOOL_RECEIPT"])
def test_non_external_sources_do_not_light_succeeded(src):
    """★★★ 意图: 只有 judge_verdict / tool_receipt 才算 succeeded。

    ★★★ 这是六层里最容易被绕过的一层 ——
      若自报也算 succeeded，那六层就退化成"我自己说自己行"，
      2607.12790 实测的"评估器塌缩成 always-pass"就会原样重演。
    """
    assert src not in w.RECEIPT_SOURCES or src == ""
    wire = w.ActivityWiring()
    wire.register("m")
    wire.record("m", "C", "decision", "D", {}, recorded_at="t")
    wire.record("m", "C", "trace", "TR",
                {"success": True, "success_source": src},
                upstream_id="D")
    assert not wire.state("m").at_least(Layer.SUCCEEDED), \
        "source=%r 不该点亮 succeeded" % src


def test_receipt_sources_are_exactly_the_two_external_ones():
    """意图: 白名单正好是 ACTOR_DESIGN 的两个外部来源。"""
    assert w.RECEIPT_SOURCES == frozenset({"judge_verdict", "tool_receipt"})


@pytest.mark.parametrize("success", [None, False, 0, "true", 1])
def test_non_true_success_does_not_light_succeeded(success):
    """★★★ 意图: success 必须是显式 True，None（未评价）不算。

    ★★★ ACTOR_DESIGN: success: Optional[bool]，None 表示未评价，
      且规则是"None 不许当 False 也不许当 True"。
      ⇒ 若把 None 当 True，那"未评价"就成了"成功"。
    """
    wire = w.ActivityWiring()
    wire.register("m")
    wire.record("m", "C", "decision", "D", {}, recorded_at="t")
    wire.record("m", "C", "trace", "TR",
                {"success": success, "success_source": "tool_receipt"},
                upstream_id="D")
    assert not wire.state("m").at_least(Layer.SUCCEEDED), \
        "success=%r 不该点亮 succeeded（None 是未评价）" % success


def test_both_valid_sources_light_succeeded():
    """意图: 两个合法来源都能点亮（不只 tool_receipt）。"""
    for src in ("judge_verdict", "tool_receipt"):
        wire = w.ActivityWiring()
        wire.register("m")
        wire.record("m", "C", "decision", "D", {}, recorded_at="t")
        wire.record("m", "C", "trace", "TR",
                    {"success": True, "success_source": src},
                    upstream_id="D")
        assert wire.state("m").at_least(Layer.SUCCEEDED), \
            "source=%r 应点亮 succeeded" % src


def test_receipt_only_counts_on_trace_stage():
    """★★ 意图: 只有 trace 环的回执才点亮 succeeded。

    ⇒ 别的环（experience/change）即使 payload 里有回执也不认 ——
      否则"在 experience 里贴个 success_source"就能冒充调用成功。
    """
    wire = w.ActivityWiring()
    wire.register("m")
    wire.record("m", "C", "decision", "D", {}, recorded_at="t")
    wire.record("m", "C", "experience", "E",
                {"success": True, "success_source": "tool_receipt"},
                upstream_id="D")
    assert not wire.state("m").at_least(Layer.SUCCEEDED), \
        "非 trace 环的回执不该点亮 succeeded"


# ══════════════════════════════════════════════════════════
# ③★★★ 负事件
# ══════════════════════════════════════════════════════════

def test_negative_event_writes_chain_but_does_not_light():
    """★★★ 意图: 负事件**写链留痕**但不点亮 called。

    ★★★ 依据 2608.24876 Table 4: 仅结果证据的故障定位 F1=0.0，
      低于 33.3% 恒定猜测基线 ⇒ 必须记录"本应调用但未调用"。
      ⇒ 而"记录"包括链里有痕（缺失本身是信息）。
    """
    wire = w.ActivityWiring()
    wire.register("m")
    wire.record("m", "C", "decision", "D", {"expected": True},
                recorded_at="t0")
    wire.record("m", "C", "trace", "TR", {"expected": True},
                upstream_id="D", not_called=True, recorded_at="t1")
    s = wire.state("m")
    assert s.not_called == 1
    assert not s.at_least(Layer.CALLED), "负事件不许点亮 called"
    assert s.is_dead(), "有未调用记录应算 dead"
    # ★ 链里必须留痕
    recs = wire.store.trace_back("C")
    assert len(recs) == 2, "负事件也要写链（缺失也是信息）"
    assert recs[-1]["stage"] == "trace"


def test_never_called_mechanism_is_dead_not_stale():
    """★★ 意图: 从未调用 = dead，不是 stale（母巢 P2-3 同款病）。"""
    wire = w.ActivityWiring()
    wire.register("idle")
    wire.record("idle", "C", "decision", "D", {}, recorded_at="t")
    assert "idle" in wire.dead()
    assert "idle" not in wire.stale()


def test_called_no_receipt_is_stale():
    """意图: 调用过但无回执 = stale。"""
    wire = full_chain(w.ActivityWiring(), mech="m", receipt=False)
    assert "m" not in wire.dead()
    # ★ 但 depth 停在 called，没有 succeeded ⇒ 属于 stale
    assert not wire.state("m").at_least(Layer.SUCCEEDED)


# ══════════════════════════════════════════════════════════
# ④ 链是唯一真值源
# ══════════════════════════════════════════════════════════

def test_chain_is_written_every_record():
    """★★ 意图: 每次 record 都在链上留痕（活性是链的投影，不是第二真值源）。"""
    wire = full_chain(w.ActivityWiring())
    assert len(wire.store.trace_back("CH1")) == 5


def test_chain_continuity_holds_through_wiring():
    """意图: 经接线写的链必须连续（upstream 逐环对齐）。"""
    wire = full_chain(w.ActivityWiring())
    v = wire.verify("CH1")
    assert v["continuous"], "链应连续: %s" % v["breaks"]
    assert v["n_records"] == 5


def test_chains_of_tracks_mechanism_usage():
    """★★ 判据 S1 的读取点: 能回答"这机制出现在哪些链里"。"""
    wire = w.ActivityWiring()
    full_chain(wire, mech="m1", cid="CH1")
    full_chain(wire, mech="m1", cid="CH2")
    full_chain(wire, mech="m2", cid="CH3")
    assert wire.chains_of("m1") == ["CH1", "CH2"]
    assert wire.chains_of("m2") == ["CH3"]
    assert wire.chains_of("ghost") == []


def test_snapshot_includes_chains():
    """★ M6 要求: 快照能事后审计"这机制用在哪"。"""
    wire = full_chain(w.ActivityWiring())
    snap = wire.snapshot()
    assert len(snap) == 1
    row = snap[0]
    assert row["mechanism"] == "scorer"
    assert row["chains"] == ["CH1"]
    assert row["depth"] == 5
    import json
    json.dumps(snap)


# ══════════════════════════════════════════════════════════
# ⑤ present 层守卫
# ══════════════════════════════════════════════════════════

def test_unregistered_mechanism_cannot_record():
    """★★ 意图: 未登记机制不许记事件（present 层是入口守卫）。

    ★★ 注意链已经写完了才抛 —— 这是**有意的**:
      缺失也是信息（Table 4），所以先留痕再报错。
      ⇒ 测试要同时验证"抛错"与"链里有痕"。
    """
    wire = w.ActivityWiring()
    with pytest.raises(w.WiringError) as e:
        wire.record("ghost", "C", "decision", "D", {}, recorded_at="t")
    assert "未登记" in str(e.value)
    # ★ 但链里有痕（因为先 append 后报错）
    assert len(wire.store.trace_back("C")) == 1, "报错前仍应留痕"


def test_register_is_idempotent():
    """意图: 重复 register 不重置已点亮的层。"""
    wire = w.ActivityWiring()
    wire.register("m")
    wire.record("m", "C", "decision", "D", {}, recorded_at="t")
    wire.record("m", "C", "turn", "T", {}, upstream_id="D")
    before = wire.state("m").depth()
    wire.register("m")
    assert wire.state("m").depth() == before, "重复登记不该重置进度"


def test_unknown_stage_rejected():
    """意图: 未在映射表里的 stage 必须 raise（不放行）。"""
    wire = w.ActivityWiring()
    wire.register("m")
    with pytest.raises(w.WiringError) as e:
        wire.record("m", "C", "bogus", "X", {}, upstream_id=None)
    assert "映射表" in str(e.value)


# ══════════════════════════════════════════════════════════
# 判据 S3/C2 · 接线层也不许驱动
# ══════════════════════════════════════════════════════════

def test_wiring_has_no_driver():
    """★★ 意图: 接线层不许有驱动型接口（S3/C2）。"""
    for banned in ("run_next", "step", "trigger", "advance", "drive",
                   "next_turn", "start"):
        assert not hasattr(w.ActivityWiring, banned), \
            "出现驱动型接口 %r（判据 S3 禁止）" % banned


def test_public_interface_is_projection_only():
    """★ 意图: 公开接口都是"记录/查询/导出"，没有写入活性之外的副作用。"""
    pub = sorted(m for m in dir(w.ActivityWiring) if not m.startswith("_"))
    allowed = {"register", "record", "state", "chains_of", "dead", "stale",
               "snapshot", "verify", "export", "store", "registry"}
    assert set(pub) - allowed == set(), "出现计划外接口: %s" % (
        set(pub) - allowed)