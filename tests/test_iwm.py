# -*- coding: utf-8 -*-
"""iwm（organs/iwm.py）· 环节⑤ 防漂移的契约 + 行为测试。

★★★ 为什么这份测试重要
  iwm 是七器官的最后一块（⑤ 防漂移）—— 在它之前「落完怎么验」没有任何
  独立观测方；而它最易犯的病正是母巢 MWM 那种「记了账但没人消费」。
  ⇒⇒ 所以这里锁三件事: ① GDI 分量算得对（构造真值）② Q6 不假装可信
      ③ drift 在 run_term 里**真的改变任务源**（门控消费, 原则 9）。

★ 判据族: ARCHITECTURE §4.5 · ORGAN_INTERFACES §六（四方法 + 不变量）
  · EVOLUTION_CORE_V2 §7（GDI Eq.8–13 / grounded / coupling）
  · STATE_SCHEMA §三（State 四层 frozen = I6 构造面）
"""
from __future__ import annotations

import io
import os
import re
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.foundation.dial_config import DialError, load_drift  # noqa: E402
from dwc.foundation.state import (  # noqa: E402
    ArchitectureVersions, AssetVersions, ExecutionContext, GateSnapshot, State,
)
from dwc.organs.iwm import (  # noqa: E402
    Advice, IwmError, IwmOrgan, Observations,
    distributional_delta, lexical_delta, semantic_delta, structural_delta,
)


def _base_iwm(**kw) -> IwmOrgan:
    """θ₀ = 空库结构观测（run_term 场景）。"""
    b = Observations(
        structural={"total": 0.0, "used": 0.0, "effective": 0.0,
                    "used_ratio": 0.0, "effective_ratio": 0.0})
    return IwmOrgan(baseline=b, **kw)


def _state(**gate_kw) -> State:
    g = dict(wm_version="wm1", wm_dev_accuracy=0.8, wm_dev_n=10,
             theta_dev=0.5, theta_dev_kind="rolling", gate1_verdict="pass",
             iwm_verdict="ok", iwm_reason="", train_verdict="ok")
    g.update(gate_kw)
    return State(
        S=AssetVersions("m1", "s1", "t1", "c1"),
        H=ArchitectureVersions("h1", "wf1", "org1"),
        G=GateSnapshot(**g),
        X=ExecutionContext(chain_id="C1", decision_id="D1", turn_index=0,
                           task_id="t1", task_source="sealed_dev",
                           split="dev"))


# ══════════════════════════════════════════════════════════
# GDI 四信号 · 分量（真值 = 构造对）
# ══════════════════════════════════════════════════════════

def test_semantic_delta_formula():
    """Eq.8: 同向 0 · 反向 1 · 垂直 0.5。"""
    assert semantic_delta((1.0, 0.0), (1.0, 0.0)) == 0.0
    assert semantic_delta((1.0, 0.0), (-1.0, 0.0)) == 1.0
    assert abs(semantic_delta((1.0, 0.0), (0.0, 1.0)) - 0.5) < 1e-9
    with pytest.raises(IwmError, match="等长"):
        semantic_delta((1.0, 0.0), (1.0, 0.0, 0.0))


def test_lexical_delta_jsd_bounds():
    """Eq.9: 相同=0 · 完全异 ∈ (0,1] · 空语料=None（不是 0）。"""
    assert lexical_delta({"a": 5}, {"a": 5}) == 0.0
    far = lexical_delta({"a": 10}, {"b": 10})
    assert far is not None and 0.0 < far <= 1.0
    assert lexical_delta({"a": 1}, {}) is None
    assert lexical_delta({}, {"a": 1}) is None


def test_structural_delta_formula():
    """Eq.10: 相同=0 · 同键翻倍≈1（ε 平滑 ⇒ 极接近但不精确等于 1）· 无共同键=None。"""
    assert structural_delta({"x": 3.0}, {"x": 3.0}) == 0.0
    assert abs(structural_delta({"x": 5.0}, {"x": 10.0}) - 1.0) < 1e-9
    assert structural_delta({"x": 1.0}, {"y": 9.0}) is None


