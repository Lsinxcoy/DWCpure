"""Move-on 停止判决 —— R125 · 项2-4b（Meta-recursion 的 goal/停止决策件）。

文献锚: R98 §⑨①「自适应停止 = move-on 四判据（5 连败 / 90% 峰值 / 时间 /
2× 预算）+ 成本-收益阈值」; 综述 §3.6.5 Table 8 meta-recursion 维明文
「'期望收益低于成本/风险时是否停'的记录」。★ 综述 §7 自陈无标准可抄
⇒ 本判决表是 R98 候选的**落地**, 不是超编。

语义（goal/停止 = meta-recursion 的第三子项, 与机制复用/后继质量并列）:
  · 一条 verdict ∈ {continue, move_on} + 触发判据名（判据名可审计）
  · 每判据带参数默认值与管理口径注记（无明文不发明, 每条标来源类型）
  · 数据不足 ⇒ verdict="continue" + status="insufficient"（X2 同族:
    不装「停止」也不装「继续」理由 — 如实说数据不够）
  · 任一**停**判据触发即 move_on（判据是并集, 不是加权评分）

判据集（五条 — R98 四判据 + §3.6.5 成本收益阈值, 全部源字面）:
  C1 loss_streak    : 连续 k_worst 次 loss（5 连败 R98/AFlow 字面）
  C2 peak_exploited : 已达标率 ≥ peak_frac 的历史峰值（90% 字面）⇒
                      剩余空间 < (1-peak_frac), 边际收益不足
  C3 time_budget    : 用时 ≥ 时间预算倍率（R98 2×预算 字面）
  C4 cost_budget    : 评估成本 ≥ 预算倍率（同 2×）
  C5 cost_benefit   : 每单位成本的已验证增益 < 阈值（§3.6.5 成本-收益
                      阈值字面 — R98「cos-收益阈值」）

定位（DWC-AUTO · 自我强化）: 停止决策 = 进化 cu 循环的调度判据, 属
  自我强化环的 goal 层; verdict 只读历史序列不做外部调用。
TRUTH_SOURCE（G2）: score_history 来自 judge 逐 term 观测（dev/sealed
  文件字节域同 truth_sha8）; cost_* 来自 CostLedger 落盘账（R99 T 序列）;
  判定不采信任何自述分数; 传入序列不足 ⇒ insufficient（如上）。
"""
from __future__ import annotations

from typing import Any

#: 判据默认（管理口径 — 每条标 calibration 注记, 无文献值的明确说）
DEFAULTS: dict[str, Any] = {
    "loss_streak_k": 5,          # R98/AFlow「5 连败」字面
    "peak_frac": 0.9,            # R98「90% 峰值」字面
    "budget_frac": 2.0,          # R98「2× 预算」字面（时间/成本共用）
    "cb_min_gain_per_cost": 0.0, # §3.6.5 成本-收益阈值: >0 收益门槛初值 0
    "score_target": None,        # 无目标默认 ⇒ C2 用历史峰值当参照
}
CALIBRATION: dict[str, str] = {
    "loss_streak_k": "R98 §⑦ move-on 四判据 + AFlow patience 字面",
    "peak_frac": "R98 §⑦「90% 峰值」字面",
    "budget_frac": "R98 §⑦「2× 预算」字面",
    "cb_min_gain_per_cost": ("阈值=0: 增益/成本正比才值得继续; 正值=净收益"
                             "门槛（管理口径, 可调）— 初值 0 保守"),
}


class StopError(ValueError):
    """输入不合契约（负值/窗口 <1/序列非数值）— 大声, 不静默。"""


def _validate(score_history: list[float], *, k: int, budget_frac: float
              ) -> None:
    if not isinstance(score_history, list) or not score_history:
        raise StopError("score_history 须为非空 list")
    for s in score_history:
        if not isinstance(s, (int, float)) or isinstance(s, bool):
            raise StopError("score_history 含非数值 %r" % (s,))
    if not isinstance(k, int) or k < 1:
        raise StopError("loss_streak_k 须 ≥1 int, 实为 %r" % (k,))
    if not (isinstance(budget_frac, (int, float)) and budget_frac > 0):
        raise StopError("budget_frac 须 >0, 实为 %r" % (budget_frac,))


def _streak_moves(score_history: list[float], k: int) -> dict[str, Any]:
    """C1: 末 k 项全**低于**首项（连败）— 确定性邻域定义, 不用外推。"""
    if len(score_history) < k:
        return {"fired": False, "why": "序列 <k（%d<%d）⇒ 不判"
                % (len(score_history), k)}
    tail, head = score_history[-k:], score_history[0]
    fired = all(t < head for t in tail)
    return {"fired": fired, "head": head, "tail": tail,
            "why": ("末 %d 项全低于首项 %r" % (k, head)) if fired
            else "末 %d 项有回升/持平" % k}


