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

from typing import Any

from dwc.organs.drawback import (
    ABSTAIN,
    CLEAN,
    DRAWBACK,
    Node,
    Op,
    _eval,
)
from dwc.organs.ops import DEFAULT_POOL, _count_nodes

#: ★ R179: op 注册表（树求值的 ops 参数 — 池里每个具名 op）
_POOL_OPS: dict[str, Op] = {op.name: op for op in DEFAULT_POOL}

#: ★ 论文常数（Appendix C — 有出处, 不是调参旋钮）
W_FAIL: float = 2.0                 # recall weight for the fail class
W_PASS: float = 1.0                 # recall weight for the pass class
LAMBDA_C: float = 0.01              # 规模惩罚系数（树每节点罚 0.01·λ）
W_TRAIN: float = 1.0                # A_train 指数（论文 w — 小常数取 1）


class MetricLoopError(Exception):
    """Metric Loop 的显式拒（缺素材/候选空/口径违反 — 大声报错）。"""


# ══════════════════════════════════════════════════════════
# R182 · A_train 精化（reliability-weighted 共识 — κ=10 有据）
# ══════════════════════════════════════════════════════════

def a_train_weighted(train_verdicts: list[dict[str, str]],
                     tree: Any, marginal: dict[str, float | None],
                     *, kappa: float = 10.0,
                     op_filter: Any | None = None) -> float | None:
    """★★★ R182 · A_train = 候选树 op 集合的 reliability-weighted 共识率。

    ★ 论文（2607.12790 逐字）:
      "共识是 reliability-weighted: 每个 opining op 的票按
       1/(1+κ·max(0,m_o)) 缩放, m_o 是该 op 的锚定 leave-one-out marginal"
      ⇒ anchor-proven ops lead, unproven ops vote near-neutrally;
      否则"一坨相关检测器...会定义 regularizer 奖励的那个伪标签自己"。
    ★ DWC 形态（R176 三态纪律不变）:
      · train_verdicts = 每 train 输出上**每个 op** 的三态判定
        （[{op_name: verdict}] — 由调用方跑 _eval 或池求值给出）
      · 一票 = 该 op 在该 train 输出上判 clean; 权重 = reliability_weight(m_o)
      · A_train = Σ(w_o·clean) / Σ(w_o)（只在有 clean/drawback 票的 op 上
        — 全 abstain 的 op 不进分子也不进分母: abstain 不是同意也不是反对）
      · 树无 op / 全 abstain ⇒ None（缺席≠0 — fail-closed 同族）
    ★ 与 R176 的关系: 上轮 A_train = component 出现率（无 per-op marginal
      可用的诚实降级）; 本轮升级为 κ=10 加权 — 公式仍乘性进 S(e)。
    """
    if not train_verdicts:
        return None
    # ★★★ R189-B: op_filter = 显式 op 集合覆盖（None ⇒ 树内, 旧行为）:
    #   train 面用 TRAIN_POOL（含无标签 op exec_ok/evidence_rich）—
    #   旧行为只认**当前选中的树**的 op ⇒ R189-B 前 A_train 恒 1.0
    #   的真根因: 出厂树（R183 可能 adopt 成单叶 pass_rate_weak）不含
    #   新 op ⇒ 它们的票被静默丢弃 ⇒ 恒 1（R189-B 实测抓到第三层洞）。
    if op_filter is not None:
        ops_in_tree = set(op_filter)
    else:
        ops_in_tree = {l.op for l in _flatten_and(tree) if l.kind == "leaf"}
    if not ops_in_tree:
        return None
    num = den = 0.0
    for tv in train_verdicts:
        for name in ops_in_tree:
            v = tv.get(name)
            if v is None or v == ABSTAIN:      # abstain 不进分母
                continue
            w = reliability_weight(marginal.get(name), kappa=kappa)
            den += w
            if v == CLEAN:
                num += w
    if den == 0.0:
        return None                           # 全 abstain ⇒ 无共识可测
    return num / den


# ══════════════════════════════════════════════════════════
# R179 · 真数据面（judge.task_scores(dev) ⇒ 每树 grade ⇒ dev_points）
# ══════════════════════════════════════════════════════════