def test_distributional_delta_wasserstein():
    """Eq.11: 相同=0 · 整体平移 1 ⇒ W1=1 · 空序列=None。"""
    assert distributional_delta((0.5, 1.0), (0.5, 1.0)) == 0.0
    assert abs(distributional_delta((0.0, 1.0), (1.0, 2.0)) - 1.0) < 1e-9
    assert distributional_delta((), (1.0,)) is None


# ══════════════════════════════════════════════════════════
# GDI 合成 · θ₀ 锚定 · 缺席归一
# ══════════════════════════════════════════════════════════

def test_gdi_zero_against_theta0():
    """相对 θ₀ 的恒等观测 ⇒ GDI=0（不是小, 是 0）。"""
    iwm = _base_iwm()
    d = iwm.drift(iwm.baseline)
    assert d["gdi"] == 0.0, d["gdi"]
    assert d["theta0_anchored"] is True
    assert d["over_tau"] is False


def test_gdi_anchor_is_theta0_not_previous_round():
    """★★ App.A.2: 漂移对 θ₀ 度量 —— 漂过的中间态之后回到 θ₀ ⇒ 仍是 0。"""
    iwm = _base_iwm()
    drifted = Observations(structural={"total": 9.0, "used": 9.0,
                                       "effective": 9.0, "used_ratio": 1.0,
                                       "effective_ratio": 1.0})
    d1 = iwm.drift(drifted)
    assert d1["gdi"] is not None and d1["gdi"] > 0
    d2 = iwm.drift(iwm.baseline)      # 中途"回到" θ₀ —— 相对 θ₀ ⇒ 0
    assert d2["gdi"] == 0.0, \
        "★ 必须相对 θ₀ 而非上一轮（否则高方差会掩盖长期漂移）"


def test_gdi_absent_signals_renormalized_not_zeroed():
    """★★ 缺席信号: 只有 structural 有效 ⇒ GDI == 该分量（权重归一）。

    若把缺席当 0 参与合成, GDI 会被稀释成 w_st*Δ ⇒ 掉到 0.25 以下 ⇒
    「没测」被当成「没漂」（G7 同族）—— 本测试锁归一。
    """
    iwm = _base_iwm()
    cur = Observations(structural={"total": 10.0, "used": 10.0,
                                   "effective": 10.0, "used_ratio": 1.0,
                                   "effective_ratio": 1.0})
    d = iwm.drift(cur)
    st = d["gdi_parts"]["structural"]
    assert st == 1.0, st
    assert abs(d["gdi"] - st) < 1e-9, \
        "缺席归一后 GDI 应等于唯一有效分量 %s, 实得 %s" % (st, d["gdi"])
    assert any("lexical" in a for a in d["absent"]), "缺席必须逐条列出"
    assert d["over_tau"] is True     # 1.0 ≥ 0.35


def test_gdi_none_when_all_signals_absent():
    """四路全缺席 ⇒ GDI=None + 说明（不许冒充 0）。"""
    iwm = IwmOrgan(baseline=Observations())
    d = iwm.drift(Observations())
    assert d["gdi"] is None
    assert any("不可算" in r for r in d["reasons"])
    assert d["over_tau"] is False    # None ⇒ 不可判超阈（不假装超）


def test_gdi_weighted_mix_two_signals():
    """两路有效 ⇒ 按权重归一合成（Eq.12–13 的缺席版）。"""
    iwm = IwmOrgan(baseline=Observations(
        lexical={"a": 1, "b": 1}, structural={"total": 2.0}))
    cur = Observations(lexical={"c": 1, "d": 1}, structural={"total": 4.0})
    d = iwm.drift(cur)
    st, lx = d["gdi_parts"]["structural"], d["gdi_parts"]["lexical"]
    assert st is not None and lx is not None
    w_l, w_st = iwm.weights["lexical"], iwm.weights["structural"]
    expect = (w_l * lx + w_st * st) / (w_l + w_st)
    assert abs(d["gdi"] - expect) < 1e-9
    assert abs(sum(d["gdi_weights_effective"].values())
               - (w_l + w_st)) < 1e-9


# ══════════════════════════════════════════════════════════
# CAR · 回归 · grounded
# ══════════════════════════════════════════════════════════