def move_on_verdict(*, score_history: list[float],
                    cost_history: list[float] | None = None,
                    time_used: float | None = None,
                    time_budget: float | None = None,
                    params: dict[str, Any] | None = None
                    ) -> dict[str, Any]:
    """★ move-on 判决（五判据并集 — 任一触发即 move_on）。

    score_history: 逐 term（或逐轮）已验证分数（judge 域）。
    cost_history: 同粒度成本（CostLedger T 序列）; None ⇒ C4/C5 不判。
    time_used/time_budget: 墙钟秒; None ⇒ C3 不判。
    """
    p = dict(DEFAULTS)
    if params:
        p.update(params)
    _validate(score_history, k=p["loss_streak_k"],
              budget_frac=p["budget_frac"])

    fired: list[str] = []
    details: dict[str, Any] = {}

    c1 = _streak_moves(score_history, p["loss_streak_k"])
    details["C1_loss_streak"] = c1
    if c1["fired"]:
        fired.append("C1_loss_streak")

    peak = max(score_history)
    cur = score_history[-1]
    # ★ C2 需序列≥2: 单点时 peak==cur ⇒ "已到峰值" 恒真但无意义
    #   （峰值就是它自己 — 数据不足 ⇒ 不判, insufficient 同族纪律）
    if len(score_history) < 2:
        c2_fired = False
        details["C2_peak_exploited"] = {
            "fired": False, "status": "insufficient",
            "why": "单点序列 ⇒ 峰值=自身 ⇒ 判据无意义（不判）"}
    else:
        c2_fired = cur >= p["peak_frac"] * peak
        details["C2_peak_exploited"] = {
            "fired": c2_fired, "peak": peak, "current": cur,
            "peak_frac": p["peak_frac"],
        "why": ("当前 %.3f ≥ 峰值%.0f%%（%.3f ⇒ 剩余空间 <%.0f%%）"
                % (cur, p["peak_frac"] * 100, peak,
                   (1 - p["peak_frac"]) * 100)) if c2_fired
        else "当前 %.3f < 峰值%.0f%%" % (cur, p["peak_frac"] * 100)}
    if c2_fired:
        fired.append("C2_peak_exploited")

    if time_used is not None and time_budget is not None and time_budget > 0:
        c3_fired = time_used >= p["budget_frac"] * time_budget
        details["C3_time_budget"] = {
            "fired": c3_fired, "used": time_used,
            "budget": time_budget, "frac": p["budget_frac"]}
        if c3_fired:
            fired.append("C3_time_budget")

    if cost_history is not None and len(cost_history) == len(score_history):
        base = cost_history[:-1] or [0.0]
        base_cost = sum(base) / len(base) if base else 0.0
        c4_fired = (cost_history[-1] >= p["budget_frac"] * base_cost
                    if base_cost > 0 else False)
        details["C4_cost_budget"] = {
            "fired": c4_fired, "term_cost": cost_history[-1],
            "base_mean_cost": base_cost, "frac": p["budget_frac"]}
        if c4_fired:
            fired.append("C4_cost_budget")
        # C5 成本-收益: 末条目增益/末条目成本 < 门槛
        gain_last = score_history[-1] - (score_history[0]
                                         if len(score_history) == 1
                                         else score_history[-2])
        denom = cost_history[-1] if cost_history[-1] > 0 else None
        if denom is None:
            details["C5_cost_benefit"] = {
                "fired": False, "status": "insufficient",
                "why": "末条目成本=0 ⇒ 比率无定义（不装数）"}
        else:
            ratio = gain_last / denom
            c5_fired = ratio < p["cb_min_gain_per_cost"]
            details["C5_cost_benefit"] = {
                "fired": c5_fired, "ratio": ratio,
                "threshold": p["cb_min_gain_per_cost"],
                "status": "ok",
                "why": ("增益/成本 %.4f < 门槛 %r" % (ratio,
                                                      p["cb_min_gain_per_cost"]))
                if c5_fired else "增益/成本 %.4f ≥ 门槛" % ratio}
            if c5_fired:
                fired.append("C5_cost_benefit")
    else:
        details["C4_cost_budget"] = {"fired": False, "status": "insufficient",
                                     "why": "cost_history 缺或长度不齐"}
        details["C5_cost_benefit"] = {"fired": False, "status": "insufficient",
                                      "why": "cost_history 缺"}

    verdict = "move_on" if fired else "continue"
    status = ("insufficient" if len(score_history) < 2
              and not fired else "ok")
    return {
        "verdict": verdict, "status": status,
        "fired_criteria": fired,
        "n_criteria_checked": 5,
        "criteria": details,
        "params_used": p,
        "calibration": CALIBRATION,
        "decision_record": (   # ★ §3.6.5「是否停的记录」字面: 决策留痕
            {"question": "期望收益低于成本/风险时是否停",
             "answer": verdict, "by": fired or ["no_criterion_fired"]}),
        "★": ("任一停判据触发即 move_on（并集非评分）; "
              "insufficient=数据不足不下判（≠continue 的正当）"),
    }
