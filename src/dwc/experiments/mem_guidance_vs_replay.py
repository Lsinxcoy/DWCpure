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

#: ★ R64 · 任务 = dev **全集 10 条**（6 behavior + 4 keyword_match, 事前全集不挑）
#:   行为类 buggy: 001–004 = e2e 同源 · 005 = e2e _LBUG（忘 .lower()）·
#:   006 = 实验构造（该任务是实现型, buggy=恒等实现 return s, 已标注）
#:   推理类无 buggy —— 基线 = 空答案（judge 同样给出真实失败签名）
BEHAVIOR_TASKS = {
    "code_fix_001": "def sum_first_n(n):\n    return sum(range(n))",
    "code_fix_002": "def average(xs):\n    return sum(xs) / (len(xs) + 1)",
    "code_fix_003": ("def factorial(n):\n    r = 1\n"
                     "    for i in range(1, n):\n        r *= i\n    return r"),
    "code_fix_004": ("def fibonacci(n):\n    a, b = 0, 1\n"
                     "    for _ in range(n - 1):\n        a, b = b, a + b\n"
                     "    return a"),
    "code_fix_005": "def is_palindrome(s):\n    return s == s[::-1]",
    "code_fix_006": "def reverse_string(s):\n    return s",
}
#: 推理任务（题面来自 dev.json 的 prompt 字段; 答案判 keyword_match）
QA_TASKS = ("reasoning_001", "reasoning_002",
            "reasoning_003", "reasoning_004")
#: 兼容旧名（测试与 main 用）
TASKS = dict(BEHAVIOR_TASKS)

#: ★ 合成种子记忆（诚实标注: 不是真实历史 —— 真值域已对齐 judge.classify_c/q）
#:   40 条 = 4 条命中（001–003 与 004 的真实签名路径）+ 36 条**干扰**
#:   （R64 稀释效应: guidance 平铺全库 vs replay 只揭路径 —— 差异就来自干扰量）
#:   干扰的 (c,q) **避开**两条命中路径, 否则会泄进 replay 揭示集
SEED_HIT: List[Dict[str, str]] = [
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
]

#: 干扰的 (c,q) 组合 —— 全部**不在**命中路径上
_DISTRACT_CQ = [
    ("E_TYPE", "type_mismatch"), ("E_TYPE", "wrong_polarity"),
    ("E_TYPE", "abstained_or_missing"),
    ("E_NO_RESULT", "type_mismatch"), ("E_NO_RESULT", "wrong_polarity"),
    ("E_NO_RESULT", "abstained_or_missing"),
    ("E_NONE", "type_mismatch"), ("E_NONE", "wrong_polarity"),
    ("E_NONE", "abstained_or_missing"),
    ("E_VALUE", "guard_missing"),
    ("E_OFF_BY_ONE", "guard_missing"),
    ("E_OFF_BY_ONE", "type_mismatch"),
]
_DISTRACT_SCENE = ["参数没归一", "提前退出漏分支", "状态没复位",
                   "哨兵值当真值"]          # 4 个变体 ×12 组 = 48 ≥ 36, 取 36


def _distractors() -> List[Dict[str, str]]:
    """★ 程序生成的合成干扰（固定顺序 ⇒ 可复现）。避开命中路径。"""
    out: List[Dict[str, str]] = []
    i = 0
    for sc in _DISTRACT_SCENE:
        for c, q in _DISTRACT_CQ:
            if len(out) >= 36:
                break
            out.append({"scene": "%s·%s" % (sc, c),
                        "c": c, "q": q,
                        "fix_hint": "第 %d 条干扰经验（合成, 供稀释对照）" % i})
            i += 1
        if len(out) >= 36:
            break
    return out


SEED_MEMORY: List[Dict[str, str]] = SEED_HIT + _distractors()

#: 预算上限 = 全库（R64: 两臂上限对等 = 40; 实际注入量如实报告 ——
#: guidance 平铺 40 vs replay 按路径 1–3, 这个差**就是**被测对象）
MEMO_BUDGET = 40