def test_car_formula_and_division_by_zero():
    """Eq.25: CAR = (𝒬_c−𝒬_0)/GDI; GDI≈0 ⇒ None + 说明（不是 inf）。"""
    iwm = _base_iwm()
    cur = Observations(structural={"total": 10.0, "used": 10.0,
                                   "effective": 10.0, "used_ratio": 1.0,
                                   "effective_ratio": 1.0})
    d = iwm.drift(cur, quality_baseline=0.5, quality_now=0.75)
    # GDI=1.0 ⇒ CAR = 0.25/1.0
    assert d["car"] is not None and abs(d["car"] - 0.25) < 1e-9
    d0 = iwm.drift(iwm.baseline, quality_baseline=0.5, quality_now=0.75)
    assert d0["car"] is None and "分母" in d0["car_why"]
    dn = iwm.drift(cur)
    assert dn["car"] is None and "quality" in dn["car_why"]


def test_regression_check_requires_both_sides_and_judge():
    """回归: 缺两侧 ⇒ not_checked; 有 judge+两侧 ⇒ 真 verdict。"""
    from dwc.organs.judge import Judge
    iwm = _base_iwm()
    d = iwm.drift(iwm.baseline)
    assert d["regression"]["verdict"] == "not_checked"

    iwm2 = _base_iwm(judge=Judge())
    def ev(rows):
        return {"details": [{"task_id": t, "success": s} for t, s in rows]}
    d_ok = iwm2.drift(iwm2.baseline,
                      judge_baseline=ev([("a", True), ("b", True)]),
                      judge_current=ev([("a", True), ("b", True)]))
    assert d_ok["regression"]["verdict"] == "ok"
    # ★ regression 必须**同一批任务**上通过数下降（judge R24 判据:
    #   任务集不同 ⇒ not_comparable —— 那是它的正确行为, 不是 bug）
    d_bad = iwm2.drift(iwm2.baseline,
                       judge_baseline=ev([("a", True), ("b", True)]),
                       judge_current=ev([("a", True), ("b", False)]))
    assert d_bad["regression"]["verdict"] == "regression"
    d_nc = iwm2.drift(iwm2.baseline,
                      judge_baseline=ev([("a", True), ("b", True)]),
                      judge_current=ev([("a", True)]))
    assert d_nc["regression"]["verdict"] == "not_comparable"


def test_grounded_reads_dials():
    """grounded 双条件: 读 dials.yaml 三布尔（AND）。"""
    g = _base_iwm().grounded()
    assert g["ok"] is True
    assert set(g["conds"]) == {"rho_grounded", "rho_external_content",
                               "not_agent_rewrite"}


def test_coupling_explicitly_not_computed():
    """协同进化三条件: 显式 not_computed（不冒充 0 —— 诚实边界）。"""
    d = _base_iwm().drift(_base_iwm().baseline)
    assert d["coupling"]["computed"] is False
    assert "未实现" in d["coupling"]["why"]


# ══════════════════════════════════════════════════════════
# Q6 · self_trust（对照臂 + min_samples）
# ══════════════════════════════════════════════════════════

def test_self_trust_insufficient_samples_degrades():
    """★ 样本不足 ⇒ trust=0 + degrade=True（ARSI: 不足时 advice 不可信）。"""
    iwm = _base_iwm()
    r = iwm.self_trust()
    assert r["trust"] == 0.0 and r["degrade"] is True
    assert "min_samples" in r["reason"]


def test_self_trust_two_arms_and_threshold():
    """对照臂: 样本足时 trust=iwm 臂成功率, 低于 degrade_below ⇒ 降级。"""
    iwm = _base_iwm()
    n = iwm.min_samples
    for k in range(n):
        iwm.record_round(adopted=True, improved=(k >= n - 1))   # 1/n < 0.35
    r = iwm.self_trust()
    assert r["n_iwm"] == n and r["degrade"] is True
    assert abs(r["trust"] - 1.0 / n) < 1e-9
    # 拉高成功率 ⇒ 不降级
    iwm2 = _base_iwm()
    for k in range(n):
        iwm2.record_round(adopted=True, improved=True)
        iwm2.record_round(adopted=False, improved=(k % 2 == 0))  # baseline 臂
    r2 = iwm2.self_trust()
    assert r2["trust"] == 1.0 and r2["degrade"] is False
    assert r2["baseline_rate"] is not None


