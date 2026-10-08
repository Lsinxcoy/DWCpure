# -*- coding: utf-8 -*-
"""★ 记忆注入 vs 记忆回放 —— V1 假设的第一个对照实验（EVOLUTION_CORE_V2 §十二）。

定位声明（DWC-MEM · 记忆底座 · 判据 G1 定位门）
  ★ 实验对象是**记忆的消费方式**（guidance vs replay）⇒ 属记忆底座证据侧。
  ★ 不抢位: 不声明 REPLACES。

★★★ TRUTH_SOURCE（判据 G2）
  实验不产生判定 —— 下游效果 = judge.evaluate 的 success（dev 集 golden）；
  LLM 只产候选代码，可解析性也只是 ast 事实。

=== 为什么做这个实验（§十二原文）===
  2609.14858 §5.1 的负面结果: prompt 级语义 guidance **一致劣于** replay
  （等 discovery 预算下, 两种范式皆然）。
  ⇒ ⇒★ 「DWC 现有记忆机制大概率是 guidance 形态」——本实验直接测它,
     也是**V1 假设「记忆写进去就会被用」的第一个对照检验**。
  ⇒ 论文自己也没给方差（§3.7 诚实清单）——本实验至少给 repeat 与逐次原始值。

=== 三臂（同一批记忆 · 同一 prompt 骨架 · 同预算上限 · 同 temperature）===
  C  none      无记忆注入（下界: 记忆到底有没有用 = 检验 V1）
  A  guidance  全部记忆**平铺**注入 prompt（论文语义: 历史以洞见形式直接进 prompt）
  B  replay     记忆组织成树（根→c→q→叶）, 用**真实失败签名**沿路径
                **prefix-only** 揭示（旁支只知存在、内容不泄露 —— 论文 §2.3 语义）

=== 指标（下游效果, 全部来自 judge）===
  n_pass / n_llm_ok / n_parsed · pass_rate · 每臂实际注入记忆条数（预算对等审计）

=== 诚实边界 ===
  ★ 种子记忆是**合成的**（真实历史还没有 —— 这正是 V1 要检验的系统尚未积累）；
    c 值域与 judge.classify_c 对齐, 保证签名匹配是真匹配不是摆拍。
  ★ 任务 2 个 × repeat 默认 2 ⇒ 样本小, 报告只给**方向**不给"证明"。
  ★ 论文的 guidance 是"高层方向性洞见"; 本实现是"记忆条目平铺"——
    同族但操作化不同（论文未给 prompt 模板）。
"""
from __future__ import annotations

import argparse
import ast
import io
import json
import os
import re
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
if _ROOT not in sys.path:
    sys.path.insert(0, os.path.join(_ROOT, "src"))

from dwc.llm import LLMClient                            # noqa: E402
from dwc.organs.actor import Actor, execute_task         # noqa: E402
from dwc.organs.judge import Judge                       # noqa: E402

#: 系统外真值源（G2）
TRUTH_SOURCE = {
    "声明": "实验不判成功：下游效果 = dwc.organs.judge.evaluate（dev golden）",
    "真值源位置": "dwc.organs.judge.TRUTH_SOURCE（config/anchors/dev.json）",
    "自判禁止": "LLM 只产候选；可解析性=ast 事实；无任何自评打分",
}

#: 任务对（buggy 实现 = e2e 任务床 code_fix_001–004 同源, 真 bug）
#: ★ 事前固定为**全部 4 个**（不按结果挑任务 —— 挑任务 = 挑结论）
#: ★ 4 个 buggy 已实测全被判 fail（失败签名: 001–003 = E_VALUE/wrong_magnitude,
#:   004 = E_OFF_BY_ONE/off_by_one_in_range —— 种子记忆按此真值域造）
TASKS = {
    "code_fix_001": "def sum_first_n(n):\n    return sum(range(n))",
    "code_fix_002": "def average(xs):\n    return sum(xs) / (len(xs) + 1)",
    "code_fix_003": ("def factorial(n):\n    r = 1\n"
                     "    for i in range(1, n):\n        r *= i\n    return r"),
    "code_fix_004": ("def fibonacci(n):\n    a, b = 0, 1\n"
                     "    for _ in range(n - 1):\n        a, b = b, a + b\n"
                     "    return a"),
}