# ══════════════════════════════════════════════════════════
# R65 · 硬战场: 自建难题锚点 + 真实误导干扰（纯稀释实验）
# ══════════════════════════════════════════════════════════

HARD_PATH = os.path.join(_ROOT, "config", "experiments", "hard_tasks.json")

#: R66 grown · 消费阶段任务（**事前固定**: dev 与 hard 同签名族是基线实测的
#:   客观事实 — clamp↔001-003 同为 E_VALUE/wrong_magnitude, median↔004 同为
#:   E_OFF_BY_ONE/off_by_one_in_range ⇒ 迁移通道天然存在）
GROWN_TASKS = ("code_fix_001", "code_fix_002",
               "code_fix_003", "code_fix_004")


def _memory_from_verdict(tid: str, v: Any) -> Dict[str, str]:
    """★ 从**真实判分结果**写入一条记忆（R66 写入侧的最小诚实实现）。

    fix_hint = 失败 diffs 的 fn/args/期望/实得 —— 全部来自 judge, 不编造。
    """
    sig = v.failure_signature or {}
    diffs = getattr(v, "diffs", None) or []
    fails = [d for d in diffs if not d.get("ok")]
    parts = ["%s%s 期望%s 实得%s" % (d.get("fn"), d.get("args"),
                                     d.get("expected"), d.get("actual"))
             for d in fails[:2]]
    hint = ("上次实测失败: " + "; ".join(parts)) if parts         else str(getattr(v, "reason", ""))[:120]
    return {"scene": tid, "c": str(sig.get("c", "")),
            "q": str(sig.get("q", "")), "fix_hint": hint, "origin": tid}

#: ★ 真实误导性干扰（R65 替换占位文本）—— 措辞像专业经验, 但方向错误/无关:
#:   这才是 guidance 平铺的真弹药（占位文本 LLM 直接无视, R64 教训）
#:   (c,q) 由基线签名**事前避让**（见 _realistic_distractors 的 exclude 参数）
_MISLEAD_HINTS = [
    "range 是右开区间, 千万别手贱 +1, 多算是初学者错误",
    "空序列应抛 ValueError 而不是返回哨兵值, 静默兜底掩盖 bug",
    "把每个分支都改成显式 raise, 宁可崩溃也别给错误结果",
    "先写类型注解再实现, 能规避九成边界问题",
    "比较浮点数直接 == 就行, 加 epsilon 是过度工程",
    "函数越短越好, 早退反模式让调用方难以推理",
    "所有边界条件合并到一个三元表达式里最清晰",
    "先查标准库再动手, 自己写循环通常不如内置函数",
    "递归比循环可读性高, 优先递归翻译数学定义",
    "把魔法数字抽成常量是第一优先级, 逻辑可以后补",
    "字符串处理直接拼接最直观, join 是过早优化",
    "try/except 兜底越宽越好, 保证主流程不中断",
]
_MISLEAD_SCENE = ["通用手法", "边界哲学", "风格准则"]   # 3 × 12 = 36