# ══════════════════════════════════════════════════════════
# governor_advice · 守卫发出口
# ══════════════════════════════════════════════════════════

def test_advice_degrades_when_self_trust_low():
    """样本不足（trust=0）⇒ degrade_to_baseline=True 且 reason 说清来源。"""
    a = _base_iwm().governor_advice(_state(), layer="all")
    assert isinstance(a, Advice)
    assert a.degrade_to_baseline is True
    assert "self_trust" in a.reason


def test_advice_degrades_on_gdi_over_tau():
    """GDI ≥ tau ⇒ degrade（drift 缓存进 advice 的通路）。"""
    iwm = _base_iwm()
    cur = Observations(structural={"total": 9.0, "used": 9.0,
                                   "effective": 9.0, "used_ratio": 1.0,
                                   "effective_ratio": 1.0})
    iwm.drift(cur)                       # GDI=1.0 ≥ 0.35
    a = iwm.governor_advice(_state(), layer="llm")
    assert a.degrade_to_baseline is True and "GDI" in a.reason
    assert "layer=llm" in a.reason       # layer 至少被标注（不假装分层）


def test_advice_downweights_in_yellow_zone():
    """★ GDI 黄区 [tau/2, tau) ⇒ downweight（预落地降权）。"""
    # 构造黄区: Δ=|100−x|/100 ∈ [0.175, 0.35) ⇒ x=125 ⇒ Δ=0.25
    iwm2 = IwmOrgan(baseline=Observations(structural={"total": 100.0}))
    iwm2.drift(Observations(structural={"total": 125.0}))
    a = iwm2.governor_advice(_state())
    assert iwm2._last_drift["gdi"] is not None
    assert 0.5 * iwm2.tau_gdi <= iwm2._last_drift["gdi"] < iwm2.tau_gdi
    assert a.downweight_pre_enactment is True and "黄区" in a.reason
    assert a.degrade_to_baseline is True   # trust=0（样本不足）也同时为真


def test_advice_block_law_forces_degrade():
    """state.G.laws_block 非空 ⇒ degrade（state 真被读, 不是死参数）。"""
    iwm = _base_iwm()
    # 先给足样本让 trust 不再触发, 隔离 laws_block 这一路
    for _ in range(iwm.min_samples):
        iwm.record_round(adopted=True, improved=True)
    a0 = iwm.governor_advice(_state())
    assert a0.degrade_to_baseline is False, a0.reason
    a1 = iwm.governor_advice(_state(laws_block=("G3",)))
    assert a1.degrade_to_baseline is True and "G3" in a1.reason


def test_advice_forbids_dream_when_grounding_broken():
    """grounded 失败 ⇒ forbid_default_dream=True。"""
    iwm = _base_iwm()
    iwm._dials = {"dials": {"rho_grounded": True, "rho_external_content": False,
                            "rho_agent_can_rewrite": False}}
    a = iwm.governor_advice(_state())
    assert a.forbid_default_dream is True and "grounded" in a.reason


def test_advice_rejects_bad_layer():
    """阳性: layer 越界 ⇒ 大声报错。"""
    with pytest.raises(IwmError, match="layer"):
        _base_iwm().governor_advice(_state(), layer="memory")


def test_iwm_source_never_touches_organ_internals():
    """★★ 不变量（ORGAN_INTERFACES §六）: advice 不得读器官内部状态。

    机械检查: iwm.py 源码不含对世界模型的属性访问/导入 ——
    （layer 字符串 "world_model" 是**值**不是访问, 模式已排除。）
    """
    src = io.open(os.path.join(ROOT, "src", "dwc", "organs", "iwm.py"),
                  encoding="utf-8").read()
    hits = re.findall(r"\.world_model\b|from dwc\.organs\.world_model|"
                      r"import world_model|self\._wm\b", src)
    assert not hits, "★ iwm 读了世界模型内部: %s" % hits


# ══════════════════════════════════════════════════════════
# probe · config 校验 · State 冻结
# ══════════════════════════════════════════════════════════