#: ★ 合成种子记忆（诚实标注: 不是真实历史 —— 真值域已对齐 judge.classify_c/q,
#:   实测词汇: c ∈ {E_VALUE, E_OFF_BY_ONE, E_TYPE, E_NO_RESULT, E_NONE, …}
#:            q ∈ {wrong_magnitude, off_by_one_in_range, …}）
#:   8 条 = 4 条命中（001–003 与 004 的真实签名路径）+ 4 条干扰
#:   （其中 1 条**同 c 异 q** ⇒ replay 只揭结构不揭内容, 演练 prefix-only）
SEED_MEMORY: List[Dict[str, str]] = [
    # ── 命中 · E_VALUE / wrong_magnitude（001/002/003 的路径）──
    {"scene": "累加和少算一项", "c": "E_VALUE", "q": "wrong_magnitude",
     "fix_hint": "确认求和范围是否覆盖全部项（首末项都算）"},
    {"scene": "分母比元素多", "c": "E_VALUE", "q": "wrong_magnitude",
     "fix_hint": "分母就是元素个数本身, 别再加常数"},
    {"scene": "阶乘循环漏乘末项", "c": "E_VALUE", "q": "wrong_magnitude",
     "fix_hint": "累乘区间要含 n 本体（range 上界 +1）"},
    # ── 命中 · E_OFF_BY_ONE / off_by_one_in_range（004 的路径）──
    {"scene": "斐波那契少迭代一轮", "c": "E_OFF_BY_ONE",
     "q": "off_by_one_in_range",
     "fix_hint": "迭代次数按定义数满 n 轮（range 边界含端点）"},
    # ── 干扰 · 同 c 异 q（replay: c 分支在, 叶不揭）──
    {"scene": "空序列没护栏", "c": "E_VALUE", "q": "guard_missing",
     "fix_hint": "空输入要给显式语义"},
    # ── 干扰 · 异 c（replay 根本不进路径; guidance 会平铺进来）──
    {"scene": "字符串当数字比", "c": "E_TYPE", "q": "type_mismatch",
     "fix_hint": "先归一类型再比较"},
    {"scene": "函数没跑出结果", "c": "E_NO_RESULT",
     "q": "abstained_or_missing",
     "fix_hint": "先确认执行路径真的 return 了"},
    {"scene": "布尔极性反了", "c": "E_NONE", "q": "wrong_polarity",
     "fix_hint": "检查返回条件是否取反"},
]

#: 预算上限（三臂对等 —— 论文的 equivalent budgets）
MEMO_BUDGET = 8

ARMS = ("none", "guidance", "replay")


# ══════════════════════════════════════════════════════════
# replay 树（prefix-only 揭示 —— 论文 §2.3: 未揭示的保持未知）
# ══════════════════════════════════════════════════════════

def make_tree(items: List[Dict[str, str]]) -> Dict[str, Any]:
    """根 → c（终止原因）→ q（因果角色）→ 叶（经验条目）。"""
    root: Dict[str, Any] = {"c_branches": {}}
    for it in items:
        root["c_branches"].setdefault(it["c"], {}).setdefault(
            it["q"], []).append(it)
    return root


def reveal_path(tree: Dict[str, Any], c: str, q: str,
                budget: int = MEMO_BUDGET) -> Tuple[List[Dict[str, str]], str]:
    """★ prefix-only: 沿 (c,q) 路径揭示; 旁支**只报存在, 不泄内容**。

    返回 (揭示的条目, 结构摘要)。预算上限内截断。
    """
    branches = tree["c_branches"]
    if c not in branches:
        return [], ("根下无 c=%s 分支 ⇒ 本轮对该方向**零揭示**"
                    "（分支集合: %s）" % (c, sorted(branches)))
    qmap = branches[c]
    summary = ("c=%s 分支存在（含 %d 个 q 子分支: %s）"
               % (c, len(qmap), sorted(qmap)))
    if q not in qmap:
        return [], summary + "；但 q=%s 叶子**未揭示**（prefix-only）" % q
    leaves = qmap[q][:budget]
    return leaves, summary + "；q=%s 叶子已揭示 %d 条" % (q, len(leaves))


# ══════════════════════════════════════════════════════════
# prompt 构造（同一骨架, 只有记忆块不同）
# ══════════════════════════════════════════════════════════

def _memory_block_guidance(items: List[Dict[str, str]]) -> str:
    lines = ["过往经验（历史教训, 直接参考）:"]
    for it in items[:MEMO_BUDGET]:
        lines.append("- [%s/%s] %s → %s"
                     % (it["c"], it["q"], it["scene"], it["fix_hint"]))
    return "\n".join(lines)


