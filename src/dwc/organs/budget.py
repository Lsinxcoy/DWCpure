# -*- coding: utf-8 -*-
"""budget · 退火编辑预算 b_t（2609.24972 式 4 · 设计稿门⑥「归因粒度」）。

定位声明 · **DWC-AUTO**（自我强化 · 判据 G1 定位门）
  ★ 服务门组第 ⑥ 步: 约束本轮可**独立归因**的编辑数 b_t（cos 退火 —
    越到后期预算越紧, 末轮 b_min=1 ⇒ 只剩一个可归因编辑）。
  ★ 不抢位: 不算分（judge）· 不判接受（split/noncomp 门）· 不落编辑
    （applier）; 本模块只给**议程**（b_t 值）+ **计数判定**（若干编辑
    是否超预算 — 调用方喂编辑清单, 本模块不生成编辑）。
  ★ 与 state.b_t 的关系（R151 前的实况）: foundation/state.py L63 有
    `b_t: int = 0` 字段但**全仓无写入方**（grep 零命中）⇒ 空挂字段;
    本模块给议程后, state.b_t 仍由调用方按议程填值（不在本模块内改
    别的模块的字段语义 — 防顺手牵羊）。

★★★ TRUTH_SOURCE（判据 G2）
  编辑清单由调用方给（本模块不数"隐含改动" — 那需要语义判断; 只会计
  显式申报的 (component, hunk) 条目）。
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

#: 议程默认参数（式 4 口径 — 全是可调管理参数, 不是论文报值）
DEFAULT_B_MIN: int = 1
DEFAULT_B_MAX: int = 8
DEFAULT_HORIZON: int = 20          # T（议程总长）


class BudgetError(Exception):
    """议程/判定的显式拒绝（b_min<1 / b_max<b_min / T<1 / t 越界）。"""


@dataclass(frozen=True)
class EditItem:
    """一条显式申报的可归因编辑（本模块的最小计数单位）。

    ★ component ∈ 𝒦 词表（调用方保证 — 本模块不查 vocab 字典, 只记名）;
      hunk = 编辑锚（文件/函数边界 — 论文口径"按函数/文件边界切,
        不按 hunk 切"的 DWC 落点是函数/文件级 id）。
    ★ (component, hunk) 二元组去重口径: 同组件同锚的两条 = 一簇
      （对齐 R42 信用日志的精确同键合并 — 不做语义相似合并）。
    """

    component: str
    hunk: str

    def __post_init__(self) -> None:
        if not self.component or not self.hunk:
            raise BudgetError("EditItem 须有非空 component + hunk")


def schedule(t: int, T: int = DEFAULT_HORIZON, *,
             b_min: int = DEFAULT_B_MIN,
             b_max: int = DEFAULT_B_MAX) -> int:
    """★ 式 4 逐字: b_t = ⌈ b_min + (b_max − b_min)·½(1 + cos(π t / T)) ⌉。

    ★ t ∈ [0, T]: t=0 ⇒ 最宽（cos0=1 ⇒ b_max）; t=T ⇒ 最紧（cosπ=−1
      ⇒ b_min）。越界 ⇒ BudgetError（t 是议程坐标, 不是"第几个 round"
      的随便数）。
    ★ b_min ≥1（末轮至少 1 个可归因编辑 — 论文显式: b_min=1 ⇒ 最后一轮
      只允许一个）; b_max ≥ b_min; T ≥1。
    """
    for name, v in (("T", T), ("b_min", b_min), ("b_max", b_max)):
        if isinstance(v, bool) or not isinstance(v, int) or v < 1:
            raise BudgetError("%s 须 ≥1 整数, 实 %r" % (name, v))
    if b_max < b_min:
        raise BudgetError("b_max(%d) ≥ b_min(%d) 才合法" % (b_max, b_min))
    if isinstance(t, bool) or not isinstance(t, int) or not (0 <= t <= T):
        raise BudgetError("t 须 ∈ [0, T=%d], 实 %r" % (T, t))
    raw = b_min + (b_max - b_min) * 0.5 * (1 + math.cos(math.pi * t / T))
    return int(math.ceil(raw - 1e-12))    # 减 epsilon 防 3.0000000001 ceil 成 4


def check(items: Sequence[EditItem], t: int, T: int = DEFAULT_HORIZON, *,
          b_min: int = DEFAULT_B_MIN, b_max: int = DEFAULT_B_MAX
          ) -> Dict[str, Any]:
    """★ 计数判定: 若干编辑去重后是否 ≤ b_t（议程一眼可复核）。"""
    if not isinstance(items, (list, tuple)):
        raise BudgetError("items 须序列")
    keys = {(i.component, i.hunk) for i in items}     # 精确同键合并
    b = schedule(t, T, b_min=b_min, b_max=b_max)
    n = len(keys)
    return {"t": t, "T": T, "b_t": b, "n_edits": n,
            "within_budget": n <= b,
            "verdict": ("ok" if n <= b else "over_budget"),
            "components": sorted({c for c, _ in keys}),
            "note": ("%d 条申报编辑（去重 %d 键）%s 预算 b_t=%d"
                     % (len(items), n,
                        "≤" if n <= b else ">", b))}


def anneal_report(T: int = DEFAULT_HORIZON, *, b_min: int = DEFAULT_B_MIN,
                  b_max: int = DEFAULT_B_MAX) -> Dict[str, Any]:
    """★ 全议程展开（审计面: 每 t 的 b_t — 单调不增性是结构性质）。"""
    rows = [{"t": t, "b_t": schedule(t, T, b_min=b_min, b_max=b_max)}
            for t in range(T + 1)]
    bs = [r["b_t"] for r in rows]
    mono = all(bs[i] >= bs[i + 1] for i in range(len(bs) - 1))
    if not mono:      # 结构断言（议程实现错了要炸, 不是等测试发现）
        raise BudgetError("议程非单调不增: %r（cos 议程实现缺陷）" % (bs,))
    return {"T": T, "b_min": b_min, "b_max": b_max, "rows": rows,
            "monotone_nonincreasing": mono,
            "endpoints": {"t0": bs[0], "tT": bs[-1]},
            "note": "末轮 b_t=%d（≠ b_min ⇒ 议程未收紧到论文口径）"
                    % bs[-1] if bs[-1] != b_min else
                    "末轮 = b_min = %d ✓" % b_min}


BUDGET_MECHANICS: Dict[str, str] = {
    "formula": "式 4: b_t = ceil(b_min + (b_max−b_min)·½(1+cos(πt/T)))",
    "anneal_direction": "t=0 最宽(b_max) → t=T 最紧(b_min=1)",
    "why": "不约束 proposer 会把很多互不相关的修改捆成一个候选 ⇒ 测得的改变难以归因到具体机制（原文理由）",
    "counting": "本模块只会计显式申报的 (component, hunk) — 不数隐含改动（要语义判断）",
    "state_b_t": "state.py L63 字段存在但无写入方（R151 前实况）⇒ 议程在此, 填值归调用方",
}
