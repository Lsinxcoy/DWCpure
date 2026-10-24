# -*- coding: utf-8 -*-
"""R453 · 任务供给 —— 让系统持续遇到"刚好不会"的题。

★★★ 定位（G1）: **DWC-AUTO** —— 自我强化：自己造题，自己判分，自己学。

为什么必须有
------------
实测：池子 16 题，最近 30 个 term `pass_rate` 全 1.0，`evo_feed.n_sigs` 全 0。
⇒ 进化不是"学得不够"，是**没有东西可学**。
RSI 的吞吐上限不是模型能力，是**新问题的供给速度**。

三级阶梯
--------
| 级 | 内容 | 期望值来源 | LLM |
|---|---|---|---|
| L1 | 原题参数扰动 | `refimpl`（已复现全部 anchor） | 不用 |
| L2 | `fresh.json` 现成题 | 文件自带 | 不用 |
| L3 | 新函数族 | 两份独立实现**逐输入一致** | 用（受预算） |

纪律
----
- 算不出期望值 ⇒ 不生成（`refimpl.compute` 返回 None 即放弃）
- L1 必须真扰动（新 args ≠ 原 args），否则只是把同一题抄一遍
- 同 seed ⇒ 同题（可复现、可审计）
- L3 不一致 ⇒ 不收（fail-closed；判分器的真值不能是"可能对"）
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import random
import re
import sys
import time
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from dwc.organs import refimpl as _REF

QUEUE_REL = os.path.join("var", "task_queue.jsonl")

#: ★ G4 生灭门 · 池子上限（队列只保留这么多道待跑题）
MAX_POOL = 40
#: 淘汰判据①：连续 ≥2 次都做对 ⇒ 这题已经不"刚好不会"了，淘汰
SOLVED_PASS = 1.0
SOLVED_MIN_ATTEMPTS = 2
#: 淘汰判据②：14 天没被做对也没被做错 ⇒ 过期（防止队列腐烂）
TTL_S = 14 * 86400

SATURATION_WINDOW = 30
SATURATION_PASS = 0.95
RELAX_PASS = 0.60

#: L1 参数采样器：fn → 生成**单个参数**的函数
SAMPLERS: Dict[str, Callable[[random.Random], Any]] = {
    "sum_first_n": lambda r: r.choice([r.randint(6, 30), r.randint(500, 3000)]),
    "fibonacci": lambda r: r.randint(2, 18),
    "fresh_fib": lambda r: r.randint(2, 18),
    "factorial": lambda r: r.randint(0, 8),
    "average": lambda r: ([] if r.random() < 0.15 else
                          [r.choice([r.randint(-20, 20), round(r.uniform(-9, 9), 1)])
                           for _ in range(r.randint(1, 6))]),
    "is_palindrome": lambda r: r.choice(
        ["Level", "noon", "AbBa", "racecar", "hello", "world", "abc", "Noon"]),
    "reverse_string": lambda r: "".join(
        r.choice("abcdefghijklmnopqrstuvwxyz") for _ in range(r.randint(1, 9))),
    "fresh_range_sum": lambda r: (lambda a, b: [a, b])(
        r.randint(-5, 10), r.randint(11, 40)),
    "fresh_second_max": lambda r: (lambda xs: xs + [r.randint(0, 9)])(
        r.sample(range(0, 30), r.randint(2, 5))),
    "fresh_sq_half": lambda r: [r.randint(1, 9) for _ in range(r.randint(1, 5))],
    "fresh_vowel_count": lambda r: "".join(
        r.choice("aeiouAEIOUbcdfghjklmnpqrstvwxyz ") for _ in range(r.randint(1, 14))),
}


def _stable_seed(text: str, seed: int) -> int:
    """跨进程稳定的种子（`hash()` 每进程加盐，不能用）。"""
    h = hashlib.sha1(("%s|%d" % (text, seed)).encode("utf-8")).hexdigest()
    return int(h[:8], 16)


# ── L1 ──────────────────────────────────────────────────────────

def perturb(task_id: str, anchor: Dict[str, Any], *, seed: int = 0,
            n: int = 2) -> List[Dict[str, Any]]:
    """对一道已有题做参数扰动，返回最多 n 道新题。

    ★ 只用 refimpl 能算的 fn；算不出 ⇒ 该检查丢弃；一条都剩不下 ⇒ 不出题。
    """
    checks = [c for c in (anchor.get("checks") or []) if isinstance(c, dict)]
    fns = [str(c.get("fn") or "") for c in checks]
    if not fns or any(f not in _REF.REFS or f not in SAMPLERS for f in fns):
        return []
    rng = random.Random(_stable_seed(task_id, seed))
    old_args = {str(c.get("args")) for c in checks}
    out: List[Dict[str, Any]] = []
    for i in range(max(0, int(n))):
        new_checks: List[Dict[str, Any]] = []
        for c in checks:
            fn = str(c["fn"])
            args = SAMPLERS[fn](rng)
            lit = repr(args)
            expected = _REF.compute(fn, lit)
            if expected is None:
                continue
            new_checks.append({"fn": fn, "args": lit, "expected": expected})
        if not new_checks:
            continue
        if {c["args"] for c in new_checks} <= old_args:
            continue                      # ★ 没扰动 ⇒ 不是新题
        out.append({
            "task_id": "%s__p%d_s%d" % (task_id, i + 1, seed),
            "anchor": {
                "category": anchor.get("category", "code_repair"),
                "verifier_rung": anchor.get("verifier_rung", 1),
                "verifier_kind": anchor.get("verifier_kind", "behavior"),
                "prompt": anchor.get("prompt", ""),
                "expected_behavior": " and ".join(
                    "%s(%s)==%s" % (c["fn"], c["args"], c["expected"])
                    for c in new_checks),
                "checks": new_checks,
            },
            "split": "supply",
            "level": 1,
            "source": task_id,
            "seed": seed,
            "created_ts": time.time(),
        })
    return out


# ── L2 ──────────────────────────────────────────────────────────

def from_fresh(path: str) -> List[Dict[str, Any]]:
    """把 fresh.json 的现成题搬进供给队列（不改判分口径）。"""
    try:
        with io.open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return []
    out: List[Dict[str, Any]] = []
    for tid, a in data.items():
        if tid.startswith("_") or not isinstance(a, dict):
            continue
        if not (a.get("checks") or []):
            continue
        out.append({
            "task_id": tid,
            "anchor": dict(a),
            "split": "supply",
            "level": 2,
            "source": "fresh.json",
            "seed": 0,
            "created_ts": time.time(),
        })
    return out


# ── L3 ──────────────────────────────────────────────────────────

_L3_PROMPT = """你是出题人。请设计一个**单参数**的纯 Python 函数任务。
要求：
1. 只接受一个参数，类型必须是 int、list[int] 或 str 之一
2. 不允许 import、不允许读写文件、不允许用 __ 开头的属性
2b. **不允许使用 while 循环**（沙箱会拒收；只能用 for）
2c. 实现保持在 30 行以内，逻辑要简单
3. 函数名用 snake_case，且不与常见内置函数重名
4. 题目描述必须让实现唯一确定（不能有歧义）
输出**严格 JSON**（不要解释）：
{"fn": "函数名", "prompt": "中文题面", "impl": "def 函数名(x):\n    ..."}
"""

#: 第二份实现：**只给题面**，不给第一份实现 —— 否则就是抄，不是独立实现
#: ★ 用拼接而不是 %/.format：题面里可能带 % 或 {}，格式化会炸（踩过）
_L3_IMPL_HEAD = """根据下面的题面写 Python 实现。
要求：不允许 import、不允许读写文件、不允许用 __ 开头的属性、
**不允许 while 循环**（只能用 for）。
只输出代码（不要解释、不要 markdown 围栏）。

