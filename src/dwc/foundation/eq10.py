"""Eq.10 Pareto 验收 —— R118 · ⑤执行轮（设计稿⑤ · DecoEvo 2607.25675 Eq.10）。

accept ⟺ ∃k∈{gain,cost}: Δ_k > δ_k  ∧  ∀j∈{gain,cost,retention}: Δ_j ≥ −η_j

★ 决策层**零权重**（稿⑤层1 字面 · 原文 "No weighted cross-objective
  aggregation"）: 任何一处不出现加权和 — 维度不可互换, 耦合维无法靠权重
  放大自己（SC-CoEvo 13/15 反向的机制被结构性掐断）。
★ retention 是**纯约束**: 不进改善门（∃k 只在 gain/cost）, 只有回退门。
★ 展示层 score_display 是等权摘要 — **无裁决效力**（稿⑤层3）:
  eq10_accept 的实现不许引用它（源码级断言在测试里锁, 破坏即红）。

门参数（稿⑤ §⑤ 逐维初值 + 校准注记 — 无明文不发明, 每个值带来源）:
  δ_gain = 0     改善门 — ★ 待校准（V 跑间抖动未测, 重复采样回填;
                          初值 0 = 不虚报"非平凡", 有 Δ 即认改善）
  δ_cost = 0.10  成本改善须 ≥10%（管理口径 — 换代有切换成本, 小于此不值）
  η_gain = 0     = 现行 no_worse 语义原样（单目标升级不放松既有底线）
  η_cost = 0.20  质量换成本合法交易的上限（超 20% = 不可控膨胀, 拒）
  η_ret  = 0     Recuris 锚点判据 — 旧能力零回退是判据不是偏好

定位（DWC-AUTO · 自我强化）: 本模块是**多目标验收判定**能力 — 提案/变体
  通过与否的支配式裁决（Eq.10），属自我强化环的验收门层。
TRUTH_SOURCE（G2 · 判定能力系统外真值源）: eq10_accept 的 Δ 输入三读数
  各有系统外真值 — ① gain = judge 对 config/anchors/dev.json（+ sealed）
  文件字节的判分序列（同 truth_sha8 对象）; ② cost = CostLedger 落盘账本
  （archive/ 决策账, 逐 term 记录）; ③ retention = regression_check 对
  保护组基线与当前的对比（同 judge 真值域）。判定只读这些来源与调用方
  传入的 Δ 值, 不采信任何自述分数; 文件缺失/缺维 ⇒ raise（Eq10Error）。
"""
from __future__ import annotations

from math import sqrt
from typing import Any

#: 改善门 δ（∃k 只在 gain/cost — retention 是纯约束不进改善门）
DELTA: dict[str, float] = {"gain": 0.0, "cost": 0.10}
#: 回退门 η（∀j 三维全查）
ETA: dict[str, float] = {"gain": 0.0, "cost": 0.20, "retention": 0.0}
#: 每个门的校准注记（诚实位 — 值从哪来/还缺什么, 稿§⑤ 表字面）
CALIBRATION: dict[str, str] = {
    "delta_gain": ("★ 初值 0（不虚报非平凡 — 有正 Δ 即认改善）; R118 重复"
                   "采样: 同底同 spec 连跑 5 次 dream V=1.0 恒等抖动 0.0"
                   "（golden 臂确定性=结构必然, 非抖动证据）— 真抖动须 LLM "
                   "臂测定后回填非平凡下限（LLM 臂样本缺, 如实待校准）"),
    "delta_cost": "管理口径 10%（换代有切换成本, 小于 10% 的省钱不值得换）",
    "eta_gain": "= 现行 no_worse 原样（best≥current）— 零放松",
    "eta_cost": "管理口径 20%（gain 改善门通过时可容许变贵 ≤20%）",
    "eta_ret": ("★ 硬 0: Recuris 锚点任务判据 — 旧能力零回退是判据"
                "不是偏好"),
}
DIMENSIONS = ("gain", "cost", "retention")
IMPROVABLE = ("gain", "cost")   # ∃k 候选域（retention 不当改善目标）

#: 展示层权重（等权 — 明标无裁决效力, 稿⑤层3）
DISPLAY_WEIGHTS: dict[str, float] = {"gain": 1 / 3, "cost": 1 / 3,
                                      "retention": 1 / 3}


class Eq10Error(ValueError):
    """输入不合 Eq.10 契约（缺维/非数值）— 大声, 不静默容错。"""


