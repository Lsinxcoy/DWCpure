# -*- coding: utf-8 -*-
"""iwm · 内省自检 · 第五器官承载进化循环环节⑤ 防漂移（ARCHITECTURE §4.5）。

定位声明 · **DWC-AUTO**（自我强化 · 判据 G1 定位门）
  ★ 判词（与 world_model/llm 同款逻辑）: 不碰 MemoryKernel、不参与记忆读写；
    它服务环节⑤「落完怎么验」= 自我强化的质检端。
  ★ 不抢位: 不声明 REPLACES（v3 起 iwm 就在清单里, 本轮是首次实现）。

★★★ TRUTH_SOURCE（判据 G2）
  iwm **不产生**成功判定 —— 回归判定来自 judge.regression_check,
  质量分 quality 由调用方从 judge 传入; GDI 是「成对观测的距离」,
  不是「是否成功」的判断（2603.06333: 漂移测量不需要任务真值源）。

=== 接口契约（docs/ORGAN_INTERFACES §六, 四方法）===
  governor_advice(state, layer) -> Advice   守卫②③ 发出口
      ★★★ 不变量: 只读 State 公开四层, **不得**读任何器官内部状态
         （第 20 项裁决的根源: 跨层自评是违规的）
  self_trust() -> dict                       Q6 内省器自检
      ★ 它度量的是 **iwm 自己**（对照臂 + min_samples 下限）——
        守卫① **不可**用它（§9 第 20 项已否决候选甲）
  drift(current) -> dict                     环节⑤ 的观测（GDI 四信号 + 回归）
      ★★★ 输出必须被某处**门控消费**（原则 9）—— 消费点在 run_term
        的 _next_task_source（drift_degrade 任务）—— 不许只做账本
  probe(probe_id) -> dict                    Level 3 行为验证探针

=== 环节⑤ 三来源的落地状态（EVOLUTION_CORE_V2 §7）===
  ① GDI 四信号（2603.06333 App. B, Eq.8–13）  ✓ 本文件 gdi 四函数
  ② grounded 双条件（2609.13406 §2.2）        ✓ grounded() 读 dials 三布尔
  ③ 协同进化三条件（2608.10299 §2.2）          ✗ 未做（coupling 显式 not_computed）

=== 诚实边界 ===
  ★ Δ_semantic 需要嵌入源, DWC 当前**没有** ⇒ 信号缺席显式（权重运行期归一到
    其余三路, 不静默改 0 —— G7 同族）。函数已实现且 probe 覆盖, 缺的只是数据源。
  ★ GDI 权重/tau 是人工初值（config/drift.yaml 已标 agent_choice ——
    论文 Eq.14/15 的值是学出来的, DWC 无标注预算）。
  ★ ECE 过置信惩罚未做: Advice 接口没有自报置信字段（无输入无校准, 要做
    须先改接口 —— 见 config/drift.yaml 诚实边界②）。
  ★ 回归风险只到「保护组回归二值」（judge.regression_check）;
    Appendix D 的概率上界未实现。
  ★ drift 相对 **θ₀（构造时固化）** 度量, 不是相对上一轮
    （App. A.2 原文: 防止短期高方差掩盖长期漂移）。
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from dwc.foundation import dial_config
from dwc.foundation.state import State

#: 系统外真值源（G2）—— 回归判定在 judge, 质量分由调用方传
TRUTH_SOURCE = {
    "声明": "iwm 不自判成功：回归判定 = dwc.organs.judge.regression_check；"
            "quality 由调用方从 judge 传入",
    "真值源位置": "dwc.organs.judge.TRUTH_SOURCE（config/anchors/dev.json）",
    "自判禁止": "GDI 是成对观测的距离不是成功判断（2603.06333: 漂移测量"
                "不需要任务真值源）；self_trust 度量 iwm 自己, 不做守卫①",
}

_EPS = 1e-12


class IwmError(Exception):
    """iwm 的违规必须大声报错（不许静默降级 —— G7 静默门同族）。"""


@dataclass(frozen=True)
class Observations:
    """θ₀ / 当前 的成对观测面（GDI 四信号的输入）。

    ★ 缺席即 None —— 不许用 0 冒充（0 是「测过, 没漂」, None 是「没测」）。
      semantic: 嵌入向量（DWC 当前无嵌入源 ⇒ 调用方通常传 None）
      lexical: 词频 dict
      structural: 结构标量 dict（如 memory.usage_stats 的五个数）
      distributional: 分数序列（经验分布样本）
    """

    semantic_embedding: Optional[Tuple[float, ...]] = None
    lexical: Optional[Dict[str, int]] = None
    structural: Optional[Dict[str, float]] = None
    distributional: Optional[Tuple[float, ...]] = None


@dataclass(frozen=True)
class Advice:
    """守卫②③ 的输出（ORGAN_INTERFACES §六原文四字段）。"""

    degrade_to_baseline: bool
    downweight_pre_enactment: bool
    forbid_default_dream: bool
    reason: str


# ══════════════════════════════════════════════════════════
# GDI 四信号（2603.06333 Appendix B · 全部落在 [0,1]）
# ══════════════════════════════════════════════════════════

def semantic_delta(e0: Tuple[float, ...], e1: Tuple[float, ...]) -> float:
    """Δ_semantic = (1 − s_cos)/2 （Eq.8）。两向量等长且非零才可算。"""
    if len(e0) != len(e1):
        raise IwmError("semantic: 两嵌入等长才可比, 实得 %d vs %d"
                       % (len(e0), len(e1)))
    num = sum(a * b for a, b in zip(e0, e1))
    n0 = math.sqrt(sum(a * a for a in e0))
    n1 = math.sqrt(sum(b * b for b in e1))
    if n0 <= _EPS or n1 <= _EPS:
        raise IwmError("semantic: 零向量无余弦相似度")
    cos = max(-1.0, min(1.0, num / (n0 * n1)))
    return (1.0 - cos) / 2.0


def _normalize(freq: Dict[str, int]) -> Dict[str, float]:
    total = float(sum(v for v in freq.values() if v > 0))
    if total <= 0:
        return {}
    return {k: v / total for k, v in freq.items() if v > 0}


def lexical_delta(p0: Dict[str, int], pt: Dict[str, int]) -> Optional[float]:
    """Δ_lexical = JSD(P₀‖P_t) （Eq.9, log2 ⇒ ∈[0,1]）。

    任一侧词频和为 0（空语料）⇒ None（不可比 —— 不是 0, 0 意味着测过没漂）。
    """
    a, b = _normalize(p0), _normalize(pt)
    if not a or not b:
        return None
    keys = sorted(set(a) | set(b))
    m = {k: 0.5 * (a.get(k, 0.0) + b.get(k, 0.0)) for k in keys}

    def kl(p, q):
        s = 0.0
        for k in keys:
            pv = p.get(k, 0.0)
            if pv > 0:
                s += pv * math.log2(pv / max(q.get(k, 0.0), _EPS))
        return s

    jsd = 0.5 * kl(a, m) + 0.5 * kl(b, m)
    return max(0.0, min(1.0, jsd))


def structural_delta(s0: Dict[str, float],
                     st: Dict[str, float]) -> Optional[float]:
    """Δ_structural = (1/K)·Σ min(1, |s₀−s_t|/(|s₀|+ε)) （Eq.10）。

    ★ 分母用 |s₀|（设计写 s₀+ε, 但结构量若为负会翻符号 ⇒ 取绝对值, 语义不变）。
    共同键数 K=0 ⇒ None。
    """
    keys = [k for k in s0 if k in st]
    if not keys:
        return None
    acc = 0.0
    for k in keys:
        d = abs(float(s0[k]) - float(st[k])) / (abs(float(s0[k])) + _EPS)
        acc += min(1.0, d)
    return acc / len(keys)


def distributional_delta(xs: Tuple[float, ...],
                         ys: Tuple[float, ...]) -> Optional[float]:
    """Δ_distributional = 1-Wasserstein（Eq.11, 等分位网格上的平均绝对差）。

    任一侧为空 ⇒ None。等长时即逐位平均 |差|；不等长用分位插值到同一网格。
    """
    if not xs or not ys:
        return None
    sx, sy = sorted(float(x) for x in xs), sorted(float(y) for y in ys)

    def quantile(sorted_x, q):
        if len(sorted_x) == 1:
            return sorted_x[0]
        pos = q * (len(sorted_x) - 1)
        lo = int(math.floor(pos))
        hi = min(lo + 1, len(sorted_x) - 1)
        frac = pos - lo
        return sorted_x[lo] * (1.0 - frac) + sorted_x[hi] * frac

    m = max(len(sx), len(sy), 2)
    acc = 0.0
    for i in range(m):
        q = (i + 0.5) / m
        acc += abs(quantile(sx, q) - quantile(sy, q))
    return acc / m


# ══════════════════════════════════════════════════════════
# IwmOrgan
# ══════════════════════════════════════════════════════════

class IwmOrgan:
    """内省自检器官 —— 环节⑤ 防漂移的观测与降级建议发出方。

    ★ θ₀ 在构造时固化（App. A.2: 漂移相对初始状态度量, 不是相对上一轮 ——
      否则短期高方差会掩盖长期漂移）。
    """

    def __init__(self, baseline: Observations,
                 config_path: Optional[str] = None,
                 judge: Optional[Any] = None):
        #: 档位（config/drift.yaml · 必填无默认 + Σweights==1 已校验）
        self.config = (dial_config.load_drift(config_path) if config_path
                       else dial_config.load_drift())
        d = self.config["drift"]
        self.weights: Dict[str, float] = {k: float(d["weights"][k])
                                          for k in dial_config.DRIFT_WEIGHT_KEYS}
        self.tau_gdi = float(d["tau_gdi"])
        self.car_floor = float(d["car_floor"])
        self.degrade_below = float(d["degrade_below"])
        self.min_samples = int(d["min_samples"])
        #: θ₀ —— 基线观测（初始状态, 构造后不许换）
        self.baseline = baseline
        #: 回归判定的 judge（可选注入 —— 没注入时回归显式 not_checked）
        self._judge = judge
        #: Q6 对照臂: {"iwm": [n, n_success], "baseline": [n, n_success]}
        self._arms: Dict[str, List[int]] = {"iwm": [0, 0], "baseline": [0, 0]}
        #: 最近一次 drift 结果（governor_advice 的输入之一）
        self._last_drift: Optional[Dict[str, Any]] = None
        self._dials = dial_config.load_dials()

    # ── 环节⑤ · drift ──────────────────────────────────────
    def drift(self, current: Observations,
              quality_baseline: Optional[float] = None,
              quality_now: Optional[float] = None,
              judge_baseline: Optional[Dict[str, Any]] = None,
              judge_current: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """GDI 四信号（对 θ₀）+ CAR + 回归风险 + grounded —— 环节⑤ 的观测。

        ★ 缺席信号进 absent（显式）, GDI 对**有效**信号做权重归一 ——
          缺一信号不许把 GDI 整体算成 0（那是把「没测」当「没漂」）。
        """
        b, c = self.baseline, current
        parts: Dict[str, Optional[float]] = {"semantic": None,
                                             "lexical": None,
                                             "structural": None,
                                             "distributional": None}
        absent: List[str] = []

        if b.semantic_embedding is None or c.semantic_embedding is None:
            absent.append("semantic: 无嵌入源（DWC 当前没有嵌入提供方）")
        else:
            parts["semantic"] = semantic_delta(b.semantic_embedding,
                                               c.semantic_embedding)

        if b.lexical is None or c.lexical is None:
            absent.append("lexical: 未提供词频语料")
        else:
            parts["lexical"] = lexical_delta(b.lexical, c.lexical)
            if parts["lexical"] is None:
                absent.append("lexical: 空语料不可比")

        if b.structural is None or c.structural is None:
            absent.append("structural: 未提供结构标量")
        else:
            parts["structural"] = structural_delta(b.structural, c.structural)
            if parts["structural"] is None:
                absent.append("structural: 无共同键不可比")

        if b.distributional is None or c.distributional is None:
            absent.append("distributional: 未提供分数序列")
        else:
            parts["distributional"] = distributional_delta(b.distributional,
                                                           c.distributional)
            if parts["distributional"] is None:
                absent.append("distributional: 空序列不可比")

        # ── GDI = Σ w_i Δ_i, 只在**有效**信号上归一（Eq.12–13 的缺席版）──
        used_w = {k: self.weights[k] for k, v in parts.items() if v is not None}
        if used_w:
            wsum = sum(used_w.values())
            if wsum <= 0:
                gdi = None
                why = "有效信号的权重和为 0（四权重全 0 不该过校验, 程序性错误）"
            else:
                gdi = sum(self.weights[k] * parts[k] for k in used_w) / wsum
                why = ""
        else:
            gdi, why = None, "四信号全部缺席 ⇒ GDI 不可算（不是 0）"

        # ── CAR = (𝒬_c − 𝒬_0)/GDI （Eq.25 · E.3 决策规则）──
        car: Optional[float] = None
        car_why = ""
        if quality_baseline is None or quality_now is None:
            car_why = "quality 未由调用方从 judge 传入 ⇒ CAR 不可算"
        elif gdi is None:
            car_why = "GDI 不可算 ⇒ CAR 不可算"
        elif gdi <= _EPS:
            car_why = "GDI≈0（相对 θ₀ 无漂移）⇒ CAR 分母为 0, 无意义"
        else:
            car = (float(quality_now) - float(quality_baseline)) / gdi

        # ── 回归风险（judge 保护组回归 · 2603.06333 App.D 的二值版）──
        if judge_baseline is not None and judge_current is not None:
            if self._judge is None:
                regression = {"verdict": "not_checked",
                              "why": "给了两侧 eval 但 iwm 未注入 judge"}
            else:
                regression = self._judge.regression_check(judge_baseline,
                                                          judge_current)
        else:
            regression = {"verdict": "not_checked",
                          "why": "调用方未提供两侧 eval（term 内只有一期）"}

        out = {
            "gdi": gdi,
            "gdi_parts": parts,
            "gdi_weights_effective": used_w,
            "absent": absent,
            "theta0_anchored": True,     # ★ 相对 θ₀, 不是相对上一轮（App.A.2）
            "car": car,
            "car_why": car_why,
            "regression": regression,
            "grounded": self.grounded(),
            "coupling": {"computed": False,
                         "why": "协同进化三条件需 S 变化对证据（2608.10299）,"
                                "本轮未实现 —— 显式 not_computed, 不冒充 0"},
            "tau_gdi": self.tau_gdi,
            "over_tau": (gdi is not None and gdi >= self.tau_gdi),
            "reasons": absent + ([why] if why else []),
        }
        self._last_drift = out
        return out

    # ── grounded 双条件（2609.13406 §2.2, AND 缺一不可）────────
    def grounded(self) -> Dict[str, Any]:
        """① 内容来自系统外 ② base 在 agent 外 —— 读 dials.yaml 三布尔。"""
        d = self._dials["dials"]
        conds = {
            "rho_grounded": bool(d["rho_grounded"]),
            "rho_external_content": bool(d["rho_external_content"]),
            "not_agent_rewrite": not bool(d["rho_agent_can_rewrite"]),
        }
        ok = all(conds.values())
        return {"ok": ok, "conds": conds,
                "why": "GAI grounded 双条件（AND）: " + " ∧ ".join(
                    "%s=%s" % (k, v) for k, v in conds.items())}

    # ── Q6 · self_trust ─────────────────────────────────────
    def record_round(self, adopted: bool, improved: bool) -> None:
        """记一轮: 采纳了 advice ⇒ iwm 臂, 否则 baseline 臂（对照臂）。"""
        arm = "iwm" if adopted else "baseline"
        self._arms[arm][0] += 1
        if improved:
            self._arms[arm][1] += 1

    def self_trust(self) -> Dict[str, Any]:
        """Q6 内省器自检 —— 度量 **iwm 自己**（ARSI calibrate 同构）。

        ★ 样本不足 ⇒ trust=0 且 degrade=True（ARSI min_samples 语义:
          不足时 advice 不可信, 系统降级 baseline —— 不假装可信）。
        ★ ECE 过置信惩罚未做: Advice 没有自报置信字段（见模块诚实边界）。
        """
        n_i, s_i = self._arms["iwm"]
        n_b, s_b = self._arms["baseline"]
        rate_i = (s_i / n_i) if n_i else None
        rate_b = (s_b / n_b) if n_b else None
        if n_i < self.min_samples:
            return {"trust": 0.0, "degrade": True, "n_iwm": n_i,
                    "n_baseline": n_b, "iwm_rate": rate_i,
                    "baseline_rate": rate_b, "degrade_below": self.degrade_below,
                    "reason": "iwm 臂样本 %d < min_samples %d ⇒ trust 记 0"
                              "（ARSI: 样本不足时 advice 不可信）"
                              % (n_i, self.min_samples)}
        trust = float(rate_i)
        degrade = trust < self.degrade_below
        # ★ R140 · ECE 轻接线（B 方案落地 — 不碰 Advice 四字段契约）:
        #   iwm 臂历史投影成 (trust, improved) 序列 ⇒ 外置 calibration 模块
        #   算 ECE ⇒ "过置信"作为**附加字段**返回（调用方自愿消费; 不减
        #   字段不改契约 — 纯增量）。样本全同 conf ⇒ ECE=0（信任自洽）;
        #   失败历史留痕 ⇒ 可审计（不是算不出就缺席）。
        ece: Dict[str, Any] = {"available": False}
        try:
            from dwc.foundation.calibration import (
                expected_calibration_error, from_trust_history)
            # 真序列: 每轮 (trust_snapshot, improved) — 历史无逐轮 trust
            # 快照（Q6 只存聚合计数）⇒ 用末态 trust 回填（诚实标注近似）
            series = [(trust, True)] * s_i + [(trust, False)] * (n_i - s_i)
            res = expected_calibration_error(
                from_trust_history(series), n_bins=10)
            ece = {"available": True, "ece": res["ece"],
                   "approx": "trust 为末态回填（Q6 只存聚合计数, 无逐轮快照）"}
        except Exception as exc:   # noqa: BLE001 — 留痕不静默（G7）
            ece = {"available": False, "error": "%s: %s"
                   % (type(exc).__name__, exc)}
        return {"trust": trust, "degrade": degrade, "n_iwm": n_i,
                "n_baseline": n_b, "iwm_rate": rate_i,
                "baseline_rate": rate_b, "degrade_below": self.degrade_below,
                "ece": ece,
                "reason": ("trust=%.3f < %.2f ⇒ 降级" % (trust, self.degrade_below))
                          if degrade else "trust=%.3f ≥ %.2f ⇒ 保持"
                          % (trust, self.degrade_below)}

    # ── 守卫②③ 发出口 · governor_advice ─────────────────────
    def governor_advice(self, state: State, layer: str = "all") -> Advice:
        """给哪一层的降级建议（ORGAN_INTERFACES §六）。

        ★★★ 不变量: 只读 State 公开四层 + 本器官自记观测 + config ——
          **不得**读任何器官的内部状态（第 20 项裁决的根源）。
        ★ 本轮判定是**系统级**的: layer 只进 reason 标注, 不区分三档
          （分层判定要 layer 各自的观测, 还没有 —— 不假装分了）。
        """
        if layer not in ("world_model", "llm", "all"):
            raise IwmError("layer=%r 不合法 ∈ {world_model, llm, all}" % (layer,))
        reasons: List[str] = []
        t = self.self_trust()
        d = self._last_drift
        g = self.grounded()

        degrade = bool(t["degrade"])
        if degrade:
            reasons.append("self_trust: " + t["reason"])
        if d is not None:
            if d["over_tau"]:
                degrade = True
                reasons.append("GDI %.4f ≥ tau %.2f ⇒ 漂移超阈"
                               % (d["gdi"], d["tau_gdi"]))
            if d["regression"].get("verdict") == "regression":
                degrade = True
                reasons.append("保护组回归: " +
                               str(d["regression"].get("why", ""))[:80])
        if state.G.laws_block:
            degrade = True
            reasons.append("block 级铁律触发: %s" % (list(state.G.laws_block),))

        downweight = False
        if d is not None and d["gdi"] is not None and not d["over_tau"] \
                and d["gdi"] >= 0.5 * d["tau_gdi"]:
            downweight = True
            reasons.append("GDI %.4f 进入半阈黄区（≥ tau/2）⇒ 预落地降权"
                           % d["gdi"])
        if d is not None and d["car"] is not None and d["car"] < self.car_floor:
            downweight = True
            reasons.append("CAR %.4f < floor %.2f ⇒ drift without improvement"
                           % (d["car"], self.car_floor))

        forbid = not g["ok"]
        if forbid:
            reasons.append("grounded 失败: " + g["why"])
        if d is not None and d["coupling"]["computed"] is False:
            reasons.append("coupling 未计算（显式边界, 不参与判定）")
        reasons.append("layer=%s（本轮系统级判定, 分层观测未备）" % layer)

        return Advice(degrade_to_baseline=degrade,
                      downweight_pre_enactment=downweight,
                      forbid_default_dream=forbid,
                      reason="；".join(reasons) if reasons else "无触发")

    # ── Level 3 探针（CONSUMER_VERIFICATION §二）──────────────
    def probe(self, probe_id: str) -> Dict[str, Any]:
        """行为级探针 —— 拿构造已知的输入验信号本身（真值 = 构造对）。

        ★ 未知 probe_id ⇒ 大声报错并列可用项（不静默返回 ok）。
        """
        if probe_id == "gdi_bounds":
            # ★ 恒等对 = current 就是 θ₀（相对 θ₀ 度量, 不另造对象）
            same = self.baseline
            d0 = self.drift(same)
            far = Observations(lexical={"c": 9, "d": 2},
                               structural={"total": 500.0, "used_ratio": 0.99},
                               distributional=(0.0, 0.0, 0.0))
            d1 = self.drift(far)
            ok = (d0["gdi"] is not None and d0["gdi"] == 0.0
                  and d1["gdi"] is not None and 0.0 < d1["gdi"] <= 1.0
                  and all(v is None or 0.0 <= v <= 1.0
                          for v in d1["gdi_parts"].values()))
            return {"probe_id": probe_id, "ok": bool(ok),
                    "detail": "恒等对 GDI=%s · 极端对 GDI=%s · 分量∈[0,1]"
                              % (d0["gdi"], d1["gdi"])}
        if probe_id == "jsd_range":
            j_same = lexical_delta({"x": 2}, {"x": 2})
            j_far = lexical_delta({"x": 10}, {"y": 10})
            ok = (j_same == 0.0 and j_far is not None and 0.0 < j_far <= 1.0)
            return {"probe_id": probe_id, "ok": bool(ok),
                    "detail": "JSD(同)=%s · JSD(异)=%s" % (j_same, j_far)}
        if probe_id == "semantic_formula":
            d_same = semantic_delta((1.0, 0.0), (1.0, 0.0))
            d_opp = semantic_delta((1.0, 0.0), (-1.0, 0.0))
            ok = d_same == 0.0 and d_opp == 1.0
            return {"probe_id": probe_id, "ok": bool(ok),
                    "detail": "Δ(同向)=%s · Δ(反向)=%s" % (d_same, d_opp)}
        raise IwmError("未知 probe_id=%r；可用: gdi_bounds / jsd_range / "
                       "semantic_formula" % probe_id)
