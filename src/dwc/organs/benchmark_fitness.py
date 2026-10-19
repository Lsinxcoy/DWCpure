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
from typing import Any, Dict, Optional

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
    if "rate" in report and report.get("rate") is not None:
        try:
            return float(report["rate"])
        except (TypeError, ValueError):
            # 无效 rate ⇒ 落到 results 重算; 计数留痕 (非静默)
            _INVALID_RATE_COUNT[0] += 1
            pass
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


def write_calibration(report_path: str, out_path: str,
                      internal_pass_rate: Optional[float] = None) -> Dict[str, Any]:
    report = load_report(report_path)
    sig = fitness_signal(report, internal_pass_rate)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(sig, f, indent=2, ensure_ascii=False)
    return sig
