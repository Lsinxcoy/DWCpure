# -*- coding: utf-8 -*-
"""R443 · P1-c · 逐例对比（把"一个分数"拆成"哪几例错了"）。

★★★ 定位（G1）: **DWC-AUTO** —— 自我强化的判据层：分数之外要看得见"错在哪一例"。

为什么要有这个模块
------------------
trial 只回 `in_score=1.0/0.0`。
一个候选"修好 3 例、弄坏 3 例"和"什么都没改"在分数上一模一样，
但前者是**回归**，后者是**没动** —— 分数看不出这个差别。

★★★ 诚实边界（必须写在代码里）
  Harness² 的对比是"参考执行 vs 候选执行"，需要**基线的逐例结果**。
  DWC 的 anchor 只有 `checks`（fn/args/expected），**不含原始实现**
  ⇒ 跑不出基线逐例结果 ⇒ `regressed` 只能为 None 并写明原因。
  本模块只做能诚实做到的那一半：候选自己的逐例分解。

纪律
----
1. **形态不一致 ⇒ None**（缺例/多例/坏形状）：不可比就不许猜。
2. **数值等价**：1 与 1.0 是同一个值（模型常返回 1.0）。
3. **不许编 regressed**：没有基线就说没有。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional


def _num(v: Any) -> Any:
    """把 "3" / "3.0" 这类字符串转成数值；转不了就原样返回。"""
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return v
    if isinstance(v, str):
        s = v.strip()
        try:
            return int(s)
        except ValueError:
            try:
                return float(s)
            except ValueError:
                return v
    return v


def _norm(v: Any) -> str:
    """比较用的规范形：能转成数值就按数值比，否则按 repr。"""
    try:
        return "num:%r" % (float(v),)
    except (TypeError, ValueError):
        return "repr:%r" % (v,)


def expected_from_checks(checks: Any) -> Dict[str, List[Any]]:
    """从 anchor 的 `checks` 抽期望值：`{fn: [expected, ...]}`。

    坏条目跳过（缺 fn / 缺 expected），不掀轮。
    """
    out: Dict[str, List[Any]] = {}
    if not isinstance(checks, list):
        return out
    for c in checks:
        if not isinstance(c, dict):
            continue
        fn = str(c.get("fn") or "").strip()
        exp = c.get("expected")
        if not fn or exp is None:
            continue
        out.setdefault(fn, []).append(_num(exp))
    return out


def from_observed(skel: Dict[str, List[List[Any]]],
                  observed: Optional[Dict[str, List[List[Any]]]],
                  expected: Optional[Dict[str, List[Any]]]
                  ) -> Optional[Dict[str, Any]]:
    """候选 vs 期望的逐例分解。不可比 ⇒ None（fail-closed）。"""
    if not isinstance(skel, dict) or not isinstance(observed, dict):
        return None
    if not isinstance(expected, dict) or not expected:
        return None               # ★ 没有期望值 ⇒ 不可判，不许全判失败
    failed: List[Dict[str, Any]] = []
    n = 0
    for fn, cases in skel.items():
        got = observed.get(fn)
        exp = expected.get(fn)
        if not isinstance(got, list) or len(got) != len(cases):
            return None           # ★ 缺例/多例 ⇒ 不可比
        if not isinstance(exp, list) or len(exp) != len(cases):
            return None           # ★ 期望值数量对不上 ⇒ 不可比
        for i, (case, res) in enumerate(zip(cases, got)):
            if not isinstance(case, (list, tuple)) or len(case) < 1:
                return None
            args = case[0]
            actual = (res[1] if isinstance(res, (list, tuple)) and len(res) > 1
                      else None)
            n += 1
            if _norm(actual) != _norm(exp[i]):
                failed.append({"fn": fn, "index": i, "args": args,
                               "expected": exp[i], "actual": actual})
    return {
        "n_cases": n,
        "n_failed": len(failed),
        "n_passed": n - len(failed),
        "failed": failed,
        # ★ 诚实缺席：anchor 不含原始实现 ⇒ 没有基线逐例结果
        "regressed": None,
        "regressed_reason": "无基线逐例结果（anchor 不含原始实现）",
    }
