# -*- coding: utf-8 -*-
"""matched-term 最小对照 —— R110 · 稿②执行轮（π0 / π* / π̂ 三臂）。

设计稿: docs/proposal_matched_term_design.html（R108 过审稿）
协议  : 稿② §⑤（seed/n_terms/arms/anchor 断言/change_scope/placebo_spec/
        verdicts/claims_allowed）· 判读 §⑥（禁用措辞表生效）

★ π 载体（稿② §②）: 策略快照 = 任务选择序策略 + 记忆底 + 判分器。
  · π0 = legacy 纯 δ 序（组序未启用 — R101 前行为）
  · π* = 现行两级组序（R101: 弱组优先 + 组内 δ 降）
  · π̂ = 盲改动安慰剂: **随机**任务序（与证据无关, 等预算 — Verma 同款）
★ 同 memory 底: 三臂从同一注入批次起（构造后 remember 同批工件 — 剥记忆混淆）。
★ matched 账: CostLedger 不适用本形态（判分器无 term 账）⇒ 以
  n_terms×n_tasks×判分次数 三计数断言相等（matched 字面的最小记账）。
★ 独立锚: truth_sha8 前后一致断言（不一致 ⇒ raise 拒报 — 稿② §⑤）。
★ 效度预告（稿② 诚实条款4 — R107 教训）: golden executor 不读记忆/序 ⇒
  若三臂恒等, **如实报结构必然**, 不当「策略无效」证据。

读:  config/anchors/dev.json · config/capability_groups.yaml
写:  docs/matched_term.json
用法: python scripts/matched_term.py [--n-terms 3 --seed 42]
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import random
import sys
from typing import Any, Dict, List, Optional, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.core import DWC  # noqa: E402
from dwc.organs.judge import TaskScoreStore  # noqa: E402
from dwc.organs.actor import Receipt  # noqa: E402

#: ★ §⑥ 禁用措辞（产出报告的 claim 值只许来自白名单）
FORBIDDEN_CLAIMS = (
    "effective L5", "effective recursion", "L5e 通过", "有效递归已验证",
    "显著优于", "显著提高", "显著改善",
)
ALLOWED_CLAIM_PREFIX = "matched-term 对照"


def _coerce(x: str) -> Any:
    try:
        return ast.literal_eval(str(x))
    except (ValueError, SyntaxError):
        return x


def truth_sha8(path: str) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()[:8]


def make_exec(anchors: Dict, tasks: List[str]):
    """golden 对值 executor（三臂同 — 判分器独立于策略, 独立锚字面）。"""
    def _exec(task):
        tid = task.get("task_id", "")
        if tid not in tasks:
            return Receipt(ok=True, verified=True, detail={})
        golden = anchors.get(tid, {})
        if golden.get("verifier_kind") == "keyword_match":
            # answer 文本含全部 kw ⇒ 命中（judge:808-818 形态）
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
    return _exec


def group_of_map() -> Dict[str, str]:
    """{task: 组名} — 组真源 core._load_capability_groups 反查。
    ★ 首版曾编造 load_groups 被 except 兜成字典序 ⇒ pi_star 臂实为 pi0
      （臂语义失效, 测试抓正）—— 真 API 坏/缺 ⇒ 大声 raise, 不兜底。"""
    from dwc.core import load_groups_with_homing
    groups = load_groups_with_homing()
    # ★ R287-E · 归位版（007-009 按 anchors category 入 code_repair ——
    #   与生产 DWC 播种同口径，不再两张皮）
    return {t: g for g, members in groups.items() for t in members}


def arm_order(arm: str, tasks: List[str], seed: int,
              rates: Optional[Dict[str, float]] = None) -> List[str]:
    """★ π 载体 = 任务选择序（同一任务集, 只改序 — 改动可执行/等预算）。

    rates = 运行时组率（world_model.group_rates(), 每 term 重读 — R101 真形态:
    弱组优先只基于已观测, 缺席组当 1.0 强组排后 = run_term L690-695 同款降级;
    组内用字典序 = δ 降的确定性代理（golden 下 δ 需 wta 上下文, 简化注明））。
    """
    if arm == "pi0":                       # legacy 纯 δ 序 = 字典序（确定性）
        return sorted(tasks)
    if arm == "pi_star":                   # R101 两级序: 弱组率升（组内字典序代理 δ）
        gmap = group_of_map()
        rates = rates or {}
        return sorted(tasks, key=lambda t: (
            rates.get(gmap.get(t, ""), 1.0), t))
    if arm == "placebo":                   # π̂ 盲序: 与证据无关的随机排列
        rng = random.Random(seed)
        out = list(tasks)
        rng.shuffle(out)
        return out
    raise ValueError("未知臂 %r（只许 pi0/pi_star/placebo）" % arm)


def run_arm(arm: str, anchors: Dict, tasks: List[str],
            n_terms: int, seed: int) -> Dict[str, Any]:
    """单臂: 同任务集/同判分/同 N term — 只有 order 策略不同（改动面唯一）。"""
    d = DWC(3, 50, executor=None, db_path=":memory:")
    d.judge.store = TaskScoreStore(dw_version="matched-term-r110")
    # ★ 同 memory 底: 三臂注入同一批工件（与臂无关 — 剥记忆混淆）
    from dwc.organs.memory import MemoryKind
    base_artifacts = [
        {"scene": "base_%d" % i, "method": "m%d" % i, "boundary": "b",
         "invalid_conditions": ["x"], "recovery_strategies": ["y"]}
        for i in range(3)]
    for a in base_artifacts:
        d.memory.remember(MemoryKind.SKILL, dict(a))
    d.executor = make_exec(anchors, tasks)
    base_order = arm_order(arm, tasks, seed)
    outcomes: List[bool] = []
    n_scores = 0
    for t in range(n_terms):
        # ★ pi_star 每 term 重读运行时组率（R101 弱组优先是动态语义 —
        #   静态一次排序会丢「观测改变组率→改变序」的真机制）
        order = (arm_order(arm, tasks, seed,
                           rates=d.world_model.group_rates())
                 if arm == "pi_star" else base_order)
        for tid in order:
            out = d.step({"task_id": tid, "kind": "dev"})
            j = out.get("judgement") or {}
            succ = j.get("success")
            if isinstance(succ, bool):
                outcomes.append(succ)
                n_scores += 1
    return {
        "arm": arm, "order_first3": order[:3], "n_terms": n_terms,
        "n_tasks": len(tasks), "n_scores": n_scores,
        "n_decisions": len(tasks) * n_terms,
        "success_rate": (sum(outcomes) / len(outcomes)) if outcomes else None,
        "n_injected_artifacts": len(base_artifacts),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-terms", type=int, default=3)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default=os.path.join(ROOT, "docs",
                                                  "matched_term.json"))
    args = ap.parse_args()

    anchors_path = os.path.join(ROOT, "config", "anchors", "dev.json")
    anchors = json.load(open(anchors_path, encoding="utf-8"))
    # ★ 全任务集 = behavior + keyword_match（judge 只认这两 kind 的 golden 判分,
    #   且必须跨组 — 首版只取 behavior 6 任务全在 code_repair 组 ⇒ 组间序无效,
    #   pi_star 臂与 pi0 逐位同（臂语义数据巧合失效, 测试抓正）
    tasks = sorted(t for t in anchors
                   if not t.startswith("_")
                   and anchors[t].get("verifier_kind") in
                   ("behavior", "keyword_match"))
    if not tasks:
        print("★ dev 无 behavior 任务 ⇒ not_applicable（不装数）")
        return 2

    sha_before = truth_sha8(anchors_path)
    arms = {a: run_arm(a, anchors, tasks, args.n_terms, args.seed)
            for a in ("pi0", "pi_star", "placebo")}
    sha_after = truth_sha8(anchors_path)
    if sha_before != sha_after:
        # 独立锚被污染 ⇒ 拒报（稿② §⑤ 字面）
        raise SystemExit("★ 锚污染: truth_sha8 前后不一致 %s→%s ⇒ 拒报"
                         % (sha_before, sha_after))

    # matched 账断言: 三臂三计数必须全等（不等=预算不匹配, 拒报）
    keys = ("n_terms", "n_tasks", "n_scores", "n_decisions",
            "n_injected_artifacts")
    budgets = {k: {arms[a][k] for a in arms} for k in keys}
    mismatched = {k: v for k, v in budgets.items() if len(v) != 1}
    if mismatched:
        raise SystemExit("★ matched 预算失配 ⇒ 拒报: %r" % mismatched)

    s0, ss, sp = (arms["pi0"]["success_rate"], arms["pi_star"]["success_rate"],
                  arms["placebo"]["success_rate"])
    vs_base = (ss - s0) if (ss is not None and s0 is not None) else None
    vs_plac = (ss - sp) if (ss is not None and sp is not None) else None
    content = (vs_plac)   # 稿② §④: π*−max(π0,π̂) 的最小实现 = 逐差两读数
    claim = ALLOWED_CLAIM_PREFIX + (
        ": π*−π0=%s, π*−π̂=%s（方向性, 单轮, 样本小）" % (vs_base, vs_plac))
    for bad in FORBIDDEN_CLAIMS:
        if bad in claim:
            raise SystemExit("★ 禁用措辞入报告: %r" % bad)

    identical = (s0 == ss == sp)
    out = {
        "protocol": ("稿② §⑤: 三臂同底同预算同判分器; π 载体=任务选择序"
                     "(pi0字典序/pi_star组序/placebo盲随机); matched三计数断言;"
                     "独立锚 truth_sha8 前后一致"),
        "seed": args.seed,
        "n_terms": args.n_terms,
        "arms": arms,
        "anchor": {"truth_source": "config/anchors/dev.json",
                   "truth_sha8_before": sha_before,
                   "truth_sha8_after": sha_after,
                   "consistent": True, "judge_frozen": True},
        "verdicts": {"vs_baseline": vs_base, "vs_placebo": vs_plac,
                     "content_effect": content},
        "claims_allowed": [claim],
        "forbidden_scanned": list(FORBIDDEN_CLAIMS),
        "caveats": [
            ("★ golden executor 不读记忆/序 ⇒ 三臂恒等是**结构必然**"
             "（R107 已证同型旁路）—— 恒等报『结构必然』, 不当策略无效证据"
             "（稿② 诚实条款4 字面）" if identical else
             "三臂出现差异 — 记录序效应方向(样本小只报方向)"),
            "n 小单轮只报方向, 无显著性检验",
            "LLM executor 形态(endpoint=llm)留位未跑 — 本跑=确定性协议验收",
            "change_scope=策略序三态(pi0/pi_star/placebo), 非 git_diff"
            " — π载体按稿②§②整快照语义的最小可执行面",
        ],
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("三臂: pi0=%s pi_star=%s placebo=%s (恒等=%s)"
          % (s0, ss, sp, identical))
    print("锚 sha8: %s 一致 ✓ · matched 三计数全等 ✓" % sha_before)
    print("claim:", claim)
    print("写出:", args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