"""

_L3_INPUTS: Sequence[Any] = (3, 5, 8, -7, [1, 2, 3], [4, 1, 9], [2, 2, 5],
                             [5], [], "abc", "hello world", "Level", "a", "Aa")


def _extract_json(text: str) -> Optional[Dict[str, Any]]:
    s = str(text or "")
    i, j = s.find("{"), s.rfind("}")
    if i < 0 or j <= i:
        return None
    try:
        d = json.loads(s[i:j + 1])
    except ValueError:
        return None
    return d if isinstance(d, dict) else None


def _extract_code(text: str) -> str:
    """从模型输出里取代码：优先 JSON 的 impl，其次去掉 markdown 围栏。"""
    d = _extract_json(text)
    if d and d.get("impl"):
        return str(d["impl"])
    s = str(text or "")
    s = re.sub(r"^\s*```[a-zA-Z]*\s*", "", s.strip())
    s = re.sub(r"\s*```\s*$", "", s)
    return s


def _run_one(code: str, fn: str, x: Any) -> Tuple[bool, Any]:
    """跑**一个**输入。单项失败不影响别的输入（旧版一批全挂就全废）。

    ★ 沙箱会**主动 raise**（禁 while / 禁 import / 超时等）——
      这里必须接住：那是"这段 LLM 代码不可用"，不是"系统坏了"。
      结果以 `(False, None)` 如实返回，调用方按"没一致"处理（fail-closed）。
    """
    try:
        from dwc.llm.sandbox import run_code_observed
    except Exception:                 # noqa: BLE001 — 没有沙箱就不出题
        return (False, None)
    try:
        obs = run_code_observed(code, {fn: [[x, None]]}, timeout=5.0)
    except Exception:                 # noqa: BLE001 — 沙箱拒收 ⇒ 该输入不可用
        return (False, None)
    if not obs or fn not in obs or not obs[fn]:
        return (False, None)
    val = obs[fn][0][1]
    if val is None:
        # ★ 返回 None 不是"答案"：拿它当期望值会造出"正确答案是 None"的垃圾题
        return (False, None)
    return (True, val)


def _sandbox_outputs(code: str, fn: str,
                     inputs: Sequence[Any]) -> List[Tuple[bool, Any]]:
    return [_run_one(code, fn, x) for x in inputs]


def generate_family(llm: Callable[[str], str], *, seed: int = 0,
                    min_agree: int = 3,
                    runner: Optional[Callable[[str, str, Any],
                                              Tuple[bool, Any]]] = None,
                    diag: Optional[Dict[str, Any]] = None
                    ) -> Optional[Dict[str, Any]]:
    """L3：出题 → 题面给第二个人写 → 逐输入一致才收。

    ★ 为什么第二份只给题面：给了第一份实现就是抄，两份必然"一致"，
      那种一致证明不了题面可判定。独立实现 + 输入一致才算数。
    ★ 不一致 / 跑挂 / 一致样本 < min_agree ⇒ None（fail-closed）。
    """
    run = runner or _run_one

    def _fail(why: str) -> None:
        if diag is not None:
            diag["why"] = why

    try:
        spec_txt = llm(_L3_PROMPT)
    except Exception as exc:          # noqa: BLE001 — 出题失败不掀轮
        _fail("llm_error_spec:%r" % (exc,))
        return None
    spec = _extract_json(spec_txt)
    if not spec or not spec.get("fn") or not spec.get("impl"):
        _fail("bad_spec")
        return None
    fn = str(spec["fn"])
    try:
        _ask2 = (_L3_IMPL_HEAD + "函数名：" + fn
                 + "\n题面：" + str(spec.get("prompt") or ""))
        impl_b = _extract_code(llm(_ask2))
    except Exception as exc:          # noqa: BLE001
        _fail("llm_error_impl:%r" % (exc,))
        return None
    if "def " not in impl_b:
        _fail("no_def_in_second_impl")
        return None
    agree: List[Tuple[Any, Any]] = []
    for x in _L3_INPUTS:
        oka, va = run(str(spec["impl"]), fn, x)
        okb, vb = run(impl_b, fn, x)
        if oka and okb and va == vb:
            agree.append((x, va))
    if len(agree) < max(1, int(min_agree)):
        _fail("agree=%d<%d" % (len(agree), max(1, int(min_agree))))
        return None
    checks = [{"fn": fn, "args": repr(x), "expected": repr(v)} for x, v in agree]
    tid = "supply_%s_%s" % (fn, hashlib.sha1(
        str(spec["impl"]).encode("utf-8")).hexdigest()[:8])
    return {
        "task_id": tid,
        "anchor": {
            "category": "code_repair",
            "verifier_rung": 1,
            "verifier_kind": "behavior",
            "prompt": str(spec.get("prompt") or ""),
            "expected_behavior": " and ".join(
                "%s(%s)==%s" % (c["fn"], c["args"], c["expected"])
                for c in checks),
            "checks": checks,
        },
        "split": "supply",
        "level": 3,
        "source": "llm_two_impl",
        "verified_by": "two_impl_agree",
        "seed": seed,
        "created_ts": time.time(),
    }


# ── 队列 ────────────────────────────────────────────────────────

def load_queue(path: Optional[str] = None) -> List[Dict[str, Any]]:
    p = path or QUEUE_REL
    out: List[Dict[str, Any]] = []
    try:
        with io.open(p, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if isinstance(r, dict) and r.get("task_id"):
                    out.append(r)
    except OSError:
        return []
    return out


def evict(path: Optional[str] = None,
          scores: Optional[Dict[str, Sequence[Optional[float]]]] = None,
          now: Optional[float] = None) -> Dict[str, Any]:
    """★ G4 淘汰判据：做对的淘汰、过期的淘汰，其余留下。

    - `scores`: `{task_id: [pass_rate, ...]}`；连续 ≥2 次全 1.0 ⇒ solved
    - 没有 scores 时只按 TTL 淘汰（不猜"做对没做对"）
    """
    p = path or QUEUE_REL
    rows = load_queue(p)
    if not rows:
        return {"n_before": 0, "n_kept": 0, "evicted": []}
    t_now = time.time() if now is None else float(now)
    kept: List[Dict[str, Any]] = []
    gone: List[Tuple[str, str]] = []
    for r in rows:
        tid = str(r.get("task_id") or "")
        prs = [float(x) for x in (scores or {}).get(tid, []) if x is not None]
        if len(prs) >= SOLVED_MIN_ATTEMPTS and min(prs) >= SOLVED_PASS:
            gone.append((tid, "solved"))
            continue
        ts = float(r.get("created_ts") or 0.0)
        if ts and (t_now - ts) > TTL_S:
            gone.append((tid, "expired"))
            continue
        kept.append(r)
    if gone:
        try:
            with io.open(p, "w", encoding="utf-8", newline="\n") as f:
                for r in kept:
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")
        except OSError as e:          # noqa: BLE001 — 淘汰失败不掀调用方
            sys.stderr.write("队列淘汰写盘失败: %r\n" % (e,))
    return {"n_before": len(rows), "n_kept": len(kept), "evicted": gone}


def admit(tasks: List[Dict[str, Any]], path: Optional[str] = None,
          scores: Optional[Dict[str, Sequence[Optional[float]]]] = None,
          now: Optional[float] = None) -> int:
    """追加进队列；同 task_id 已存在 ⇒ 跳过。返回**新增**条数。

    ★ G4 超限行为：先按判据淘汰，再按 `MAX_POOL` 封顶；
      收不下的**直接拒收**并写 stderr —— 不许悄悄扩容。
    """
    p = path or QUEUE_REL
    evict(p, scores=scores, now=now)
    have = {t.get("task_id") for t in load_queue(p)}
    n = 0
    try:
        parent = os.path.dirname(p)
        if parent and not os.path.isdir(parent):
            os.makedirs(parent, exist_ok=True)
        with io.open(p, "a", encoding="utf-8", newline="\n") as f:
            for t in tasks or []:
                tid = str((t or {}).get("task_id") or "")
                if not tid or tid in have:
                    continue
                if len(have) >= MAX_POOL:
                    sys.stderr.write(
                        "队列已满(%d) ⇒ 拒收 %s\n" % (MAX_POOL, tid))
                    continue
                f.write(json.dumps(t, ensure_ascii=False) + "\n")
                have.add(tid)
                n += 1
    except OSError:
        return n
    return n


# ── 饱和与升级 ──────────────────────────────────────────────────

def saturation(terms: Sequence[Dict[str, Any]],
               window: int = SATURATION_WINDOW) -> Dict[str, Any]:
    """最近 window 个 term 的通过率。**没有数据 ⇒ 不饱和**（不许凭空升级）。"""
    vals = []
    for t in list(terms)[-max(1, int(window)):]:
        pr = (t or {}).get("pass_rate")
        if pr is None:
            continue
        try:
            vals.append(float(pr))
        except (TypeError, ValueError):
            continue
    if not vals:
        return {"n": 0, "mean": None, "saturated": False}
    mean = sum(vals) / len(vals)
    return {"n": len(vals), "mean": round(mean, 4),
            "saturated": mean >= SATURATION_PASS}


def next_level(current: int, sat: Dict[str, Any]) -> int:
    """0=池内原题, 1=L1, 2=L2, 3=L3。饱和升一级，太难降一级。"""
    cur = max(0, min(3, int(current)))
    if sat.get("saturated") and cur < 3:
        return cur + 1
    if sat.get("mean") is not None and float(sat["mean"]) <= RELAX_PASS and cur > 0:
        return cur - 1
    return cur