def eq10_accept(deltas: dict[str, float], *,
                gates: dict[str, Any] | None = None) -> dict[str, Any]:
    """★ Eq.10 支配式验收（唯一有裁决效力的函数）。

    deltas: {"gain": Δ(越大越好), "cost": Δ(变便宜为正 — 方向已翻转),
             "retention": Δ(0 或负 — 保持量)}
    返回 {accept, improved_by, violated, deltas, gates} — 无加权和。
    """
    if not isinstance(deltas, dict):
        raise Eq10Error("deltas 须 dict, 实为 %r" % type(deltas))
    missing = [d for d in DIMENSIONS if d not in deltas]
    if missing:
        raise Eq10Error(
            "deltas 缺维 %r（三维齐才可比 — 缺维不许装可比, X2 同族）"
            % (missing,))
    vals: dict[str, float] = {}
    for d in DIMENSIONS:
        v = deltas[d]
        if not isinstance(v, (int, float)) or isinstance(v, bool):
            raise Eq10Error("deltas[%s] 须数值, 实为 %r" % (d, v))
        vals[d] = float(v)
    delta_t = dict(DELTA)
    eta_t = dict(ETA)
    if gates:
        delta_t.update(gates.get("delta", {}))
        eta_t.update(gates.get("eta", {}))

    improved = [k for k in IMPROVABLE if vals[k] > delta_t[k]]
    violated = [j for j in DIMENSIONS if vals[j] < -eta_t[j]]
    accept = bool(improved) and not violated
    return {
        "accept": accept,
        "improved_by": improved,          # 哪些维过了改善门（可为空）
        "violated": violated,             # 哪些维破了回退门
        "deltas": vals,
        "gates": {"delta": delta_t, "eta": eta_t},
        "★": ("Eq.10 支配式: 一维非平凡改善 + 全维不回退; "
              "无加权和（DecoEvo 明文 No weighted aggregation）"),
    }


def score_display(norms: dict[str, float]) -> float:
    """★ 展示层等权摘要（稿⑤层3）— **不参与任何 accept/reject 判定**。

    用途: 报告/趋势图的单值可读性。等权 = 不引入先验独裁, 但仍是聚合
    ⇒ 无裁决力; 判定只认 eq10_accept 的支配门。
    """
    missing = [d for d in DIMENSIONS if d not in norms]
    if missing:
        raise Eq10Error("norms 缺维 %r" % (missing,))
    return sum(DISPLAY_WEIGHTS[d] * float(norms[d]) for d in DIMENSIONS)


# ════════════════════════════════════════════════════════════
# 审计A · 耦合审计（稿⑤ §⑥ — 防 DecoEvo 教训的 13/15 反向）
# ════════════════════════════════════════════════════════════

def pearson(xs: list[float], ys: list[float]) -> float | None:
    """Pearson ρ — 手写（无外部依赖）; n<2 或零方差 ⇒ None（不装）。"""
    n = len(xs)
    if n != len(ys) or n < 2:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx <= 0 or syy <= 0:
        return None                       # 零方差 ⇒ ρ 无定义（不装 0）
    return sxy / sqrt(sxx * syy)


#: 耦合判定阈值（稿⑤ §⑥ |ρ|>0.8 ⇒ 标 coupled 警示伪多目标）
COUPLE_TAU = 0.8
#: 耦合审计最小样本（稿⑧: ρ 不足样本 ⇒ insufficient 不装数）
AUDIT_MIN_N = 8


def coupling_audit(samples: list[dict[str, float]]) -> dict[str, Any]:
    """维间 ρ 矩阵 + |ρ|>0.8 标 coupled（只警示不裁决 — 稿⑧.3）。"""
    n = len(samples)
    if n < AUDIT_MIN_N:
        return {"status": "insufficient_samples", "n": n,
                "need": AUDIT_MIN_N,
                "why": ("n<%d 的 ρ 不稳定 ⇒ 不出矩阵（不装数）"
                        % AUDIT_MIN_N)}
    cols = {d: [float(s[d]) for s in samples] for d in DIMENSIONS}
    rho: dict[str, float | None] = {}
    coupled: list[tuple[str, str]] = []
    for i, a in enumerate(DIMENSIONS):
        for b in DIMENSIONS[i + 1:]:
            r = pearson(cols[a], cols[b])
            rho["%s~%s" % (a, b)] = r
            if r is not None and abs(r) > COUPLE_TAU:
                coupled.append((a, b))
    return {
        "status": "ok", "n": n, "rho": rho, "coupled": coupled,
        "note": ("|ρ|>%.1f 标 coupled = 伪多目标警示（Eq.10 的 ∃k 门"
                 "会被耦合维主导）— 只警示不做裁决" % COUPLE_TAU),
    }