def test_probes_all_ok():
    """三个 Level3 探针全过（真值 = 构造对）。"""
    iwm = _base_iwm()
    for pid in ("gdi_bounds", "jsd_range", "semantic_formula"):
        r = iwm.probe(pid)
        assert r["ok"] is True, "%s: %s" % (pid, r["detail"])


def test_unknown_probe_raises():
    """阳性: 未知 probe_id ⇒ 报错并列可用项（不静默 ok）。"""
    with pytest.raises(IwmError, match="可用"):
        _base_iwm().probe("all_good")


def test_drift_config_validation(tmp_path):
    """★ drift.yaml 校验: Σweights≠1 / 缺 tau ⇒ DialError（yaml 不是文本）。"""
    p1 = tmp_path / "d1.yaml"
    p1.write_text("drift:\n  weights: {semantic: 0.5, lexical: 0.5,"
                  " structural: 0.5, distributional: 0.5}\n"
                  "  tau_gdi: 0.3\n  car_floor: 0.0\n"
                  "  degrade_below: 0.35\n  min_samples: 5\n",
                  encoding="utf-8")
    with pytest.raises(DialError, match="Σweights"):
        load_drift(str(p1))
    p2 = tmp_path / "d2.yaml"
    p2.write_text("drift:\n  weights: {semantic: 0.3, lexical: 0.25,"
                  " structural: 0.25, distributional: 0.2}\n",
                  encoding="utf-8")
    with pytest.raises(DialError, match="tau_gdi"):
        load_drift(str(p2))


def test_state_layers_are_frozen():
    """★ I6 构造面: State 四层冻结（中途改不动 = 冻结是实测不是声称）。"""
    st = _state()
    with pytest.raises(Exception):
        st.S = _asset_altered()          # frozen dataclass 拒绝重绑
    with pytest.raises(Exception):
        st.G.laws_block = ("X",)         # 字段重绑同样拒绝


def _asset_altered() -> AssetVersions:
    return AssetVersions("m2", "s1", "t1", "c1")


# ══════════════════════════════════════════════════════════
# 环节⑤ 接线 · run_term 的门控消费（原则 9）
# ══════════════════════════════════════════════════════════

def test_run_term_records_drift_and_consumes_signal():
    """★★★ 门控消费: 注入 iwm ⇒ rep.drift 留痕, 且 drift_degrade 任务
    与 over_tau **一致**（信号真的改变任务源, 不是只做账本）。"""
    from dwc.harness.run_term import TermRunner
    iwm = _base_iwm()                     # θ₀=空库, term 后 total 会变 ⇒ 漂
    tr = TermRunner(iwm=iwm)
    rep = tr.run_term("t", n_steps=1)
    assert rep.drift is not None and rep.drift["theta0_anchored"] is True
    kinds = [x["kind"] for x in rep.next_task_source["tasks"]]
    assert ("drift_degrade" in kinds) == bool(rep.drift["over_tau"]), \
        "消费点必须与 over_tau 一致: drift=%s kinds=%s" % (
            rep.drift.get("gdi"), kinds)


def test_run_term_drift_degrade_fires_when_over_tau():
    """★ 超阈场景: θ₀=空库与 term 后状态差到 GDI≥tau ⇒ drift_degrade 在任务源。"""
    from dwc.harness.run_term import TermRunner
    tr = TermRunner(iwm=_base_iwm())
    rep = tr.run_term("t", n_steps=1)
    assert rep.drift["over_tau"] is True, rep.drift["gdi"]
    assert "drift_degrade" in [x["kind"] for x in rep.next_task_source["tasks"]]
    # 缺席三路必须可见（run_term 只有 structural —— 不是"测了没漂"）
    assert any("lexical" in a for a in rep.drift["absent"])


def test_run_term_without_iwm_keeps_old_behavior():
    """不注入 ⇒ rep.drift=None, 任务源无 drift_degrade（可选注入纪律）。"""
    from dwc.harness.run_term import TermRunner
    rep = TermRunner().run_term("t", n_steps=1)
    assert rep.drift is None
    kinds = [x["kind"] for x in rep.next_task_source["tasks"]]
    assert "drift_degrade" not in kinds