def _ctx_from_evidence(evi: dict[str, Any]) -> dict[str, Any]:
    """★ R179: verdict evidence dict ⇒ op ctx（口径桥 — 只投影不重算）。

    ★ 字段映射（judge/ops 两侧字段名核实后定 — 不猜）:
      · success    = verdict 总判（label 的唯一源 — 不用 score 阈值造
                     第二口径: score 是连续分, success 才是 judge 的判）
      · pass_rate  = k_passed/n_checks（op_pass_rate_weak 的原值口粮）
      · candidate_diff / vocabulary = evidence 里的对应字段（缺 ⇒ None）
      · parsed_ok  = verdict 在场即结构解析过（judge 只记 success 非 None
                     的点 ⇒ 恒 True, 与 ctx_from_facts 同口径）
    ★★★ R193 · `candidate_diff` 键名 vs `diffs` 落盘字段的**错位修正**（X1 的真根因）:
      R180 记"candidate_diff 不在 evidence 判据面" — 半错。实测
      evidence.jsonl **49/49 条都有 `diffs`**（judge 逐 check 落的
      {index,kind,fn,kw,args,expected,actual,ok,reason}）; 缺的只是
      "把 diffs 列表投影成 op 吃的 diff 文本"。⇒ 本桥补该投影:
      首个 **notok** check 的 `fn(args): expected → actual（reason）`;
      全 ok ⇒ None（判过、无差异 ⇒ 该点没有可 diff 的内容）。
    ★ 缺字段 ⇒ None/不进（op 对该 ctx 面 abstain — 三值协议的第三态）
    """
    k = evi.get("k_passed")
    n = evi.get("n_checks")
    diff_txt: str | None = None
    for d in (evi.get("diffs") or []):
        if isinstance(d, dict) and not d.get("ok", True):
            diff_txt = "%s(%s): %s → %s（%s）" % (
                d.get("fn") or "?", d.get("args"),
                d.get("expected"), d.get("actual"),
                d.get("reason") or "值不匹配")
            break
    return {"judge_success": evi.get("success"),
            "pass_rate": (None if not n else (float(k) / float(n))),
            "candidate_diff": diff_txt,
            "vocabulary": evi.get("vocabulary"),
            "component": (evi.get("component")
                          or (evi.get("checks") or [{}])[0].get("component")),
            "parsed_ok": True}


