# -*- coding: utf-8 -*-
"""benchmark_fitness · 外部基准 → 进化 fitness 信号（Phase 3.1）。

定位声明 · **DWC-AUTO**（自我强化 · 判据 G1 定位门）
  ★ 服务环节进化链的 fitness 信号生产, 不碰记忆读写 ⇒ 非 DWC-MEM。

★★★ TRUTH_SOURCE（判据 G2: 含评分能力的模块必须声明系统外真值源）
  · 外部 resolved rate 的真值 = SWE-bench 实例测试执行结果
    (scripts/dwc_benchmark_adapter.py 产出的 report) — 本模块不生成 label
  · 内部 pass_rate 仅作校准参考, 不作真值
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional, List

#: 静默门留痕计数 (G7 非静默)
_INVALID_RATE_COUNT = [0]


def load_report(path: str) -> Dict[str, Any]:
    """读取 benchmark 报告 (adapter 输出格式)。"""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def external_score(report: Dict[str, Any]) -> float:
    """外部 resolved rate (0..1)。缺失 ⇒ 0.0 (fail-closed, 不猜)。"""
    if not isinstance(report, dict):
        return 0.0
    if "resolved_rate" in report and report.get("resolved_rate") is not None:
        try:
            return float(report["resolved_rate"])
        except (TypeError, ValueError):
            _INVALID_RATE_COUNT[0] += 1
    if "rate" in report and report.get("rate") is not None:
        try:
            return float(report["rate"])
        except (TypeError, ValueError):
            _INVALID_RATE_COUNT[0] += 1
    res = report.get("results") or []
    if not res:
        return 0.0
    n = len(res)
    ok = sum(1 for r in res if r.get("resolved"))
    return ok / n if n else 0.0


def calibration(internal_pass_rate: Optional[float],
               external_rate: float) -> Dict[str, Any]:
    """内部 pass_rate vs 外部 resolved rate 的校准对比。"""
    out: Dict[str, Any] = {
        "internal_pass_rate": internal_pass_rate,
        "external_resolved_rate": external_rate,
    }
    if internal_pass_rate is None:
        out["delta"] = None
        out["verdict"] = "no_internal_metric"
        return out
    try:
        ipr = float(internal_pass_rate)
    except (TypeError, ValueError):
        out["delta"] = None
        out["verdict"] = "invalid_internal_metric"
        return out
    delta = ipr - external_rate
    out["delta"] = delta
    # 噪声带 0.05: 差异在此内视为对齐
    if abs(delta) <= 0.05:
        out["verdict"] = "aligned"
    elif delta > 0.05:
        out["verdict"] = "internal_overestimates"   # 内部虚高
    else:
        out["verdict"] = "internal_underestimates"  # 内部偏低
    return out


def fitness_signal(report: Dict[str, Any],
                   internal_pass_rate: Optional[float] = None) -> Dict[str, Any]:
    """进化循环可消费的 fitness 信号包。"""
    ext = external_score(report)
    cal = calibration(internal_pass_rate, ext)
    return {
        "external_resolved_rate": ext,
        "n_instances": len(report.get("results") or []),
        "calibration": cal,
        # fitness 主值: 优先外部 (真值), 内部仅作参考
        "fitness": ext,
    }


# ══════════════════════════════════════════════════════════════════
# Phase C · 分级 fitness（6 级，替代二值 resolved）
# ══════════════════════════════════════════════════════════════════

#: 六级的固定顺序（前 3 级量"变异有没有落地"，后 3 级量"问题有没有解决"）
GRADED_LEVELS = ("parse_ok", "apply_ok", "syntax_ok",
                 "f2p_ok", "p2p_ok", "verifier_ok")

#: 落地层 / 结果层
REALIZATION_LEVELS = ("parse_ok", "apply_ok", "syntax_ok")
OUTCOME_LEVELS = ("f2p_ok", "p2p_ok", "verifier_ok")


def _rate(records, level: str) -> Optional[float]:
    """某一级的通过率；该级无任何已测样本 ⇒ None（不是 0）。

    ★ 纪律：未填 ≠ 测得零。`None` 字段不计入分母。
    """
    vals = [r.get(level) for r in records if r.get(level) is not None]
    if not vals:
        return None
    return sum(1 for v in vals if v) / len(vals)


def fitness_breakdown(records) -> Dict[str, Any]:
    """把逐 instance 的六元组汇总成分级 fitness。

    输入: [{instance_id, parse_ok, apply_ok, syntax_ok,
            f2p_ok, p2p_ok, verifier_ok}, ...]（缺失字段用 None）

    输出:
      counts     每级 {ok, total, rate}
      realization 落地率 = 前 3 级已测项的平均
      outcome     结果率 = 后 3 级已测项的平均
      scalar      realization * outcome（落地是前提：落地为 0 ⇒ scalar 为 0）
    """
    recs = [r for r in (records or []) if isinstance(r, dict)]
    counts: Dict[str, Dict[str, Any]] = {}
    for lv in GRADED_LEVELS:
        vals = [r.get(lv) for r in recs if r.get(lv) is not None]
        counts[lv] = {
            "ok": sum(1 for v in vals if v),
            "total": len(vals),
            "rate": _rate(recs, lv),
        }

    def _mean(levels) -> Optional[float]:
        got = [counts[lv]["rate"] for lv in levels if counts[lv]["rate"] is not None]
        return sum(got) / len(got) if got else None

    realization = _mean(REALIZATION_LEVELS)
    outcome = _mean(OUTCOME_LEVELS)
    if realization is None or outcome is None:
        scalar = None
        verdict = "insufficient_data"
    else:
        scalar = realization * outcome
        verdict = "measured"

    return {
        "n": len(recs),
        "counts": counts,
        "realization": realization,
        "outcome": outcome,
        "scalar": scalar,
        "verdict": verdict,
    }


def record_from_harness(report: Dict[str, Any]) -> Dict[str, Any]:
    """把 `dwc_agent_patch` 的报告转成一条分级记录。

    ★ 只做字段搬运，不补值：harness 没测的级保持 None。
    """
    tr = report.get("last_tool_result") or {}
    f2p = tr.get("f2p") or {}
    p2p = tr.get("p2p") or {}
    verdict = tr.get("verdict")

    # p2p 被跳过（集合过大 / 实例无 P2P）⇒ None，不当成 0
    p2p_ok = None
    if p2p and not p2p.get("skipped"):
        p2p_ok = p2p.get("all_passed")

    parse_ok = True if tr else None          # 有 tool_result ⇒ 解析成功过
    return {
        "instance_id": report.get("instance_id", ""),
        "parse_ok": parse_ok,
        "apply_ok": tr.get("applied"),
        "syntax_ok": tr.get("syntax_ok"),
        "f2p_ok": f2p.get("all_passed"),
        "p2p_ok": p2p_ok,
        "verifier_ok": (verdict == "PASS") if verdict else None,
        "resolved": bool(report.get("success")),
    }


def compare_policies(policy_records: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
    """在**共同测量集**上比较多个策略的 fitness（可比口径）。

    ★ 为什么需要：`fitness_breakdown` 的 outcome 分母随 realization 变化——
      策略 A 的补丁语法失败时 f2p 未测，策略 B 语法通过后 f2p 被测且失败，
      于是 outcome 从 2/3 变 2/4，**看起来变差，实际是测得更全**。
      直接比较 scalar 会得出反向结论（Phase C 实测踩中）。

    口径：
      1. `common_instances` = 所有策略都有记录的 instance_id 交集
      2. 每一级再取「所有策略都测到该级」的子集（None 不进分母）
      3. 各策略在同一子集上算 rate ⇒ realization / outcome / scalar 可比
    """
    pols = [p for p, recs in (policy_records or {}).items() if recs]
    if len(pols) < 2:
        return {"comparable": False, "why": "少于两个策略，无可比对象",
                "policies": pols}

    by_id: Dict[str, Dict[str, Dict[str, Any]]] = {}
    for p in pols:
        for r in policy_records[p]:
            iid = r.get("instance_id")
            if iid:
                by_id.setdefault(iid, {})[p] = r

    common_ids = sorted(iid for iid, m in by_id.items() if all(p in m for p in pols))

    per_level: Dict[str, Dict[str, Any]] = {}
    for lv in GRADED_LEVELS:
        ids = [iid for iid in common_ids
               if all(by_id[iid][p].get(lv) is not None for p in pols)]
        rates = {}
        for p in pols:
            if ids:
                rates[p] = sum(1 for iid in ids if by_id[iid][p][lv]) / len(ids)
            else:
                rates[p] = None
        per_level[lv] = {"n": len(ids), "rates": rates}

    def _mean(levels, p):
        got = [per_level[lv]["rates"][p] for lv in levels
               if per_level[lv]["rates"][p] is not None]
        return sum(got) / len(got) if got else None

    per_policy = {}
    for p in pols:
        rl = _mean(REALIZATION_LEVELS, p)
        oc = _mean(OUTCOME_LEVELS, p)
        per_policy[p] = {
            "realization": rl,
            "outcome": oc,
            "scalar": (rl * oc) if (rl is not None and oc is not None) else None,
        }

    return {
        "comparable": True,
        "common_instances": common_ids,
        "per_level": per_level,
        "per_policy": per_policy,
        "note": "所有比率均在同一 instance 子集上计算；None 级不进分母",
    }


def write_calibration(report_path: str, out_path: str,
                      internal_pass_rate: Optional[float] = None) -> Dict[str, Any]:
    report = load_report(report_path)
    sig = fitness_signal(report, internal_pass_rate)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(sig, f, indent=2, ensure_ascii=False)
    return sig