def _memory_block_replay(items: List[Dict[str, str]], summary: str) -> str:
    if not items:
        return ("过往经验回放树: %s\n⇒ 本轮无已揭示经验（只有结构事实）。"
                % summary)
    lines = ["过往经验回放树: %s" % summary, "沿路径已揭示的经验:"]
    for it in items:
        lines.append("- [%s/%s] %s → %s"
                     % (it["c"], it["q"], it["scene"], it["fix_hint"]))
    return "\n".join(lines)


def build_prompt(arm: str, task_id: str, buggy: str,
                 fn_hint: str = "",
                 memo_items: Optional[List[Dict[str, str]]] = None,
                 replay_summary: str = "") -> str:
    """同一 prompt 骨架 —— 三臂只差记忆块（对照的干净性）。"""
    if arm not in ARMS:
        raise ValueError("未知臂 %r ∈ %s" % (arm, list(ARMS)))
    memo = ""
    if arm == "guidance":
        memo = _memory_block_guidance(memo_items or []) + "\n\n"
    elif arm == "replay":
        memo = _memory_block_replay(memo_items or [], replay_summary) + "\n\n"
    body = (
        "%s"
        "修复下面 Python 函数的 bug。只输出修复后的完整代码"
        "（可围 ```python 代码块, 不要解释）。\n\n```python\n%s\n```\n"
        % (memo, buggy))
    if fn_hint:
        body = "函数名: %s\n" % fn_hint + body
    return body


def extract_code(text: str) -> Optional[str]:
    """从 LLM 回复抽代码; ast 可解析才返回（否则 None —— 不猜）。"""
    if not text:
        return None
    blocks = re.findall(r"```(?:python)?\s*\n(.*?)```", text, re.S)
    cand = blocks[0] if blocks else text
    i = cand.find("def ")
    if i >= 0:
        cand = cand[i:]
    cand = cand.strip()
    try:
        ast.parse(cand)
    except SyntaxError:
        return None
    return cand


# ══════════════════════════════════════════════════════════
# 实验主循环
# ══════════════════════════════════════════════════════════