def _realistic_distractors(exclude: set) -> List[Dict[str, str]]:
    """★ 36 条**真实误导**干扰: (c,q) 避开 exclude（hard 任务真实签名）。

    exclude 为空（如 dev 旧路径）时退化为与 R64 相同的干扰 (c,q) 池。
    固定顺序 ⇒ 可复现。
    """
    # ★ R65 实测: hard 任务的真实签名组必须**在池内**（历史经验的签名分布
    #   本该覆盖它们）—— 否则"避让"无对象 = 形同虚设（破坏②实测不红的根因）
    #   置于池首: 排除后列表左移, pairs 恰好用剩余 12 组
    base_cq = [
        ("E_VALUE", "wrong_magnitude"),
        ("E_OFF_BY_ONE", "off_by_one_in_range"),
        ("E_MISMATCH", "wrong_content"),
        ("E_MISMATCH", "value_mismatch"),
        ("E_FALSE_POSITIVE", "wrong_polarity"),
        ("E_TYPE", "type_mismatch"), ("E_TYPE", "wrong_polarity"),
        ("E_TYPE", "abstained_or_missing"),
        ("E_NO_RESULT", "type_mismatch"), ("E_NO_RESULT", "wrong_polarity"),
        ("E_NO_RESULT", "abstained_or_missing"),
        ("E_NONE", "type_mismatch"), ("E_NONE", "wrong_polarity"),
        ("E_NONE", "abstained_or_missing"),
        ("E_VALUE", "guard_missing"),
        ("E_OFF_BY_ONE", "guard_missing"),
        ("E_OFF_BY_ONE", "type_mismatch"),
    ]
    cq = [(c, q) for (c, q) in base_cq if (c, q) not in exclude] or base_cq
    # ★ 恒 12 对/场景 ⇒ 36 条（exclude 后 (c,q) 循环补位, 条数不缩水 ——
    #   条数是预算对等的前提, 不许因避让而变）
    pairs = [(cq[i % len(cq)], _MISLEAD_HINTS[i % len(_MISLEAD_HINTS)])
             for i in range(12)]
    out: List[Dict[str, str]] = []
    for sc in _MISLEAD_SCENE:
        for (c, q), hint in pairs:
            out.append({"scene": "%s·%s" % (sc, c),
                        "c": c, "q": q,
                        "fix_hint": hint})
    return out


def hard_judge() -> Any:
    """实验自带锚点的 judge（同一判分逻辑, 真值源=锚点文件）。"""
    from dwc.organs.judge import Judge as _Judge
    return _Judge(anchors_path=HARD_PATH)


def hard_fns(judge: Any) -> List[str]:
    """hard 任务的**函数名**集合（沙箱白名单的键是 fn 不是 task id）。"""
    fns = set()
    for tid, rec in judge.anchors.items():
        if tid.startswith("_") or not isinstance(rec, dict):
            continue
        for c in rec.get("checks") or []:
            if c.get("fn"):
                fns.add(str(c["fn"]))
    return sorted(fns)


def hard_sources(judge: Any) -> Dict[str, str]:
    """hard 任务的 buggy 实现（锚点 rec 自带字段, judge 校验只认 kind/checks）。"""
    return {tid: rec["buggy"] for tid, rec in judge.anchors.items()
            if not tid.startswith("_") and isinstance(rec, dict)}


class _HardSandbox:
    """★ 进程内具名扩沙箱白名单（跑完恢复 —— 不改承重件, 影响面=本进程）。

    白名单是防任意执行的边界: 只加实验锚点里的**具名**函数, 不放开通配。
    """

    def __init__(self, fns):
        from dwc.organs.actor import PureFunctionExecutor as _P
        self._cls = _P
        self._fns = tuple(fns)

    def __enter__(self):
        old = self._cls.ALLOWED
        self._old = old
        merged = tuple(dict.fromkeys(list(old) + list(self._fns)))
        # ★ 具名白名单, 无通配; 扩的每个名字来自实验锚点
        self._cls.ALLOWED = merged
        return self

    def __exit__(self, *exc):
        self._cls.ALLOWED = self._old   # 恢复原状（异常路径也恢复）
        return False

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


