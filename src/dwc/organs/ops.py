# -*- coding: utf-8 -*-
"""ops · drawback 门③ 的原子检测器池 + 固定 root（R166 — 补 op 池缺口）。

定位声明 · **DWC-AUTO**（自我强化 · 判据 G1 定位门）
  ★ R149 落了树引擎（六形态/三值/clean≠认证正确）; R152 链上只挂了
    一个**投影 op**（pass-rate-weak — 它是把入参折成三值的适配器, 不是
    真检测器）⇒ 门③"框架 live 判定虚": 树能算但叶子上没真 op。
  ★ 本模块补**论文 §2.3 的 op 池**（三类成本层）:
      · static ops（解析产物 — 不跑代码, 看结构）
      · execution ops（真跑 — 由 caller 的 ctx 带执行结果进来, 本模块
        不持沙箱: 判据与执行分离, 沙箱在 actor/executor 已有）
      · judge ops（问 LLM 窄问题 — **不在本模块**: LLM 调用是 e2e
        step9/candidates 的面; 本模块只收 ctx 里的判决结论）
  ★★★ 每族固定的、不进化的 root（原文: "validates basic structure and
    caches the parsed artifact the other ops read"）⇒ root_parse_ok:
      它在树上**永为 conjoined root 的第一层**, 且**不可被进化改动**。

★★★ TRUTH_SOURCE（判据 G2）
  · op 判据 ← 已 live 的模块输出（judge Verdict / leakage 门 / bridge
    的 UNKNOWN_COMPONENT / TermFacts.candidate_diff）— 本模块**不重算**
    任何判据, 只把既有结论折成三值（投影纪律同 R152 口径桥）。
  · C(e) 规模成本: Node 数（无权重计点, 与论文 λ·C(e) 的"表达式规模"
    同口径 — 节点计数, 不加权）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from dwc.organs.drawback import (
    VERDICTS, DrawbackError, Grader, Node, Op)

#: 三值枚举（与 R149 同源 — 不复制字面量, import 防漂移）
DRAWBACK = "drawback"
CLEAN = "clean"
ABSTAIN = "abstain"


class OpsPoolError(Exception):
    """op 池的显式拒绝（op 三值外/root 缺失/ctx 键缺）。"""


# ══════════════════════════════════════════════════════════
# op 池（R166 · 五个真 op + 一个固定 root）
#   每个 op 的 fn(task, y, ctx) 只读 ctx 里**已算好的**结论
# ══════════════════════════════════════════════════════════

def _mk(name: str, fn) -> Op:
    return Op(name=name, fn=fn)


def op_root_parse_ok():
    """★★ 固定 root（不进化的第一层 — 原文 §2.3）。

    判据: ctx["parsed_ok"]（结构是否解析成功 — 由 caller 的 bridge 给）。
    · True ⇒ clean（继续往下看）
    · False ⇒ drawback（结构坏, 后面 op 无从谈起）
    · 缺键 ⇒ abstain（没解析过 ≠ 解析失败 — 缺席≠0 纪律, 不猜）
    """
    def fn(task, y, ctx):
        if "parsed_ok" not in ctx:
            return ABSTAIN                        # 没解析过 ⇒ 不知道
        return CLEAN if ctx["parsed_ok"] else DRAWBACK
    return _mk("root_parse_ok", fn)


def op_judge_verdict():
    """judge op 投影（判据源 = judge Verdict — 真跑过的那次）。"""
    def fn(task, y, ctx):
        v = ctx.get("judge_success")
        if v is None:
            return ABSTAIN                        # 没判过 ⇒ 不知道
        return CLEAN if v else DRAWBACK
    return _mk("judge_verdict", fn)


def op_nonempty_diff():
    """static op: 候选 diff 非空（没干预 = 空过 — 结构类缺点）。"""
    def fn(task, y, ctx):
        d = ctx.get("candidate_diff", None)
        if d is None:
            return ABSTAIN
        return CLEAN if str(d).strip() else DRAWBACK
    return _mk("nonempty_diff", fn)


def op_component_known():
    """static op: 组件在词表内（越界 = 归属不明的干预）。

    ★★ R166 实测抓的归因错: 空词表 () ⇒ "没词表可校" ≠ "校出越界"
      — 首版把 `comp in set(())` = False 判 drawback, 于是 run_term
      无候选流（vocabulary=()）时门③全被误 veto。修: 空词表 ⇒ abstain
      （没词表=不校, 与 R153『vocabulary 外置不从 patch 猜』同族）。
    """
    def fn(task, y, ctx):
        comp = ctx.get("component", None)
        vocab = ctx.get("vocabulary", None)
        if comp is None or vocab is None or len(vocab) == 0:
            return ABSTAIN                       # ★ 没词表可校（≠越界）
        return CLEAN if comp in set(vocab) else DRAWBACK
    return _mk("component_known", fn)


def op_pass_rate_weak():
    """★★ R166 收编: gates.py 链上原匿名投影 op 的**具名化**。

    ★ 出身: R152 链上只有它一个 op（`pass-rate-weak` 匿名 lambda）⇒
      门③"框架 live 判定虚"的实证。R166 把它收进池当**第六个 op**（出身
      显式: 它是 pass_rate 的三值投影, 不是真检测器 — 名字里带 weak 是
      提醒, 与论文 op 的定义“检测一个失效类”同类但口径是聚合投影）。
    ★ 口枸不变（保 e2e 绿的兼容面）: pass_rate < 1 ⇒ drawback; ==1 ⇒ clean;
      缺 ⇒ abstain。
    """
    def fn(task, y, ctx):
        pr = ctx.get("pass_rate", None)
        if pr is None:
            return ABSTAIN
        return CLEAN if float(pr) >= 1.0 else DRAWBACK
    return _mk("pass_rate_weak", fn)


def op_golden_leak():
    """static op: 无 golden 泄漏（判据源 = leakage 门 R147 的 screen）。"""
    def fn(task, y, ctx):
        leaked = ctx.get("leakage_hits", None)
        if leaked is None:
            return ABSTAIN
        return DRAWBACK if leaked else CLEAN
    return _mk("golden_leak", fn)


#: 池的出厂清单（root 单独装 — 它永远在 conjunction 首位）
DEFAULT_POOL: Tuple[Op, ...] = (
    op_root_parse_ok(), op_judge_verdict(), op_nonempty_diff(),
    op_component_known(), op_golden_leak(), op_pass_rate_weak(),
)


@dataclass
class PoolReport:
    """一次池评估的报告（逐 op 三值 + 汇总 — 全留痕, 不静默）。"""

    per_op: Dict[str, str] = field(default_factory=dict)
    tree_verdict: Optional[str] = None
    root_verdict: Optional[str] = None
    n_nodes: int = 0
    notes: List[str] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return {"per_op": self.per_op, "tree_verdict": self.tree_verdict,
                "root_verdict": self.root_verdict, "n_nodes": self.n_nodes,
                "notes": self.notes}


def build_grader(extra_ops: Optional[Tuple[Op, ...]] = None,
                 *, root_first: bool = True) -> Tuple[Grader, Node]:
    """★ 装一个带 root 的 Grader（出厂配置 — 链上直接可用）。

    ★ 树 = 固定 root ⋀ 全池（论文: "the final verdict being the fixed
      root conjoined with the evolved expression" — R166 的 evolved 部分
      先取全池 conjunction, 进化的重组留 Metric Loop 的 backlog）。
    """
    g = Grader()
    for op in DEFAULT_POOL + tuple(extra_ops or ()):
        g.register_op(op)
    names = [op.name for op in DEFAULT_POOL] + [o.name for o in
                                               (extra_ops or ())]
    if root_first:
        # ★ root 恒在 conjunction 首位（不进化的结构保证 — 不是约定, 是构造）
        leaves = [Node(kind="leaf", op="root_parse_ok")] + [
            Node(kind="leaf", op=n) for n in names if n != "root_parse_ok"]
    else:
        leaves = [Node(kind="leaf", op=n) for n in names]
    tree: Node = leaves[0]
    for leaf in leaves[1:]:
        tree = Node(kind="and", children=(tree, leaf))
    g.set_tree(tree)
    return (g, tree)


def evaluate_pool(g: Grader, ctx: Dict[str, Any],
                  task: Any = None, y: Any = None) -> PoolReport:
    """★ 跑整池（逐 op 单跑 + 树汇总 — 两路都记, 可对账）。"""
    rep = PoolReport()
    for name in g.ops:
        rep.per_op[name] = g.ops[name].run(task, y, ctx)
    if g.tree is None:
        rep.notes.append("树未设 ⇒ 只出逐 op 报告（不凑合一个树）")
        return rep
    rep.tree_verdict = g.grade(task, y, ctx).get("verdict")  # R149 汇总三值
    rep.root_verdict = rep.per_op.get("root_parse_ok")
    rep.n_nodes = _count_nodes(g.tree)
    return rep


def _count_nodes(n: Node) -> int:
    """节点计数（C(e) 规模 — 与论文 λ·C(e) 同口径, 无权重计点）。"""
    if n.kind == "leaf":
        return 1
    return 1 + sum(_count_nodes(c) for c in n.children)


def ctx_from_facts(facts: Any) -> Dict[str, Any]:
    """★ TermFacts ⇒ op ctx（口径桥 — 投影不从 facts 重算, 只搬字段）。"""
    ctx: Dict[str, Any] = {}
    pr = getattr(facts, "pass_rate", None)
    ctx["judge_success"] = (None if pr is None
                            else bool(pr >= 1.0))
    # ★ pass_rate 原值同投（pass_rate_weak op 的口粮 — 别只给 bool 化
    #   版本:  op 的判据是"<1 ⇒ drawback", 要的是原值）
    ctx["pass_rate"] = pr
    ctx["candidate_diff"] = getattr(facts, "candidate_diff", None)
    ctx["vocabulary"] = getattr(facts, "vocabulary", None)
    # ★ TermFacts 无顶层 component（它在 edits/candidate 面 — R153 bridge
    #   投影的是 edit 列表）⇒ 从首 edit 取; 无 edits ⇒ None ⇒ op abstain
    _edits = getattr(facts, "edits", None) or []
    ctx["component"] = (getattr(_edits[0], "component", None)
                        if _edits else None)
    # ★ parsed_ok: 结构面（facts 在场即解析过 — bridge 已验字段形态）
    ctx["parsed_ok"] = True
    return ctx


POOL_MECHANICS: Dict[str, str] = {
    "cost_layers": "static(结构)/execution(真跑, 结果经 ctx 注入)/judge(LLM 结论经 ctx 注入) — 本模块都不自持执行, 只投影",
    "fixed_root": "root_parse_ok 恒在 conjunction 首位（构造保证, 非约定）— 原文『validates basic structure + caches parsed artifact』",
    "no_second_judge": "op 只读 ctx 里已算结论（judge/leakage/bridge 的）— 不重算（R152 口径桥同纪律）",
    "evolved_part": "R166 取全池 conjunction; Metric Loop 的重组/交叉留 backlog（S(e)=A_dev·A_train^w−λC 未接 — 诚实标注）",
    "cost_fn": "C(e)=节点计数（与论文 λ·C(e) 同口径, 无权重）",
    "pool_defaults": "root_parse_ok/judge_verdict/nonempty_diff/component_known/golden_leak/pass_rate_weak — 六个: 五真检测器 + R152 匿名投影 op 的具名收编（出身显式, 保链上兼容）",
    "absorbed_weak": "pass-rate-weak 从 gates.py 匿名 lambda 收编为 op_pass_rate_weak（显式承认是聚合投影, 不是论文定义的真检测器 — 待 Metric Loop 长出替代 op）",
}
