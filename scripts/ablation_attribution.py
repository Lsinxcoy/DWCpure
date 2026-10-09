# -*- coding: utf-8 -*-
"""四跑消融归因 —— R114 · M1（设计稿③ §④⑤ 可分性数学 + 消融回路）。

协议: s(0)/s(A)/s(B)/s(A⊕B) 四读 →
  主效应A = s(A)−s(0) · 主效应B = s(B)−s(0) ·
  交互 I = s(A⊕B)−s(A)−s(B)+s(0) → τ 分流:
  |I|<τ ⇒ additive（可加: 拆分归因, 单点纪律续用, 组合解散）
  |I|≥τ ⇒ interactive（整体归档不拆功）· I<−τ ⇒ compensation_flag

★ π 载体 = PolicySpec 键域（稿§⑦ 基因位点）:
  spec0 = π0 默认 (w=1, r=1, s=children)
  specA = seg_order:"delta"          （键域A）
  specB = prefer_revealable:False    （键域B — 与 A 不相交, 构造即断言）
  specAB = 两键合（merge 同键冲突由构造保证: 两键不同 ⇒ 合法）
★ 分数 = DreamReport.v_by_version（dream 对四 spec 各出 V — 同回放底
  单次 dream 出四 V = 更严的控变量（R86 M>1 同款）, 四 spec 共享 ℋ 起底。
★ 效度预告（稿§⑨①）: golden 替身下 V 对策略键可能不敏感 ⇒ 恒等风险 —
  恒等 ⇒ I=0 ⇒ 分流 additive, **如实报结构必然**, 不冒充"可加性发现"。
★ τ₀ = 0.2（R105c 跨跑抖动量级 — 自家实测非文献值, calibration_note 必带）。

读:  config/anchors/dev.json
写:  docs/ablation_attribution.json
用法: python scripts/ablation_attribution.py [--seed 42]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, List, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.core import DWC  # noqa: E402
from dwc.organs.judge import TaskScoreStore  # noqa: E402
from dwc.organs.replay import PolicySpec  # noqa: E402

#: τ 初值 = 自家跑间抖动量级（R105c）— 文献无此协议, 待校准（稿§④）
TAU0 = 0.2
CALIBRATION_NOTE = ("初值 0.2 = R105c 同配置跨跑 guidance 0.60→0.80 抖动量级"
                    "（自家实测, 非文献值 — 文献无组合归因协议）, 待校准")


def build_specs() -> Dict[str, PolicySpec]:
    """四 spec（0/A/B/AB）+ 键域不相交断言（稿§⑦ 交叉合法域）。"""
    key_a, key_b = "seg_order", "prefer_revealable"
    assert key_a != key_b, "★ 键域必须不相交（同键无法分解主效应）"
    specs = {
        "s0": PolicySpec(),
        "sA": PolicySpec.from_mapping({key_a: "delta"}),
        "sB": PolicySpec.from_mapping({key_b: False}),
        "sAB": PolicySpec.from_mapping({key_a: "delta", key_b: False}),
    }
    pids = [sp.pid for sp in specs.values()]
    assert len(set(pids)) == 4, "四 spec 必须四 pid（撞键=自覆盖）: %r" % pids
    return specs


def read_effects(v: Dict[str, float]) -> Dict[str, Any]:
    """★ 三读数 + τ 分流（纯函数 — 破坏测试靶）。"""
    s0, sA, sB, sAB = v["s0"], v["sA"], v["sB"], v["sAB"]
    eff_a = sA - s0
    eff_b = sB - s0
    inter = sAB - sA - sB + s0
    split = "additive" if abs(inter) < TAU0 else "interactive"
    return {
        "main_effect_A": eff_a, "main_effect_B": eff_b,
        "interaction_I": inter,
        "tau": TAU0, "calibration_note": CALIBRATION_NOTE,
        "split": split,
        "compensation_flag": bool(split == "interactive" and inter < 0),
        "fork_rule": ("|I|<τ ⇒ additive: 拆分归因单点续用; ≥τ ⇒ interactive: "
                      "整体归档不拆功（稿§④）"),
        "identical_v": (s0 == sA == sB == sAB),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default=os.path.join(ROOT, "docs",
                                                  "ablation_attribution.json"))
    args = ap.parse_args()

    anchors = json.load(open(os.path.join(ROOT, "config", "anchors",
                                          "dev.json"), encoding="utf-8"))
    # 起底: 跑 term 产 ℋ 回放底（同底四 spec — 控变量）
    d = DWC(3, 50, executor=None, db_path=":memory:", )
    d.judge.store = TaskScoreStore(dw_version="ablation-m1-r114")
    tasks = sorted(t for t in anchors
                   if not t.startswith("_")
                   and anchors[t].get("verifier_kind") in
                   ("behavior", "keyword_match"))

    from dwc.organs.actor import Receipt
    import ast

    def _coerce(x):
        try:
            return ast.literal_eval(str(x))
        except (ValueError, SyntaxError):
            return x

    def _exec(task):
        tid = task.get("task_id", "")
        golden = anchors.get(tid, {})
        if golden.get("verifier_kind") == "keyword_match":
            kws = [c.get("kw") for c in (golden.get("checks") or [])
                   if c.get("kw")]
            return Receipt(ok=True, verified=True,
                           detail={"observed": {"answer": " ".join(kws)}})
        obs: Dict[str, Any] = {}
        for c in golden.get("checks", []):
            if "fn" not in c:
                continue
            obs.setdefault(c["fn"], []).append(
                [_coerce(c.get("args", "")), _coerce(c["expected"])])
        return Receipt(ok=True, verified=True,
                       detail=({"observed": obs} if obs else {}))

    d.executor = _exec
    # ★ 起底必须走 core.step（R103 教训: run_term 是编排不执行不判分 —
    #   无判分 ⇒ 无失败签名/无回放料 ⇒ V 恒 0 假象）。golden 全对 ⇒
    #   仍可能无可回放失败 ⇒ V=0 属"回放底无料"的如实结果（caveat 自带）。
    for _round in range(2):
        for tid in tasks:
            d.step({"task_id": tid, "kind": "dev"})

    specs = build_specs()
    report = d.dream(k2_max=4, policy_variants=list(specs.values()))
    v_by = dict(report.v_by_version)
    # 映射 pid→槽名（四 spec 四 pid）
    pid2slot = {sp.pid: k for k, sp in specs.items()}
    v_slots: Dict[str, float] = {}
    for pid, val in v_by.items():
        slot = pid2slot.get(pid)
        if slot:
            v_slots[slot] = float(val)
    missing = [k for k in ("s0", "sA", "sB", "sAB") if k not in v_slots]
    if missing:
        print("★ 四 spec V 缺槽 %s（v_by=%r）⇒ not_computable（不装数）"
              % (missing, list(v_by)))
        out = {"protocol": "四跑消融(稿§④)", "status": "not_computable",
               "missing_slots": missing, "v_by_version": v_by,
               "caveats": ["V 槽缺失 — 如实不装数"]}
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
        return 2

    eff = read_effects(v_slots)
    out = {
        "protocol": ("M1 四跑消融: 同ℋ底单次dream四spec(键域A/B不相交断言); "
                     "三读数+τ分流; τ₀=0.2 自家抖动量级待校准"),
        "seed": args.seed,
        "specs": {k: {"pid": sp.pid,
                      "keys": {kk: getattr(sp, kk)
                               for kk in ("w_delta", "prefer_revealable",
                                          "seg_order")}}
                  for k, sp in specs.items()},
        "v_by_slot": v_slots,
        "effects": eff,
        "caveats": [
            ("★ V 恒等(四 spec 同值) ⇒ I=0 分流 additive = **结构必然**"
             "（dream V 对策略键不敏感时）, 不冒充可加性发现 — 稿§⑨①"
             if eff["identical_v"] else
             "V 有区分度 — 记录三读数方向(单次跑无方差, 只报方向)"),
            "单次 dream 无重复采样 — 交互项接近 τ 时按稿§⑤加跑定噪声(留)",
            "补偿 flag 是候选不是自动判决（W5 + 生产门归用户）",
        ],
        "attribution_plan_required_for": (
            "多改提案进 evolver 必带 plan（R114 路径乙已接）— 本脚本"
            "为 plan 的 τ/消融预算提供实跑读数"),
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("四V:", v_slots)
    print("主效应A=%s 主效应B=%s 交互I=%s ⇒ %s%s" % (
        round(eff["main_effect_A"], 4), round(eff["main_effect_B"], 4),
        round(eff["interaction_I"], 4), eff["split"],
        " [补偿flag]" if eff["compensation_flag"] else ""))
    print("写出:", args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