def build_prompt(arm: str, task_id: str, material: str,
                 fn_hint: str = "",
                 memo_items: Optional[List[Dict[str, str]]] = None,
                 replay_summary: str = "",
                 material_kind: str = "code",
                 feedback: Optional[str] = None) -> str:
    """同一 prompt 骨架 —— 三臂只差记忆块（对照的干净性）。

    material_kind="code":  修 bug（material = buggy 源码）
    material_kind="qa":    答问题（material = dev 题面, 答案走 keyword_match）
    feedback:              第 ≥2 轮的**臂中立**反馈（上轮产出 + judge 失败原因）
    """
    if arm not in ARMS:
        raise ValueError("未知臂 %r ∈ %s" % (arm, list(ARMS)))
    memo = ""
    if arm == "guidance":
        memo = _memory_block_guidance(memo_items or []) + "\n\n"
    elif arm == "replay":
        memo = _memory_block_replay(memo_items or [], replay_summary) + "\n\n"
    if material_kind == "code":
        task_block = (
            "修复下面 Python 函数的 bug。只输出修复后的完整代码"
            "（可围 ```python 代码块, 不要解释）。\n\n```python\n%s\n```"
            % material)
    elif material_kind == "qa":
        task_block = ("直接回答下面问题（只输出答案文本, 不要解释过程）。\n"
                      "问题: %s" % material)
    else:
        raise ValueError("material_kind=%r 非法" % material_kind)
    if feedback:
        task_block += ("\n\n上一轮尝试与判分反馈（臂中立, 三臂同文）:\n%s"
                       % feedback)
    body = memo + task_block
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

