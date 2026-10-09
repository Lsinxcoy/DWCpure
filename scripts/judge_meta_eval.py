# -*- coding: utf-8 -*-
"""judge meta-evaluation —— HealthBench(2505.08775) 协议的 DWC 版（R99 · 阶段1b）。

★★ HealthBench 原协议: 判分器 macro-F1 + 随机基线 0.50 + 「落在人类分布分位」。
★★ DWC 版的诚实映射:
   · judge 的「真」= 合成**已知真值**的观测对（对值⇒期望 pass / 错值⇒期望 fail）
     —— 测的是「规则比对在已知答案上判对判错」, 抓系统性误判（如 e2e 出现过的
     E_FALSE_NEGATIVE/wrong_polarity 族）
   · 无医生评审分布 ⇒ 「人类分位」项 = not_applicable（显式, 不编造分位）
   · 零判据变动: 只读 anchors + 调 evaluate, 不写任何配置

读:  config/anchors/dev.json（经 Judge 默认构造）
写:  docs/judge_meta_eval.json
用法: python scripts/judge_meta_eval.py
"""
from __future__ import annotations

import ast
import json
import os
import sys
from typing import Any, Dict, List, Optional

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.organs.judge import Judge  # noqa: E402


def _coerce(x: str) -> Any:
    """golden 的 args/expected 是字符串 —— 字面量化（R83 口径: 列表/浮点）。"""
    try:
        return ast.literal_eval(x)
    except (ValueError, SyntaxError):
        return x


def obs_pass(anchors: Dict, tid: str) -> Optional[Dict[str, Any]]:
    """按 golden 拼**全对**观测。

    ★★ 契约（judge._diff behavior 段, 首读踩坑修正）:
      observed = {fn: [[args, value], ...]} —— **[arg, val] 对列表**,
      _eq(call[0], args) 定位入参后再比值; 第一版造成裸 [val] ⇒ 6/6 全判
      「压根没调这个入参」= 构造 bug, 不是 judge 误判（先读再写, 记教训）。
    """
    obs: Dict[str, Any] = {}
    for c in anchors[tid].get("checks", []):
        if "fn" not in c:
            # keyword_match 类: golden 关键词直拼（必然命中）
            if c.get("kw"):
                obs["answer"] = (obs.get("answer", "") + " " + c["kw"]).strip()
            continue
        arg = _coerce(str(c.get("args", "")))
        val = _coerce(str(c["expected"]))
        obs.setdefault(c["fn"], []).append([arg, val])
    return obs or None


def obs_fail(anchors: Dict, tid: str) -> Optional[Dict[str, Any]]:
    """按 golden 拼**全错**观测（args 对位正确、值错 —— trial_run noise 同款口径）。"""
    obs: Dict[str, Any] = {}
    for c in anchors[tid].get("checks", []):
        if "fn" not in c:
            if c.get("kw"):
                obs["answer"] = "__meta_wrong_answer__"
            continue
        arg = _coerce(str(c.get("args", "")))
        v = _coerce(str(c["expected"]))
        if isinstance(v, bool):
            bad: Any = (not v)
        elif isinstance(v, (int, float)):
            bad = v + 1000
        elif isinstance(v, list):
            bad = []
        else:
            bad = str(v) + "_wrong"
        obs.setdefault(c["fn"], []).append([arg, bad])
    return obs or None


def _f1(tp: int, fp: int, fn: int) -> Optional[float]:
    if tp == 0 and (fp or fn):
        return 0.0
    den = 2 * tp + fp + fn
    return (2 * tp / den) if den else None


def evaluate_meta() -> Dict[str, Any]:
    j = Judge()
    anchors = j.anchors
    rows: List[Dict[str, Any]] = []
    # 混淆（正类 = pass）: 期望 pass 的对值样本 / 期望 fail 的错值样本
    tp = fp = tn = fn = 0
    none_pass = none_fail = 0            # 未评价单列（None 不许当 0/1）
    failures: List[Dict[str, Any]] = []
    for tid in sorted(anchors):
        if tid.startswith("_"):
            continue
        kind = anchors[tid].get("verifier_kind")
        if kind != "behavior":
            continue                     # 本审计聚焦 behavior（数字/函数比对）
        # ── 期望 pass: 对值观测 ──
        op = obs_pass(anchors, tid)
        vp = j.evaluate(tid, observed=op)
        if vp.success is None:
            none_pass += 1
        elif vp.success is True:
            tp += 1
        else:
            fn += 1                       # ★ 系统性误判: 对值被判 fail
            failures.append({"task_id": tid, "expected": "pass",
                             "got": "fail", "reason": vp.reason[:160]})
        # ── 期望 fail: 错值观测 ──
        of = obs_fail(anchors, tid)
        vf = j.evaluate(tid, observed=of)
        if vf.success is None:
            none_fail += 1
        elif vf.success is False:
            tn += 1
        else:
            fp += 1                       # ★ 漏判: 错值被判 pass
            failures.append({"task_id": tid, "expected": "fail",
                             "got": "pass", "reason": vf.reason[:160]})
        rows.append({"task_id": tid,
                     "pass_case": vp.success, "fail_case": vf.success})
    n = len(rows)
    acc = (tp + tn) / (tp + tn + fp + fn) if (tp + tn + fp + fn) else None
    f1_pass = _f1(tp, fp, fn)             # pass 类: TP=判对pass, FP=错值判pass
    f1_fail = _f1(tn, fn, fp)             # fail 类: 正类反转
    macro = None
    if f1_pass is not None and f1_fail is not None:
        macro = (f1_pass + f1_fail) / 2
    return {
        "protocol": ("HealthBench(2505.08775) 协议的 DWC 版: macro-F1 + "
                     "随机基线 0.50; ★ 无医生评审分布 ⇒ 人类分位 = "
                     "not_applicable（显式, 不编造）"),
        "n_behavior_tasks": n,
        "confusion_pass_as_positive": {
            "tp": tp, "fn": fn, "tn": tn, "fp": fp},
        "accuracy": acc,
        "f1_pass": f1_pass, "f1_fail": f1_fail, "macro_f1": macro,
        "random_baseline": 0.50,
        "macro_f1_beats_random": (None if macro is None
                                  else macro > 0.50),
        "unevaluated": {"on_pass_cases": none_pass,
                        "on_fail_cases": none_fail,
                        "note": "None 单列（不许当 0/1 — judge 纪律）"},
        "human_percentile": "not_applicable",
        "systematic_misjudgements": failures,   # ★ FN/FP 清单（核心价值）
        "length_bias_audit": {
            "status": "no_source",
            "why": ("evidence.jsonl 存 Verdict.to_dict()（diffs 只含失败条目）, "
                    "不含观测原文 ⇒ 输出长度原料缺失; 接线需动判分序列化"
                    "（判据层）⇒ 列缺口不默认动"),
        },
        "source": "config/anchors/dev.json（经 Judge 默认构造, 只读）",
    }


def main() -> int:
    out = evaluate_meta()
    p = os.path.join(ROOT, "docs", "judge_meta_eval.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("behavior 任务数: %s" % out["n_behavior_tasks"])
    print("混淆(pass为正): %s" % out["confusion_pass_as_positive"])
    print("accuracy=%s macro_f1=%s (随机基线 0.50) 打赢=%s"
          % (out["accuracy"], out["macro_f1"], out["macro_f1_beats_random"]))
    print("未评价: %s" % out["unevaluated"])
    print("系统性误判: %d 条" % len(out["systematic_misjudgements"]))
    for x in out["systematic_misjudgements"][:8]:
        print("   ", x)
    print("写出:", p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
