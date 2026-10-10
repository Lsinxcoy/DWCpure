# -*- coding: utf-8 -*-
"""metrics · 四量采集器（R168 — measure.py 的"喂数方", 不是第二实现）。

定位声明 · **DWC-AUTO**（自我强化 · 判据 G1 定位门）
  ★ R171 的 measure.py 已把四量的**结构与口径**落全（Activation/
    FaithfulUse/DownstreamBenefit 各有 __post_init__ 校验: 分母 0 ⇒ raise,
    越界 ⇒ raise, 缺侧 ⇒ not_instrumented）; 缺的是**采集面** — ②③④
    自 R22 起一直 not_instrumented（"recall_search 不记 access" / 
    "无执行痕迹面" / "judge 分数差可算但无源"）。
  ★ 本模块只做采集 + 投影: 从 Loop/RoundLog/ledger **真数**造三量,
    交给 measure.measure() 汇总 — 不在本模块重算任何四量口径
    （避免 R144 第二实现漂移族; 时间/口径/三值全部以 measure.py 为准）。

★★★ TRUTH_SOURCE（判据 G2）
  ② activation  ← evolver 的**候选过门率**: n_gated/n_proposals（R162
    gate_all 的 gated+pending 二元输出; 生成面到过门面的检索命中 — 母巢
    病"98.8% 未访问"的 DWC 同构量: 提了没人要）
  ③ faithful    ← **落地执行率**: n_landed/n_gated（R163 landing 的
    state=adopted 数; "过门⇒照做" — 过了门不落 = 检索到不照做）
  ④ downstream  ← ledger: adopted 组与未 adopted 组的 **ΔS 均值差**
    （R156 ℒ_t 的 adopted 标记 + delta_s 字段 — 已 live 的账号素材;
    单侧空 ⇒ not_instrumented, 不拿 0 顶替）

★ 缺任何一侧源 ⇒ 该量**显式 not_instrumented**（与 measure.py 纪律同构 —
  缺席≠0: "没测"必须与"测了是 0"分开 — 母巢 98.8% 无人发现的病根就是把
  没测当没问题）。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

from dwc.organs.measure import (
    NOT_INSTRUMENTED, Activation, DownstreamBenefit, FaithfulUse,
    UpdateQuality, measure)


class MetricsError(Exception):
    """采集面的显式拒绝（输入不是已知形状 — 不猜）。"""


# ══════════════════════════════════════════════════════════
# 三个采集器（每个: 素材元组 ⇒ measure 数据类 or None）
# ══════════════════════════════════════════════════════════

def collect_activation(n_proposals: Optional[int],
                       n_gated: Optional[int]) -> Optional[Activation]:
    """② 候选过门率（分母=生成数, 分子=过门数 — 检索命中同构量）。

    ★ 任一 None 或分母 0 ⇒ None（→ not_instrumented;  Denominator 0 不是
      0% 命中 — measure 的 raise 陈述, 此处前置同义转 None, 不吞异常
      也不造数）。
    """
    if n_proposals is None or n_gated is None:
        return None
    if n_proposals <= 0:
        return None                                # 没生成 ⇒ 无分母
    return Activation(n_items=n_proposals, n_retrieved=min(n_gated,
                                                          n_proposals))


def collect_faithful(n_gated: Optional[int],
                     n_landed: Optional[int]) -> Optional[FaithfulUse]:
    """③ 落地执行率（过门⇒照做 — R163 landed=state adopted）。"""
    if n_gated is None or n_landed is None or n_gated <= 0:
        return None
    return FaithfulUse(n_retrieved_used=n_gated,
                       n_faithful=min(n_landed, n_gated))


def collect_downstream(entries: Optional[Sequence[Any]]
                       ) -> Optional[DownstreamBenefit]:
    """④ ℒ_t 账本 ΔS 组间差（adopted=1 组均值 − adopted=0 组均值）。

    ★ 单侧无条目 ⇒ None（不拿 0 顶替 — measure 的缺侧纪律前置同义）。
    ★ delta_s 口径 = CreditEntry.delta_s（R156 赢家归属 — 本模块不重算）。
    """
    if not entries:
        return None
    used, unused = [], []
    for e in entries:
        a = getattr(e, "adopted", None)
        d = getattr(e, "delta_s", None)
        if a is None or d is None or not isinstance(d, (int, float)):
            continue
        (used if int(a) == 1 else unused).append(float(d))
    if not used or not unused:
        return None
    return DownstreamBenefit(quality_used=_mean(used),
                             quality_unused=_mean(unused))


def _mean(xs: Sequence[float]) -> float:
    return sum(xs) / len(xs)


def four_metrics(n_proposals: Optional[int] = None,
                 n_gated: Optional[int] = None,
                 n_landed: Optional[int] = None,
                 ledger_entries: Optional[Sequence[Any]] = None,
                 update: Optional[UpdateQuality] = None
                 ) -> Dict[str, Any]:
    """★★★ 一次成筐（Loop/RoundLog/ledger ⇒ measure.measure 汇总形状）。"""
    act = collect_activation(n_proposals, n_gated)
    fai = collect_faithful(n_gated, n_landed)
    dow = collect_downstream(ledger_entries)
    return measure(update=update, activation=act, faithful=fai,
                   downstream=dow)


def metrics_from_round(round_log: Any,
                       ledger_entries: Optional[Sequence[Any]] = None,
                       n_proposals: Optional[int] = None
                       ) -> Dict[str, Any]:
    """★ RoundLog（R164 daemon 台账）⇒ 四量（Loop 每轮出口的采集位）。

    ★ round_log 字段（R164 真形状）: n_candidates / chain_verdict / landed /
      score; n_proposals 由调用方补（RoundLog 记的是 candidates 数 —
      proposals 在 evolver 面, 同一个数在 R168 语义下同源: 一次 diagnose
      的候选提案集合）。
    """
    n_cands = getattr(round_log, "n_candidates", None)
    landed = bool(getattr(round_log, "landed", False))
    if n_cands is None:
        return four_metrics()                        # 全 not_instrumented
    n_prop = n_proposals if n_proposals is not None else n_cands
    n_land = 1 if landed else 0
    return four_metrics(n_proposals=n_prop, n_gated=n_cands,
                        n_landed=n_land,
                        ledger_entries=ledger_entries)


METRICS_MECHANICS: Dict[str, str] = {
    "collector_not_second_impl": "本模块只采集+投影; 四量口径/三值/raise 全在 measure.py（R171 已落）— 防 R144 第二实现漂移",
    "activation_source": "evolver 候选过门率 n_gated/n_proposals（母巢『98.8% 未访问』的 DWC 同构: 提了没人要）",
    "faithful_source": "落地执行率 n_landed/n_gated（R163 state=adopted）",
    "downstream_source": "ℒ_t 账本 ΔS 组间差（adopted vs 非 — R156 已 live 的账号素材, 不重算）",
    "absent_not_zero": "任一侧源缺 ⇒ 该量显式 not_instrumented（『没测』与『测了是 0』必须分开 — 母巢病根）",
    "denominator_zero": "分母 0 ⇒ None（不造 0% — measure raise 同义前置, 不吞异常）",
}


def summarize(fm: Dict[str, Any]) -> str:
    """★ 一行可读摘要（监控/日志面 — 未埋点显式 na, 不当数字）。

    ★ R168 实测修: measure.measure 返 {"quantities": {...}, ...} 嵌套
      （不是扁平四键 — 首版 fm.get("update") 全 None ⇒ 全 na, 读真返
      回后才对上层）。
    """
    q = fm.get("quantities", {})

    def _f(sec: Dict[str, Any], key: str, label: str) -> str:
        if sec.get("instrumented"):
            return "%s=%.3f" % (label, sec.get(key, 0.0))
        return "%s=na" % label
    return " ".join([
        _f(q.get("update_quality", {}), "quality", "update"),
        _f(q.get("activation", {}), "activation", "act"),
        _f(q.get("faithful_use", {}), "faithful", "faith"),
        _f(q.get("downstream_benefit", {}), "benefit", "down"),
    ]) + " · %s" % fm.get("health", "")
