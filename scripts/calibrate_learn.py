# -*- coding: utf-8 -*-
"""calibrate_learn · learn 管参数校准（网格搜索 β/τ）。

★★★ 为什么需要:
  learn() 的 β=0.1 / τ=0.3 是从 Prometheus-X 借的初值，DWC 无实测支撑
  ⇒ 返回值标 `initial_uncalibrated`。本脚本用**真实库数据**校准。

★ 判据（可复跑）:
  对每组 (β, τ) 重算全库 importance，按分档（高/中/低）看
  **effect 命中率**（effect_count>0 的比例）是否单调递增。
  ⇒ 单调性最强 = importance 真的能预测"这条记忆有用"。
  ⇒ 逆序越多说明参数越差（importance 与实测价值不相关）。

★ 数据门槛:
  effect_count>0 的节点 < MIN_EFFECT_SAMPLES(30) ⇒ 直接输出"数据不足"。
  ★ 不许拿 3 条样本拍出参数 —— 那比初值更不可信（X2 纪律: 缺席≠0）。

用法:
  python scripts/calibrate_learn.py [--db var/dwc_prod.sqlite]
  python scripts/calibrate_learn.py --apply   # 打印写回代码的具体改动（不自动改）
"""
from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.organs.memory import MemoryKernel, MemoryKind  # noqa: E402

MIN_EFFECT_SAMPLES = 30
BETAS = (0.05, 0.1, 0.2)
TAUS = (0.2, 0.3, 0.4)


def _surprise_of(m: MemoryKernel, n) -> float:
    """与 learn() 同款 surprise（失败签名按簇大小，其余 0.5）。"""
    if n.kind is MemoryKind.FAILURE_SIGNATURE:
        c, q, mm = (n.payload.get("c"), n.payload.get("q"),
                    n.payload.get("m"))
        if c and q and mm:
            same = m._conn.execute(
                "SELECT COUNT(*) AS n FROM failure_sig"
                " WHERE c=? AND q=? AND m=?", (c, q, mm)).fetchone()["n"]
            return 1.0 / (1.0 + max(0, int(same) - 1))
    return 0.5


def _importance_of(access: int, effect: int, surprise: float,
                   beta: float, tau: float) -> tuple[float, bool]:
    """与 learn() 同款公式（返回 importance, gated）。"""
    utility = min(1.0, 0.3 * access + 0.7 * effect)
    if utility < tau:
        return 0.5, True
    score = min(1.0, utility * (surprise + beta))
    return round(0.5 + 0.5 * score, 4), False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=os.path.join(ROOT, "var", "dwc_prod.sqlite"))
    ap.add_argument("--apply", action="store_true",
                    help="打印写回 LEARN_BETA/LEARN_UTILITY_TAU 的具体改动")
    args = ap.parse_args()

    m = MemoryKernel(args.db)
    rows = m._conn.execute(
        "SELECT node_id, kind, payload, access_count, effect_count"
        " FROM memory_node WHERE archived_at IS NULL").fetchall()
    samples = []
    for r in rows:
        try:
            pl = json.loads(r["payload"] or "{}")
        except ValueError:
            continue
        # 构造一个最小 node（只用于 _surprise_of）
        n = type("N", (), {"kind": MemoryKind(r["kind"]),
                           "payload": pl})()
        samples.append((int(r["access_count"]), int(r["effect_count"]),
                        _surprise_of(m, n)))
    m.close()

    n_eff = sum(1 for _, e, _ in samples if e > 0)
    print("样本: %d 条未归档记忆, 其中 effect>0 的 %d 条" % (len(samples), n_eff))
    if n_eff < MIN_EFFECT_SAMPLES:
        print()
        print("✗ 数据不足: effect>0 样本 %d < %d —— 无法校准（不拍脑袋）"
              % (n_eff, MIN_EFFECT_SAMPLES))
        print("  前置: record_effect 接线后需积累真实 effect 数据（边界3）")
        print("  当前 learn 参数保持 initial_uncalibrated 是正确姿态。")
        return 2

    # ── 网格搜索 ──
    results = []
    for beta in BETAS:
        for tau in TAUS:
            scored = []
            for access, effect, surp in samples:
                imp, gated = _importance_of(access, effect, surp, beta, tau)
                scored.append((imp, effect > 0, gated))
            # 按 importance 分三档（去 gated 的 0.5 基线，否则全挤一档）
            live = [s for s in scored if not s[2]]
            if len(live) < MIN_EFFECT_SAMPLES:
                results.append((beta, tau, None, "gated 过多 (%d 条可用)"
                                % len(live)))
                continue
            live.sort(key=lambda x: -x[0])
            third = max(1, len(live) // 3)
            bands = [live[:third], live[third:2 * third], live[2 * third:]]
            rates = [sum(1 for _, hit, _ in b if hit) / max(1, len(b))
                     for b in bands]
            # 单调性: 高>中>低 的严格逆序数（0 = 完美单调）
            inversions = sum(1 for i in range(len(rates) - 1)
                             if rates[i] < rates[i + 1])
            results.append((beta, tau, (rates, inversions), ""))

    print()
    print("β      τ     高档命中率  中档   低档   逆序  判定")
    best = None
    for beta, tau, payload, note in results:
        if payload is None:
            print("%.2f   %.2f   —          —      —      —     %s"
                  % (beta, tau, note))
            continue
        rates, inv = payload
        print("%.2f   %.2f   %.3f      %.3f  %.3f  %d     %s"
              % (beta, tau, rates[0], rates[1], rates[2], inv,
                 "✓ 单调" if inv == 0 else ("△ 部分" if inv == 1 else "✗ 逆序")))
        # 选: 逆序最少 → 高低档差最大
        key = (inv, -(rates[0] - rates[2]))
        if best is None or key < best[0]:
            best = (key, (beta, tau, rates, inv))

    print()
    if best is None:
        print("✗ 无可用组合（全部 gated 过多）")
        return 2
    beta, tau, rates, inv = best[1]
    print("推荐: β=%.2f, τ=%.2f（逆序 %d, 高低档差 %.3f）"
          % (beta, tau, inv, rates[0] - rates[2]))
    if args.apply:
        print()
        print("写回改动（人工确认后应用）:")
        print("  src/dwc/organs/memory.py")
        print("    LEARN_BETA = %.2f          # 原 0.1" % beta)
        print("    LEARN_UTILITY_TAU = %.2f   # 原 0.3" % tau)
        print("  learn() 返回值 params_status: initial_uncalibrated → calibrated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
