# -*- coding: utf-8 -*-
"""metric_loop · Metric Loop 选优面（R177 · 2607.12790 式2 S(e) 的 DWC 组装）。

DWC-AUTO（自我强化）: Metric Loop 的候选打分 = 选"哪个缺点判据树"当裁判 —
  自我强化的判据自身进化; 不动 DWC-MEM 记忆底座。

★★ 论文式（不改公式 — memory 铁律）:
    S(e) = A_dev(e) · A_train(e)^w − λ · C(e)
  常数全部有据（Appendix C 逐条）:
    · A_dev recall-weighted: w_f=2, w_p=1（missed drawback 双倍代价）
    · A_train reliability-weighted: κ=10（本轮先用 R176 的 component
      一致度 — per-op LOO marginal 需锚定数据集, 显式降级并记录）
    · λ·C(e): C = 树节点数（ops._count_nodes 同口径 — 规模惩罚）
  两个 guard（原文逐字）:
    · fail-closed selection: 无 dev 意见的候选 unselectable
    · validity gate: 丢"pass, fail, or abstain on everything"的候选

★★ DWC 候选产生器（诚实降级 — 显式标注）:
    论文的候选来自 LLM composer; DWC 无 composer（且造 composer 越
    R175 的范围）⇒ **机械变异族**: 单 op 叶树 + root∧op 对（每池 op
    各一枚）。这不是发明策略 — 是"无 composer 时的确定性退化",
    每一步可复现; 真正的进化重组（crossover/mutation 随机搜）留
    backlog（需要先有 fitness landscape 的实证, 现在没有）。

★★ 选择（§4 逐字）: argmax_e S(e), **在候选与现任之间取**, 且过
    validity gate + fail-closed。

★★★ TRUTH_SOURCE（判据 G2: 含评分能力的模块必须声明系统外真值源）
  · A_dev 的 label（真值）= judge 器官的 dev 判分点（TaskScorePoint.split
    == "dev" — 系统外注入的真值, 本模块不生成 label）
  · 候选树的判定 = 注入的确定性 op（drawback 池）在 ctx 上的 grade
    — 本模块不引入 LLM 判断（共谋纪律同 drawback 模块）
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from dwc.organs.drawback import (ABSTAIN, CLEAN, DRAWBACK, Grader, Node,
                                Op, VERDICTS, _eval)
from dwc.organs.ops import DEFAULT_POOL, _count_nodes, op_root_parse_ok

#: ★ R179: op 注册表（树求值的 ops 参数 — 池里每个具名 op）
_POOL_OPS: Dict[str, Op] = {op.name: op for op in DEFAULT_POOL}

#: ★ 论文常数（Appendix C — 有出处, 不是调参旋钮）
W_FAIL: float = 2.0                 # recall weight for the fail class
W_PASS: float = 1.0                 # recall weight for the pass class
LAMBDA_C: float = 0.01              # 规模惩罚系数（树每节点罚 0.01·λ）
W_TRAIN: float = 1.0                # A_train 指数（论文 w — 小常数取 1）


class MetricLoopError(Exception):
    """Metric Loop 的显式拒（缺素材/候选空/口径违反 — 大声报错）。"""


# ══════════════════════════════════════════════════════════
# R179 · 真数据面（judge.task_scores(dev) ⇒ 每树 grade ⇒ dev_points）
# ══════════════════════════════════════════════════════════

def _ctx_from_evidence(evi: Dict[str, Any]) -> Dict[str, Any]:
    """★ R179: verdict evidence dict ⇒ op ctx（口径桥 — 只投影不重算）。

    ★ 字段映射（judge/ops 两侧字段名核实后定 — 不猜）:
      · success    = verdict 总判（label 的唯一源 — 不用 score 阈值造
                     第二口径: score 是连续分, success 才是 judge 的判）
      · pass_rate  = k_passed/n_checks（op_pass_rate_weak 的原值口粮）
      · candidate_diff / vocabulary = evidence 里的对应字段（缺 ⇒ None）
      · parsed_ok  = verdict 在场即结构解析过（judge 只记 success 非 None
                     的点 ⇒ 恒 True, 与 ctx_from_facts 同口径）
    ★ 缺字段 ⇒ None/不进（op 对该 ctx 面 abstain — 三值协议的第三态）
    """
    k = evi.get("k_passed")
    n = evi.get("n_checks")
    return {"judge_success": evi.get("success"),
            "pass_rate": (None if not n else (float(k) / float(n))),
            "candidate_diff": evi.get("candidate_diff"),
            "vocabulary": evi.get("vocabulary"),
            "component": (evi.get("component")
                          or (evi.get("checks") or [{}])[0].get("component")),
            "parsed_ok": True}


def dev_points_from_store(store: Any, *, split: str = "dev",
                          trees: Optional[List[Node]] = None
                          ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """★★★ R179: judge store ⇒ dev_points（Metric Loop 的真数据面接线）。

    ★ 每点 = {label, tree_verdicts: {key: verdict}}:
      · label = evidence["success"]（judge 总判 — 唯一 label 源）
      · tree_verdicts[key] = 该树在该点 ctx 上的 grade（Grader.grade）
    ★ 缺席诚实化: 无 dev 点 / evidence 解析失败 ⇒ 该点跳过并计数
      （notes 里给 n_points/n_skipped — 不造点）
    """
    trees = trees if trees is not None else mechanical_candidates()
    try:
        pts_in = store.task_scores(split=split)
    except Exception as exc:                      # noqa: BLE001 — 留痕不静默
        raise MetricLoopError(
            "task_scores(split=%r) 失败: %s: %s（Metric Loop 无数据面 ⇒ "
            "不选优 — 不造点）" % (split, type(exc).__name__, exc))
    out: List[Dict[str, Any]] = []
    n_skip = 0
    for p in pts_in:
        try:
            evi = store.evidence(p.evidence_ref)
        except Exception as exc:                  # noqa: BLE001 — 留痕不静默
            n_skip += 1
            continue
        label = evi.get("success")
        if label is None:
            n_skip += 1
            continue
        ctx = _ctx_from_evidence(evi)
        tv: Dict[str, str] = {}
        for t in trees:
            # ★★ R179 实测纠偏: Grader.grade 是**实例方法**（tree 绑在
            #   实例上, 且返 dict）— dev_points 要的是单值三态 ⇒ 直接用
            #   drawback 的模块级求值器 _eval(tree, ops, task, y, ctx)
            #   （grade 内部就调它 — 同一条判定路径, 不另造口径）
            tv[_tree_key(t)] = _eval(t, _POOL_OPS, None, None, ctx)
        out.append({"label": bool(label), "task_id": p.task_id,
                    "score": p.score, "tree_verdicts": tv})
    notes = {"n_points": len(out), "n_skipped": n_skip, "split": split}
    if not out:
        raise MetricLoopError(
            "dev 面无点（n_skipped=%d）⇒ fail-closed: Metric Loop 不选优"
            "（论文: 无 dev 意见 ⇒ unselectable — 不拿空集当'全过'）"
            % n_skip)
    return out, notes


# ══════════════════════════════════════════════════════════
# R181 · 采纳面（选优 ⇒ 换 ③门树 + 门组回归快照 — 前置闸）
# ══════════════════════════════════════════════════════════

def regression_probe(facts_factory: Any, *, new_tree: Any) -> Dict[str, Any]:
    """★★★ R181 门组回归快照: 同一组 TermFacts 在旧树/新树下的 ③门判定对比。

    ★ 纪律（采纳的前置闸 — 论文 fail-closed 同族）:
      · 任何一条 fact 在新树下**变严**（blocked）而旧树放行 ⇒ adopt=False
        （"更优树"不许把原本能过的候选拦了 — 那是回退不是进化）
      · 任何一条 fact 在新树下**变松**（passed）而旧树拦 ⇒ 记 relaxed
        条目（不自动拒 — 放行是进化方向; 但必须逐条可审计）
      · 完全一致 ⇒ adopt=True（空操作也如实: 没变化 = 没风险 = 没价值）
    ★ facts_factory: () => Iterable[TermFacts]（调用方的事实例 — 本函数
      不猜面）; 返回 {adopt, relaxed, blocked_more, n}（+ 每条的 diff）
    """
    from dwc.harness import gates as _gates
    out = {"adopt": True, "relaxed": [], "blocked_more": [], "n": 0}
    try:
        facts_iter = list(facts_factory())
    except Exception as exc:                  # noqa: BLE001 — 留痕不静默
        return {"adopt": False, "why": "facts_factory 失败: %s: %s"
                                      % (type(exc).__name__, exc), "n": 0}
    old = _gates._current_tree_injection()
    for i, f in enumerate(facts_iter):
        try:
            _gates.set_current_tree(None)          # 出厂树 = 旧判据
            o_old = _gates._g3_drawback(f)
            _gates.set_current_tree(new_tree)      # 新树
            o_new = _gates._g3_drawback(f)
        except Exception as exc:                  # noqa: BLE001 — 留痕不静默
            out["blocked_more"].append({"i": i, "why": str(exc)})
            out["adopt"] = False
            continue
        finally:                                   # 复位置换态 — 不污染后续
            _gates.set_current_tree(old)
        out["n"] += 1
        if o_old.status == "passed" and o_new.status != "passed":
            out["blocked_more"].append({"i": i, "old": o_old.status,
                                        "new": o_new.status})
            out["adopt"] = False
        elif o_old.status != "passed" and o_new.status == "passed":
            out["relaxed"].append({"i": i, "old": o_old.status,
                                   "new": o_new.status})
    return out


def adopt(new_tree: Any, facts_factory: Any) -> Dict[str, Any]:
    """★★★ R181 采纳: 回归快照过 ⇒ 注入 ③门; 不过 ⇒ 拒绝 + 原因（不半吊）。"""
    rep = regression_probe(facts_factory, new_tree=new_tree)
    if not rep.get("adopt", False):
        return {"adopted": False, "regression": rep,
                "why": rep.get("why") or "回归快照: 新树拦了旧树放行的候选"
                                       "（更优树不许是回退）"}
    from dwc.harness import gates as _gates
    _gates.set_current_tree(new_tree)
    return {"adopted": True, "regression": rep,
            "why": "回归过（n=%d, relaxed=%d）⇒ 注入生效树"
                   % (rep.get("n", 0), len(rep.get("relaxed", [])))}


# ══════════════════════════════════════════════════════════
# A_dev（recall-weighted — 论文 §4 逐字）
# ══════════════════════════════════════════════════════════

def a_dev_recall(verdicts: List[str], labels: List[bool]
                 ) -> Tuple[Optional[float], Dict[str, Any]]:
    """★ A_dev = (w_f·r_fail + w_p·r_pass)/(w_f+w_p)（无意见 ⇒ None）。

    ★ 口径（论文"so a missed drawback costs twice a false alarm"）:
      · r_fail = 真失败点中被判 drawback 的比例（召回）
      · r_pass = 真成功点中被判 clean 的比例
      · 两类全缺席 ⇒ None（fail-closed — 不装分辨力）
      · 只有一类 ⇒ 按该类加权归一（不静默补零 — 记 n_* 字段）
    """
    fails = [(v, l) for v, l in zip(verdicts, labels) if not l]
    passes = [(v, l) for v, l in zip(verdicts, labels) if l]
    if not fails and not passes:
        return None, {"why": "无 dev 意见 ⇒ None（fail-closed）"}
    num = den = 0.0
    if fails:
        r_f = sum(1 for v, _ in fails if v == DRAWBACK) / float(len(fails))
        num += W_FAIL * r_f
        den += W_FAIL
    if passes:
        r_p = sum(1 for v, _ in passes if v == CLEAN) / float(len(passes))
        num += W_PASS * r_p
        den += W_PASS
    return num / den, {"r_fail": (sum(1 for v, _ in fails if v == DRAWBACK)
                                  / float(len(fails)) if fails else None),
                       "r_pass": (sum(1 for v, _ in passes if v == CLEAN)
                                  / float(len(passes)) if passes else None),
                       "n_fail": len(fails), "n_pass": len(passes)}


def validity_gate(verdicts: List[str]) -> Tuple[bool, str]:
    """★ validity gate: 丢"pass, fail, or abstain on everything"（原文逐字）。

    ★ 判据: 非 abstain 的 verdict 若**只有一种**（恒 drawbacK 或恒 clean）
      ⇒ 无分辨力 ⇒ invalid（论文: 这种候选定义不了伪标签）。空 ⇒ invalid。
    """
    non_abs = [v for v in verdicts if v != ABSTAIN]
    if not non_abs:
        return False, "全 abstain ⇒ 无意见（invalid）"
    kinds = set(non_abs)
    if len(kinds) == 1:
        return False, "恒定单一判定 %r ⇒ 无分辨力（invalid）" % kinds.pop()
    return True, "有 %r 两种判定（valid）" % sorted(kinds)


# ══════════════════════════════════════════════════════════
# 候选族（机械变异 — 诚实降级, 见模块 docstring）
# ══════════════════════════════════════════════════════════

def mechanical_candidates() -> List[Node]:
    """★ 候选树族: [current] + 每 op 单叶 + root∧op 对（全确定性可复现）。"""
    trees: List[Node] = [_current_tree()]
    for op in DEFAULT_POOL:
        trees.append(Node(kind="leaf", op=op.name))
        trees.append(Node(kind="and",
                          children=(Node(kind="leaf",
                                         op="root_parse_ok"),
                                    Node(kind="leaf", op=op.name))))
    return trees


def _current_tree() -> Node:
    """current = R166 出厂树（fixed root ⋀ 全池 conjunction）。"""
    leaves = [Node(kind="leaf", op="root_parse_ok")] + [
        Node(kind="leaf", op=op.name) for op in DEFAULT_POOL]
    tree = leaves[0]
    for leaf in leaves[1:]:
        tree = Node(kind="and", children=(tree, leaf))
    return tree


def _tree_key(t: Node) -> str:
    return "%s(%d)" % (t.op if t.kind == "leaf" else t.kind, _count_nodes(t))


# ══════════════════════════════════════════════════════════
# S(e) 组装 + 选优（§4 逐字: argmax 在候选与现任之间取）
# ══════════════════════════════════════════════════════════

def score_candidate(*, verdicts: List[str], labels: List[bool],
                    a_train: Optional[float], n_nodes: int
                    ) -> Tuple[Optional[float], Dict[str, Any]]:
    """★ S(e) = A_dev·A_train^w − λ·C（None 传播 — 不伪造任一因子）。

    ★ A_train None ⇒ S None（乘性因子缺席 — fail-closed: 单因子不裁决）;
      这是 R176 三态纪律在 S 面的延伸。
    """
    a_dev, dev_why = a_dev_recall(verdicts, labels)
    if a_dev is None or a_train is None:
        return None, {"a_dev": a_dev, "a_train": a_train,
                      "why": "因子缺席 ⇒ S=None（fail-closed）",
                      "detail": dev_why}
    s = (a_dev * (a_train ** W_TRAIN)) - (LAMBDA_C * float(n_nodes))
    return s, {"a_dev": a_dev, "a_train": a_train, "c": n_nodes,
               "w_train": W_TRAIN, "lambda_c": LAMBDA_C,
               "detail": dev_why}


def select(dev_points: List[Dict[str, Any]], *, a_train: Optional[float],
           trees: Optional[List[Node]] = None,
           include_current: bool = True) -> Dict[str, Any]:
    """★★★ R177 选优: 候选族逐个体检（validity + fail-closed）⇒ argmax S。

    dev_points: [{label, tree_verdicts: {key: verdict}}] — 每 dev item 上
      **每棵候选树一个判定**（由调用方跑树给出 — 本函数只组装 S, 不判树）;
      trees=None ⇒ mechanical_candidates()（默认族; 测试/实验可注入自族）。
    返回 {picked_key, s, candidates: [...], notes} — picked=None ⇒ 不换
      （现任保持 — 没有候选胜过现任; 平手取现任, 论文同款不折腾）。
    """
    trees = trees if trees is not None else mechanical_candidates()
    labels = [bool(p.get("label")) for p in dev_points]
    scored: List[Dict[str, Any]] = []
    for t in trees:
        key = _tree_key(t)
        if not include_current and key == _tree_key(_current_tree()):
            continue
        # 该树在 dev 面上的逐点判定: 同 ctx 面逐树判（跨点不共享断言）
        vs = [p["tree_verdicts"][key] for p in dev_points]
        ok, why = validity_gate(vs)
        if not ok:
            scored.append({"key": key, "valid": False, "why": why})
            continue
        s, detail = score_candidate(verdicts=vs, labels=labels,
                                    a_train=a_train, n_nodes=_count_nodes(t))
        scored.append({"key": key, "valid": True, "s": s, "detail": detail,
                       "why": why})
    valid = [c for c in scored if c["valid"] and c.get("s") is not None]
    if not valid:
        return {"picked_key": None, "s": None, "candidates": scored,
                "notes": "无有效候选（validity 或 fail-closed 全拦）⇒ 不换"}
    best = max(valid, key=lambda c: (c["s"], c["key"]))    # 确定 tie-break
    cur_key = _tree_key(_current_tree())
    if cur_key not in [c["key"] for c in valid]:
        return {"picked_key": best["key"], "s": best["s"],
                "candidates": scored,
                "notes": "现任无效 ⇒ 取最优候选"}
    cur = next(c for c in valid if c["key"] == cur_key)
    if best["key"] == cur_key or best["s"] <= cur["s"]:
        return {"picked_key": cur_key, "s": cur["s"], "candidates": scored,
                "notes": "无候选严格优于现任 ⇒ 保持（不折腾 — 论文同款）"}
    return {"picked_key": best["key"], "s": best["s"], "candidates": scored,
            "notes": "候选 %s 优于现任（%s > %s）" % (best["key"], best["s"],
                                                 cur["s"])}
