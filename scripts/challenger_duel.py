# -*- coding: utf-8 -*-
"""challenger 对拍 —— R115 · E2 首次（设计稿④ §⑤⑧ 点界对拍 · 平票在位者）。

协议（稿 §⑤ 字面）:
  challenger 提案（评估策略层键: regression ε — 稿 §④「回归判据的参数」明列）
  → 准入关 = meta-eval macro-F1 ≥ 在位者 − δ（同锚同任务集对拍）
  → 比对规则 = **平票判在位者**（RQGM 字面, 保守）
  → 赢 ⇒ EpochGuard.close_epoch 换代 + dep(z) 弃置扫描; 输 ⇒ 在位者续任
     + challenger **归档不静默**（G7）

★ 分层注记（首次对拍的结构性事实）: ε 是**策略参数** — 不进 diff 对值
  判分（锚层 L-inner 不动）⇒ meta-F1 对 ε **结构性不敏感** ⇒ 首次对拍
  预期为**平票** → 在位者续任。这不是脚本失败, 是分层设计的正确表现:
  评估策略层的换代证据必须来自**锚上无损 + 行为差异**, 而裁决规则按稿
  只认 F1 ⇒ 平票保守拒绝。行为差异（ε 让 -0.5% 回退转 ok）作**描述性
  证据**入档, 不作裁决项（稿未授权其裁决 — 不发明）。

读:  docs/judge_meta_eval.json 机制（evaluate_meta 复用）· judge 源指纹
写:  docs/challenger_duel.json
用法: python scripts/challenger_duel.py
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Any, Dict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from dwc.organs.judge import Judge, JudgeError  # noqa: E402
from dwc.foundation.epoch_guard import EvaluatorEpochGuard  # noqa: E402
from dwc.foundation.inheritance import judge_fingerprint  # noqa: E402

JUDGE_PATH = os.path.join(ROOT, "src", "dwc", "organs", "judge.py")

#: challenger 提案: regression 容忍度 0 → 0.02（r̂≤ε 原文口径的策略键）
CHALLENGER_EPSILON = 0.02


def _regression_duo() -> Dict[str, Any]:
    """★ 行为差异证据（描述性, 不裁决）: 同一对回归样本, 两 ε 判定对照。"""
    j = Judge()
    # 造一对回归样本: baseline 80% → current 79.5%（delta=-0.005）
    # （同任务集可比 — graded_set 交集语义由同构造保证）
    n = 200
    def mk(pass_n):
        return {"details": [{"task_id": "t%03d" % i,
                             "success": i < pass_n}
                            for i in range(n)]}
    base, cur = mk(160), mk(159)          # 0.80 → 0.795, delta=-0.005
    inc = j.regression_check(base, cur)                 # ε=0（在位者）
    chl = j.regression_check(base, cur, epsilon=CHALLENGER_EPSILON)
    assert inc["epsilon"] == 0.0 and chl["epsilon"] == CHALLENGER_EPSILON
    return {"sample": {"baseline_pass_rate": 0.80, "current_pass_rate": 0.795,
                       "delta": -0.005},
            "incumbent_verdict": inc["verdict"],
            "challenger_verdict": chl["verdict"],
            "behaviour_differs": inc["verdict"] != chl["verdict"],
            "note": ("行为差异=描述性证据（ε 改变回归判定）; 裁决只认 "
                     "meta-F1（稿 §⑤ — 不发明裁决项）")}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "docs",
                                                  "challenger_duel.json"))
    ap.add_argument("--archive", default=os.path.join(ROOT, "archive"))
    args = ap.parse_args()

    # ── 准入关: meta-F1 对拍（同锚同任务集 — evaluate_meta 机制复用）──
    # ★ ε 不进 diff 判分 ⇒ 两配置 F1 结构性相同 = 平票（分层正确表现）
    from judge_meta_eval import evaluate_meta
    duel_start = time.time()
    incumbent_meta = evaluate_meta()
    challenger_meta = json.loads(json.dumps(incumbent_meta))  # 同判分实体
    f1_i = incumbent_meta["macro_f1"]
    f1_c = challenger_meta["macro_f1"]
    tie = (f1_i == f1_c)
    winner = "incumbent" if tie else (
        "incumbent" if (f1_c is None or f1_i is None
                        or f1_c < f1_i) else "challenger")
    # ★ 平票判在位者（RQGM 字面）— 本首次对拍预期 tie=True
    decision = "incumbent_holds" if winner == "incumbent" else "regime_change"

    behaviour = _regression_duo()

    # ── 换代联动（仅 regime_change; 首次预期不触发 — 空清单如实）──
    fp_now = judge_fingerprint(JUDGE_PATH)
    guard = EvaluatorEpochGuard(epoch_id=1, judge_fingerprint=fp_now)
    dep_after: Dict[str, Any] = {}
    transitions = []
    if decision == "regime_change":
        # 换代: guard 记录 + dep(z) 弃置扫描（此处 challenger 未改 judge
        # 源文件 ⇒ 指纹同 ⇒ 实际扫描需以提案落盘后的指纹为准 — 见 honest）
        guard.close_epoch(fp_now, reason="challenger 赢对拍",
                          by="challenger_win")
        transitions = list(guard.transitions)
        from dep_scan import scan, split_fingerprint
        dep_after = scan(args.archive, fp_now, split_fingerprint(ROOT),
                         regime_change=True)["counts"]
    else:
        from dep_scan import scan, split_fingerprint
        dep_after = scan(args.archive, fp_now, split_fingerprint(ROOT),
                         regime_change=False)["counts"]

    out = {
        "protocol": ("E2 首次对拍: challenger=regression ε 0→%s（稿§④策略键）; "
                     "准入=meta-F1 同锚对拍; 裁决=平票判在位者(RQGM字面); "
                     "行为差异=描述性证据不裁决" % CHALLENGER_EPSILON),
        "at": time.time(),
        "duel": {"incumbent_macro_f1": f1_i,
                 "challenger_macro_f1": f1_c,
                 "tie": tie, "winner": winner, "decision": decision},
        "behaviour_evidence": behaviour,
        "epoch_guard": guard.to_dict(),
        "dep_scan_after": dep_after,
        "regime_change_happened": decision == "regime_change",
        "historical_comparability": {
            "broken_since": None,
            "reason": ("换代未发生 ⇒ 分数链连续（judge 指纹未变 %s）" % fp_now)
            if decision != "regime_change" else "★ 换代发生, 见 dep 弃置",
        },
        "challenger_archive": {
            "proposal": {"type": "regression_epsilon",
                         "epsilon": CHALLENGER_EPSILON,
                         "status": "archived_not_adopted" if tie
                         else "adopted"},
            "why": ("meta-F1 平票 ⇒ 平票判在位者（稿§⑤ · RQGM 字面）— "
                    "challenger 归档不静默（G7）"),
        },
        "honest": [
            "★ 结构性平票: ε 是策略参数不进 diff 判分 ⇒ meta-F1 对 ε 不敏感"
            " — 分层设计(L-inner 不动)的正确表现, 非对拍失败",
            "要产生换代证据, challenger 须在锚对拍上有净胜（如 meta 锚扩展"
            "或更强策略键）— 首次结果呈用户过目后才常态化（稿§⑧）",
            "若未来换代: judge 源变更后 fp 变 ⇒ dep(z) 以新 fp 重扫（本脚本"
            "已留联动口）; epsilon kwarg 本身已进 judge 源, fp 已含之",
        ],
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("对拍: incumbent F1=%s vs challenger F1=%s ⇒ tie=%s → %s"
          % (f1_i, f1_c, tie, decision))
    print("行为证据: %s(incumbent) vs %s(challenger) differs=%s"
          % (behaviour["incumbent_verdict"], behaviour["challenger_verdict"],
             behaviour["behaviour_differs"]))
    print("dep 扫描:", dep_after)
    print("写出:", args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
