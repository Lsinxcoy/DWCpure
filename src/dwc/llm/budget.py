# -*- coding: utf-8 -*-
"""R441 · P1-a · 三段式工具预算（economy → strict → finalize）。

★★★ 定位（G1）: **DWC-AUTO** —— 自我强化的执行控制层。

为什么要有这个模块
------------------
DWC 原来只有一道悬崖：`NATIVE_TOOLS_MAX_ROUNDS=15` 一到就强制 final。
模型第 14 轮还在发散探索，第 15 轮突然被掐断 —— 中间没有任何"该收着点"的信号。

三段式（借 HarnessPro §5.3 的 economy/strict/finalize）：

  economy  到点 ⇒ 提醒批量检查、别重复读、别叙述过程
  strict   到点 ⇒ 提醒停止发散，只查与当前失败直接相关的证据（每 N 次重复）
  finalize 到点 ⇒ **硬阻断**新工具调用，要求基于现有证据作答

三条纪律
--------
1. **提醒只追加**到观测，绝不重写系统提示 —— 重写会毁掉前缀（HarnessPro 的做法）。
2. **坏配置不许把顺序倒过来** —— `normalized()` 负责排序与非负。
3. **提醒文本里不许出现内部常量名/路径** —— 它是给模型看的，不是给日志看的。
"""
from __future__ import annotations

from dataclasses import dataclass

#: economy 阶段提醒
_ECONOMY = (
    "★ 进入经济阶段：把互相独立的检查**批量**做（一次列目录/一次搜完再读），"
    "不要重复读已经读过且没变的内容，也不要叙述过程。"
    "但不要为了省而跳过任务要求的验证。")

#: strict 阶段提醒
_STRICT = (
    "★ 进入收敛阶段：停止发散式探索。只查看与**当前失败或当前交付物**直接相关的证据。"
    "如果存在具体失败、无法解释的不稳定、或被改坏的交付物，先修它，不要因为阶段变了就收尾。"
    "然后重新核对一遍确切路径、接口、行为与最终状态，再结束。")


@dataclass(frozen=True)
class ToolBudget:
    """三段阈值（步数）。默认值 = 生产实测的经验值。"""

    economy_after: int = 6
    strict_after: int = 10
    finalize_after: int = 15
    reminder_every: int = 3

    def normalized(self) -> "ToolBudget":
        """排序 + 下界 1。坏配置（倒序/零/负）不许把阶段语义倒过来。"""
        def _i(x: int) -> int:
            try:
                return max(1, int(x))
            except (TypeError, ValueError):
                return 1

        e, s, f = sorted((_i(self.economy_after),
                          _i(self.strict_after),
                          _i(self.finalize_after)))
        return ToolBudget(economy_after=e, strict_after=s,
                          finalize_after=f,
                          reminder_every=_i(self.reminder_every))


def stage_of(count: int, b: ToolBudget) -> str:
    """当前处于哪一段。count 是已完成的步数。"""
    if count >= b.finalize_after:
        return "finalize"
    if count >= b.strict_after:
        return "strict"
    if count >= b.economy_after:
        return "economy"
    return "normal"


def reminder(count: int, b: ToolBudget) -> str:
    """该步是否要追加提醒；不需要 ⇒ 空串。

    · economy 只在**跨过阈值那一步**提醒一次（它不是周期性提醒）
    · strict 每 `reminder_every` 步重复一次（防止模型忘了）
    · finalize 不提醒 —— 它由 `stage_of` 驱动硬阻断，不需要软话
    """
    if count == b.economy_after:
        return _ECONOMY
    if (b.strict_after <= count < b.finalize_after
            and (count - b.strict_after) % b.reminder_every == 0):
        return _STRICT
    return ""
