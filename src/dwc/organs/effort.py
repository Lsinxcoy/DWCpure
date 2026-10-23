"""effort · 探索预算调度（2609.14858 §5.2「交替节流-冲刺」· R252）。

定位声明 · **DWC-AUTO**（自我强化 · 判据 G1 定位门）
  ★ 调度的是回放预算（dream K₂/段步）, 不碰记忆读写 ⇒ 非 DWC-MEM。
  ★ 不抢位: 不声明 REPLACES。

=== 论文观察（§5.2 Figure 6 · ConvDiv 单任务）===
  性能上升期: attempt 110 → 50（节流）; 平台期: 50 → 92/91/86（冲刺）。
  论文自陈这是**学到的行为观察**, 未形式化为算法, 且只在单任务报告。
  ⇒ ⇒★ 深读报告标注「DWC 照搬时必须自验」⇒ 本模块**不照抄系数**:
    factor/eps 全部必传无默认（β 同款纪律: 没出处就不给默认）;
    自验 = simulate_schedule 合成序列回放（升→平台→升 交替可复现, 测试锁）。

★★★ TRUTH_SOURCE（判据 G2）
  本模块**不判分** —— gain 由调用方从 judge 观测分（max_s）算出;
  本模块只做纯函数预算决策（输入 gain, 输出 next effort）。
"""
from __future__ import annotations

from collections.abc import Sequence


class EffortError(ValueError):
    """参数违规必须大声报错（G7 静默门同族）。"""


def next_effort(*, gain: float, prev: int, plateau_eps: float,
                factor_up: float, factor_down: float,
                lo: int, hi: int) -> int:
    """★ §5.2 交替: gain<ε 平台 ⇒ 冲刺（×factor_up）; 有 gain ⇒ 节流（×factor_down）。

    ★ gain 语义: 本轮相对上轮的改进量（如 max_s 差）, 由调用方从 judge
      观测分算 —— 本函数不产分（G2）。
    ★ factor_up>1（冲刺放大）, 0<factor_down<1（节流收缩）— 论文行为方向;
      具体数值**必传**（论文未报告 ⇒ 不编默认, β 同款纪律）。
    ★ 夹在 [lo, hi]（lo≥1, hi≥lo）; 结果取整（effort 是整数预算）。
    """
    if not isinstance(prev, int) or isinstance(prev, bool) or prev < 1:
        raise EffortError("prev 须 ≥1 整数, 实得 %r" % (prev,))
    if plateau_eps < 0:
        raise EffortError("plateau_eps 须 ≥0, 实得 %r" % (plateau_eps,))
    if factor_up <= 1.0:
        raise EffortError(
            "factor_up 应 >1（平台期冲刺放大 — §5.2 行为方向）, 实得 %r"
            % (factor_up,))
    if not 0 < factor_down < 1.0:
        raise EffortError(
            "factor_down 应 ∈(0,1)（上升期节流收缩 — §5.2）, 实得 %r"
            % (factor_down,))
    if not isinstance(lo, int) or isinstance(lo, bool) or lo < 1:
        raise EffortError("lo 须 ≥1 整数, 实得 %r" % (lo,))
    if not isinstance(hi, int) or isinstance(hi, bool) or hi < lo:
        raise EffortError("hi 须为 ≥lo 整数, 实得 hi=%r lo=%r" % (hi, lo))
    if gain < plateau_eps:
        nxt = prev * factor_up        # 平台: 冲刺
    else:
        nxt = prev * factor_down      # 上升: 节流
    return max(lo, min(hi, int(round(nxt))))


def simulate_schedule(*, gains: Sequence[float], init: int,
                      plateau_eps: float, factor_up: float,
                      factor_down: float, lo: int, hi: int) -> list[int]:
    """★ 自验回放（深读「必须自验」的兑现）: 逐 gain 序列复现调度轨迹。

    返回与 gains 等长的 effort 序列（第 t 个 = 用了第 t 个 gain 后的预算）。
    ★ 纯合成 — 不触网不产分, 单测/审计可复跑。
    """
    out: list[int] = []
    prev = init
    for g in gains:
        prev = next_effort(gain=g, prev=prev, plateau_eps=plateau_eps,
                           factor_up=factor_up, factor_down=factor_down,
                           lo=lo, hi=hi)
        out.append(prev)
    return out
