# -*- coding: utf-8 -*-
"""R452 · 参考实现登记表 —— 新任务期望值的**唯一合法来源**。

★★★ 定位（G1）: **DWC-AUTO** —— 自我强化：给系统造新题，题必须有真值。

为什么必须存在
--------------
anchor 里只有 `(fn, args, expected)`，**没有原始实现**。
想扰动参数就得重算 expected，而"重算"的凭据不能是"我觉得对"。

所以本模块的纪律只有一条：
**每条实现必须先复现现有全部 anchor 检查，才有资格被用于生成新题。**
`verify()` 就是这道门；`tests/test_r452_refimpl.py` 把门锁死。

覆盖范围
--------
只登记 anchors 里真实出现过的函数（dev 6 + fresh 5）。
没登记的函数 ⇒ `compute()` 返回 None，**绝不猜**。
"""
from __future__ import annotations

import ast
import math
from typing import Any, Callable, Dict, List, Optional, Tuple


def _sum_first_n(n: int) -> int:
    """1+2+…+n。"""
    return int(n) * (int(n) + 1) // 2


def _fibonacci(n: int) -> int:
    """fib(0)=0, fib(1)=1。"""
    n = int(n)
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a


def _average(xs: List[Any]) -> float:
    """空列表返回 0.0（anchor 口径：average([]) == 0.0）。"""
    xs = list(xs)
    return 0.0 if not xs else sum(xs) / len(xs)


def _factorial(n: int) -> int:
    return math.factorial(int(n))


def _is_palindrome(s: str) -> bool:
    """大小写不敏感（anchor：'Racecar' → True）。"""
    t = str(s).lower()
    return t == t[::-1]


def _reverse_string(s: str) -> str:
    return str(s)[::-1]


def _fresh_range_sum(pair: List[int]) -> int:
    """a..b 闭区间求和。"""
    a, b = pair
    return sum(range(int(a), int(b) + 1))


def _fresh_second_max(xs: List[int]) -> int:
    """去重后第二大（anchor：second_max([5,5,4]) == 4）。"""
    uniq = sorted(set(xs))
    return uniq[-2]


def _fresh_sq_half(xs: List[int]) -> int:
    """平方和的一半（整除）。"""
    return sum(int(x) * int(x) for x in xs) // 2


def _fresh_vowel_count(s: str) -> int:
    return sum(1 for ch in str(s) if ch in "aeiouAEIOU")


#: fn → 实现。**只收 anchors 里出现过的**；新增必须先过 verify()。
REFS: Dict[str, Callable[..., Any]] = {
    "sum_first_n": _sum_first_n,
    "fibonacci": _fibonacci,
    "fresh_fib": _fibonacci,      # anchor 口径与 fibonacci 相同
    "average": _average,
    "factorial": _factorial,
    "is_palindrome": _is_palindrome,
    "reverse_string": _reverse_string,
    "fresh_range_sum": _fresh_range_sum,
    "fresh_second_max": _fresh_second_max,
    "fresh_sq_half": _fresh_sq_half,
    "fresh_vowel_count": _fresh_vowel_count,
}

_BAD = object()


def _parse(literal: Any) -> Any:
    try:
        return ast.literal_eval(str(literal))
    except (ValueError, SyntaxError, TypeError):
        return _BAD


def compute(fn: str, args_literal: Any) -> Optional[str]:
    """按 anchor 口径算期望值，返回 `repr()` 字符串；算不出 ⇒ None。

    ★ None 一律表示"不知道"，调用方**不许**把它当 0 或当通过。
    """
    f = REFS.get(str(fn))
    if f is None:
        return None
    v = _parse(args_literal)
    if v is _BAD:
        return None
    try:
        out = f(*v) if isinstance(v, tuple) else f(v)
    except Exception:                 # noqa: BLE001 — 算不出就是不知道
        return None
    return repr(out)


def verify(checks: List[Dict[str, Any]]) -> Tuple[List[str], List[str]]:
    """逐 fn 校验参考实现能否复现给定检查。

    返回 `(ok_fns, bad_fns)` —— 坏的必须被点名，不许整体放行。
    一个 fn 只要有一条检查对不上，就整条进 bad（不按检查放行）。
    """
    ok: List[str] = []
    bad: List[str] = []
    seen: Dict[str, bool] = {}
    for c in checks or []:
        if not isinstance(c, dict):
            continue
        fn = str(c.get("fn") or "")
        if not fn or fn not in REFS:
            continue
        got = compute(fn, c.get("args"))
        good = (got is not None and got == str(c.get("expected")))
        seen[fn] = bool(seen.get(fn, True)) and good
    for fn, good in seen.items():
        (ok if good else bad).append(fn)
    return sorted(ok), sorted(bad)