def run_experiment(llm: Any, repeat: int = 2,
                   tasks: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """跑三臂对照。llm 只要 .complete/.configured（可注入假的离线跑）。"""
    tasks = tasks or TASKS
    judge, actor = Judge(), Actor()
    tree = make_tree(SEED_MEMORY)
    records: List[Dict[str, Any]] = []
    started = time.time()

    for task_id, buggy in tasks.items():
        # ① 先拿**真实**失败签名（B 臂路径的依据 —— 不是摆拍的匹配）
        base_obs = execute_task(actor, judge, task_id,
                                implementation=buggy)["observation"]
        v_base = judge.evaluate(task_id, "dev", observed=base_obs)
        sig = v_base.failure_signature or {}
        c, q = sig.get("c", ""), sig.get("q", "")
        if v_base.success is not False:
            records.append({"task": task_id, "arm": "-", "rep": -1,
                            "error": "前提失败: buggy 实现没被判 fail "
                                     "(success=%s) ⇒ 实验不成立" % v_base.success})
            continue
        for arm in ARMS:
            for rep in range(repeat):
                rec = {"task": task_id, "arm": arm, "rep": rep,
                       "sig_c": c, "sig_q": q,
                       "memo_n": 0, "llm_ok": False, "parsed": False,
                       "pass_": None, "error": ""}
                memo_items, summary = [], ""
                if arm == "guidance":
                    memo_items = SEED_MEMORY[:MEMO_BUDGET]
                    rec["memo_n"] = len(memo_items)
                elif arm == "replay":
                    memo_items, summary = reveal_path(tree, c, q)
                    rec["memo_n"] = len(memo_items)
                prompt = build_prompt(arm, task_id, buggy,
                                      memo_items=memo_items,
                                      replay_summary=summary)
                res = llm.complete(
                    prompt,
                    system="你是修复器。只输出可运行的修复代码。")
                if not res.ok:
                    rec["error"] = "llm: %s" % (res.error or res.source)
                    records.append(rec)
                    continue
                rec["llm_ok"] = True
                code = extract_code(res.text)
                if code is None:
                    rec["error"] = "回复不可解析为代码"
                    records.append(rec)
                    continue
                rec["parsed"] = True
                try:
                    obs = execute_task(actor, judge, task_id,
                                       implementation=code)["observation"]
                    v = judge.evaluate(task_id, "dev", observed=obs)
                    rec["pass_"] = bool(v.success)
                except Exception as exc:   # noqa: BLE001 —— 如实记录, 不静默
                    rec["error"] = "执行/判分异常 %s: %s" % (
                        type(exc).__name__, str(exc)[:100])
                records.append(rec)

    # ── 汇总（逐臂, 原始值全留）──
    summary: Dict[str, Any] = {}
    for arm in ARMS:
        rows = [r for r in records if r["arm"] == arm]
        n_llm = sum(1 for r in rows if r["llm_ok"])
        n_parsed = sum(1 for r in rows if r["parsed"])
        n_pass = sum(1 for r in rows if r.get("pass_") is True)
        summary[arm] = {
            "n_calls": len(rows), "n_llm_ok": n_llm, "n_parsed": n_parsed,
            "n_pass": n_pass,
            "pass_rate": (n_pass / len(rows)) if rows else None,
            "memo_n_per_call": sorted({r["memo_n"] for r in rows}),
        }
    return {"arms": summary, "records": records,
            "n_tasks": len(tasks), "repeat": repeat,
            "elapsed_s": round(time.time() - started, 1),
            "seed_memory": "synthetic (8 条, c 值域对齐 judge.classify_c)",
            "verdict": _verdict(summary)}


def _verdict(summary: Dict[str, Any]) -> Dict[str, Any]:
    """只给**方向**（样本小, 不给"证明"）—— 两个问题分开答。"""
    def rate(a):
        return summary[a]["pass_rate"]

    def n(a):
        return summary[a]["n_calls"]

    out: Dict[str, Any] = {"v1_memory_useful": None,
                           "paper_direction_replay_gt_guidance": None,
                           "note": "样本小(任务×repeat), 只报方向; "
                                   "论文 §3.7 自己也无方差"}
    try:
        if n("none") and n("guidance"):
            base, g = rate("none"), rate("guidance")
            if base is not None and g is not None:
                out["v1_memory_useful"] = bool(g > base)
                out["v1_detail"] = ("guidance %.2f vs none %.2f"
                                    % (g, base))
        if n("guidance") and n("replay"):
            g, rp = rate("guidance"), rate("replay")
            if g is not None and rp is not None:
                out["paper_direction_replay_gt_guidance"] = bool(rp > g)
                out["direction_detail"] = ("replay %.2f vs guidance %.2f"
                                           % (rp, g))
    except Exception as exc:   # noqa: BLE001 —— 汇总失败也不吞
        out["error"] = "%s: %s" % (type(exc).__name__, exc)
    return out


def _print_report(result: Dict[str, Any]) -> None:
    print("\n" + "=" * 64)
    print("★ 记忆注入 vs 记忆回放（guidance vs replay）· 三臂对照")
    print("=" * 64)
    hdr = "%-10s %6s %8s %8s %6s %10s  %s"
    print(hdr % ("arm", "calls", "llm_ok", "parsed", "pass", "pass_rate",
                 "memo_n"))
    for arm in ARMS:
        s = result["arms"][arm]
        print(hdr % (arm, s["n_calls"], s["n_llm_ok"], s["n_parsed"],
                     s["n_pass"],
                     "%.3f" % s["pass_rate"] if s["pass_rate"] is not None
                     else "-",
                     s["memo_n_per_call"]))
    v = result["verdict"]
    print("\nV1 检验（记忆有用? guidance>none）: %s  %s"
          % (v.get("v1_memory_useful"), v.get("v1_detail", "")))
    print("论文方向（replay>guidance）:        %s  %s"
          % (v.get("paper_direction_replay_gt_guidance"),
             v.get("direction_detail", "")))
    print("★ %s" % v.get("note"))
    errs = [r for r in result["records"] if r.get("error")]
    if errs:
        print("★ 异常/降级 %d 条（原始值已入 JSON）:" % len(errs))
        for e in errs[:6]:
            print("   %s/%s/rep%s: %s" % (e["task"], e["arm"], e["rep"],
                                          e["error"][:80]))


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="memory guidance vs replay 实验")
    ap.add_argument("--repeat", type=int, default=2)
    ap.add_argument("--out", default=os.path.join(
        _ROOT, "archive", "experiments", "mem_guidance_vs_replay.json"))
    args = ap.parse_args(argv)

    llm = LLMClient()
    if not llm.configured:
        # ★ 不静默跳过（G7 同族）: 明说为什么没测
        print("★ LLM 未配置 ⇒ 实验未跑（不是通过）。配置: config/llm.json "
              "或 DWC_LLM_* 三件套")
        return 2
    result = run_experiment(llm, repeat=args.repeat)
    _print_report(result)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    result["at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    with io.open(args.out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    print("\n原始记录: %s" % os.path.relpath(args.out, _ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
