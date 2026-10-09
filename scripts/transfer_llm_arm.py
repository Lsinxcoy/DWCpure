# -*- coding: utf-8 -*-
"""Transfer LLM 臂 —— R124 · 项2-4a（R107 三臂的二期真区分版）。

动机（R107 效度边界原文）: golden 替身 executor **不读记忆** ⇒ 记忆→执行
路径被旁路 ⇒ 三臂恒等 1.0 是结构必然, 不构成「记忆无效」的证据。
④ 期（本脚本）: 换 LLM executor — prompt 里注入记忆工件内容 ⇒ transplant
臂的**真工件**与 placebo 臂的**盲造工件**对 LLM 的内容通道打通。

协议（保持 R107 三维解耦 + 等预算 + 盲安慰剂原样, 只换 executor）:
  author = A 实例跑 n_terms 沉淀真工件（behavior 任务）。
  user   = 全新实例 B; 三臂（transplant 真工件 / blind_placebo 同数盲造 /
    baseline 空）各自独立全新实例, 同预算同任务同判分。
  ★ executor = LLM: prompt 携带 (a) 记忆工件文本与 (b) 任务 checks 结构;
    回复按 fn→[[args,obs]] 形态解析成 observed（不猜 — 未解析=缺, 判 None）。
  ★ 预算: n_user 步 × 每步 1 次 LLM call（per-arm 计数, 对等）。

风险与诚实（如实写死）:
  · LLM 端点波动 ⇒ 多次跑（repeat）序列报均值, 单次仅记录不复用结论;
  · 解析失败率如实报（n_parsed / n_calls）;
  · 若 LLM 端不可用（未配置/调用错）⇒ not_computable, 不装数、不造假数;
  · 判别口径: content_effect = transplant − placebo（Verma 同款 —
    增益须超安慰剂才算内容效应; 此为 R107 协议原样继承）。

读:  config/anchors/dev.json · src/dwc/llm（LLMClient）
写:  docs/transfer_llm_arm.json
用法: python scripts/transfer_llm_arm.py [--repeat 2] [--seed 42]
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import sys
from typing import Any, Dict, List, Optional

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.core import DWC  # noqa: E402
from dwc.llm import LLMClient  # noqa: E402
from dwc.organs.actor import Receipt  # noqa: E402
from dwc.organs.judge import TaskScoreStore  # noqa: E402
from dwc.organs.memory import MemoryKind  # noqa: E402


def _coerce(x):
    try:
        return ast.literal_eval(str(x))
    except (ValueError, SyntaxError):
        return x


def _obs_skeleton(anchors: Dict, tid: str) -> Dict[str, Any]:
    """任务 fn→[[args,None]] 骨架 — LLM 需回 expected 位置的真值形态。"""
    obs: Dict[str, List[List[Any]]] = {}
    for c in anchors.get(tid, {}).get("checks", []):
        if "fn" not in c:
            continue
        obs.setdefault(c["fn"], []).append([_coerce(c.get("args", "")), None])
    return obs


def _parse_llm_observed(raw: str, skeleton: Dict[str, List[List[Any]]]
                        ) -> Optional[Dict[str, List[List[Any]]]]:
    """从 LLM 回复抽 observed（对 skeleton 的 fn 找 JSON/字面块）— 不猜。"""
    import re
    if not raw or not raw.strip():
        return None
    text = raw.strip()
    # 提取 JSON 对象（宽容围栏）
    m = re.search(r"\{.*\}", text, re.S)
    if m:
        try:
            parsed = ast.literal_eval(m.group(0))
        except Exception:
            try:
                parsed = json.loads(m.group(0))
            except Exception:
                parsed = None
        if isinstance(parsed, dict):
            out: Dict[str, List[List[Any]]] = {}
            for fn, pairs in parsed.items():
                if isinstance(pairs, list) and all(
                        isinstance(x, list) and len(x) == 2
                        for x in pairs):
                    out[str(fn)] = [[_coerce(x[0]), _coerce(x[1])]
                                    for x in pairs]
            return out or None
    return None


def llm_executor(llm: LLMClient, anchors: Dict, tasks: List[str],
                  memory_text: str = "", *,
                  stats: Optional[Dict[str, int]] = None):
    """LLM executor: 把工件文本与任务 checks 结构给 LLM, 回 observed 形态。"""

    def _exec(task):
        tid = task.get("task_id", "")
        g = anchors.get(tid, {})
        if g.get("verifier_kind") != "behavior" or tid not in tasks:
            return Receipt(ok=True, verified=True, detail={})
        skel = _obs_skeleton(anchors, tid)
        prompt = (
            "任务 %s 的观测需要返回 observed, 形态如下（fn -> "
            "[[args, observed_value], ...]）:\n%s\n"
            "已知参考资料（skill 工件, 可能有用）:\n%s\n"
            "直接输出 JSON 对象（只有 observed 的内容, 把 None 换成你认为"
            "正确的观测值）。" % (tid, json.dumps(skel, ensure_ascii=False),
                                memory_text or "（无）"))
        res = llm.complete(prompt, system="只输出 JSON, 不解释。")
        if stats is not None:
            stats["n_calls"] = stats.get("n_calls", 0) + 1
        if getattr(res, "error", None) or not getattr(res, "text", None):
            if stats is not None:
                stats["n_errors"] = stats.get("n_errors", 0) + 1
            return Receipt(ok=True, verified=True, detail={})
        observed = _parse_llm_observed(res.text, skel)
        if observed is None:
            return Receipt(ok=True, verified=True, detail={})
        if stats is not None:
            stats["n_parsed"] = stats.get("n_parsed", 0) + 1
        return Receipt(ok=True, verified=True,
                       detail={"observed": observed})
    return _exec


def _memory_text(b: DWC) -> str:
    """把实例记忆库里全部 SKILL 工件渲染成文本（transplant/安慰剂共用通道）。"""
    rows = b.memory._conn.execute(
        "SELECT payload FROM memory_node WHERE kind='skill'"
        " AND archived_at IS NULL").fetchall()
    if not rows:
        return ""
    return "\n".join(json.dumps(json.loads(r["payload"]), ensure_ascii=False)
                     for r in rows)


def run_arm(anchors: Dict, user_tasks: List[str], artifacts: List[Dict],
            llm: Optional[LLMClient], n_user: int, seed: int
            ) -> Dict[str, Any]:
    """单臂: 全新实例 + 注入工件（等预算: 同数注入）+ LLM executor 同预算。"""
    b = DWC(3, 50, executor=None, db_path=":memory:")
    b.judge.store = TaskScoreStore(dw_version="transfer-llm-r124")
    for a in artifacts:
        b.memory.remember(MemoryKind.SKILL, dict(a))
    stats = {"n_calls": 0, "n_parsed": 0, "n_errors": 0}
    if llm is not None and getattr(llm, "configured", False):
        b.executor = llm_executor(llm, anchors, user_tasks,
                                  _memory_text(b), stats=stats)
    else:                                            # 端点不可用 ⇒ 全 None
        stats["n_errors"] = -1
        b.executor = _null_exec()
    outcomes: List[bool] = []
    for i in range(n_user):
        out = b.step({"task_id": user_tasks[i % len(user_tasks)],
                      "kind": "dev"})
        j = out.get("judgement") or {}
        succ = j.get("success")
        if isinstance(succ, bool):
            outcomes.append(succ)
    return {"n_steps": len(outcomes),
            "success_rate": (sum(outcomes) / len(outcomes))
            if outcomes else None,
            "n_artifacts": len(artifacts), "outcomes": outcomes,
            "llm": stats}


def _null_exec():
    """LLM 不可用占位 — 返回无观测 ⇒ judge 判 None（未评价, 不为 False）。"""
    def _exec(task):
        return Receipt(ok=True, verified=True, detail={})
    return _exec


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repeat", type=int, default=2)
    ap.add_argument("--n-author", type=int, default=4)
    ap.add_argument("--n-user", type=int, default=8)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default=os.path.join(ROOT, "docs",
                                                  "transfer_llm_arm.json"))
    args = ap.parse_args()

    anchors = json.load(open(os.path.join(ROOT, "config", "anchors",
                                          "dev.json"), encoding="utf-8"))
    tasks = sorted(t for t in anchors
                   if not t.startswith("_")
                   and anchors[t].get("verifier_kind") == "behavior")
    if len(tasks) < 3:
        print("★ behavior 任务 <3 ⇒ author≠user 切分不可行 ⇒ not_applicable")
        return 2
    author_tasks, user_tasks = tasks[:1], tasks[1:]

    llm = LLMClient()
    if not getattr(llm, "configured", False):
        print("★ LLM 未配置（endpoint/key 缺席）⇒ not_computable — 不装数")
        json.dump({"status": "not_computable",
                   "why": "llm unconfigured",
                   "caveats": ["端点不可用 ⇒ 无内容通道 ⇒ 不测不报"]},
                  open(args.out, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        return 3

    # author 沉淀真工件（确定性 golden executor — 同 R107 造工件侧）
    import random
    rng = random.Random(args.seed)
    auth = DWC(3, 50, executor=None, db_path=":memory:")
    auth.judge.store = TaskScoreStore(dw_version="transfer-llm-r124")
    auth.executor = _null_exec()          # author 侧只跑链不真判分（工件提取侧）
    for i in range(args.n_author):
        auth.step({"task_id": author_tasks[i % len(author_tasks)],
                   "kind": "dev"})
    rows = auth.memory._conn.execute(
        "SELECT payload FROM memory_node WHERE kind='skill'"
        " AND archived_at IS NULL").fetchall()
    real_artifacts = [json.loads(r["payload"]) for r in rows]
    placebo = [{"scene": "blind_%d" % i,
                "method": "r%d" % rng.randrange(10 ** 6),
                "boundary": "b", "invalid_conditions": ["x"],
                "recovery_strategies": ["y"]}
               for i in range(max(len(real_artifacts), 1))]

    runs: List[Dict[str, Any]] = []
    for rep in range(args.repeat):
        arms_spec = {"transplant": real_artifacts,
                     "blind_placebo": placebo, "baseline": []}
        rep_res: Dict[str, Any] = {}
        for arm, arts in arms_spec.items():
            rep_res[arm] = run_arm(anchors, user_tasks, arts, llm,
                                   args.n_user, args.seed + rep)
        runs.append(rep_res)

    # 汇总（跨 repeat 均值序列 — 单次不复用结论; 端点波动如实）
    summary: Dict[str, Any] = {}
    for arm in ("transplant", "blind_placebo", "baseline"):
        rates = [r[arm]["success_rate"] for r in runs
                 if r[arm]["success_rate"] is not None]
        summary[arm] = {
            "rates": rates,
            "mean_rate": (sum(rates) / len(rates)) if rates else None,
            "n_parsed": sum(r[arm]["llm"]["n_parsed"] for r in runs),
            "n_calls": sum(r[arm]["llm"]["n_calls"] for r in runs)}

    t, p = summary["transplant"]["mean_rate"], summary["blind_placebo"]["mean_rate"]
    gain = (None if (t is None or p is None) else round(t - p, 6))
    out = {
        "protocol": ("4a Transfer LLM 臂: R107 三维解耦+等预算+盲安慰剂原样, "
                     "只把 golden executor 换 LLM（prompt 带工件内容 ⇒ "
                     "记忆→执行内容通道打通）; 增益须超安慰剂(Verma 同款)"),
        "seed": args.seed, "repeat": args.repeat,
        "budget": {"n_author": args.n_author, "n_user": args.n_user},
        "author_tasks": author_tasks, "n_user_tasks": len(user_tasks),
        "n_real_artifacts": len(real_artifacts),
        "arms_summary": summary,
        "attribution": {
            "transplant_minus_placebo": gain,
            "content_effect_verdict": ("not_computable" if gain is None else
                                       ("content_gain" if gain > 0 else
                                        ("placebo_equal" if gain == 0
                                         else "negative")))},
        "runs": runs,
        "reproducibility_rules": [
            "seed 显式; repeat 序列报均值（端点波动不藏）",
            "三臂同预算同任务同实例结构",
            "盲安慰剂臂：同数量盲造工件",
            "LLM 解析失败率如实报（n_parsed/n_calls）"],
        "caveats": [
            "n_user=8 单臂小样本 — 只报方向, 不做显著性声称",
            "LLM 端点质量决定绝对分数 — 对打的是臂间差不是绝对分",
            "author 产物可能 0 件 ⇒ transplant≈baseline=『无工件可移植』"
            " 如实, 不造工件",
            "真工件内容=memory 账本片段（R107 step 链不写 SKILL ⇒ "
            "author 侧 step 不改行为）— 真工件数须看报数字段",
        ],
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("三臂均值: transplant=%s placebo=%s baseline=%s" %
          (summary["transplant"]["mean_rate"],
           summary["blind_placebo"]["mean_rate"],
           summary["baseline"]["mean_rate"]))
    print("内容效应: %s ⇒ %s" % (gain, out["attribution"]
                                ["content_effect_verdict"]))
    print("解析: n_parsed=%s n_calls=%s" %
          (summary["transplant"]["n_parsed"],
           summary["transplant"]["n_calls"]))
    print("写出:", args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
