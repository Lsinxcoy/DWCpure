# -*- coding: utf-8 -*-
"""R444 · P2 · 按任务选档（规则优先）。

★★★ 定位（G1）: **DWC-AUTO** —— 自我强化的资源层：让"用多少子弹"跟着任务走。

为什么要有这个模块
------------------
DWC 现在全局一个 `reasoning_effort`、一个固定预算档。
简单题用牛刀是浪费，难题省子弹是掉分。HarnessPro 的做法是按 profile 分档。

★★★ 两条硬约束（来自 DWC 自己的实测，不是论文）
  1. **R411 实测「推理档越高越差」** ⇒ 所有 profile 的 `reasoning_effort` 默认
     `None`（继承全局）。选档只调**预算**，不偷偷改推理力度。
     要改推理力度必须走 A/B，不许在路由规则里夹带。
  2. **规则优先，不引 LLM 分类器当默认路径**。
     用模型做确定性判断是反模式（贵、不稳、不可解释）。
     规则命中率天然 100%（最后有 standard 兜底）。

规则顺序（先匹配先赢）
----------------------
  research → deep → compact → lean → standard
  把"最贵的判断"放前面：宁可把长任务判成 deep，也不要把研究任务判成 compact。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from dwc.llm.budget import ToolBudget


@dataclass(frozen=True)
class Profile:
    """一个档位：预算 + （可选）推理力度。"""

    name: str
    budget: ToolBudget
    # ★ None = 继承客户端全局值。选档**不**改推理力度（R411 实测越高越差）。
    reasoning_effort: Optional[str] = None
    desc: str = ""


PROFILES: Dict[str, Profile] = {
    "compact": Profile(
        "compact", ToolBudget(economy_after=3, strict_after=5, finalize_after=8),
        desc="一句话就能办完的小事"),
    "lean": Profile(
        "lean", ToolBudget(economy_after=5, strict_after=8, finalize_after=12),
        desc="单一交付物、步骤少"),
    "standard": Profile(
        "standard", ToolBudget(economy_after=6, strict_after=10, finalize_after=15),
        desc="默认档（与 R441 的全局默认一致）"),
    # ★ finalize 一律 ≤ NATIVE_TOOLS_MAX_ROUNDS(15)：循环硬上限只有 15，
    #   写 36 就是承诺一个永远不会到来的轮次（幻影预算）。要抬高上限先做测量。
    "deep": Profile(
        "deep", ToolBudget(economy_after=8, strict_after=12, finalize_after=15),
        desc="多文件/审计/重构：晚一点催，但硬上限仍是 15"),
    "research": Profile(
        "research", ToolBudget(economy_after=8, strict_after=12, finalize_after=15),
        desc="要检索、要对比多个来源：晚一点催，硬上限仍是 15"),
}

_RESEARCH_KW = ("调研", "检索", "搜索", "查资料", "文献", "论文", "多个来源", "对比多个")
_DEEP_KW = ("审计", "重构", "架构", "设计", "调用链", "多文件", "全量", "逐个核对", "逐个检查")
# ★ 多交付物标记：有这些词就不是"一句话能办完"
_MULTI_KW = ("并", "然后", "再", "分别", "每个", "所有", "逐一", "逐项", "同时")

_DEEP_LEN = 600
_COMPACT_LEN = 40
_LEAN_LEN = 120


def _hit(text: str, kws) -> str:
    for k in kws:
        if k in text:
            return k
    return ""


def explain(task: str) -> Dict[str, Any]:
    """返回选档结果 + 命中的规则 + 信号（可审计，不猜）。"""
    t = str(task or "")
    n = len(t)
    r = _hit(t, _RESEARCH_KW)
    if r:
        return {"profile": "research", "rule": "research_keyword",
                "signals": {"keyword": r, "len": n}}
    d = _hit(t, _DEEP_KW)
    if d:
        return {"profile": "deep", "rule": "deep_keyword",
                "signals": {"keyword": d, "len": n}}
    if n > _DEEP_LEN:
        return {"profile": "deep", "rule": "long_text", "signals": {"len": n}}
    m = _hit(t, _MULTI_KW)
    if n <= _COMPACT_LEN and not m:
        return {"profile": "compact", "rule": "short_single",
                "signals": {"len": n}}
    if n <= _LEAN_LEN:
        return {"profile": "lean", "rule": "medium",
                "signals": {"len": n, "multi_marker": m}}
    return {"profile": "standard", "rule": "default", "signals": {"len": n}}


def choose(task: str) -> Profile:
    """按任务文本选档。永远有返回值（standard 兜底）。"""
    name = explain(task)["profile"]
    return PROFILES.get(name) or PROFILES["standard"]