def run_experiment(llm: Any, repeat: int = 2, rounds: int = 2,
                   tasks: Optional[Dict[str, str]] = None,
                   qa: Optional[bool] = None,
                   dataset: str = "dev") -> Dict[str, Any]:
    """R66 · 三臂对照。dataset="dev"/"hard"/"grown"。

    ★ 两阶段: ①全基线拿臂中立签名（前提: 每条基线须 fail）→ ②建树 → ③臂循环。
    ★ hard: judge=实验锚点 · 种子=36 条**真实误导**（签名事前避让 · 无命中）。
    ★ grown: **记忆增长+跨任务迁移** —— 先写入（hard 5 题真实失败 ⇒ 记忆库,
      fix_hint 全部来自 judge diffs, 不是合成）→ 再消费（dev 同签名族 4 题三臂）。
      这才是 V1 的真正考验: 记忆**自己长出来之后**有没有被用。
    ★ 多轮: r≥2 带臂中立反馈; 任一轮 pass ⇒ 该 trial 早停。
    """
    if dataset not in ("dev", "hard", "grown"):
        raise ValueError("dataset=%r 非法" % dataset)
    if dataset == "hard":
        judge = hard_judge()
        behav = hard_sources(judge)
        include_qa = False
        ctx: Any = _HardSandbox(hard_fns(judge))
    elif dataset == "grown":
        behav = {t: BEHAVIOR_TASKS[t] for t in GROWN_TASKS}
        include_qa = False
        judge, ctx = Judge(), _NullCtx()
    else:
        behav = dict(tasks) if tasks is not None else dict(BEHAVIOR_TASKS)
        include_qa = (tasks is None) if qa is None else bool(qa)
        judge, actor = Judge(), Actor()
        ctx = _NullCtx()
    actor = Actor()
    records: List[Dict[str, Any]] = []
    started = time.time()

    specs: List[Tuple[str, str, str]] = [
        (tid, "code", buggy) for tid, buggy in behav.items()]
    if include_qa:
        specs += [(tid, "qa",
                   str(judge.anchors[tid].get("prompt", "")))
                  for tid in QA_TASKS]

    # ── R66 grown · 写入阶段: hard 5 题真实失败 ⇒ 记忆库（判分产物, 非合成）──
    grown_memory: List[Dict[str, str]] = []
    if dataset == "grown":
        hj = hard_judge()
        with _HardSandbox(hard_fns(hj)):
            for tid, buggy in hard_sources(hj).items():
                obs = execute_task(Actor(), hj, tid,
                                   implementation=buggy)["observation"]
                v = hj.evaluate(tid, "dev", observed=obs)
                if v.success is not False:
                    records.append({"task": tid, "arm": "w", "rep": -1,
                                    "round": 0,
                                    "error": "写入前提失败: %s 基线没 fail "
                                             "⇒ 不许进记忆库" % tid})
                    continue
                grown_memory.append(_memory_from_verdict(tid, v))
        if len(grown_memory) != len(hard_sources(hj)):
            records.append({"task": "_write", "arm": "w", "rep": -1, "round": 0,
                            "error": "写入不全: %d/%d"
                                     % (len(grown_memory),
                                        len(hard_sources(hj)))})

    with ctx:
        # ── 阶段① 全基线（臂中立签名; hard 还要给干扰避让用）──
        sig_map: Dict[str, Optional[Tuple[str, str]]] = {}
        for tid, kind, material in specs:
            if kind == "code":
                base_obs = execute_task(
                    actor, judge, tid, implementation=material)["observation"]
            else:
                base_obs = {"answer": ""}      # 推理类基线 = 空答案
            v_base = judge.evaluate(tid, "dev", observed=base_obs)
            if v_base.success is not False:
                records.append({"task": tid, "arm": "-", "rep": -1, "round": 0,
                                "error": "前提失败: 基线没被判 fail "
                                         "(success=%s) ⇒ 实验不成立"
                                         % v_base.success})
                sig_map[tid] = None
                continue
            s = v_base.failure_signature or {}
            sig_map[tid] = (str(s.get("c", "")), str(s.get("q", "")))

        # ── 阶段② 建树（hard: 真实误导; grown: **真实增长**的; dev: R64 种子）──
        if dataset == "hard":
            exclude = {v for v in sig_map.values() if v}
            seed = _realistic_distractors(exclude)
        elif dataset == "grown":
            seed = grown_memory       # ★ 消费的就是写入阶段长出来的
        else:
            seed = SEED_MEMORY
        tree = make_tree(seed)

        # ── 阶段③ 臂循环 ──
        for tid, kind, material in specs:
            if sig_map.get(tid) is None:
                continue                       # 前提失败的任务不进臂
            c, q = sig_map[tid]  # type: ignore[misc]
            for arm in ARMS:
                for rep in range(repeat):
                    if arm == "guidance":
                        memo_items: List[Dict[str, str]] = seed[:MEMO_BUDGET]
                        summary = ""
                    elif arm == "replay":
                        memo_items, summary = reveal_path(tree, c, q)
                    else:
                        memo_items, summary = [], ""
                    feedback: Optional[str] = None
                    for rnd in range(1, rounds + 1):
                        rec = {"task": tid, "arm": arm, "rep": rep,
                               "round": rnd, "kind": kind,
                               "sig_c": c, "sig_q": q,
                               "memo_n": len(memo_items), "llm_ok": False,
                               "parsed": False, "pass_": None, "error": ""}
                        prompt = build_prompt(arm, tid, material,
                                              memo_items=memo_items,
                                              replay_summary=summary,
                                              material_kind=kind,
                                              feedback=feedback)
                        res = llm.complete(
                            prompt,
                            system="只输出可运行的修复代码或直接答案。")
                        if not res.ok:
                            rec["error"] = "llm: %s" % (res.error or res.source)
                            records.append(rec)
                            break
                        rec["llm_ok"] = True
                        if kind == "code":
                            output = extract_code(res.text)
                            if output is None:
                                rec["error"] = "回复不可解析为代码"
                                records.append(rec)
                                break
                            rec["parsed"] = True
                        else:
                            output = res.text
                            rec["parsed"] = True
                        try:
                            if kind == "code":
                                obs = execute_task(
                                    actor, judge, tid,
                                    implementation=output)["observation"]
                            else:
                                obs = {"answer": str(output)}
                            v = judge.evaluate(tid, "dev", observed=obs)
                            rec["pass_"] = bool(v.success)
                        except Exception as exc:   # noqa: BLE001 —— 如实记录
                            rec["error"] = "执行/判分异常 %s: %s" % (
                                type(exc).__name__, str(exc)[:100])
                            records.append(rec)
                            break
                        records.append(rec)
                        if rec["pass_"]:
                            break                  # ★ 早停
                        # ★ 臂中立反馈（三臂同文 —— 只含上轮产出与 judge 原因）
                        if kind == "code":
                            feedback = ("你上轮的代码:\n```python\n%s\n```\n"
                                        "判分失败原因: %s"
                                        % (output, str(v.reason)[:300]))
                        else:
                            diffs = getattr(v, "diffs", None) or []
                            miss = [str(d.get("kw")) for d in diffs
                                    if not d.get("ok") and d.get("kw")]
                            feedback = ("你上轮的答案: %s\n缺失关键词: %s"
                                        % (str(output)[:300], ", ".join(miss)))

    # ── 汇总（trial = (task, rep); pass_rate = 曾 pass 的 trial 占比）──
    summary: Dict[str, Any] = {}
    for arm in ARMS:
        rows = [r for r in records if r["arm"] == arm]
        trials = {(r["task"], r["rep"]) for r in rows}
        passed = {(r["task"], r["rep"]) for r in rows
                  if r.get("pass_") is True}
        summary[arm] = {
            "n_calls": len(rows),
            "n_llm_ok": sum(1 for r in rows if r["llm_ok"]),
            "n_parsed": sum(1 for r in rows if r["parsed"]),
            "n_trials": len(trials),
            "n_trials_passed": len(passed),
            "pass_rate": (len(passed) / len(trials)) if trials else None,
            "memo_n_per_call": sorted({r["memo_n"] for r in rows}),
        }
    if dataset == "hard":
        seed_desc = "36 条真实误导（签名避让, 无命中）"
    elif dataset == "grown":
        seed_desc = ("★ %d 条**真实增长**（hard 5 题判分产物, 非合成）"
                     % len(grown_memory))
    else:
        seed_desc = ("synthetic (40 条: 4 命中 + 36 干扰, "
                     "c/q 值域对齐 judge.classify_c)")
    return {"arms": summary, "records": records, "dataset": dataset,
            "n_tasks": len(specs), "repeat": repeat, "rounds": rounds,
            "elapsed_s": round(time.time() - started, 1),
            "seed_memory": seed_desc,
            "verdict": _verdict(summary)}


