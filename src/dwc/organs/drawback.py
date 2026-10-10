# -*- coding: utf-8 -*-
"""drawback · 原子缺点检测器 + 表达式树（2607.12790 §2 · V2 门③「不认证正确」）。

定位声明 · **DWC-AUTO**（自我强化 · 判据 G1 定位门）
  ★ 服务门组的第 ③ 步: 对候选**只找缺点**（find drawbacks）—— clean
    只意味着"没找到已知缺点", **不是**"认证正确"（原文: "a clean
    verdict means no known drawback was found, not certified
    correctness"）。
  ★ 不抢位: 不判总分（judge）· 不判收益（非补偿门）; 本模块只跑检测
    器树 = **确定性为主**（原文配套设计理由: deterministic detectors
    fail differently from the graded model ⇒ 抵抗 shared-blind-spot
    共谋塌缩 — 裸 LLM judge 同源失效则互相串通）。
  ★ 表达式树（metric = 原子检测器的组合）: 叶 op · 析取(or) · 合一
    (and) · 否定(not) · k-of-v 无权重投票 · 加权投票对阈值 θ。

★★★ TRUTH_SOURCE（判据 G2）
  检测器判定由注入的确定性 op 计算 — 本模块不引入 LLM 判断
  （LLM judge 在 judge 器官, 且原文警告它共谋风险）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

#: op 三值输出（原文 §2.1: ⟨drawback, clean, abstain⟩ — 值枚举, 不添第四态）
VERDICTS: Tuple[str, ...] = ("drawback", "clean", "abstain")

#: 表达式树节点类型（式 1 六种形态 — 值枚举）
NODE_KINDS: Tuple[str, ...] = ("leaf", "or", "and", "not", "k_of_v",
                               "weighted")

#: 求值面三值（与 op 三值对齐; 组合语义由 _eval 定义）
DRAWBACK, CLEAN, ABSTAIN = "drawback", "clean", "abstain"


class DrawbackError(Exception):
    """检测器定义/求值的显式拒绝（未知 op / k 越界 / θ 越界 / 权重非正）。"""


@dataclass(frozen=True)
class Op:
    """一个原子缺点检测器（确定性 — callable (task, output, ctx) -> str）。

    ★ 返回必须是 VERDICTS 之一（拿 None/异常当 clean = 静默放行 — 禁）;
    ★ ctx 是共享上下文（原文 "shared context" 的一等参数）。
    """

    name: str
    fn: Callable[[Any, Any, Dict[str, Any]], str]

    def __post_init__(self) -> None:
        if not self.name:
            raise DrawbackError("Op.name 非空")
        if not callable(self.fn):
            raise DrawbackError("Op.fn 须 callable (task, y, ctx) -> verdict")

    def run(self, task: Any, y: Any, ctx: Dict[str, Any]) -> str:
        v = self.fn(task, y, ctx)
        if v not in VERDICTS:
            raise DrawbackError(
                "op %r 返回 %r — 三值枚举外（None/异常当 clean = 静默放行, 禁）"
                % (self.name, v))
        return v


@dataclass(frozen=True)
class Node:
    """表达式树节点（式 1 六形态 · 递归定义）。

    ★ leaf: op 名（由注册表解析）;
      or/and: children 按布尔组合（三值 — abstain 子节点被**排除**, 原文
        "Abstaining children are excluded …"）;
      not: 单 child（drawback↔clean 互换, abstain 透传）;
      k_of_v: k 个 drawback ⇒ 判 drawback（k ≥1, k ≤ n_children）;
      weighted: 权重对阈值 θ（Σ w_i·𝕜(drawback) ≥ θ ⇒ drawback;
        权重须非负, θ ∈ (0, Σw] — 越界即拒）。
    """

    kind: str
    op: Optional[str] = None                       # leaf 用
    children: Tuple["Node", ...] = ()              # 组合节点用
    k: Optional[int] = None                        # k_of_v 用
    weights: Optional[Tuple[float, ...]] = None    # weighted 用
    theta: Optional[float] = None                  # weighted 用

    def __post_init__(self) -> None:
        if self.kind not in NODE_KINDS:
            raise DrawbackError("Node.kind 未知: %r（%s）"
                                % (self.kind, "/".join(NODE_KINDS)))
        if self.kind == "leaf":
            if not self.op:
                raise DrawbackError("leaf 节点须 op 名")
        else:
            if not self.children:
                raise DrawbackError("%s 节点须有 children" % (self.kind,))
            if not isinstance(self.children, tuple):
                raise DrawbackError(
                    "children 须为 tuple（单 child 也要包成 1-tuple — "
                    "TypeError 的 len() 无型保护, 入口拦）")
        if self.kind == "not" and len(self.children) != 1:
            raise DrawbackError("not 只收 1 个 child")
        if self.kind == "k_of_v":
            if self.k is None or self.k < 1 or self.k > len(self.children):
                raise DrawbackError(
                    "k_of_v 的 k 须 ∈ [1, n_children=%d], 实 %r"
                    % (len(self.children), self.k))
        if self.kind == "weighted":
            ws = self.weights or ()
            if len(ws) != len(self.children):
                raise DrawbackError(
                    "weighted 权重数(%d) 与 children 数(%d) 不符"
                    % (len(ws), len(self.children)))
            if any(w < 0 for w in ws):
                raise DrawbackError("weighted 权重须非负（负权=反向否决, 原文无）")
            tw = sum(ws)
            if self.theta is None or not (0.0 < self.theta <= tw):
                raise DrawbackError(
                    "weighted 的 θ 须 ∈ (0, Σw=%.3f], 实 %r" % (tw, self.theta))


def _eval(n: Node, ops: Dict[str, Op], task: Any, y: Any,
          ctx: Dict[str, Any]) -> str:
    """表达式树求值（三值 — abstain 排除由组合规则处理）。"""
    if n.kind == "leaf":
        return ops[n.op].run(task, y, ctx)     # KeyError 显式 — 未注册 op

    sub = [_eval(c, ops, task, y, ctx) for c in n.children]
    non_abs = [s for s in sub if s != ABSTAIN]      # ★ abstain 子节点排除
    if n.kind == "not":
        s = sub[0]
        if s == ABSTAIN:
            return ABSTAIN                         # abstain 透传（不折 clean）
        return DRAWBACK if s == CLEAN else CLEAN
    if not non_abs:                                 # 全 abstain ⇒ abstain
        return ABSTAIN
    if n.kind == "or":
        return DRAWBACK if DRAWBACK in non_abs else CLEAN
    if n.kind == "and":
        # 合一: 有 drawback ⇒ drawback; 全 clean ⇒ clean
        return DRAWBACK if DRAWBACK in non_abs else CLEAN
    if n.kind == "k_of_v":
        # k 个（非 abstain 子节点里的）drawback ⇒ drawback
        nd = sum(1 for s in non_abs if s == DRAWBACK)
        return DRAWBACK if nd >= n.k else CLEAN
    if n.kind == "weighted":
        score = sum(w for w, s in zip(n.weights or (), sub)
                    if s == DRAWBACK)
        return DRAWBACK if score >= n.theta else CLEAN
    raise DrawbackError("未覆盖节点 kind: %r" % (n.kind,))


class Grader:
    """门③ 评分器（op 注册表 + 树求值 + verdict 汇总）。

    ★ clean ⇒ "没找到已知缺点"（**不是**认证正确 — 原文 §2.1 明确）;
    ★ abstain 汇总单列（原文: abstain 不是 clean, 也不该计 drawback）;
    ★ 全 abstain ⇒ verdict=abstain 且 **不许过门**（没查≠干净）。
    """

    def __init__(self) -> None:
        self.ops: Dict[str, Op] = {}
        self.tree: Optional[Node] = None

    def register_op(self, op: Op) -> None:
        if op.name in self.ops:
            raise DrawbackError("op 重名 %r（不静默覆盖）" % (op.name,))
        self.ops[op.name] = op

    def set_tree(self, root: Node) -> None:
        """设检测树（leaf 引用的 op 必须已注册 — 未注册即拒, 防树挂空 op）。"""
        if root.kind == "leaf" and root.op not in self.ops:
            raise DrawbackError("树引用未注册 op: %r" % (root.op,))
        self.tree = root

    def grade(self, task: Any, y: Any,
              ctx: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if self.tree is None:
            return {"verdict": "no_tree", "ok": False,
                    "note": "未设检测树 ⇒ 无法判（显式缺席, 不默认 clean）"}
        v = _eval(self.tree, self.ops, task, y, ctx or {})
        ok = (v == CLEAN)                    # ★ 只有 clean 过门; abstain 不过
        return {"verdict": v, "ok": ok,
                "note": ("clean = 没找到已知缺点（**非**认证正确 — §2.1）"
                         if v == CLEAN else
                         ("找到缺点 ⇒ 不过门③" if v == DRAWBACK else
                          "全 abstain ⇒ 没查≠干净 ⇒ 不过门"))}


DRAWBACK_MECHANICS: Dict[str, str] = {
    "verdicts": "op 三值: drawback/clean/abstain（§2.1 — 不添第四态）",
    "tree": "式 1: leaf/or/and/not/k_of_v/weighted（abstain 子节点被排除）",
    "not_correctness": "clean 只=没找到已知缺点, 不是认证正确（bootstrap 就靠这个不对称）",
    "why_deterministic": "mostly deterministic detectors ⇒ 与被评模型 fail differently ⇒ 抗共谋塌缩（裸 LLM judge 同源失效会串通）",
    "abstain_never_pass": "全 abstain ⇒ 不过门（没查≠干净 — X2 同族）",
}