def dev_points_from_store(store: Any, *, split: str = "dev",
                          trees: list[Node] | None = None
                          ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
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
    out: list[dict[str, Any]] = []
    n_skip = 0
    for p in pts_in:
        try:
            evi = store.evidence(p.evidence_ref)
        except Exception:                  # noqa: BLE001 — 留痕不静默
            n_skip += 1
            continue
        label = evi.get("success")
        if label is None:
            n_skip += 1
            continue
        ctx = _ctx_from_evidence(evi)
        tv: dict[str, str] = {}
        for t in trees:
            # ★★ R179 实测纠偏: Grader.grade 是**实例方法**（tree 绑在
            #   实例上, 且返 dict）— dev_points 要的是单值三态 ⇒ 直接用
            #   drawback 的模块级求值器 _eval(tree, ops, task, y, ctx)
            #   （grade 内部就调它 — 同一条判定路径, 不另造口径）
            tv[_tree_key(t)] = _eval(t, _POOL_OPS, None, None, ctx)
        out.append({"label": bool(label), "task_id": p.task_id,
                    "score": p.score, "tree_verdicts": tv,
                    # ★ R182: ctx 随点带出（loo_marginal_dev 要重算
                    #   树判定 — 不存 ctx 就得回读 evidence, 浪费且可能
                    #   两次读不一致; 同点同 ctx = 可复现）
                    "ctx": ctx})
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

def regression_probe(facts_factory: Any, *, new_tree: Any) -> dict[str, Any]:
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


def adopt(new_tree: Any, facts_factory: Any) -> dict[str, Any]:
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

def a_dev_recall(verdicts: list[str], labels: list[bool]
                 ) -> tuple[float | None, dict[str, Any]]:
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


def validity_gate(verdicts: list[str]) -> tuple[bool, str]:
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

def mechanical_candidates() -> list[Node]:
    """★ 候选树族: [current] + 每 op 单叶 + root∧op 对（全确定性可复现）。"""
    trees: list[Node] = [_current_tree()]
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

def loo_marginal_dev(dev_points: list[dict[str, Any]], op_name: str,
                     incumbent: Any) -> float | None:
    """★★★ R182 · m_o = op 的锚定 leave-one-out marginal（2607.12790 ④）。

    ★ 口径（论文原文 + e2e 参考实现逐字对齐）:
      拿掉 op_name 后的表达式 vs 原表达式, 在 dev 面上的**判定变化幅度**;
      论文"per-op fitness = 现任表达式的 leave-one-out marginal", "可自动
      判定的淘汰判据就是这个值"。负边际（拿掉它反而更好）⇒ 退役候选
      （grace 2 轮后 — 附录 C）。
    ★ 实现: 从 incumbent 树重建一棵不含该 op 叶的树（and 树去掉一个叶 =
      剩下的 and 链 — leaf 本身被拿掉时用 sibling 顶上; 根叶被拿掉 ⇒
      None（不可拿 — 那会改 fixed root 结构）⇒ 记 None 不造数）
    ★ 无 dev 点 / incumbent 不含该 op ⇒ None（缺席≠0）
    """
    if not dev_points:
        return None
    from dwc.organs.drawback import _eval as _ev
    ops = _POOL_OPS
    reduced = _drop_leaf(incumbent, op_name)
    if reduced is None:
        return None                      # 根叶/不在树 ⇒ 不造 marginal
    n_changed = 0
    n_total = 0
    for p in dev_points:
        ctx = p.get("ctx") or {}
        if "ctx" not in p:
            # dev_points 若无 ctx（旧形态 — select 注入的树判定已算）, 用
            # tree_verdicts 里 incumbent（and(13)）与 reduced 的差 ⇒ 不适用
            # ⇒ 诚实返回 None（本函数只吃带 ctx 的真点）
            return None
        try:
            v_full = _ev(incumbent, ops, None, None, ctx)
            v_drop = _ev(reduced, ops, None, None, ctx)
        except Exception:                 # noqa: BLE001 — 留痕不静默
            return None
        n_total += 1
        if v_full != v_drop:
            n_changed += 1
    if n_total == 0:
        return None
    return n_changed / float(n_total)


def _drop_leaf(tree: Any, op_name: str) -> Any:
    """★ 从 and 链里拿掉一个叶（保留其余 — 结构变换, 不改语义组合规则）。"""
    from dwc.organs.drawback import Node as _N
    if tree.kind == "leaf":
        return None                          # 不能拿根叶
    if tree.kind != "and":
        return None                          # 只处理 and 链（出厂形态）
    leaves = _flatten_and(tree)
    if not any(l.op == op_name for l in leaves if l.kind == "leaf"):
        return None                          # 不含该 op ⇒ 无 marginal 可算
    # ★★ R182 实测纠偏: 出厂树的**固定 root**（root_parse_ok, build_grader
    #   root_first=True 的构造保证 — 论文"the fixed root conjoined with
    #   the evolved expression"）不可拿 — 摊平后无法按位置分辨, 但它的
    #   name 是出厂保留字 ⇒ 按名拦（结构保证的名字签名, 不是魔法串）
    if op_name == "root_parse_ok":
        return None                          # 固定 root 不可拿（构造保证）
    kept = [l for l in leaves
            if not (l.kind == "leaf" and l.op == op_name)]
    if not kept:
        return None                          # 全拿光 ⇒ 无表达式
    out = kept[0]
    for leaf in kept[1:]:
        out = _N(kind="and", children=(out, leaf))
    return out


def _flatten_and(tree: Any) -> list[Any]:
    if tree.kind == "leaf":
        return [tree]
    if tree.kind != "and":
        return [tree]
    out: list[Any] = []
    for c in tree.children:
        out.extend(_flatten_and(c))
    return out


def reliability_weight(m_o: float | None, *, kappa: float = 10.0
                       ) -> float:
    """★★ 共识权重 1/(1+κ·max(0,m_o))（论文逐字 — 安全选择非调参旋钮）。

    ★ m_o=None ⇒ 1.0（该 op 无锚定 marginal ⇒ 中性票, 不罚不奖 —
      论文 "unproven ops vote near-neutrally"）
    ★ m_o 大（拿掉它共识变多）⇒ 权重趋 0（它的票与锚不一致 — 降权）
    """
    if m_o is None:
        return 1.0
    return 1.0 / (1.0 + kappa * max(0.0, float(m_o)))


def score_candidate(*, verdicts: list[str], labels: list[bool],
                    a_train: float | None, n_nodes: int
                    ) -> tuple[float | None, dict[str, Any]]:
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


def select(dev_points: list[dict[str, Any]], *, a_train: float | None,
           trees: list[Node] | None = None,
           include_current: bool = True) -> dict[str, Any]:
    """★★★ R177 选优: 候选族逐个体检（validity + fail-closed）⇒ argmax S。

    dev_points: [{label, tree_verdicts: {key: verdict}}] — 每 dev item 上
      **每棵候选树一个判定**（由调用方跑树给出 — 本函数只组装 S, 不判树）;
      trees=None ⇒ mechanical_candidates()（默认族; 测试/实验可注入自族）。
    返回 {picked_key, s, candidates: [...], notes} — picked=None ⇒ 不换
      （现任保持 — 没有候选胜过现任; 平手取现任, 论文同款不折腾）。
    """
    trees = trees if trees is not None else mechanical_candidates()
    labels = [bool(p.get("label")) for p in dev_points]
    scored: list[dict[str, Any]] = []
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