class _NullCtx:
    """dev 模式不做沙箱操作的空上下文（统一 with 结构）。"""

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False



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
    print("★ 记忆注入 vs 记忆回放（guidance vs replay）· 三臂对照"
          " · dataset=%s · %d轮早停"
          % (result.get("dataset", "dev"), result.get("rounds", 1)))
    print("=" * 64)
    hdr = "%-10s %6s %8s %8s %11s %10s  %s"
    print(hdr % ("arm", "calls", "llm_ok", "parsed", "pass(trial)",
                 "pass_rate", "memo_n"))
    for arm in ARMS:
        s = result["arms"][arm]
        print(hdr % (arm, s["n_calls"], s["n_llm_ok"], s["n_parsed"],
                     "%d/%d" % (s["n_trials_passed"], s["n_trials"]),
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
            print("   %s/%s/rep%s/r%s: %s" % (e["task"], e["arm"], e["rep"],
                                              e.get("round", "?"),
                                              e["error"][:70]))


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="memory guidance vs replay 实验")
    ap.add_argument("--repeat", type=int, default=1,
                    help="每 trial 重复次数（R64 建议 1, 靠 rounds 拿样本）")
    ap.add_argument("--rounds", type=int, default=2,
                    help="多轮上限（臂中立反馈, pass 早停）")
    ap.add_argument("--dataset", choices=("dev", "hard", "grown"),
                    default="dev",
                    help="任务集: dev / hard(R65 硬战场) / "
                         "grown(R66 记忆增长+跨任务迁移)")
    ap.add_argument("--out", default=os.path.join(
        _ROOT, "archive", "experiments", "mem_guidance_vs_replay.json"))
    args = ap.parse_args(argv)

    llm = LLMClient()
    if not llm.configured:
        # ★ 不静默跳过（G7 同族）: 明说为什么没测
        print("★ LLM 未配置 ⇒ 实验未跑（不是通过）。配置: config/llm.json "
              "或 DWC_LLM_* 三件套")
        return 2
    result = run_experiment(llm, repeat=args.repeat, rounds=args.rounds,
                           dataset=args.dataset)
    _print_report(result)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    result["at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    with io.open(args.out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    print("\n原始记录: %s" % os.path.relpath(args.out, _ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
