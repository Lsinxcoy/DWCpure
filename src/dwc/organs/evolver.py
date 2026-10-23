"""DWC evolver —— 变异器（器官 4/7）。★ 让分数能掉下来的那个器官。

★★★ 这个器官为什么现在最要紧
  R26 实测: actor + judge 链路已通，dev 的 6 条 behavior 任务全过
  ⇒ pass_rate = 1.0
  ⇒⇒ ★★ 而那个 1.0 是**必然的** —— actor 跑的是基准实现，它不会失败
  ⇒⇒ ⇒★ 所以这套东西目前**修不了任何 bug**，只会一直满分
  ⇒⇒⇒ ⇒★ 唯一能让分数掉下来的东西就是 evolver:
    它提出**会失败**的候选实现，actor 执行，judge 判分
    ⇒⇒⇒⇒ ★★ 那才是真正的进化闭环:
      失败签名 → 提案 → 过门 → actor 执行 → judge 判分 → 采纳/拒绝

定位声明（DWC-MEM · 记忆底座 · 判据 G1 定位门）
  ★ evolver 属记忆底座 —— 它消费失败签名（EXPERIENCE 区），产出提案
  ★ 它**不落地**：落地是 APPLIER 的职责（原则 6: 器官各司其职）
  ★ 它**不判分**：判分是 judge（原则 1: 判据必须在系统外）

★★★ 四条约束（EVOLUTION_CORE_DESIGN §九 逐条核过）
  约束 1 · 禁止"先落再测"
    依据 2609.24972 / 2609.26457 / 2607.12790
    ⇒⇒ 所以提案**先过门再采纳**，落地与测量必须分离
  约束 2 · 判据必须在可写面之外
    依据 2609.13406 grounded 双条件
    ⇒⇒ 所以 evolver 只**读**失败签名，不改判据
  约束 3 · 必须有两组 split
    依据 2606.09498 (Δ_in ≥ 0 ∧ Δ_ho ≥ 0)
    ⇒⇒ 所以采纳要同时看 in-sample 与 held-out
    ⇒⇒ ⇒★ 而 test 未落地 ⇒ **只能判 in** ⇒ adopt 返回 blocked
  约束 4 · 每轮变更数必须可归因
    依据 2606.09498 原文: "一簇对应一处干预"
    + 2609.24972 退火预算 b_t
    ⇒⇒ ★★ 所以本模块硬性限制: **一个提案只改一处**
    ⇒⇒ ★ 若允许多处 ⇒ 任何测量都无法归因
"""
from __future__ import annotations

#: ★★★ TRUTH_SOURCE（判据 G2）
#: ★★ 本模块**不判分、不落地** ⇒ 它没有真值源
#: ★★ 它产出的提案最终由 judge 在 dev/test 上判，本模块只做生成 + 门检
TRUTH_SOURCE = {
    "本模块不自判": "提案是否被采纳由 judge 判分决定（约束 1/2）",
    "本模块的产出": "proposal（待判分的候选），不是判分结果",
    "判读位置": "dwc.organs.judge.Judge（真值源 config/anchors/dev.json）",
    "★ 约束 2": "判据在可写面之外 ⇒ evolver 只读失败签名，不改判据",
}

#: ★★★ R193 · 词表收口至**单一真源** foundation/vocabulary.py（债 X4）
#:   ★ 为什么不是"另建一张表": 本文件原持两张字面量（𝒦9 + 𝒦_meta5）, 与
#:     docs/COMPONENT_VOCABULARY.md 构成"代码/文档双源"; 收口后代码层只有
#:     vocabulary.py 一处, 本文件改为**引用同一对象**（不是复制值 —
#:     测试锁 `is` 同一性, 防"看起来收口了其实两套值"）。
#:   ★ 值一字不动（转抄）— 收口是位置手术, 不是语义手术（R193 计划 §四）。
from dwc.foundation.vocabulary import (  # noqa: F401
    COMPONENT_VOCAB,
    K_META,
    K_META_READONLY,
    STRUCTURAL,
)

# ═══════════════════════════════════════════════════════════
# ★★★★ R37 · 𝒦_meta（系统层 5 项）—— 实现 docs/COMPONENT_VOCABULARY §二
#   真源: papers_txt/2609.24972.txt 式12（𝒦 9 项，逐字核）
#        docs/COMPONENT_VOCABULARY.md §2.1（𝒦_meta 5 项）
#   ★★ 为什么 𝒦 不扩而另建一张表: 代码/评估器不是"harness 片段"
#     ⇒ 塞进 𝒦 会让 proposer 尝试改评估器
#       ⇒ ⇒ 那正是 GAI Dial 2 说的 "base that the agent may rewrite"
#         （破坏 grounded 的第二条件）
#   ★★★ R193 · 该表（连同上面的 R37 注释）已**原样搬至**
#     foundation/vocabulary.py — 见本文件 import 区; 这里不再自持字面量
#     （唯一性验收: evolver.COMPONENT_VOCAB is vocabulary.COMPONENT_VOCAB）
# ═══════════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════════
# ★★★★★ R38 · **逐项映射**（用户 2026-10-06 裁决「D」）
#   原 §四① 是「表 ⇒ 层」一刀切: 𝒦⇒assets · 𝒦_meta⇒architecture
#   ⇒⇒ ★★ 与 §三 的**逐项处置**冲突:
#     §3.1 code  「仍须过 b_t + 保护组回归」    ← **没要人工批准**
#     §3.2 architecture「门通过 ≠ 可落地 ⇒ 须批准」
#     §四① 把 code 也归 architecture ⇒ code 被迫要批准
#     ⇒⇒ **与 §3.1 明文冲突**（而 §三 才是逐项处置的实质内容）
#   ⇒ ⇒★ 裁决 D: `target_layer` 由**每项的处置**决定，不由「在哪张表」
#     · 改的是 §四① 那句粗映射，**§三 三处处置一字不动**
#     · 与原表的差别**只有 `code` 一项**: architecture → assets
#   ★ K2 仍照常查（只是真值表更细），不需要模型理解两表区别
# ═══════════════════════════════════════════════════════════

#: ★ 逐项真值表: component → target_layer
#:   ★ 每一项都注了**依据哪一条处置**（可复核，不是我拍的）
LAYER_BY_ITEM: dict[str, str] = {
    # ── 𝒦 9 项（§四① 原样，未动）──
    **{c: "assets" for c in COMPONENT_VOCAB},
    # ── 𝒦_meta 5 项（按 §三 的逐项处置）──
    "code": "assets",          # ★ D 的唯一变化: §3.1 只给 b_t+回归
                               #   ⇒ 无批准要求 ⇒ 归可落地层
    "architecture": "architecture",   # §3.2: 须人工批准（G3 人类主权）
    "meta_evolution": "architecture",  # §3.3: 系统层（改的是提议器自己
                                       #   ⇒ 保守归架构层；§3.3 的三条护栏
                                       #   不等于"无须批准"）
    "evaluator": "architecture",       # §3.4: 不可编辑（登记在系统层）
    "external_source": "architecture",  # §3.5: 只读登记
}

#: ★ K2 真值表的**反向索引**（layer → components）
LAYER_BY_GROUP: dict[str, frozenset] = {
    "assets": frozenset(k for k, v in LAYER_BY_ITEM.items()
                        if v == "assets"),
    "architecture": frozenset(k for k, v in LAYER_BY_ITEM.items()
                              if v == "architecture"),
}


def layer_of(component: str) -> str:
    """component → target_layer（**逐项**真值表 · R38 裁决 D）。

    ★★ 返回 `assets` / `architecture`
    ⇒ 不在表里 ⇒ ★ **不猜**，raise（两表并集 = 全部可选组件）
    ⇒⇒ 每项的层由 §三 的**处置**决定（见 LAYER_BY_ITEM 的注释）
    """
    if component in LAYER_BY_ITEM:
        return LAYER_BY_ITEM[component]
    raise ValueError(
        "component=%r 既不在 𝒦(9) 也不在 𝒦_meta(5) ⇒ **无层可归**"
        "（proposer 只能在这两表里选，见 §四①）" % component)


# ═══════════════════════════════════════════════════════════
# ★★★★ R40 · ν_t 新颖度（RRSI 式16 + DWC 版）—— 设计 §四②
#   论文原文（2609.24972 式16，逐字核）:
#     ν_t(H') = Σ_{ℓ ∈ K_str} 1[ℓ ∈ comp(H') ∧ N_t(ℓ)=0]
#     K_str = {client_tool, skill, memory, subagent}        （式15）
#     N_t(ℓ) = round t 之前、被**采纳**且 tagged ℓ 的编辑记录数
#     「Prompt, control-flow, configuration, output-plumbing,
#      and context-management edits **do not receive** this bonus」
#   ★ DWC 版（COMPONENT_VOCABULARY §四②）: K_str ∪ {meta_evolution}
#     —— meta_evolution 是唯一默认拿奖励的新增项（§3.3: 它是
#        "可新增的结构"，符合 K_str 的本意）
#   ★★ 为什么它可落地而 ℬ_t/ℰ_t 不行（R40 实测）:
#     · N_t 的数据 = **RULES 已固化条目**（component 字段 3/3 有）✓
#     · ℬ_t 需要 ℒ_t 信用日志（**不存在**）+ 组件级 g_t（**只有整体 gain**）
#     · 且量化阶梯 ⇒ gain 恒 0 ⇒ 照式14 会**全体剪枝**（灾难）
#   ⇒ ⇒★ 三式里 ν_t 是唯一数据齐的 —— 先做它，另两式**先修数据前置**
# ═══════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════
# ★★★★ R40 · K1 —— 21 个可进化对象 → 𝒦 ∪ 𝒦_meta 的映射
#
# ★★★★ 权威清单的**冲突已挑明**（我核了三处）:
#   · COMPONENT_VOCABULARY §七 写「权威清单以 EVOLUTION_DIMENSIONS_TABLE 为准」
#     列了 1标量…21元认知（含 智能体/推理增强/harness/基础设施/元认知）
#   · ARCHITECTURE.md 说「v4 实测修正 (DEDUP_AUDIT_6SYSTEMS.md): 对象层 21」
#   · DEDUP_AUDIT §2.4 指出 EVOLUTION_DIMENSIONS_TABLE 是**旧表 28 个**,
#     并逐个证伪了 7 项（智能体/推理增强/harness/基础设施/元认知/…）
#   ⇒⇒ ★ 结论: **DEDUP_AUDIT §2.3 的 21 项并集**才是权威
#     （v4 严格去重: 6 套体系 39 仓库源码逐字提取）
#   ⇒ ⇒★ COMPONENT_VOCABULARY §七 引的是**被证伪的旧表** —— 文档间冲突，
#     我按 memory「审计文档权威」+ 时间序（v4 最新）取 DEDUP_AUDIT
#
# ★★ 映射允许**多对一**（K1 是"覆盖"判据: 每个对象必须映射到某组件，
#   不要求组件与对象一一对应）—— 文档 §五 K1 原文:
#   「21 个对象名必须各自出现在两张表之一」
#
# ★★★ 争议项**显式标注**（不擅自裁决，沿文档诚实边界⑩ 的做法）:
#   · `in_disputed` 里的对象: 我选的映射**可能被推翻**
#   · 尤其 §七 说的「基础设施→code」类（本次清单里已无该项）
# ═══════════════════════════════════════════════════════════

#: ★ 权威 21 对象（DEDUP_AUDIT §2.3 · v4 严格去重并集）
EVOLUTION_OBJECTS_21 = (
    "标量参数/超参", "策略", "技能", "记忆", "知识", "代码", "架构",
    "提示词", "工具", "协作", "上下文", "观测", "执行环境", "元进化",
    "评估器", "控制/安全", "模型选择", "训练桥", "行为/工作流",
    "外部机制源(GitHub)", "外部机制源(论文)",
)

#: ★ 对象 → 组件（每项注**依据**；`†` = 有争议未裁决）
OBJECT_TO_COMPONENT = {
    "标量参数/超参": "config",           # 超参归 config
    "策略": "control_flow",              # 策略即控制流
    "技能": "skill",
    "记忆": "memory",
    "知识": "memory†",                   # † 知识存于记忆 vs 独立对象
    "代码": "code",                      # §3.1
    "架构": "architecture",              # §3.2
    "提示词": "prompt",
    "工具": "client_tool",
    "协作": "subagent",
    "上下文": "context_mgmt",
    "观测": "output_plumbing†",          # † 观测 vs 评估器的边界
    "执行环境": "config†",               # † 执行环境归 config 还是独立
    "元进化": "meta_evolution",          # §3.3
    "评估器": "evaluator",               # §3.4 不可编辑
    "控制/安全": "control_flow†",        # † 与「策略」多对一
    "模型选择": "config†",               # † 与「超参」多对一
    "训练桥": "external_source†",        # † 训练桥是否属外部源
    "行为/工作流": "control_flow†",      # † 与「策略/控制安全」三对一
    "外部机制源(GitHub)": "external_source",
    "外部机制源(论文)": "external_source",
}


def k1_coverage() -> dict[str, Any]:
    """★★ K1 —— 21 个对象是否**逐个**映射到 𝒦 ∪ 𝒦_meta。

    ★ 依据: §五 K1「21 个对象名必须各自出现在两张表之一」
    ★ 返回: {covered, missing, bad_target, disputed}
      · missing     : 没映射的对象
      · bad_target  : 映射到**不在两表**的组件（映射是无效的）
      · disputed    : 标 † 的（我选的、可被推翻）
    """
    vocab = set(COMPONENT_VOCAB) | set(K_META)
    missing, bad, disp = [], [], []
    for obj in EVOLUTION_OBJECTS_21:
        c = OBJECT_TO_COMPONENT.get(obj)
        if not c:
            missing.append(obj)
            continue
        clean = c.rstrip("†").strip()
        if clean not in vocab:
            bad.append("%s → %r（不在 𝒦∪𝒦_meta）" % (obj, c))
        if c.endswith("†"):
            disp.append("%s → %s" % (obj, clean))
    return {"total": len(EVOLUTION_OBJECTS_21),
            "covered": len(EVOLUTION_OBJECTS_21) - len(missing),
            "missing": missing, "bad_target": bad,
            "disputed": disp,
            "n_disputed": len(disp)}


#: ★ 式15 的 K_str（论文原文 4 项）∪ DWC 的 meta_evolution（§四②）
NOVELTY_ELIGIBLE = frozenset(STRUCTURAL | {"meta_evolution"})


# ═══════════════════════════════════════════════════════════
# ★★★★ R40 · 𝒯_t / 𝒰_t / ℬ_t（RRSI 伪码 line 7-11，逐字核论文）
#   论文伪码:
#     7: 𝒯_t ← {ℓ_i : (t_i, ℓ_i, …) ∈ ℒ_t}          ← **信用日志**
#     8: 𝒰_t ← 𝒦 ∖ 𝒯_t                              ← 未探索
#     9: ℰ_t ← (σ_t, 𝒰_t, m_draft)                   ← 停滞才激活
#    10: ℬ_t ← {ℓ ∈ 𝒯_t : g_t(ℓ) ≤ 0}                ← 剪枝目标
#    DWC 版（COMPONENT_VOCABULARY §四③④）:
#     ℬ_t = {ℓ ∈ 𝒯_t ∩ 𝒦_editable : g_t(ℓ) ≤ 0}     ← 加**交集**
#     𝒰_t = (𝒦 ∪ 𝒦_meta_editable) ∖ 𝒯_t             ← 探索含 meta
#
# ★★★★★ R40 实测的**两个 blocker**（所以 ℬ_t 不敢启用）:
#   ① `ℒ_t` **不存在**: causal_chain 没有 change 写入函数
#      ⇒ 论文的 𝒯_t 数据源是空的（文档诚实边界⑨也记了"未测"）
#      ⇒ ⇒★ 本模块给**近似** 𝒯_t = 已固化条目的 component 集
#        （语义: "留下过采纳记录的组件" —— 与 ℒ_t 同向但更粗）
#   ② ★★★ **量化阶梯会让式14 全体剪枝**（applier L43/L46/L47 的旧教训）:
#      「scorer 是量化阶梯 ⇒ 同一台阶内 gain 恒 0」
#      ⇒ g_t(ℓ) 恒 0 ⇒ `g_t ≤ 0` **恒真** ⇒ ℬ_t = 𝒯_t ∩ 𝒦_editable
#      ⇒⇒ **所有被测过的组件全被标为删除目标** —— 灾难
#   ⇒ ⇒★ 所以: 公式实现了，但 `enabled=False` + `blockers()` 报原因
#     —— 那不是"空转"，是**大声报错**（G7 纪律: 不许静默跳过）
# ═══════════════════════════════════════════════════════════

#: ★ 𝒦_editable = 𝒦 ∪ {m ∈ 𝒦_meta : m.editable}（§四③ · K5 的交集项）
def editable_vocab() -> frozenset:
    """组件层 + 系统层里**可编辑**的项（evaluator/external_source 不在）。"""
    return frozenset(COMPONENT_VOCAB) | frozenset(
        k for k, ok in K_META.items() if ok)


# ═══════════════════════════════════════════════════════════
# ★★★★★ R42 · ℒ_t 信用日志（RRSI **式10/11 逐字**）—— 用户裁决「乙」
#   ① 我 R41 给的「乙」引用错依据: 我说「§9 (bm) A_t 三元 =
#      (hypothesis, component, hunk)」—— 实测两处错:
#        · (bm) 不是第25项缺口（GAP_AUDIT: 已落第20/2项）
#        · `hunk` 全库仅 1 次，且 RRSI 笔记明说「按**函数/文件**边界切，
#          **不按 hunk 切**」
#      ⇒ ⇒★ 但用户的**意图**（细粒度归因）正是式10 ⇒ 按原文实现
#   ② 论文原文（2609.24972 式10，逐字核）:
#        ℒ_t = { (t_i, ℓ_i, h_i, d_i, ΔS_i, ΔC_i, a_i) : i ≤ n_t }
#        a_i ∈ {0,1}；每个被评估候选里的每个**原子编辑**打三个标签:
#        组件 ℓ / 假设 h / 源码 diff d
#      · `a_i = 1` ⟺ 携带编辑 i 的候选成为**该轮赢家**
#      · `a_i = 0` 且通过所有门 ⇒ "admissible but lost"（**有用信息**，
#        论文原话 —— 不是失败记录，要能查到）
#   ③ 派生（式11，★ 逐字）:
#        𝒯_t  = { ℓ_i : i ≤ n_t }
#        g_t(ℓ) = max{ ΔS_i : ℓ_i = ℓ, t − t_i ≤ n_prune },  max∅ = **−∞**
#      ★★★ `max∅ = −∞` 的作用 —— **我 R42 初版注释写错了, 这里更正**:
#        初版说「交集挡不住没测过 ⇒ −∞ ⇒ 被剪」**是错的**。重推:
#          · 并集: 𝒯_t ∪ 𝒦_editable 会把 **𝒯_t 外**的项拉进来
#                  ⇒ 那些项无记录 ⇒ g_t = −∞ ⇒ `≤0` 恒真 ⇒ **全被标删**
#          · 交集: 𝒯_t ∩ 𝒦_editable 只看 **𝒯_t 内**
#                  ⇒ 每项至少一条记录 ⇒ g_t **不可能是 −∞** ⇒ 语义自洽
#        ⇒ ⇒★ 所以交集**同时**解决了两件事: ① 不可编辑项被标删
#          ② `max∅ = −∞` 导致的未测项误剪（文档 §七 说的正是并集的坑）
#        ⇒ ⇒★ 我初版把 ② 当成"交集没解决" —— 属**声称与实测不符**, 已更正
# ═══════════════════════════════════════════════════════════

#: ★ 式10 的七元字段名（顺序即论文顺序）
LIQUIDITY_FIELDS = ("t_i", "ℓ_i", "h_i", "d_i", "ΔS_i", "ΔC_i", "a_i")

# ★★★ R42 执行事故（两连）:
#   ① 我把 `LIQUIDITY_PATH`（用 os.path）放在了 `import os`（L652）**之前**
#      ⇒ 模块级 NameError —— 同族第 3 次「引用先于定义/导入」
#   ② 修的时候又把 `os.path.join` 写成 `os.join`（丢了 `.path` ⇒
#      `os` 模块**没有** join 属性）⇒ AttributeError
#   ⇒ ⇒★ 教训: 改 import 时**照抄原样**，别顺手改路径写法
import glob as _glob4wired
import os as _os4path

#: ★ 归档落点（式10 的持久化位置 —— 与 RULES 分开: 那是规则, 这是历史）
#: ★★★ R44 修: 我 R42 写成 dirname×2 ⇒ 算出 `src/dwc/config/anchors/`
#:   （目录不存在, 接线前没暴露）—— 而 `LEARNED_PATH` 用的是
#:   dirname×4 + abspath ⇒ `E:/…/config/anchors/rules.json` ✓
#:   ⇒ ⇒★ 我 R42 注释刚写过「照抄原样别顺手改路径写法」，**第 3 次没照抄**
#:     （同族: ① os 引用先于 import ② os.path→os.join ③ 这次层数少）
#:   ⇒ 现在**逐字照抄** LEARNED_PATH 的写法（只换文件名）
LIQUIDITY_PATH = _os4path.path.join(
    _os4path.path.dirname(_os4path.path.dirname(_os4path.path.dirname(
        _os4path.path.dirname(_os4path.path.abspath(__file__))))),
    "config", "anchors", "liquidity.jsonl")


def record_edit(liquidity: list[dict[str, Any]], round_no: int, component: str,
                hypothesis: str, diff: str, delta_s: float, delta_c: float,
                is_winner: bool, path: str = None) -> dict[str, Any]:
    """★★ 记一条式10 的编辑记录 (t_i, ℓ_i, h_i, d_i, ΔS_i, ΔC_i, a_i)。

    ★ 三条硬要求:
      ① **三个标签必须齐**（ℓ/h/d 缺一 ⇒ 归因不成立 ⇒ 拒记, 不静默补空）
      ② `a_i` 只有 0/1 —— "admissible but lost"（过了门但输分）记 **0**,
        但**要留痕**（论文说它是有用信息, 不是失败）
      ③ `ΔS_i`/`ΔC_i` **不许用 0 充数**: 没测到就该报错, 因为 g_t 用 max,
        填 0 会污染 `max{ΔS}` 的语义（0 比 −∞ 好 ⇒ 假装测过）
    """
    if not component or not hypothesis:
        raise ValueError(
            "★ 式10 三标签必须齐: ℓ=%r h=%r —— 缺任一 ⇒ 归因不成立"
            % (component, hypothesis))
    if not isinstance(is_winner, bool):
        raise ValueError("★ a_i ∈ {0,1}，实得 %r（不是 bool）" % (is_winner,))
    # ★★★ R45 · 我 R42 把 ΔS 与 ΔC **一起**拒 None —— 那过严, 已拆开:
    #   · ΔS（分数变化）: **能测必须测** ⇒ 拒 None
    #       理由: g_t = max{ΔS} 用 max, 填 0 会让没测过的组件假装测过
    #   · ΔC（成本变化, 式6 = 相对变化 `(Ĉ'−Ĉ)/Ĉ`）: e2e **没有成本测量**
    #       （论文的 Ĉ 用 token, DWC 未记）⇒ None 是**诚实的"没测"**
    #   ⇒⇒ ★ 关键区分（我 R42 混为一谈了）:
    #       None = 没测（诚实, 记 null 留痕）
    #       0.0  = 测了且恰好没变（**声称**）—— 若没测却填 0.0 = 充数
    #   ⇒ ⇒★ 所以: ΔS 拒 None · ΔC **收 None**（记 null, 不许填 0.0 冒充）
    #   ★ 而 DWC 现在**不消费 ΔC**（g_t 只用 ΔS; 式7 成本规则未实现）
    #     ⇒ 缺 ΔC 暂无下游影响 —— 等式7 落地时 ΔC 已有值才可启用
    if delta_s is None:
        raise ValueError(
            "★ ΔS_i 必须实测（能测必须测）—— "
            "g_t = max{ΔS} 用 max，填 0 会让没测过的组件假装测过")
    if delta_c is None and False:        # ← 占位: None 现在**收**（见上）
        raise ValueError("★ ΔC 不许 None（旧规则, R45 已改）")
    if delta_c is not None and not isinstance(delta_c, (int, float)):
        raise ValueError(
            "★ ΔC_i 只能是数值或 None（实测值/诚实未测），实得 %r" % (delta_c,))
    rec = {"t_i": int(round_no), "ℓ_i": str(component),
           "h_i": str(hypothesis), "d_i": str(diff),
           "ΔS_i": float(delta_s),
           # ★ ΔC 可为 None（诚实未测, 记 null）—— R45
           "ΔC_i": (None if delta_c is None else float(delta_c)),
           "a_i": 1 if is_winner else 0}
    liquidity.append(rec)
    if path:
        # ★ 照 LEARNED_PATH/land_rule 的做法: 目录不存在就建（否则炸）
        d = os.path.dirname(path)
        if d and not os.path.isdir(d):
            os.makedirs(d, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def touched_from_liquidity(liq) -> frozenset:
    """𝒯_t = { ℓ_i : i ≤ n_t }（式11 第一式 · **逐字**）。"""
    return frozenset(r["ℓ_i"] for r in (liq or []) if r.get("ℓ_i"))


def gain(liq, component: str, now_round: int, window: int) -> float:
    """★★★ g_t(ℓ) = max{ ΔS_i : ℓ_i = ℓ, now − t_i ≤ window }（式11）。

    ★★ 三处**逐字**（不许改语义）:
      ① **max 不是 sum/mean**（论文原式）
      ② **窗口**: `now − t_i ≤ window`（`n_prune`, 剪枝窗）
      ③ `max∅ = **−∞**` —— 没有合格记录 ⇒ **-inf**（不是 0!）
         ⇒⇒ 填 0 会让「没测过」看起来像「测过且平」 ⇒ 语义错
    """
    if window < 0:
        raise ValueError("★ window(剪枝窗) 必须非负，实得 %r" % (window,))
    best = None
    for r in (liq or []):
        if r.get("ℓ_i") != component:
            continue
        if now_round - int(r.get("t_i", now_round)) > window:
            continue
        v = float(r.get("ΔS_i"))
        if best is None or v > best:
            best = v
    # ★ max∅ = −∞（论文原式, 不是 0）
    return float("-inf") if best is None else float(best)


def liquidity_summary(liq, now_round: int, window: int) -> dict[str, Any]:
    """式11 的三个派生量（一次算齐, 供 ℬ_t/𝒯_t/ν_t 共用）。"""
    T = touched_from_liquidity(liq)
    return {
        "n_records": len(liq or []),
        "T_t": sorted(T),
        # ★★ 已被测过**且**增益>0 的组件（可留在候选集）
        "g_t": {c: gain(liq, c, now_round, window) for c in sorted(T)},
        # ★ 未被测过的组件按定义 g_t = −∞（式11 max∅）
        "unmeasured": None,
        "winners": sorted({r["ℓ_i"] for r in (liq or []) if r.get("a_i") == 1}),
        # ★ "admissible but lost"（过了门但输分）—— 论文说它**有用**
        "admissible_but_lost": sorted({
            r["h_i"] for r in (liq or [])
            if r.get("a_i") == 0 and r.get("h_i")}),
    }


# ═══════════════════════════════════════════════════════════
# ★★★★★ R46 · 多候选竞争 → 选赢家（RRSI **式13 line 8-15** 逐字）
#   论文原文:
#     P_t = {(Δ_j, a_j)}_{j=1..K}     ← K 个候选
#     for each: evaluate → Δ_in^(j), Δ_ho^(j)
#     if Δ_in ≥ 0 and Δ_ho ≥ 0 and max(...) > 0: Accept(Δ_j)   ← 通过门
#     a_i = 1 iff candidate was **selected as the winner of its round**
#     "Candidates that are **admissible but lose to a higher-scoring
#      admissible candidate** have a_i = 0"  ← 论文说这是**有用信息**
#
# ★★★★ R46 核出的**真缺口**（我 R45 指错了地方）:
#   · 我 R45 说「land 是 a_i=1 的本义」= **误读** —— 原文 a_i 在
#     「评估 + 判赢家」那一刻就定（接线点 window_settle 是对的）
#   · 真正缺的是: DWC 候选池**有**（`r_gen["candidates"]` 是 List）
#     但**评估/竞争/选赢家没接** ⇒ e2e 只 `for c in …: print`
#     ⇒ 于是 a_i 只能 = `verdict=="keep"`（**单候选近似**）
#     ⇒ "admissible but lost" 这一类**根本不可能出现**
#   ⇒ ⇒★ 本函数补上「竞争」这一步（纯排序, **不判分** ⇒ 不破三分离:
#        judge 判分 · evolver 生成 · applier 写读）
# ═══════════════════════════════════════════════════════════


def select_winner(evaluated) -> dict[str, Any]:
    """★★ 多候选竞争 —— 选赢家（式13 line 8-15 的排序步）。

    ★ 参数: `evaluated` = [(candidate, score, passed_gate: bool), …]
      · `score` 必须是 **judge 产出**的（本函数不判分 —— 三分离）
      · `passed_gate` = 是否通过非补偿门（Δ_in≥0 ∧ Δ_ho≥0 的结果）
    ★ 返回:
      · winner      —— 最高分**且过门**的那个（没过门的不许当赢家）
      · losers      —— "admissible but lost"（过门但分数更低, a_i=0）
      · rejected    —— 没过门的（**不进 ℒ_t** —— 论文: "candidates that
                       fail before a valid measurement is obtained" 被忽略）
      · n / n_gate  —— 总数 / 过门数（可复核）
    ★★★ 三条硬要求:
      ① **空池必须报错**（不许静默返回"没赢家" —— 那会假装竞争过）
      ② `score` 缺失/非数 ⇒ 报错（不许默认 0 —— 会让"没测"= "平分"）
      ③ 没有任何过门候选 ⇒ winner=None **且说清为什么**（不是空结果）
    """
    if not evaluated:
        raise ValueError(
            "★ 空候选池 —— 没有候选就没竞争过；"
            "不许返回空赢家（那等于假装这轮选过了）")
    # ② 分数必须是真值
    for i, row in enumerate(evaluated):
        if len(row) < 3:
            raise ValueError(
                "★ 第 %d 个候选缺字段（需 (candidate, score, passed_gate)）"
                % i)
        _cand, score, ok = row[0], row[1], row[2]
        if score is None or not isinstance(score, (int, float)):
            raise ValueError(
                "★ 第 %d 个候选的 score=%r 不是实测数 —— "
                "不许默认 0（会让「没测」变成「平分」）" % (i, score))
        if not isinstance(ok, bool):
            raise ValueError("★ passed_gate 必须是 bool, 实得 %r" % (ok,))
    gated = [r for r in evaluated if r[2]]        # 过门的
    rejected = [r for r in evaluated if not r[2]]  # 没过门 ⇒ 不进 ℒ_t
    if not gated:
        return {"winner": None, "losers": [], "rejected": rejected,
                "n": len(evaluated), "n_gate": 0,
                "why": ("★ %d 个候选**都没过门**（Δ_in/Δ_ho 或 max>0 "
                        "不满足）⇒ 无赢家, 且**都不进 ℒ_t**（论文: "
                        "fail before a valid measurement 被忽略）"
                        % len(evaluated))}
    # 过门的按分数降序（同分: 保持输入顺序 —— **稳定**, 不挑隐式偏好）
    order = sorted(gated, key=lambda r: -r[1])
    winner = order[0]
    losers = order[1:]                            # admissible but lost
    return {"winner": winner[0], "winner_score": winner[1],
            "losers": losers, "rejected": rejected,
            "n": len(evaluated), "n_gate": len(gated),
            "why": None,
            # ★ 可复核: 赢家与各落选者的分差
            "margin_vs_losers": [(l[1], winner[1] - l[1]) for l in losers]}


# ═══════════════════════════════════════════════════════════
# ★★★★★ R49 · 消费验证的**可测实现**（R47 的断言原本只活在 e2e 里）
#   ★ 问题: R47 我把「这条记录有没有被消费」写成 e2e 内联断言 ⇒
#     ① 验它要跑整条 e2e（80s × 破坏次数）
#     ② **R47 ③ 那条我连续两轮记着「验不出」**（竞争 ℓ 与结算 ℓ 同名
#       ⇒ 弱断言 `COMPETE_L in T_t` 与强断言 `d_i 指纹` **等价**）
#   ⇒ ⇒★ 现在抽成函数: 纯逻辑 ⇒ 可用 pytest 直接构造**同名碰撞**场景
#
# === 为什么 `ℓ_i` 弱、`d_i` 强（这次要验的核心）===
#   · `ℓ_i` = **component 名** ⇒ 两个不同来源的记录可能**同名**
#     （R47 实测: 竞争与结算**都是 control_flow**）
#   · `d_i` = 那条记录的 **diff 原文** ⇒ 唯一指纹
#   ⇒ 只按 ℓ_i 查 ⇒ **残留/别的来源的同名记录会冒充命中**（骗过断言）
# ═══════════════════════════════════════════════════════════


def liquidity_find(liq, **criteria) -> list[dict[str, Any]]:
    """按**字段精确匹配**查 ℒ_t 记录（消费验证用）。

    ★ 参数: `criteria` = 字段名→期望值, 如 `d_i=..., t_i=1`
    ★ 返回: **全部**命中记录（不只第一条 —— 否则"多命中"看不出来）
    ★ 硬要求（每条都对应一个我犯过的坑）:
      ① criteria 为空 ⇒ **报错**（返回全部 = 等于没查, 会假绿）
      ② 字段名不存在 ⇒ **报错**（打错字段名静默返回空 ⇒ 假红,
         而假红会让人去改**对的**断言 ⇒ 修错方向）
      ③ 期望值为 None ⇒ 仍精确匹配（不降级成"存在即可"）

    ★★★★ **别用 `ℓ_i=...` 作关键字实参**（R49 实测踩到, 守卫②抓的）:
      PEP 3131: Python 3 的标识符按 **NFKC** 规范化
      `ℓ`(U+2113 SCRIPT SMALL L) 的 NFKC = `l`(U+006C)
      · `liquidity_find(recs, ℓ_i="x")` ⇒ kwarg 名被归一成 `l_i`
      · 而记录里的**字符串键**是 `"ℓ_i"`（不归一化）
      ⇒ 二者永不匹配 ⇒ **必报字段名错**
      ⇒ 正确写法: `liquidity_find(recs, **{"\u2113_i": "x"})`（字符串形式）
      ★ 而守卫②**没静默返回空**, 报了错 —— 否则假红会让人去改
        **对的**断言（修错方向）。这正是②存在的理由。
    """
    if not criteria:
        raise ValueError(
            "★ liquidity_find 必须给至少一个条件 —— 无条件返回全部 = "
            "没查（那会让『消费验证』假绿）")
    if liq is None:
        liq = []
    # ② 先看有没有记录**带**这些字段（没有 ⇒ 字段名打错了）
    all_fields = set()
    for r in liq:
        if isinstance(r, dict):
            all_fields.update(r.keys())
    unknown = [k for k in criteria if k not in all_fields]
    if unknown and liq:
        raise ValueError(
            "★ ℒ_t 记录里**没有**字段 %s（已知字段: %s）—— "
            "字段名打错了 ⇒ 空结果是假红, 会让人去改对的断言"
            % (unknown, sorted(all_fields)))
    out = []
    for r in liq:
        if not isinstance(r, dict):
            continue
        if all(r.get(k) == v for k, v in criteria.items()):
            out.append(r)
    return out


def touched_components(accepted_rules) -> frozenset:
    """𝒯_t 的**近似** —— 已留下采纳记录的组件集合。

    ★★ 与论文的差异（必须说清，不许当真 ℒ_t 用）:
      论文 𝒯_t 来自 ℒ_t（每次 measured edit 的 (t, ℓ, …) 三元日志）
      ⇒ DWC **没有** ℒ_t（chain 无 change 写入）
      ⇒ 本函数退而用"已固化规则的 component 集"
      ⇒⇒ 语义差: 论文的 𝒯_t 记**每次**尝试，本近似只记**成功的**
      ⇒ ⇒★ 后果: 试过但没采纳的组件会被算作"未探索"（偏乐观）
    """
    return frozenset(
        str((r or {}).get("component") or "")
        for r in (accepted_rules or []) if (r or {}).get("component"))


def unexplored_components(accepted_rules, liquidity=None) -> frozenset:
    """𝒰_t = (𝒦 ∪ 𝒦_meta_editable) ∖ 𝒯_t（式8 + DWC §四④）。

    ★ K6 判据的实现处: 探索**必须**含 𝒦_meta_editable，
      否则架构层永不被探索（文档 §四④ 原话）
    """
    # ★★ R50: 加 `liquidity` 参数（**真源优先**）—— 与 R45 的
    #   `prune_targets(liquidity=)` **对齐**
    #   ★ 我 R45 给 prune_targets 加了真源, 却漏了这个同族接口
    #   ⇒ 两处一个用真、一个用近似 = **同一个 𝒯_t 两种算法**
    #   ⇒⇒ ★ 正是 R39 我记的「一个判据不许散多处」的新变体
    if liquidity:
        return editable_vocab() - touched_from_liquidity(liquidity)
    return editable_vocab() - touched_components(accepted_rules)


# ═══════════════════════════════════════════════════════════
# ★★★★ R41 · σ_t 停滞判据 + ℰ_t 三元（论文**伪码 line 6/9**，逐字核）
#   6: σ_t ← 1[Ŝ_t − Ŝ_{t−w} ≤ δ]     ← progress **未超过**噪声带
#   9: ℰ_t ← (σ_t, 𝒰_t, m_draft)       ← 停滞才**激活**探索
#   论文原文: 「We treat the search as **stalled** when its progress
#     over the previous w rounds remains within the empirical noise band δ.
#     During a stall, a small portion of the proposal budget is **reserved**
#     for components that have not yet been exercised」
#
# ★★★★ 参数 w/δ **不由我定死**（A11 死判据的教训: 定一个拍脑袋的常数
#   ⇒ 死判据）。⇒ 本函数要求**显式传入**，并返回"依据"（可复核）。
#   ★ δ 是「empirical noise band」= **实测得来**的（论文措辞），
#     ⇒ ⇒★ 正确做法是先量噪声带再定 δ —— 现在没量 ⇒ 调用方必须自己给，
#     这里只负责算判据 + 把依据留痕。
#   ★ ★☆ 与 R40 的关系: B（窗口聚合 g_t）**依赖** ℒ_t + 组件级归因
#     ⇒ 归因是**新设计问题**（哪个组件产生多少增益），未裁决前不实现
#     ⇒ σ_t 不依赖归因（只看整体分数史）⇒ 先做它
# ═══════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════
# ★★★★★ R50 · 噪声带 δ 的**实测**取值（我 R41 拒拍脑袋 ⇒ 现在量了）
#   ★ 我 R41/R42 的纪律: w/δ **无默认值**（A11 死判据教训）——
#     但那只是"不许猜", **从没跑过真数据去定它** ⇒ σ_t 一直空转
#
# === R50 实测（三组）===
#   ① 同实现重复判分 5 次: [0.0×5] · **标准差 0.0**
#      ⇒ 判分是**确定性**的（judge 零随机源: random/shuffle/seed 全 0 次）
#      ⇒ 判分噪声 = 0
#   ② 候选池分数: {0.0, 1.0} ⇒ **Δ ∈ {−1, 0, 1}**（二值粒度）
#   ③ δ 可行域（w=1 逐个跑 stall_signal）:
#        序列       δ=0.0   δ=0.5   δ=1.0
#        涨(0→1)      0        0        1   ← δ≥1 后"涨"也算停滞 ⇒ 退化
#        平(1→1)      1        1        1
#        跌(1→0)      1        1        1
#        抖(0/1/0/1)  0        0        1
#
# === 结论（**实测推导**, 不是拍脑袋）===
#   · δ ∈ [0, 1) 全部**等价于 0**（Δ 只取整数 ⇒ 小数带无调节作用）
#   · δ ≥ 1 ⇒ σ **恒 1**（连"涨"都算停滞）⇒ 违背 σ 的本义
#     （式13: 仅停滞时把预算留给未探索组件 ⇒ 恒激活 = 这个信号没用）
#   ⇒ ⇒★ R50 结论: 0.0 是唯一非退化值（**二值粒度下**成立 —— R54 改
#     k/n 粒度后**已作废**, 现行 δ 见下方 NOISE_DELTA 定义 + noise_delta()）
#
# ★★★ 而这暴露**真问题**: 分数粒度 = 二值 ⇒ δ 没有调节空间
#   —— 与 R41 裁决 A 的「量化阶梯」**同一根因**
#   ⇒ 要让 δ 有意义 ⇒ 需要**细粒度分数**（如多任务 pass_rate = k/n）
#   ⇒ 那是**设计问题** —— ★已解决: R54 用户裁决「选甲」⇒ pass_rate=k/n
#     ⇒ R57 三区实测出调节区间 (0.111, 0.222] ⇒ R58 用户拍板 δ=0.15
#     （本常量现行值, 依据见 noise_delta()["basis"]）
#
# ★ w（回看几轮）**不在这里定**: 它是**业务语义**（"几轮没涨算停滞"），
#   不是数据能推的 ⇒ 仍须显式给（保持 R41 的硬要求 ①）
# ═══════════════════════════════════════════════════════════

#: ★ R58 拍板值 δ=0.15 —— 依据链: R54 甲案粒度(k/n) → R57 三区实测
#:   （调节区间 (0.111, 0.222]）→ 用户 2026-10-08 拍板选项②
#:   ★ 前提: **分数粒度 = k/n over checks**（R54 甲案）
#:   ⇒ 粒度一变（换判据/改 check 数口径）这个值**必须重测**, 别照抄
NOISE_DELTA = 0.15


def noise_delta() -> float:
    """★ 取实测噪声带 δ（返回常量, 但**带出依据**让调用方可复核）。

    ★ 为什么给函数而不只是常量:
      调用方 `stall_signal(hist, w, NOISE_DELTA)` 拿到的是个裸常量 ——
      **看不出它是实测的还是拍的**（我 A11 踩过"死判据"）
    ★ 返回 {"delta": 当前拍板 δ, "basis": 依据链, "precondition": 粒度前提}
    """
    return {
        "delta": NOISE_DELTA,
        "basis": (
            '★ 拍板链 R54→R57→R58: ① 判分仍确定性(重复 5 次 std=0.0) ⇒ 噪声=0 · ② 分数=k/n over checks(R54 甲案, 11 task/26 check, 单 task n∈{1..4}) · ③ R57 三区实测(真实 e2e 序列, Δ 档位 {+0.1111,+0.2222,−0.2222}): δ∈[0,0.111] 最严格 · δ∈(0.111,0.222] **容忍微涨+拒绝大涨**(唯一有调节作用 ⇒ 推荐区间) · δ>0.222 退化(恒 1) · ④ 用户 2026-10-08 **拍板 δ=0.15**(选项②, 落在调节区) ★ 数据锚点: 聚合步长 1/Σn(e2e 现 6 check ⇒ ≈0.167) ⇒ δ=0.15 < 0.167 仍能分辨单个 check 变化'),
        "precondition": (
            '★ 分数口径 = **k/n over checks**(R54 甲案) —— 再改粒度(换判据/改 check 数口径) ⇒ **必须再重测** · ★★ R50 的二值结论(δ∈[0,1) 全等价)**已作废**, 别照抄'),
    }


def has_drop(scores) -> dict:
    """★★★★ R56 · 序列里**跌过吗**（单源 —— e2e 与 pytest 同一套）。

    ★ 为什么单独立: R55 我挑明「σ 没见过跌 ⇒ 那个语义就是没验过」
      ⇒ ⇒★ 「跌过」与「涨过」是**两个不同判据**（natural_rise 只管涨）
      ⇒ 而我第一版把「跌过」内联在 e2e 里 ⇒ **pytest 验不到** ⇒ 破坏
        ④⑤ 直接去掉断言**没红**（我验错了方向, 但根因是判据没单源）

    返回: {ok, n_drops, first_drop, drops, precondition, reasons}
      ★ 前置: ≥2 个分数（同 natural_rise）—— 不足 ⇒ precondition=False
    """
    scores = list(scores or [])
    if len(scores) < 2:
        return {"ok": None, "precondition": False, "n_drops": 0,
                "drops": [], "reasons":
                ["数据不足: 需 ≥2 个分数, 实得 %d 个" % len(scores)]}
    drops = [k for k in range(1, len(scores)) if scores[k] < scores[k - 1]]
    out = {"ok": bool(drops), "precondition": True, "n_drops": len(drops),
           "drops": drops, "reasons": []}
    if not out["ok"]:
        out["reasons"].append(
            "序列**从未跌过** ⇒ 「跌 = 停滞」的 σ 语义**没被验**"
            "（分数只涨不跌 = 不是真演化）: %s"
            % [round(x, 4) for x in scores[:8]])
    else:
        out["first_drop"] = (scores[drops[0] - 1], scores[drops[0]])
    return out


def has_rise(scores) -> dict:
    """★ 序列里**涨过吗**（natural_rise 验「必须真涨且非构造」,
    这个只验「有涨」—— 两条断言的**前置不同**）。

    ★ R56: 我在 e2e 加「涨过」断言时与 natural_rise 混了 ——
      natural_rise 是**有 src 的完整判据**, 这个是**纯涨跌计数**。
    """
    scores = list(scores or [])
    if len(scores) < 2:
        return {"ok": None, "precondition": False, "n_rises": 0,
                "rises": [], "reasons":
                ["数据不足: 需 ≥2 个分数, 实得 %d 个" % len(scores)]}
    rises = [k for k in range(1, len(scores)) if scores[k] > scores[k - 1]]
    reasons = [] if rises else [
        "序列从未涨过（退化到不修了？）: %s" % [round(x, 4) for x in scores[:8]]]
    return {"ok": bool(rises), "precondition": True, "n_rises": len(rises),
            "rises": rises, "reasons": reasons}


def natural_rise(scores, srcs=None) -> dict:
    """★★★★★ R55 · 验序列**自然涨过**（不是构造的）—— 判据单源。

    ★ 背景: R51/R54 我一直在**构造**波动（轮换 base/cur 二值、与上轮
      同分才轮换）⇒⇒ ★ 那分数是**编排出来的**, 不是**演化出来的**
      ⇒ 这条把「必须真涨过」变成**可测函数**（e2e 与 pytest 同源）

    硬要求（每条对应一个我犯过的错）:
      ① 至少一次**严格上涨**（否则 = 从未涨过, 恒定/单调降）
      ② 上涨那次的 `src` 不许含「构造对照」（不能是轮换造的）
      ③ 分数**不许恒定**（恒定 = 细粒度没在演化中用上, R54 边界①）
      ④ `srcs` 缺省 ⇒ 只验 ①③（**不能**因为没 src 就放过 ② ——
        那是「验不了就不验」的偷懒 ⇒ 显式标 `src_checked=False`）

    返回: {ok, risen, first_rise(from,to), n_rises, reasons[]}
    """
    reasons = []
    scores = list(scores or [])
    # ★★★★ R56 · **数据不足 ≠ fail**（同 σ_t 的「历史不足不判」）
    #   ⇒ 首轮只有 1 个分数 ⇒ 没法判「有没有涨」⇒ 那是**前置不满足**
    #   ⇒⇒ ★ 若当 fail, 清历史后第一轮必红（= 拿「还没数据」当失败）
    #   ⇒ 返回 `precondition=False` 让调用方**分开处理**（不许当 ok 用）
    if len(scores) < 2:
        return {"ok": None, "precondition": False,
                "reasons": ["数据不足: 需 ≥2 个分数才有『涨』可判, 实得 %d 个"
                            % len(scores)],
                "risen": [], "n_rises": 0, "src_checked": bool(srcs)}
    risen = [k for k in range(1, len(scores) if not srcs else len(scores))
             if k < len(scores) and scores[k] > scores[k - 1]]
    if not risen:
        reasons.append("序列从未自然涨过: %s" % ["%.4f" % x for x in scores[:6]])
    if len(set(scores)) <= 1:
        # ★ 单点已被上面的前置挡住 ⇒ 走到这里 = ≥2 个但全同 ⇒ **真恒定**
        reasons.append("分数恒定(%.4f) ⇒ 细粒度没在演化中用上" % scores[0])
    src_checked = bool(srcs)
    if srcs:
        srcs = list(srcs)
        # ★ 只对**最后一次**上涨查 src（第一次涨之后可能有新机制介入）
        if risen and "构造对照" in str(srcs[risen[-1]]):
            reasons.append("那次上涨是**构造**的(src=%s) — 要真演化"
                           % srcs[risen[-1]])
    out = {"ok": not reasons, "reasons": reasons, "risen": risen,
           "n_rises": len(risen), "src_checked": src_checked}
    if risen:
        out["first_rise"] = (scores[risen[0] - 1], scores[risen[0]])
    return out


def stall_signal(score_history, window: int, delta: float) -> dict[str, Any]:
    """★★ σ_t —— 搜索是否停滞（伪码 line 6 · 论文式13 的第一项）。

    ★ 参数:
      score_history  **按轮次升序**的整体分数序列 Ŝ（最近的在最后）
      window         w —— 回看几轮（论文 "previous w rounds"）
      delta          δ —— 噪声带（论文 "empirical noise band"）
    ★ 返回: {"sigma": 0/1, "now": Ŝ_t, "past": Ŝ_{t−w}, "delta": δ,
             "window": w, "basis": 可复核的算式}
    ★★ 三条硬要求:
      ① **不做任何默认 w/δ**（死判据教训 ⇒ 必须显式给）
      ② 数据不够 window+1 轮 ⇒ 返回 sigma=0 **并说清为什么**
        （不许用现有多短算多短 —— 那会让"只跑 1 轮"也算出 σ）
      ③ 边界: `Ŝ_t − Ŝ_{t−w} ≤ δ`（**≤**，论文原式）⇒ 停滞
    """
    h = list(score_history or [])
    if window < 0 or not isinstance(window, int):
        raise ValueError("★ window 必须是非负整数，实得 %r" % (window,))
    if not isinstance(delta, (int, float)) or delta < 0:
        raise ValueError("★ delta(δ) 必须是非负数，实得 %r" % (delta,))
    if len(h) < window + 1:
        # ★ 不许在数据不足时硬算（那是静默给个看似合理的 σ）
        return {"sigma": 0, "now": None, "past": None, "delta": delta,
                "window": window, "basis": None,
                "reason": ("★ 历史只有 %d 轮，不足以回看 w=%d "
                           "⇒ 不判（sigma=0 且不参与 ℰ_t 激活）"
                           % (len(h), window))}
    now, past = h[-1], h[-(window + 1)]
    delta_now = float(now) - float(past)
    sigma = 1 if delta_now <= float(delta) else 0
    return {"sigma": sigma, "now": now, "past": past, "delta": delta,
            "window": window, "delta_now": delta_now,
            # ★ 依据可复核: 拿它能自己重算一遍
            "basis": "Ŝ_t - Ŝ_{t-w} = %r - %r = %r, ≤ δ(%r) ? %s"
                     % (now, past, delta_now, delta, sigma == 1),
            "reason": None}


def exploration_signal(score_history, window, delta, accepted_rules,
                       draft: Any = None, liquidity=None) -> dict[str, Any]:
    """★★★ ℰ_t 三元 = (σ_t, 𝒰_t, m_draft)（伪码 line 9）。

    ★ 语义（论文原文）: **仅在停滞时**才把预算的一部分**保留给**
      「components that have not yet been exercised」
    ★ 返回:
      · active  —— 是否激活（= σ_t == 1，且 σ_t 有效）
      · sigma   —— σ_t 明细（含 basis，可复核）
      · unexplored —— 𝒰_t = (𝒦 ∪ 𝒦_meta_editable) ∖ 𝒯_t（K6）
      · draft   —— m_draft（本轮的探索草案位；没给就是 None）
      · ready   —— 三元是否**齐**（任一缺 ⇒ ℰ_t 不完整，不许当完整用）
    ★★★ 不许做的: σ_t 无效（历史不足）时**不许**返回 active=True
      ⇒ 那等于"数据不够就当停滞"（G7 静默跳过的同类）
    """
    st = stall_signal(score_history, window, delta)
    sigma_ok = "reason" not in st or st["reason"] is None
    sigma = st.get("sigma", 0)
    active = bool(sigma_ok and sigma == 1)
    # ★ R50: 真源优先（与 prune_targets 对齐）—— 近似仅 fallback
    U = unexplored_components(accepted_rules, liquidity=liquidity)
    ready = sigma_ok and draft is not None and bool(U)
    # ★ 为什么没激活 —— **分步算**（我第一版写成嵌套三元 ⇒ 括号不配、
    #   文件写坏了；教训: 复杂条件别塞进 dict 字面量）
    if active:
        why_inactive = None
    elif not sigma_ok:
        why_inactive = st.get("reason")
    else:
        why_inactive = st.get("reason")
        if why_inactive is None:
            why_inactive = (
                "σ_t=0（进展 %r > δ %r ⇒ **未停滞** ⇒ 不激活探索）"
                % (st.get("delta_now"), delta))
    return {"active": active, "sigma": st, "unexplored": sorted(U),
            "draft": draft, "ready": ready,
            # ★ 数据源可复核（否则看不出用真源还是近似）
            "T_source": ("liquidity(式11 真源)" if liquidity
                         else "近似(RULES component)"),
            "why_inactive": why_inactive}


def prune_blockers() -> list[str]:
    """★★★★ ℬ_t 的启用前提清单（**没满足就不许启用**）。

    ★ 依据: R40 实测的两个 blocker（见模块注释）
    ⇒ 返回空 = 可以启用；非空 = 每一条都是**硬阻塞**
    """
    out: list[str] = []
    # ① ★ R42 更新: ℒ_t **已实现**（`record_edit` 式10 七元）
    #   ⇒ blocker 从「不存在」变成「**没接线**」: 没有任何调用点在记它
    #   ⇒ ⇒★ 这是准确的降级 —— 有数据结构 ≠ 有数据
    wired = False
    try:
        # 查有没有调用点: 全库 search `record_edit(`
        for _fp in _glob4wired.glob(
                os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
                    __file__))), "**", "*.py"), recursive=True):
            if os.path.abspath(_fp) == os.path.abspath(__file__):
                continue
            if "record_edit(" in open(
                    _fp, encoding="utf-8", errors="replace").read():
                wired = True
                break
    except Exception:
        wired = False
    if not wired:
        out.append("ℒ_t **没接线**: 式10 的 `record_edit` 已实现但**无调用点**"
                   "（只有结构没数据）⇒ 𝒯_t/g_t 仍无真源（只有近似）")
    # ② ★ R44 更新: g_t 已实现 + 量化阶梯已由裁决 A 缓解 + **已接线**
    #   ⇒ 与 ① **同源同一个 wired 判定** —— 接线后**两条一起消失**
    #   ★★ R42 我把 ② 写成**无条件 append** ⇒ ① 清了 ② 还在（状态不一致）
    #     ⇒⇒ ⇒★ 教训: 同源的 blocker 必须**同一个开关**（否则会自相矛盾）
    if not wired:
        out.append("g_t(ℓ) 已实现（式11 max）但**没接线**（与 ① 同一缺口: "
                   "record_edit 无调用点 ⇒ 无真实 ΔS_i 记录）；"
                   "量化阶梯灾难已由裁决 A 缓解（`<0` 不误剪零增益）")
    return out


def prune_targets(accepted_rules, gains_by_component=None,
                  enabled: bool = False,
                  liquidity=None) -> dict[str, Any]:
    """★★★ ℬ_t = {ℓ ∈ 𝒯_t ∩ 𝒦_editable : g_t(ℓ) ≤ 0}（式14 + K5 交集）。

    ★ 三条硬要求（R40）:
      ① **交集** 𝒦_editable（K5: 用并集会把 evaluator/external_source
        也标成删除目标，而它们不可编辑 ⇒ 删除无法执行）
      ② `enabled=False` 时**返回 blockers 不返回目标**（不假装在跑）
      ③ 即便 enabled，gains 缺失也**不许用 0 充数**（那会全剪）
    """
    blockers = prune_blockers()
    if not enabled:
        return {"enabled": False, "targets": [], "blockers": blockers,
                "why": "ℬ_t 默认关闭 —— 前提未满足（见 blockers）"}
    if blockers:
        return {"enabled": False, "targets": [], "blockers": blockers,
                "why": "★ blockers 未清 ⇒ 不许启用（会误剪）"}
    if gains_by_component is None:
        # ★★★ 不许用 0 填 —— 量化阶梯下 0 就是"恒 ≤0" ⇒ 全剪
        raise ValueError(
            "★ ℬ_t 需要**组件级** gains（不是整体 gain）；"
            "不许用默认 0 —— 那会让 ℬ_t = 全部 𝒯_t（灾难性剪枝）")
    # ★★★★★ R45 · **𝒯_t 优先用真 ℒ_t**（我 R44 接线了但这里没用 ⇒
    #   e2e 实测 `pool=[]` 因为 `touched=∅` —— 字段不匹配:
    #   ℒ_t 是 `ℓ_i`, 而 `touched_components(accepted_rules)` 取 `component`
    #   ⇒⇒ ★ 也就是说: 消费方还在读**近似源**, 有真源却不用 = 假打通）
    #   ⇒ ⇒★ 现在: 传了 liquidity ⇒ 用式11 的 𝒯_t = {ℓ_i}
    #            没传 ⇒ 回落近似（RULES 的 component, docstring 已声明差异）
    if liquidity:
        T = touched_from_liquidity(liquidity)
        _t_src = "liquidity(式11 真源)"
    else:
        T = touched_components(accepted_rules)
        _t_src = "近似(RULES component)"
    # 交集（K5 关键）
    pool = T & editable_vocab()
    # ★★★★★ R41 **裁决 A**（用户拍板）: `g_t ≤ 0` → `g_t < 0`
    #   ⚠ 论文式14 原文是 `≤ 0`（"no strictly positive gain"）
    #     —— 本行**偏离原文**，是 DWC 针对量化阶梯的裁决:
    #     量化阶梯下 gain 恒 0（applier L43/46/47）⇒ 用 `≤ 0` 会把
    #     **所有被测组件全标成删除目标**（灾难性误剪）
    #   ⇒ ⇒★ `g = 0` 在本系统里 = 「卡在同一台阶」≠「无价值」
    #   ⇒ ⇒★ 代价（必须知道）: 平台期 gain=0 的组件**不再被剪**
    #     ⇒ 剪枝变保守（漏剪可接受，误剪不可接受）
    #   ★ 若将来量化阶梯被解决（换连续 scorer 或窗口聚合生效），
    #     应回到论文的 `≤ 0` —— 改回时**这条注释要一起改**
    targets = sorted(
        c for c in pool
        if float(gains_by_component.get(c, 0.0)) < 0.0)
    return {"enabled": True, "targets": targets, "blockers": [],
            "touched": sorted(T), "pool": sorted(pool),
            # ★ 数据源可复核（否则"用了哪个 𝒯_t"看不出来 —— G7 纪律）
            "T_source": _t_src,
            "gains": {c: gains_by_component.get(c) for c in sorted(pool)}}


def novelty_score(touched_components, accepted_rules) -> dict[str, int]:
    """★★★ ν_t —— 候选触到的、**从未被采纳过**的结构组件数（式16）。

    ★ 参数:
      touched_components  候选 H' 触到的组件集合 comp(H')
      accepted_rules      已采纳的规则条目（取其 component ⇒ N_t(ℓ)）
    ★ 返回: {"nu": ν_t, "new": 首次出现的组件列表, "n_t": N_t 快照}
    ★★★ 三条硬要求（否则 ν_t 会被刷）:
      ① 只有 `NOVELTY_ELIGIBLE` 里的组件**可能**拿分（式16 前提）
      ② `N_t(ℓ) = 0` 必须按**已采纳记录**算，不按"当前是否存在"
      ③ 新颖度只对**从未出现过的**计 1，同一候选碰多个只累加不重复
    """
    touched = set(touched_components or [])
    if not touched:
        return {"nu": 0, "new": [], "n_t": {}}
    # N_t(ℓ): 采纳记录里 component 的出现次数
    n_t: dict[str, int] = {}
    for r in (accepted_rules or []):
        c = str((r or {}).get("component") or "")
        if c:
            n_t[c] = n_t.get(c, 0) + 1
    # 只对 K_str ∪ {meta_evolution} 且 N_t=0 计分
    fresh = sorted(c for c in touched
                   if c in NOVELTY_ELIGIBLE and n_t.get(c, 0) == 0)
    return {"nu": len(fresh), "new": fresh,
            "n_t": {c: n_t.get(c, 0) for c in sorted(touched)}}


def check_component(component: str) -> list[str]:
    """★ R37 · component 合法性的**唯一入口**（两表都认）。

    ★★★ 为什么要有这个包装（而不是各处 `in COMPONENT_VOCAB`）:
      我 R37 同一轮里犯了**三处不同源**:
        ① prompt 给两表（模型真选了 `code`）
        ② 生成校验只认 𝒦 9 项 ⇒ **拒了合法组件**
        ③ 固化校验 `entry_from_candidate` 也只认 𝒦 ⇒ 同款拒
      ⇒⇒ ⇒★★ 「一个判据三个来源」= 必然漂移
        （同 R30 的 c/q 值域、R34 的 DIFF_FIELDS —— 我一再踩）
      ⇒ ⇒★ 收敛: 都走这里（`layer_of` 是真源，两表 + 词表外 raise）
    """
    try:
        layer_of(component)
    except ValueError as ex:
        return [str(ex)]
    return []


def check_pairing(component: str, target_layer: str) -> list[str]:
    """★★★ 判据 K2 · component_type 与 target_layer 必须一致。

    ★ 依据 §四①: 「两个字段必须一致: component_type ∈ 𝒦 ⇒ target_layer
      必为 assets；**不一致 ⇒ 声明与意图矛盾, 门应拒**」
    ★★ 文档内部编号有冲突（我**挑明不擅自改设计**）:
      §四① 那句写的是「判据 K3」，而 §五 判据列表里 **K2 才是**
      「component_type 与 target_layer 必须一致」
      ⇒ ⇒★ 本实现按 §五（判据**定义处**为准）
      ⇒ ⇒★ 若裁决为 K3，改一行常量即可（见 CHECK_ID）

    ★ 返回问题列表（[] = 通过）—— 与 `check_entry` 同口径
    """
    problems: list[str] = []
    try:
        want = layer_of(component)
    except ValueError as e:
        return [str(e)]
    if target_layer != want:
        problems.append(
            "★ K2: component=%r 应配 target_layer=%r，实得 %r"
            " ⇒ **声明与意图矛盾**（§四①）" % (component, want, target_layer))
    return problems


#: ★ 当前判据编号（文档冲突时的唯一改动点）
CHECK_ID = "K2"

#: ★★ 九维分类法（2606.14249 §3.3 原文）
DIMENSIONS = ("D1", "D2", "D3", "D4", "D5", "D6", "D7", "D8", "D9")

#: ★★ 提案状态（约束 1: 先过门再采纳 ⇒ 状态机而非一次性通过）
PROPOSAL_STATES = ("draft", "gated", "rejected", "adopted",
                   "adopted_not_implemented")

import hashlib
import json
import os
import sys
import time
from dataclasses import dataclass
from typing import Any

# ═══════════════════════════════════════════════════════════
# ★★★★ R37 · 种子迁移: 给**旧条目**补 target_layer
#   实测: 3 个种子条目 `target_layer=None`（它们写于 §四① 之前）
#   ⇒⇒ ⇒★ 而 schema 现在必填该字段 ⇒ 读到 None 就炸（跨进程那步）
#   ⇒ ⇒★ 用 `layer_of` 推（**不手填** —— 那是真值表，机械可推）
#   ⇒ 这是**数据迁移**，不是改设计
# ═══════════════════════════════════════════════════════════
#: ★★★ R37 · G7 抓到我在这写过 `except: pass`（同族第 N 次）
#:   ⇒⇒ 修法不是"加日志"，而是**先判词表再推**（消除异常路径）
#:     —— 比吞异常干净: 没有异常就没有静默
MIGRATE_SKIPPED: list[str] = []

def _migrate_target_layer(table: dict[str, dict[str, Any]]) -> int:
    n = 0
    for k, v in table.items():
        if v.get("target_layer"):
            continue
        comp = str(v.get("component") or "")
        # ★★★ R39 审计抓到: 这里原本展开写 `in COMPONENT_VOCAB or in K_META`
        #   = **第 8 个来源**（A1 门正是为抓它而写）
        #   ⇒ 收敛到 `check_component`（真源 = layer_of）
        if check_component(comp) == []:
            v["target_layer"] = layer_of(comp)
            n += 1
        else:
            # ★ 跳过也**留痕**（G7: 不许无痕跳过）—— 由 check_entry 报
            MIGRATE_SKIPPED.append("%s(component=%r)" % (k, comp))
    return n


class EvolverError(Exception):
    """违反 evolver 契约。★ 承重代码不许吞异常（判据 E2/E3）。"""


# ══════════════════════════════════════════════════════════
# 提案
# ══════════════════════════════════════════════════════════


@dataclass
class Proposal:
    """★ 一个候选变更（一处干预）。

    ★★★★ 约束 4 的落地: `target` + `patch` **只能有一处**
      ⇒ 若多处 ⇒ 任何测量都无法归因（2606.09498 原文）
      ⇒⇒ 所以我加了 `_assert_single_change()` 在构造时就拦

    ★★ 状态机（约束 1）:
      draft → gated（过门）→ rejected / adopted
      ★ adopted_not_implemented 是**第五态**（R14 引入）
        —— 「过了门但还没落地」必须与「已落地」区分
    """
    proposal_id: str
    #: ★ 由哪个失败签名驱动（可归因的锚点）
    failure_signature: dict[str, str]
    #: ★ 改什么（必须属 COMPONENT_VOCAB）
    component: str
    #: ★ 改哪里（唯一一处）
    target: str
    #: ★ 怎么改（可执行的表达式或代码）
    patch: str
    #: ★ 为什么这么改（依据 —— 不许"看着办"）
    rationale: str
    #: 结构型组件取新颖度奖励（式 15）
    #: ★★★★ R37 · §四① 第 2 个字段（**proposer 必须声明**）
    #:   component ∈ 𝒦 ⇒ assets · ∈ 𝒦_meta ⇒ architecture
    #:   ⇒⇒ 不一致 = 声明与意图矛盾（判据 K2）
    target_layer: str = ""
    #: ★ R338 · 原子算子（OpenRSI Draft/Improve/Debug/Crossover）——
    #:   训练与推理共用同一动作空间；propose 时显式声明。
    operator: str = "improve"
    is_structural: bool = False
    dimension: str | None = None
    #: ★ R78 批3-D（裁决②: 加）· 进化方向标注 —— 与 direction.EvolutionDirection
    #:   三成员语义表对齐（FORWARD/LATERAL/REVERSE）; None=未标注（合法 ——
    #:   多数提议不声明方向）。构造时经 ensure_direction 精确校验（非 None ⇒
    #:   拒 None 变体/大小写/未知值）。
    #:   ★ 诚实边界: **填值方（方向选择策略）无设计明文**（R73 裁定"无设计
    #:   不发明选择器"）—— 本字段先就位形态+校验, 选择策略落地时消费。
    direction: str | None = None
    #: ★ M1（设计稿③ §⑥ 路径乙 · 用户拍板"都做"）· 多改提案的归因计划:
    #:   带**合法** plan 的多处变更 = 放行（成员/预算/τ/同键不相交声明齐）;
    #:   无 plan 的多处变更 = 原 raise 照旧（路径甲单点零破坏）。
    #:   plan 缺字段/成员重复/τ 无校准注记 ⇒ 构造期 raise（与单点同款严厉）。
    attribution_plan: dict[str, Any] | None = None
    #: ★ R295-Task2 · LLM 写的完整可执行函数代码（code_repair 写码真执行；
    #:   None=没出码——trial 走老报数路，不废起草）。
    code: str | None = None

    state: str = "draft"
    gate_verdict: dict[str, Any] | None = None
    #: ★ 判分结果（由 judge 填，不由 evolver 填）
    verdict: dict[str, Any] | None = None
    created_at: float = 0.0

    def __post_init__(self):
        # ★★★ R37 · 第 5 个来源（prompt/生成/固化/schema/提案）
        #   我原来只查 COMPONENT_VOCAB ⇒ 已固化的 `code`(𝒦_meta)
        #   在**读取**这一步被拒 ⇒ e2e 跨进程那步炸
        #   ⇒⇒ ⇒★ 「一个判据五个来源」——本轮核心教训的完整形态
        _cc = check_component(str(self.component or ""))
        if _cc:
            raise EvolverError(
                "component=%r 不在 𝒦∪𝒦_meta 内（2609.24972 式12 ∪ "
                "COMPONENT_VOCABULARY §2.1）: %s"
                % (self.component, _cc[0][:70]))
        # ★ R438 · 只读组件必须在**构造时**就拒（G10 密封）
        #   现场：editable_vocab() 只用于新颖度候选池，从不做校验 ⇒
        #   直接构造 component='evaluator' 的 Proposal 会被**接受**
        #   ⇒ "不可编辑"只是文档承诺，不是代码事实。
        if str(self.component or "") not in editable_vocab():
            raise EvolverError(
                "component=%r 不可编辑（只读：评估器/训练桥；"
                "可编辑集=%r）" % (self.component,
                                   sorted(editable_vocab())))
        # ★★★★ K2: component ↔ target_layer 必须一致（§四①）
        #   ★★ R37 我第一版直接对 `target_layer=""` 跑 K2 ⇒
        #     所有**没声明**第 2 字段的构造全炸（19 个测试红）
        #     ⇒⇒ ⇒★ 而 §四① 的意图是查**矛盾**，不是查"空"
        #   ⇒ ⇒★ 分两段（与 propose() 同款兜底）:
        #     · 没声明 ⇒ 由 `layer_of` **推**（真值表，机械可推）
        #       ⇒ 这是"补全声明"，不是"替它决定"（值必然与 component 一致）
        #     · 声明了但矛盾 ⇒ **拒**（那才是真正的『说一套做一套』）
        if not str(self.target_layer or "").strip():
            self.target_layer = layer_of(str(self.component or ""))
        _pair = check_pairing(str(self.component or ""),
                              str(self.target_layer or ""))
        if _pair:
            raise EvolverError("K2 提案声明矛盾: " + _pair[0])
        if self.state not in PROPOSAL_STATES:
            raise EvolverError(
                "state=%r 不在 %r 内" % (self.state, list(PROPOSAL_STATES)))
        if self.dimension is not None and self.dimension not in DIMENSIONS:
            raise EvolverError(
                "dimension=%r 不在 %r 内（2606.14249 九维）"
                % (self.dimension, list(DIMENSIONS)))
        #: R78 批3-D · direction 精确校验（None 合法; 非 None 走 ensure_direction）
        if self.direction is not None:
            from dwc.organs.direction import ensure_direction
            self.direction = ensure_direction(self.direction)
        if not self.rationale.strip():
            raise EvolverError(
                "★ rationale 必填 —— 不许『看着办』"
                "（约束 4: 变更可归因 ⇒ 必须说清依据）")
        # ★★★ R44: 约束 4 的**实际**拦截（docstring 声称过但一直没实现）
        self._assert_single_change()
        self.is_structural = self.component in STRUCTURAL
        self.created_at = self.created_at or time.time()

    def _assert_single_change(self) -> None:
        """★★★★ R44 · 约束 4「一个提案只改一处」的**实际**实现。

        ★★ 声称 vs 实测（R44 核出）:
          docstring 原写「所以我**加了** `_assert_single_change()` 在构造时就拦」
          ⇒⇒ 而全库实测: **只有那句 docstring**（函数不存在）
          module docstring L34 也说「本模块硬性限制: 一个提案只改一处」
          ⇒⇒ ⇒★ 声称有、**实现 0** —— 约束 4 根本没被强制
          ⇒ 而它正是**归因的前提**（2606.09498: 「一簇对应一处干预」，
            若多处 ⇒ 任何测量都无法归因）
          ⇒ ⇒★ 所以接线 ℒ_t（R42）前必须先补它 —— 否则 ℒ_t 记的是
            「**假定**单变更」，归因是空的

        ★★★ 判据依据（**用实测数据定，不拍脑袋**）:
          · 实测 target 5 个全为**单标识/路径**（fibonacci / config/…/dev.json）
            ⇒ 多处的形态是: 含 `,` `;` 换行（多值/多语句/多目标）
          · 实测 patch 5 个全为**单行表达式**
            ⇒ 多处的形态是: 多个 `@@`（diff 多 hunk）
          ★★ **多行 patch 是合法的**（改一个函数的多行 = 还是**一处**）
            ⇒ 所以**不禁换行**，只禁「多个 diff 头」
        """
        t = str(self.target or "")
        p = str(self.patch or "")
        # ① 通用必填（两路径共用 — 语义与原判据同款）
        if not t.strip():
            raise EvolverError("★ target 必填（单变更约束: 得有个确定的目标）")
        if not p.strip():
            raise EvolverError("★ patch 必填 —— 空 patch = 没有干预")
        # ★★★ M1 路径乙（设计稿③ §⑥）: 合法 attribution_plan ⇒ 放行多处
        #   —— 单点纪律**升级**为归因纪律, 不是废除: 多改必须带消融账,
        #   缺 plan 的多处仍走下方路径甲原判据（零回退）
        if self.attribution_plan is not None:
            self._validate_attribution_plan()
            return
        # ── 路径甲（现状原样 — 单处形态判据, 全部消息不变）──
        for sep, what in ((",", "多个目标(逗号分隔)"), (";", "多条语句(分号)")):
            if sep in t:
                raise EvolverError(
                    "★ 约束 4: target 含 %s = **多处变更** (%r) ⇒ 无法归因 "
                    "（2606.09498「一簇对应一处干预」）" % (what, t[:50]))
        if "\n" in t or "\r" in t:
            raise EvolverError(
                "★ 约束 4: target 含换行 = 指向多处 (%r)" % t[:50])
        # ② patch: 多个 diff 头 = 多 hunk（多处）；**多行本身合法**
        n_hunks = p.count("@@")
        if n_hunks > 1:
            raise EvolverError(
                "★ 约束 4: patch 含 %d 个 `@@`(多 hunk) = **多处变更** "
                "⇒ 测量无法归因；一处干预只需一个 hunk" % n_hunks)
        # ③ 空 patch 判据已提前至通用必填段（M1 重排, 消息不变）

    def _validate_attribution_plan(self) -> None:
        """★★★ M1 · 路径乙的牙齿（设计稿③ §⑥ attribution_plan 四字段）。

        members=键域清单(唯一 ⇒ 同键冲突构造期拒, 稿§⑦) · ablation_budget
        (n_runs≥1 且成本入账) · tau>0 + calibration_note 必填（τ 初值待校准
        的诚实位）· fork_rule 必填（可加性/交互的分流去向声明）。
        """
        plan = self.attribution_plan
        if not isinstance(plan, dict):
            raise EvolverError(
                "★ attribution_plan 必须 dict, 实为 %r" % type(plan))
        members = plan.get("members")
        if not (isinstance(members, list) and len(members) >= 2
                and all(isinstance(x, str) and x.strip() for x in members)):
            raise EvolverError(
                "★ plan.members 须为 ≥2 个非空键域清单, 实为 %r" % (members,))
        if len(set(members)) != len(members):
            raise EvolverError(
                "★ plan.members 含重复键域 %r — 同键冲突不可消融"
                "（稿§⑦ keys(A)∩keys(B)=∅ 的成员层表达）" % (members,))
        budget = plan.get("ablation_budget")
        if not isinstance(budget, dict) or not (
                isinstance(budget.get("n_runs"), int)
                and budget["n_runs"] >= 1):
            raise EvolverError(
                "★ plan.ablation_budget.n_runs 须 ≥1 int（消融预算必须声明）"
                ", 实为 %r" % (budget,))
        if not budget.get("cost_to_ledger"):
            raise EvolverError(
                "★ plan.ablation_budget.cost_to_ledger 必须 true"
                "（§3.6.5 评估成本入预算 — CostLedger 记账）")
        tau = plan.get("tau")
        if not (isinstance(tau, (int, float)) and not isinstance(tau, bool)
                and tau > 0):
            raise EvolverError("★ plan.tau 须 >0 数值, 实为 %r" % (tau,))
        if not str(plan.get("calibration_note") or "").strip():
            raise EvolverError(
                "★ plan.calibration_note 必填（τ 初值来源诚实位 — "
                "无明文不发明, 初值须注明）")
        if not str(plan.get("fork_rule") or "").strip():
            raise EvolverError(
                "★ plan.fork_rule 必填（|I|<τ 可加拆分 / ≥τ 整体归档的"
                " 分流去向 — 稿§④ τ 分流）")

    def key(self) -> str:
        """★ 提案指纹（去重 + 可归因）。"""
        blob = "%s|%s|%s|%s" % (self.component, self.target,
                               self.patch, json.dumps(
                                   self.failure_signature, sort_keys=True))
        return hashlib.sha256(blob.encode()).hexdigest()[:16]

    def to_dict(self) -> dict[str, Any]:
        d = dict(self.__dict__)
        d["key"] = self.key()
        return d


# ══════════════════════════════════════════════════════════
# 失败签名 → 提案的映射表
# ══════════════════════════════════════════════════════════


class Mutator:
    """★ 变异器：失败签名 → 候选实现。

    ★★ 为什么第一版是**确定性**的（不是 LLM）:
      · 可验证性不该依赖 LLM（而 judge 的存在正是为了判分可信）
      · 且确定性变异能让"同一个失败 → 同一个提案"可复现
      ⇒⇒ ⇒★ LLM 版留作可插拔的第二个 Mutator（诚实边界④）
    """

    #: ★ 查询键 = **(c, q, fn)** → 提案
#:   · c/q 是原文三元组的前两段（规则填）
#:   · ★★ **fn 是定位维度** —— 不在三元组里!
#:     三元组是聚类语义（什么失败/什么行为/什么机制），
#:     而"要改哪个函数"是定位 ⇒ 必须显式在键里
#:   · m 由**条目产出**（R30 结构修正: m 不能是查询输入）
    #:
    #: ★★ 这里刻意做成**数据**而不是代码 —— 因为
    #:   「失败签名 → 该改哪」这条映射本身就是假设，
    #:   把它写成数据就能被门检查、能被测试、能被审计

    # ══════════════════════════════════════════════════════
    # ★★★ R32 · 固化（把验证过的候选写进 RULES）
    #   依据: 2606.09498 §3.4（旧注"Algorithm 1 line 23"系假精确，
    #   论文无 Algorithm 1——R300 论文深读修正）
    #     `merged into the next version of the harness` —— 通过才**合并进主干**
    #   ⇒⇒ ⇒★ 位置: **在候选副本上评估通过之后**
    #   ⇒⇒ ⇒★★ 于是 R31 的学习成果才能**累积**（否则每次重试）
    # ══════════════════════════════════════════════════════

    #: ★ 条目的**必填**字段（propose 用下标读 ⇒ 缺了就 KeyError）
    #:   ⇒ 固化前必须校验，否则固化一条坏规则会炸在**查表那一刻**
    RULE_ENTRY_FIELDS = ("component", "dimension", "target_layer", "target",
                         "m", "m_source", "patch", "rationale")

    #: ★ 允许的 component（RRSI 式12 词表）—— 与 Proposal 校验同源
    #: ★★★ R32 · **学到的**规则的落盘位置
    #   ⇒ 种子（代码里那 3 条，人工写的）留在 evolver.py —— 可被门/评审管
    #   ⇒ 而**固化产生的**规则落盘 —— 否则进程结束就丢
    #   ⇒⇒ ⇒★ 分开放的理由: 代码改动要走评审（G5），
    #     落盘的是**系统自己学的**（要能持久，且不改代码）
    LEARNED_PATH = os.environ.get("DWC_LEARNED_PATH") or os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))))),
        "config", "anchors", "rules.json")

    #: ★ 种子键（**代码里定义的**）—— persist 时排除它们
    SEED_KEYS: frozenset = frozenset()

    #: ★ R审计-P1 · G7 静默门：_carry 坏 key 降级的可观测计数
    _SILENT_CARRY: int = 0

    @classmethod
    def load_learned(cls) -> int:
        """★ 把**落盘学到的**规则合并进 RULES（进程启动时调）。

        ★ 返回合并条数；文件不存在 ⇒ 0（**不报错** —— 没学到过是常态）
        ★★★ 合并而非替换: 种子（代码）与学到的（落盘）必须并存
        """
        try:
            with open(cls.LEARNED_PATH, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            return 0
        n = 0
        for k, v in (data.get("learned") or {}).items():
            if k not in cls.RULES and isinstance(v, dict):
                cls.RULES[k] = v
                n += 1
        return n

    @classmethod
    def persist_learned(cls) -> dict[str, Any]:
        """★★★ 把 RULES 里**非种子**的条目写盘（固化后的持久化）。

        ★ 只写「学到的」⇒ 种子不进 json（否则代码与 json **双源**）
        ★ 返回 {path, n_written, n_seed} —— 可审计
        """
        learned = {k: v for k, v in cls.RULES.items()
                   if k not in cls.SEED_KEYS}
        os.makedirs(os.path.dirname(cls.LEARNED_PATH), exist_ok=True)
        payload = {
            "_provenance": {
                "why": ("★ R32: 2606.09498 §3.4 非回归合并 —— "
                        "通过才合并进主干；而『合并』必须**跨进程存活**"),
                "seed_location": ("src/dwc/organs/evolver.py 的 "
                                  "Mutator.RULES（人工写，可评审）"),
                "★ 分流": ("种子留代码 · 学到的落盘 —— "
                       "否则代码与 json **双源**，或学到的随进程消失"),
            },
            "_version": "R333",
            "_content_hash": Mutator._state_hash(learned),
            "learned": learned,
        }
        with open(cls.LEARNED_PATH, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=1)
        return {"path": cls.LEARNED_PATH, "n_written": len(learned),
                "n_seed": len(cls.SEED_KEYS),
                "version": "R333",
                "content_hash": Mutator._state_hash(learned)}

    # ★ C2 · carried 率计数（companion Eq.11 activation 第三级：被后轮
    #   propose 引用次数）。种子进程内有效（重启归零 —— persist 只写非种
    #   子）；learned 随落盘跨重启累计。计数永不断提案主路（脏 key 跳过）。
    @classmethod
    def _carry(cls, key: str) -> None:
        try:
            _r = cls.RULES.get(key)
            if isinstance(_r, dict):
                _r["carried"] = int(_r.get("carried", 0) or 0) + 1
        except (TypeError, ValueError):
            # ★ R审计-P1 · G7 静默门：坏 key 计数必须可观测（不许 except: pass）
            cls._SILENT_CARRY += 1

    # ★ C1 · ARCHIVE 中间态（多版本并存；RULES 仍单条目）。
    ARCHIVE: dict[str, list] = {}
    # ★ R346 · Raven Gene Bank：quality-diversity，cell=(edit_cat, pathology) → elite。
    GENE_BANK: dict[str, Any] = {}
    # ★ R350 · DWC-internal skill system（不依赖 Hermes）。
    SKILLS: dict[str, dict[str, Any]] = {}

    @staticmethod
    def cell_of(entry: dict[str, Any]) -> str:
        _ec = (entry or {}).get("target_layer") or "runtime"
        _task = (entry or {}).get("task") or (entry or {}).get(
            "failure_signature", {}).get("task", "")
        _path = str(_task).split("_")[0] if _task else "unknown"
        return "%s|%s" % (_ec, _path)

    @staticmethod
    def gene_bank_update(cell: str, entry: dict[str, Any]) -> None:
        try:
            _cur = Mutator.GENE_BANK.get(cell)
            _score = (entry or {}).get("in_score")
            if _cur is None or (_score is not None and
                                 (_cur.get("in_score") is None or
                                  _score > _cur.get("in_score"))):
                Mutator.GENE_BANK[cell] = {
                    **dict(entry or {}),
                    # ★ R351 · Evo² donor strategy fields
                    "mechanism": (entry or {}).get("mechanism", ""),
                    "observed_effect": (entry or {}).get("in_score", 0) -
                                       (entry or {}).get("baseline_in", 0),
                    "presence": (entry or {}).get("presence", False),
                }
        except Exception:  # noqa: BLE001 — 坏不断主路
            pass

    @staticmethod
    def select_donor(task: str, gene_bank=None) -> dict[str, Any] | None:
        """★ R351 · Evo² crossover: 从 donor library 选 strategy。"""
        try:
            _gb = gene_bank if gene_bank is not None else Mutator.GENE_BANK
            _fam = str(task).split("_")[0] if task else ""
            _best = None
            for _cell, _entry in (_gb or {}).items():
                if _fam and _fam not in str(_cell):
                    continue
                if _best is None or (_entry.get("observed_effect", 0) or 0) > (
                        _best.get("observed_effect", 0) or 0):
                    _best = _entry
            if _best is None:
                return None
            return dict(_best)
        except Exception:  # noqa: BLE001 — 坏不断主路
            return None

    @staticmethod
    def skill_register(name: str, description: str = "", content: str = "",
                       trigger: str = "") -> dict[str, Any]:
        try:
            _cur = Mutator.SKILLS.get(name)
            _ver = 1 if _cur is None else int(_cur.get("version", 0)) + 1
            Mutator.SKILLS[name] = {
                "name": name,
                "description": description,
                "content": content,
                "trigger": trigger or name.split("_")[0],
                "version": _ver,
            }
            # ★ R438 · 落盘（改前只在进程内 dict ⇒ 重启即失，且无消费者）
            _path = ""
            try:
                from dwc.organs import skill_store as _SS
                _saved = _SS.save(name, description=description,
                                  content=content,
                                  trigger=(trigger or name.split("_")[0]),
                                  version=_ver)
                _path = _saved["path"]
                Mutator.SKILLS[name]["path"] = _path
            except Exception as _se:  # noqa: BLE001 — 落盘坏不掀主路，但留痕
                import sys as _s
                _s.stderr.write("skill 落盘失败 %s: %r\n" % (name, _se))
            return {"registered": True, "name": name, "version": _ver,
                    "path": _path}
        except Exception as _e:  # noqa: BLE001 — 坏不断主路（留痕）
            import sys as _s
            _s.stderr.write("skill_register 失败 %s: %r\n" % (name, _e))
            return {"registered": False, "name": name}

    @staticmethod
    def skill_select(task: str) -> dict[str, Any] | None:
        try:
            _fam = str(task).split("_")[0] if task else ""
            _best = None
            for _s in (Mutator.SKILLS or {}).values():
                if _fam and str(_s.get("trigger", "")).startswith(_fam):
                    if _best is None or int(_s.get("version", 0)) > int(_best.get("version", 0)):
                        _best = _s
            return _best
        except Exception:  # noqa: BLE001 — 坏不断主路
            return None

    @staticmethod
    def skill_evolve_from_sig(sig: dict[str, Any], patch: str = "",
                             rationale: str = "") -> dict[str, Any]:
        try:
            _task = (sig or {}).get("task", "")
            _name = "skill_%s" % (_task or "unknown")
            _content = (rationale or "") + "\n" + (patch or "")
            return Mutator.skill_register(
                _name, description="evolved from %s" % _task,
                content=_content, trigger=_task.split("_")[0] if _task else "")
        except Exception:  # noqa: BLE001 — 坏不断主路
            return {"registered": False, "name": _name if "_name" in locals() else ""}


    @staticmethod
    def reconstruct_context(task: str) -> str:
        """★ R349 · Reconstructive retrieval."""
        try:
            _fam = str(task).split("_")[0] if task else ""
            _lines = []
            for _key, _lst in (Mutator.ARCHIVE or {}).items():
                for _e in (_lst or []):
                    _t = (_e or {}).get("task", "")
                    if _fam and not str(_t).startswith(_fam):
                        continue
                    _succ = (_e or {}).get("success")
                    _partial = (_e or {}).get("partial")
                    _patch = (_e or {}).get("patch", "")
                    _patch = (_patch or "")[:120]
                    _lines.append("  - task=%s success=%s partial=%s patch=%s"
                                  % (_t, _succ, _partial, _patch))
            if not _lines:
                return ""
            return ("Reconstructed history (family=%s, n=%d):\n%s"
                    % (_fam, len(_lines), "\n".join(_lines[:20])))
        except Exception:  # noqa: BLE001 — 坏不断主路
            return ""


    # ★ N3 · archive 持久化路径（与 LEARNED_PATH 同族 —— 跨进程存活）。
    ARCHIVE_PATH = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))))),
        "config", "anchors", "archive.json")

    @classmethod
    def bootstrap_state(cls) -> dict[str, int]:
        """★ R333 · 启动接线：把落盘 learned + archive 合并进内存。"""
        return {"learned_loaded": cls.load_learned(),
                "archive_loaded": cls.load_archive()}

    @staticmethod
    def _state_hash(payload: Any) -> str:
        """★ R333 · 持久化产物的内容指纹（可审计 state inheritance）。"""
        import hashlib
        blob = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:12]

    @classmethod
    def load_archive(cls) -> int:
        """★ 把落盘 archive 合并进 ARCHIVE（进程启动时调）。

        ★ 文件不存在 ⇒ 0（没 archive 过是常态）；合并而非替换。
        """
        try:
            with open(cls.ARCHIVE_PATH, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            return 0
        n = 0
        for k, v in (data.get("archive") or {}).items():
            if isinstance(v, list):
                cls.ARCHIVE.setdefault(k, []).extend(v)
                n += len(v)
        return n

    @classmethod
    def persist_archive(cls) -> dict[str, Any]:
        """★ 把 ARCHIVE 全量写盘（archive ≠ adopt，落盘供后搜）。

        ★ 返回 {path, n_written}。
        """
        os.makedirs(os.path.dirname(cls.ARCHIVE_PATH), exist_ok=True)
        payload = {"_version": "R333",
                   "_content_hash": Mutator._state_hash(cls.ARCHIVE),
                   "archive": cls.ARCHIVE}
        with open(cls.ARCHIVE_PATH, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=1)
        return {"path": cls.ARCHIVE_PATH,
                "n_written": sum(len(v) for v in cls.ARCHIVE.values()),
                "version": "R333",
                "content_hash": Mutator._state_hash(cls.ARCHIVE)}

    @classmethod
    def select_parent(cls, key: str, strategy: str = "latest") -> dict[str, Any] | None:
        """★ N3 · parent 选择器（多版本 archive ⇒ 选一）。

        ★ strategy:
          - "latest"（默认）：最后追加的版本（版本号最大）；
          - "first"：最早版本。
          - "best"：in_score 最高；
          - "worst"：in_score 最低（U-shaped 采样用）。
        ★ 空 archive ⇒ None（诚实缺席，不编）。
        """
        _lst = cls.ARCHIVE.get(key) or []
        if not _lst:
            return None
        if strategy == "first":
            return dict(_lst[0])
        if strategy == "best":
            return dict(max(_lst, key=lambda e: (e or {}).get("in_score") or 0))
        if strategy == "worst":
            return dict(min(_lst, key=lambda e: (e or {}).get("in_score") or 0))
        return dict(_lst[-1])

    @staticmethod
    def ushape_weight(entry: dict[str, Any], eps: float = 0.05) -> float:
        """★ R353 · Evo² U-shaped: w(h)=ε+|V̂-1/2|。"""
        _v = (entry or {}).get("in_score")
        if _v is None:
            _v = 0.5
        try:
            return float(eps) + abs(float(_v) - 0.5)
        except (TypeError, ValueError):
            return float(eps)

    @classmethod
    def promote_archived(cls, key: str, strategy: str = "latest") -> dict[str, Any]:
        """★ N3 · 把选中的 archive parent 推进 RULES（adopt 路）。

        ★ 选 parent ⇒ 写 RULES（幂等：已存在 ⇒ already_landed）；
          随 persist_learned 落盘。archive 保留（不删 —— 历史供后搜）。
        """
        _parent = cls.select_parent(key, strategy=strategy)
        if _parent is None:
            return {"outcome": "no_parent", "key": key, "strategy": strategy}
        if key in cls.RULES:
            return {"outcome": "already_landed", "key": key,
                    "strategy": strategy}
        cls.RULES[key] = dict(_parent)
        _persist = cls.persist_learned()
        return {"outcome": "landed", "key": key, "strategy": strategy,
                "version": (cls.ARCHIVE.get(key) or []).index(_parent) + 1
                if _parent in (cls.ARCHIVE.get(key) or []) else None,
                "persist": _persist}

    # ★ C1 · 候选进 archive（只保留，不进 RULES —— adopt 另行显式）。
    @classmethod
    def archive_candidate(cls, key: str, entry: dict[str, Any]) -> dict[str, Any]:
        _lst = cls.ARCHIVE.setdefault(key, [])
        _lst.append(entry)
        # ★ R346 · Raven Gene Bank：archive 时按 cell 更新 elite（quality-diversity）。
        try:
            _cell = cls.cell_of(entry)
            cls.gene_bank_update(_cell, entry)
        except Exception:  # noqa: BLE001 — 坏不断主路
            pass
        return {"archived": True, "key": key,
                "version": len(_lst), "n_versions": len(_lst)}

    # ★ C3 · withdraw 撤回（companion §9.7：毒规则必须可撤）。
    #   内存删除＋返回被删条目（含 provenance 供审计）；无 key ⇒
    #   withdrawn False（幂等撤回，不抛）。不自动 persist（写盘是调用方
    #   决策 —— R32 落盘点明确）；诚实边界：种子 withdraw 进程内有效，
    #   重启复活（种子在代码里，彻底删须改代码）。
    @classmethod
    def withdraw(cls, key: str, reason: str = "") -> dict[str, Any]:
        _entry = cls.RULES.pop(key, None)
        if _entry is None:
            # ★ C1 · RULES 无 ⇒ 撤 archive（整 key 全撤；版本选择另轮）。
            _arch = cls.ARCHIVE.pop(key, None)
            if _arch is None:
                return {"withdrawn": False, "key": key, "reason": reason}
            return {"withdrawn": True, "key": key,
                    "entry": _arch, "from": "archive", "reason": reason,
                    "note": "archive 内存态（落盘另轮）"}
        return {"withdrawn": True, "key": key, "entry": _entry,
                "reason": reason,
                "note": ("learned 须调 persist_learned 落盘；"
                         "种子重启复活")}

    @staticmethod
    def key_for(sig: dict[str, str]) -> str:
        """★ 由失败签名构造**查询键** (c:q:fn) —— 与 propose 同口径。

        ★★ 这个函数存在的理由: 固化方若自己拼键，
          与 propose 拼的不一致 ⇒ 固化了**永远查不到**
          ⇒⇒ ⇒★ 那是"写了没人读"的老病（ARSI C4 同款）
        ⇒ ⇒★ 所以键的构造必须收敛成**一个**函数（两侧共用）
        """
        if not all(sig.get(k) for k in ("c", "q", "fn")):
            raise ValueError(
                "★ 查询键需 (c,q,fn)，m 不参与（R30 结构修正）: %r"
                % (sig,))
        return "%s:%s:%s" % (sig["c"], sig["q"], sig["fn"])

    @classmethod
    def dev_targets(cls, anchors: dict[str, Any] | None = None
                    ) -> set:
        """★ 真源集 = dev 任务 id ∪ dev behavior 函数名（target 的合法落点）。

        ★ R202（审计 P2 裁决）: RULES target **语义双载**（behavior 族 =
          fn 名 / 文本族 = task_id — R171 起两口径并存）, 双载本身是历史
          语义不动; 本方法给校验面提供"已知落点"集合, 让 target 写错
          （指向不存在的 fn/task）在固化时被拒。
        ★ anchors 给定 ⇒ 从该 dict 算（调用方复用已加载 judge — 无双源）;
          缺省 ⇒ 读真源文件（模块缓存, 与 judge TRUTH_SOURCE 同一文件）。
        """
        if anchors is None:
            cached = getattr(cls, "_dev_targets_cache", None)
            if cached is None:
                import json as _json

                from dwc.organs.judge import TRUTH_SOURCE
                data = _json.loads(open(TRUTH_SOURCE[0][1],
                                            encoding="utf-8").read())
                anchors = data
            else:
                return cached
        tids = {k for k in anchors if not str(k).startswith("_")}
        fns = {c.get("fn") for v in anchors.values() if isinstance(v, dict)
               for c in (v.get("checks") or []) if c.get("fn")}
        out = tids | fns
        if getattr(cls, "_dev_targets_cache", None) is None:
            cls._dev_targets_cache = out
        return out

    @classmethod
    def check_entry(cls, key: str, entry: dict[str, Any],
                    dev_targets: set | None = None
                    ) -> list[str]:
        """★ 固化前的字段校验（**数据完整性**，不是判分）。

        ★ 返回缺失字段列表；空 = 合格
        ⇒⇒ ★ 为什么在 evolver 而不在 applier:
          schema 是**进化侧的知识**，applier 是通用写入器
          ⇒⇒ 让 applier 懂 RULES 的结构 = 职责越界
        ★ R202 · target 真源校验（审计 P2 裁决 = 推荐②）: dev_targets
          提供时, target 必须落在真源集（dev task_id ∪ dev fn）——把
          "双载语义写错落点"挡在固化门前。
          · 生产注入: loop 固化 / e2e 固化显式传入 ⇒ **主路径必过**
            （不是装饰 — Layer 23.2: 纪律要能在真实写入路径生效）。
          · 缺省不查: 单元测试的合成占位 target（'f'/'f1'）合法 ——
            schema 层与真源层解耦是既有测试设计, 不为校验破坏它。
        """
        missing = [f for f in cls.RULE_ENTRY_FIELDS
                   if not str(entry.get(f, "")).strip()]
        if dev_targets is not None:
            tgt = str(entry.get("target") or "")
            if tgt and tgt not in dev_targets:
                missing.append("target∉真源(dev task∪fn): %r" % tgt)
        # ★★★ R37 · 第 4 个来源（prompt/生成/固化/schema）
        #   我原来写 `not in COMPONENT_VOCAB` ⇒ 模型给的 `code`
        #   (𝒦_meta 合法) 在 **schema 这一步**又被拒
        #   ⇒⇒ ⇒★ 「一个判据四个来源」= 必然漂移（本轮核心教训）
        #   ⇒ ⇒★ 收敛: 都走 `check_component`（layer_of 是真源）
        _cc = check_component(str(entry.get("component") or ""))
        if _cc:
            missing.append("component∉𝒦∪𝒦_meta:%s"
                           % entry.get("component"))
        if entry.get("dimension") not in DIMENSIONS:
            missing.append("dimension∉九维:%s" % entry.get("dimension"))
        if not key.count(":") == 2:
            missing.append("key 必须是 c:q:fn 三段")
        return missing

    RULES: dict[str, dict[str, Any]] = {
        # ★ 示例规则：sum_first_n 少算一个（off-by-one）
        "E_VALUE:wrong_magnitude:sum_first_n": {
            "component": "control_flow",
            "dimension": "D7",
            "target": "sum_first_n",
            "m": "range_bounds",
            "m_source": "rule",
            "patch": "return sum(range(n + 1))",
            "rationale": "range(1,n+1) 漏掉 n；按 c 判据只应累加 1..n"},
        # ★ 示例规则：average 空列表除零
        "E_ZERO_DIV:wrong_magnitude:average": {
            "component": "control_flow",
            "dimension": "D7",
            "target": "average",
            "m": "empty_input_guard",
            "m_source": "rule",
            "patch": "return (sum(xs) / len(xs)) if xs else 0.0",
            "rationale": "空列表 len=0 ⇒ 除零；按判据应返回 0.0"},
        # ★ 示例规则：factorial 无限递归
        "E_NO_RESULT:abstained_or_missing:factorial": {
            "component": "control_flow",
            "dimension": "D7",
            "target": "factorial",
            "m": "recursive_base_case",
            "m_source": "rule",
            # ★★★ R30 数据修正: 此前是 0/8/4（+4 ⇒ 4/12/8 ✗ 应 4/8/4）
            #   ⇒ 因为**没有应用方**，这个 bug 一直测不到
            #   ⇒⇒ ⇒★★ 端到端暴出的第三类问题（数据错误，非代码错）
            "patch": ("if n <= 1:\n    return 1\n"
                      "return n * factorial(n - 1)"),
            "rationale": "缺递归基 ⇒ 无限递归；按判据 0!/1! 都应为 1"},
        # ★★★ R171 · E_MISMATCH 族（keyword_match 知识题 — 修法 =
        #   含全部 expected_keywords 的答案文本）
        #   ★ 口径: 签名的 fn = 首条失败 kw（judge L788 — first.get("kw")）
        #   ⇒ 键 = c:q:kw; patch = 完整答案文本（judge 按 kw 逐条判）
        #   ★ component=prompt（文本/提示面 — COMPONENT_VOCAB 族内,
        #     不是新造类别）; 这不是"编答案骗判"——修法本身就是
        #     任务相关知识（规则库随任务集增长 = 2606.09498 语义）
        "E_MISMATCH:extra_content:pivot": {
            "component": "prompt",
            "dimension": "D3",
            "target": "reasoning_001",
            "m": "keyword_completion",
            "m_source": "rule",
            "patch": ("快速排序的最坏时间复杂度是 O(n^2)：当 pivot 恰好选到"
                      "极值，分区极度不平衡时，递归深度退化到 n 层，每层"
                      "都要扫过剩余元素。"),
            "rationale": "答案缺 pivot/递归/最坏 全部关键词 ⇒ 补成完整"
                         "解释（judge 按 expected_keywords 逐条判）"},
        "E_MISMATCH:extra_content:一致性": {
            "component": "prompt",
            "dimension": "D3",
            "target": "reasoning_002",
            "m": "keyword_completion",
            "m_source": "rule",
            "patch": ("CAP 定理指分布式系统三者不可兼得：一致性"
                      "（consistency，各节点同刻看到相同数据）、可用性"
                      "（availability，每个请求都能得到非错响应）、分区容错"
                      "（partition tolerance，网络分区时系统仍可工作）。"),
            "rationale": "答案缺 一致性/可用性/分区容错 全部关键词 ⇒ 补"
                         "完整三属性解释"},
        "E_MISMATCH:extra_content:SYN": {
            "component": "prompt",
            "dimension": "D3",
            "target": "reasoning_003",
            "m": "keyword_completion",
            "m_source": "rule",
            "patch": ("TCP 三次握手：客户端发 SYN，服务端回 SYN+ACK，客户端"
                      "再回 ACK，连接建立。需要三次是为了双向确认彼此的发送"
                      "和接收能力都正常；两次无法证明客户端能收到服务端的"
                      "响应。"),
            "rationale": "答案缺 SYN/ACK/三次/握手 全部关键词 ⇒ 补完整"
                         "握手过程解释"},
        "E_MISMATCH:extra_content:B+树": {
            "component": "prompt",
            "dimension": "D3",
            "target": "reasoning_004",
            "m": "keyword_completion",
            "m_source": "rule",
            "patch": ("数据库索引是加快查询的辅助数据结构。B+树比二叉"
                      "搜索树更适合，因为它的树更平衡、高度更低，且节点"
                      "大小按磁盘页设计，减少磁盘 I/O，叶子节点链表便于"
                      "范围扫描。"),
            "rationale": "答案缺 索引/B+树/平衡/磁盘 全部关键词 ⇒ 补完整"
                         "解释"},
        # ★★★★ R200 · E_VALUE/E_OFF_BY_ONE 的 expected_values 族
        #   （rung3 数值容差题 — 修法 = **该任务的完整正确答案文本**）
        #   ★ 与 E_MISMATCH 族同一合法性论证（R171 逐字）: 这不是"编答案
        #     骗判" — 修法本身就是任务相关知识（均值/极差/幂的正确计算
        #     值 = 任务要的全部内容; 规则库随任务集增长 = 2606.09498 语义）。
        #   ★ 键口径: judge 对 expected_values 的失败签名 fn = **key 名**
        #     （R199 _diff: mean/median/std/range/pow2/pow3）⇒ 键 = c:q:key。
        #   ★★★ 撞键事实（R200 施工中实测）: "mean" 同时是 reproduce_001
        #     与 002 的失败 key（键空间 c:q:fn **不含任务维度**）⇒ 该键只
        #     登记 001（先见者）; 002 的修复走它的独有键 range —— loop 侧
        #     R200 撞键守卫（文本任务提案按 target==tid 过滤）保证 002 绝不
        #     试 001 的答案文本。
        #   ★ target = **task_id**（文本族口径, 与 behavior 族 target=fn
        #     不同 — R171 定的, _trial_run docstring 逐字）。
        "E_OFF_BY_ONE:off_by_one_in_range:mean": {
            "component": "prompt",
            "dimension": "D3",
            "target": "reproduce_001",
            "m": "value_completion",
            "m_source": "rule",
            "patch": "mean=6.00, std=2.83, median=6.00",
            "rationale": "[2,4,6,8,10] 均值=30/5=6.00, 总体标准差=sqrt(8)≈2.83,"
                         " 中位数=6.00 — 补完整正确答案（judge 按容差逐 key 判）"},
        "E_OFF_BY_ONE:off_by_one_in_range:median": {
            "component": "prompt",
            "dimension": "D3",
            "target": "reproduce_001",
            "m": "value_completion",
            "m_source": "rule",
            "patch": "mean=6.00, std=2.83, median=6.00",
            "rationale": "同 reproduce_001 完整答案（median 键命中同任务）"},
        "E_VALUE:wrong_magnitude:std": {
            "component": "prompt",
            "dimension": "D3",
            "target": "reproduce_001",
            "m": "value_completion",
            "m_source": "rule",
            "patch": "mean=6.00, std=2.83, median=6.00",
            "rationale": "总体标准差=sqrt(((4+0+4+16+36)/5))=sqrt(8)≈2.83 — 同任务完整答案"},
        "E_VALUE:wrong_magnitude:range": {
            "component": "prompt",
            "dimension": "D3",
            "target": "reproduce_002",
            "m": "value_completion",
            "m_source": "rule",
            "patch": "mean=6.00, range=10.00",
            "rationale": "[1,3,5,7,9,11] 均值=36/6=6.00, 极差=11-1=10.00 — 补完整"
                         "正确答案（mean 撞键被 001 占, 本任务经 range 键修复）"},
        "E_VALUE:wrong_magnitude:pow2": {
            "component": "prompt",
            "dimension": "D3",
            "target": "reproduce_003",
            "m": "value_completion",
            "m_source": "rule",
            "patch": "pow2=1024.00, pow3=243.00",
            "rationale": "2^10=1024, 3^5=243 — 补完整正确答案"},
        "E_VALUE:wrong_magnitude:pow3": {
            "component": "prompt",
            "dimension": "D3",
            "target": "reproduce_003",
            "m": "value_completion",
            "m_source": "rule",
            "patch": "pow2=1024.00, pow3=243.00",
            "rationale": "同 reproduce_003 完整答案（pow3 键命中同任务）"},
    }

    # ★★★★ R37 · 模块加载即给种子补 target_layer（数据迁移）
    #   实测: 3 个种子写于 §四① 之前 ⇒ target_layer=None
    #   ⇒⇒ 读取侧有 layer_of 兜底（propose 那行），但**落盘**还是 None
    #   ⇒ ⇒★ 迁移让数据本身完整（check_entry 必填该字段）
    _seed_migrated = _migrate_target_layer(RULES)

    # ★★★ R32: RULES 定义**之后**立刻捕获种子
    #   ⇒ 顺序要紧: 先有种子（代码字面量）⇒ 再判哪些是"学到的"
    #   ⇒⇒ 若不捕获 SEED_KEYS ⇒ persist 会把种子也写进 json ⇒ 双源
    SEED_KEYS = frozenset(RULES)

    # ★ R438 · 种子快照（测试隔离用）：生产 rules.json 现在会真的有内容，
    #   而 RULES 是类级全局 ⇒ 一个落盘规则会渗进所有测试的计数断言。
    #   conftest 在每个测试前用它复位，测试只看到**代码里的种子**。
    import copy as _copy
    SEED_SNAPSHOT = _copy.deepcopy(RULES)

    #: ★★ 加载的**触发点** = 模块级（import 即生效）
    #   ★★★ 两次踩同一个坑，都记下:
    #   ① 第一版: 类体里 `try: load_learned() except: pass`
    #      ⇒ 类定义时 classmethod 还没绑 ⇒ 必抛 ⇒ **被 pass 吞掉**
    #      ⇒ 于是它**从未被调用**（写了但没接 = 形同没写）
    #   ② 第二版: 挂进 `Mutator.__init__`（实例构造）
    #      ⇒ 而 `RULES` 是**类属性**，调用方写 `Mutator.RULES`（类访问）
    #        ⇒ 实例从未构造 ⇒ `ensure_loaded` 从未被调
    #      ⇒⇒ 实测: 跨进程**读不到**落盘的规则（查表 n_proposals=0）
    #   ⇒⇒ ⇒★★ 结论: 挂在"类访问"之外的东西上，就等于没挂
    #      ⇒ ⇒★ 只有**模块级**对"用类属性的调用方"必然生效
    _loaded = False

    @classmethod
    def ensure_loaded(cls) -> int:
        """★ 幂等加载（**幂等**靠 `_loaded` 守卫，不靠调用时机）。

        ★★★ R32 变异验证的结论（**这个守卫是冗余的**）:
          摘掉 `if cls._loaded: return 0` 后实测: 第 1 次=1、第 2 次=0
          ⇒⇒ 因为 `load_learned` 里已有 `if k not in RULES` ⇒ **自身就幂等**
          ⇒⇒ ⇒★ 所以本守卫**不承重** —— 它只让 `_loaded` 这个标志
            有语义（测试与排查时能问"加载过了吗"）
          ⇒ ⇒★ 显式标注，免得后人以为它承重而"小心翼翼地维护"
            （幻影承重与幻影代码同型: 名字与实现不对齐）
        """
        if cls._loaded:
            return 0
        cls._loaded = True
        return cls.load_learned()

    @classmethod
    def reload_learned(cls) -> int:
        """★ R438 · 强制与盘对齐（只补缺失键；已有键不覆盖）。"""
        cls._loaded = False
        return cls.ensure_loaded()


    @classmethod
    def entry_from_candidate(cls, cand: Any, rationale: str = ""
                             ) -> dict[str, Any]:
        """★★★ R35 · 把**候选**组装成可固化的规则条目（7 字段）。

        ★★★ 职责为什么在这里（不在 applier）:
          · `RULE_ENTRY_FIELDS` / 词表是**进化侧的知识**
          · applier 是通用写入器 ⇒ 它不懂 RULES 的结构
          ⇒ ⇒★ 所以: evolver **组装**（懂 schema）+ applier **写**（懂机制）
            —— 与『check_fn 注入』是同一个分工

        ★★ 三条硬要求（缺一条就是坏规则）:
          ① 7 字段**全齐**（缺字段 ⇒ 炸点在查表那一刻）
          ② component/dimension **必须**来自候选
            ⇒ 绝不默认值兜底（那等于我替模型编了 component）
          ③ m 若是模型产的 ⇒ **必须带指纹**（provenance）
            ⇒ 否则固化后无法回溯"这 m 哪次调用产的"，
              且会被误读成「m 可复现」（温度 0.2 也不保证）
        """
        if cand is None:
            raise ValueError("★ 没有候选 ⇒ 无可固化内容（不许空固化）")
        comp = str(getattr(cand, "component", "") or "")
        dim = str(getattr(cand, "dimension", "") or "")
        # ★★★ R37: 用**单源**（COMPONENT_VOCAB ∪ K_META）
        #   我原来只查 COMPONENT_VOCAB ⇒ 模型给的 `code`(𝒦_meta 合法)
        #   在**固化**这一步被拒 —— 同一个判据第三个来源
        _cp = check_component(comp)
        if _cp:
            raise ValueError(
                "★ candidate.component=%r 不在 𝒦∪𝒦_meta ⇒ 拒绝固化"
                "（**不猜默认值** —— 那就是编造）: %s" % (comp, _cp[0][:60]))
        if dim not in DIMENSIONS:
            raise ValueError("★ candidate.dimension=%r 不在九维 ⇒ 拒绝固化"
                             % dim)
        # ★★★★ R37 · K2: component 与 target_layer **必须一致**
        #   （§四①: 不一致 = 声明与意图矛盾 ⇒ 拒）
        _layer = str(getattr(cand, "target_layer", "") or "")
        _pair = check_pairing(comp, _layer)
        if _pair:
            raise ValueError("★ K2 固化前校验: " + _pair[0])
        m = str(getattr(cand, "m", "") or "")
        if not m:
            raise ValueError("★ m 为空 ⇒ 这条规则没有机制假设，固化无意义")
        m_source = str(getattr(cand, "m_source", "") or "none")
        prov = dict(getattr(cand, "provenance", {}) or {})
        entry = {
            "component": comp,
            "dimension": dim,
            # ★★★★ R37 · §四① 第 2 个字段（proposer 必须声明）
            #   + K2 配对校验（component ↔ target_layer 一致）
            "target_layer": _layer,
            "target": str(getattr(cand, "target", "") or ""),
            "m": m,
            "m_source": m_source,
            "patch": str(getattr(cand, "patch", "") or ""),
            # ★ rationale 必须能回答"凭什么固化这条"
            "rationale": (rationale.strip() or
                          "R35 固化: source=%s rule=%s；grounding=%d 条"
                          % (getattr(cand, "source", "?"),
                             getattr(cand, "rule", "?"),
                             len(getattr(cand, "grounding", []) or []))),
        }
        # ★★★ 模型产的 m ⇒ 指纹**必须**进条目（否则是"无源的 m"）
        if m_source == "llm":
            if not prov:
                raise ValueError(
                    "★ m_source=llm 但没有 provenance ⇒ "
                    "这条 m **无源**（哪次调用产的不知道 ⇒ 拒绝）")
            entry["_m_fingerprint"] = {
                "prompt_ver": prov.get("prompt_ver", ""),
                "model": prov.get("model", ""),
                "n_diffs": prov.get("n_diffs"),
                "raw_m": prov.get("raw_m", m),
            }
        return entry

    def propose(self, sig: dict[str, str]) -> Proposal | None:
        """★ 给一条失败签名 ⇒ 一个提案（无规则则 None）。

        ★★ 关键: 返回 None 是**合法**结果（该机制我们不会改）
          ⇒ 而若强行给提案 ⇒ 那就是"为改而改"
        """
        # ★★★★ R30 结构修正: 查询键只用 (c, q)
        #   原文分工（2609.06396）: c/q 由**规则**填 · m 由**模型假设**填
        #   ⇒⇒ ⇒★ 于是 m 必须在诊断里**产出来**，不能是查询的**输入**
        #   ⇒⇒ ⇒★★ 而我第一版把 RULES 的键也写成 (c,q,m) ⇒ 死锁:
        #     要查 RULES 需要 m → m 要规则推 → 而推它的规则在 RULES 里
        #   ⇒⇒ ⇒★★ 这与 R27 同源: 我拿**聚类语义**当了**实现接口**
        #     （R27: q 我当函数名 · R30: m 我当查询键 —— 同一种错）
        #   ⇒ ⇒★ 签名**语义**不变（仍三元组用于聚类），变的是规则表的键
        lookup = "%s:%s:%s" % (sig.get("c"), sig.get("q"),
                                 sig.get("fn", ""))
        rule = self.RULES.get(lookup)
        if rule is None:
            return None
        # ★ C2 · 直接命中即一次引用（carried＋1，供 activation 第三级）。
        self._carry(lookup)
        pid = "P_" + hashlib.sha256(lookup.encode()).hexdigest()[:8]
        # ★★ 产出的签名**补全** m（由规则给出 —— 第一版无 LLM ⇒ 规则填，
        #   并在 rule 里标注 mechanism_source 以免冒充"模型假设"）
        full = dict(sig)
        full["m"] = rule.get("m", "")
        full["m_source"] = rule.get("m_source", "rule")
        # ★★★★ R37: target_layer 必须带上（§四① 第 2 字段）
        #   旧条目没有它 ⇒ 由 `layer_of` 推（真值表，机械可推）
        #   ⇒⇒ 一定与 component 一致（同一个真源 ⇒ 不可能 K2 矛盾）
        return Proposal(proposal_id=pid, failure_signature=full,
                        component=rule["component"], target=rule["target"],
                        patch=rule["patch"], rationale=rule["rationale"],
                        # ★ R438 · 学到并通过试跑的实现随规则复用
                        code=rule.get("code"),
                        dimension=rule.get("dimension"),
                        target_layer=(rule.get("target_layer")
                                      or layer_of(rule["component"])))

    def known_signatures(self) -> list[str]:
        """★ 声明过的失败签名（可审计：我们只修这些）。"""
        return sorted(self.RULES)

    def propose_lateral(self, sig: dict[str, str],
                         prefer_components: tuple | None = None
                         ) -> Proposal | None:
        """★★★ R173 · LATERAL 泛化提案（同 (c,q) 不同 fn 的近亲修法）。

        ★ 依据: direction.py 的 R73 边界注释**自己点名的第一落点** —
          「world_tree.yaml stuck.on_stuck: switch_strategy 语义近似
          LATERAL」+ proposal 层的『换一个方向试』语义; 本方法 = 那个
          语义在**签名匹配**面的实例化: 本 fn 的签名没规则时, 拿
          **同 (c,q) 近亲 fn** 的 patch 当候选（换一个 fn 试）。
        ★ 返回 None（无同族）⇒ 调用方**如实弃权**（unfixable_now）——
          不编修法; 有同族 ⇒ Proposal（rationale 显式标泛化来源,
          dimension/component 取近亲的 — 可归因, 不冒充"专为该 fn 学"）。
        ★★★ 边界: 这是**候选生成**, 不是采纳 — 真有效性由门组 + 试跑
          （R170 _trial_run）判; 泛化 patch 修不好 ⇒ 门拦/试跑 fail
          ⇒ 弃权, 不硬过。
        """
        c, q = sig.get("c", ""), sig.get("q", "")
        if not c or not q:
            return None
        # ★★★ R202（审计悬置①裁决 = 推荐b）: **同 component 优先**。
        #   背景: RULES 键 (c,q) 跨组件 — behavior 任务的 (c,q) 族里混着
        #   prompt 组件的 answer-text kin（R200 加 expected_values 族后
        #   **实测发生**: average 的 LATERAL 借到 pow2 答案文本 ⇒ 编译炸,
        #   白试一轮）。prefer_components = 当前任务偏好的组件组:
        #     · 文本任务（keyword/expected_values）→ ("prompt",)
        #     · behavior 任务 → COMPONENT_VOCAB 去 prompt（代码组件）
        #   组内仍 sorted 首个（确定性不变）; **偏好组空 ⇒ 回落全集首个
        #   （R173 原行为 — 不因偏好弃候选, 弃权只在真无同族时）**。
        cands = [k for k in sorted(self.RULES)
                 if k.split(":", 2)[:2] == [c, q]]
        if not cands:
            return None
        if prefer_components:
            pref = [k for k in cands
                    if str(self.RULES[k].get("component", ""))
                    in prefer_components]
            kin = (pref or cands)[0]            # 无偏好组 ⇒ 回落全集首个
        else:
            kin = cands[0]                      # 未传偏好 ⇒ R173 原行为
        if kin is None:
            return None
        rule = self.RULES[kin]
        # ★ C2 · 近亲引用同样计数（归因到被借的 kin，不归因到无规则的本 fn）。
        self._carry(kin)
        full = dict(sig)
        full["m"] = rule.get("m", "")
        full["m_source"] = "lateral_rule"
        return Proposal(
            proposal_id="P_" + hashlib.sha256(
                ("LAT:" + Mutator.key_for(sig)).encode()).hexdigest()[:8],
            failure_signature=full,
            component=rule["component"], target=rule["target"],
            patch=rule["patch"],
            rationale=("LATERAL 泛化: %s 无本 fn 规则 ⇒ 借同族 (c=%s,"
                       "q=%s) 的 %s 修法试（R173 — 有效性由门+试跑判）"
                       % (sig.get("fn", ""), c, q, kin)),
            dimension=rule.get("dimension"),
            target_layer=(rule.get("target_layer")
                          or layer_of(rule["component"])))


# ══════════════════════════════════════════════════════════
# ★ R278 · LLM-Mutator（第二个 Mutator，可插拔）。
#   · Mutator（查表，确定性）认不出 ⇒ unmapped ⇒ 到这里问 LLM 起草新条目。
#   · 只新增：diagnose/propose/consolidate 零改；默认不用（调用方显式开）。
#   · m_source 强制 "llm"（防冒充规则推导 — R30 分工）。
#   · 坏 JSON/缺字段 ⇒ None + last_reason 留痕（禁静默）；
#     llm 抛异常 ⇒ 原样上抛（大声，不吞）。
# ★ R333 · 启动接线：进程导入时把落盘 state 合并进内存（state inheritance
#   的"加载"半边）。文件不存在 ⇒ 0，不报错。
try:
    Mutator.bootstrap_state()
except Exception:  # noqa: BLE001 — 启动接线坏不掀导入
    pass


# ══════════════════════════════════════════════════════════


class LLMMutator:
    """★ 由失败签名簇 ⇒ LLM 起草新 RULES 条目 ⇒ Proposal（新键）。"""

    def __init__(self, llm: Any = None):
        self.llm = llm
        self.last_reason: str = ""
        #: ★ R290-P2 · 方向尝试史（实例级内存 —— credit 同款进程语义；
        #:   每轮 new LLMMutator ⇒ 每轮三方向额度，max_clusters=3 刚好）
        self._direction_history: list[Any] = []

    def _prompt(self, sigs: list[dict[str, Any]],
                context: str = "", want_code: bool = False,
                learned_hint: str = "") -> str:
        s0 = dict(sigs[0])
        _ctx = context or ""
        _hint = (learned_hint or "").strip()
        _f = {
            "head": ("你是 DWC 进化器的规则起草员。下列失败签名属同一簇"
                     "（c/q/fn 一致，n=%d）：" % (len(sigs),)),
            "sig_line": ("c=%s q=%s fn=%s" % (s0.get("c"), s0.get("q"),
                                              s0.get("fn", ""))),
            "m_samples": ("m 样本=%s" % ([str(s.get("m", ""))[:60]
                                          for s in sigs[:3]],)),
            "task_line": ("任务=%s" % (s0.get("task", ""),)),
            "context_block": ("" if not _ctx
                              else "判分对照事实（真值 vs 模型断言）：\n"
                              + _ctx + "\n"),
            "hint_block": ("" if not _hint
                           else "该簇已有落地规则（禁重复已落地机制；另寻机制，"
                           "或明确写出超越点）：\n" + _hint + "\n"),
            "code_block": ("" if not want_code
                           else "另加 code 字段：完整可执行 Python 函数定义（def "
                           + str(s0.get("fn", "fn"))
                           + "(...) 起，纯函数，只用 sum/len/range 等纯内建，禁 import、"
                           "禁 open/exec/eval、禁 while —— 沙箱真跑它判分，跑不通=白起草）。"),
        }
        try:  # ★ R307 · 模板渲染（失败⇒老路，老路一字不差）
            from dwc.llm.prompt_ota import note_miss as _ota_miss
            from dwc.llm.prompt_ota import render_here as _render
            _t = _render("drafter", _f, __file__)
            if _t:
                return _t
        except Exception:
            _ota_miss()
        lines = [
            "你是 DWC 进化器的规则起草员。下列失败签名属同一簇"
            "（c/q/fn 一致，n=%d）：" % (len(sigs),),
            "c=%s q=%s fn=%s" % (s0.get("c"), s0.get("q"),
                                 s0.get("fn", "")),
            "m 样本=%s" % ([str(s.get("m", ""))[:60] for s in sigs[:3]],),
            "任务=%s" % (s0.get("task", ""),),
        ]
        if context:
            lines.append("判分对照事实（真值 vs 模型断言）：\n" + context)
        # ★ R300-A · 已落地规则段（非空才拼；空⇒老路一字不差）。
        if (learned_hint or "").strip():
            lines.append("该簇已有落地规则（禁重复已落地机制；另寻机制，"
                         "或明确写出超越点）：\n" + learned_hint.strip())
        lines += [
            "先简短思考（≤200字），然后另起一行输出JSON对象收尾",
            "（思考再长也会被截断 ⇒ JSON 必须在结尾前出现）。",
            "只输出一个 JSON 对象（无解释），字段必须齐：",
            "component（只能是这9个词之一：client_tool/config/context_mgmt/",
            "control_flow/memory/output_plumbing/prompt/skill/subagent）、",
            "dimension（如 D7）、target_layer（如 assets）、",
            "target（修哪里：函数名）、m（新机制名，须能解释上面的对照事实）、",
            "patch（怎么改：一句话修法）、rationale（为什么：必须引用对照事实，",
            "禁编造数量级 — 先算真值与断言的比值再下结论）。",
        ]
        if want_code:
            lines.append(
                "另加 code 字段：完整可执行 Python 函数定义（def "
                + str(s0.get("fn", "fn"))
                + "(...) 起，纯函数，只用 sum/len/range 等纯内建，禁 import、"
                "禁 open/exec/eval、禁 while —— 沙箱真跑它判分，跑不通=白起草）。")
        return "\n".join(lines)

    def _extract(self, text: str) -> dict[str, Any] | None:
        # ★ 多候选取末尾真 JSON（R277b-4 同款纪律：推理前言在前，真答案在后）。
        # ★ 用真解析器倒序试（raw_decode）：前言杂散括号/引号再多也不怕，
        #   能 parse 成 dict 的才算 —— 数括号是旁门左道，已废。
        dec = json.JSONDecoder()
        starts = [i for i, ch in enumerate(text or "") if ch == "{"]
        for i in reversed(starts):
            try:
                obj, _ = dec.raw_decode(text, i)
            except (ValueError, TypeError):
                continue
            if isinstance(obj, dict):
                return obj
        return None

    def propose_from_cluster(self, sigs: list[dict[str, Any]],
                                 context: str = "",
                                 max_attempts: int = 3,
                                 want_code: bool = False,
                                 learned_hint: str = "",
                                 operator: str = "improve",
                                 component: str = "",
                                 ) -> Proposal | None:
        if not sigs:
            self.last_reason = "空簇：无签名可起草"
            return None
        if self.llm is None:
            self.last_reason = "未注入 llm（显式开才用 — 默认不用）"
            return None
        s0 = dict(sigs[0])
        if not all(s0.get(k) for k in ("c", "q", "fn")):
            self.last_reason = "首签名缺 c/q/fn：%r" % (s0,)
            return None
        # ★ R290-P2 · 起草前选方向（○-3 摘牌：next_action 生产调用点）。
        #   三方向耗尽 ⇒ DirectionError 上抛（run_round 已隔离：单簇留痕
        #   不掀轮）。方向不进 prompt（prompt 方向化是 P4+，零语义发明）。
        from dwc.organs.direction import DirectionAttempt, next_action
        _dec = next_action(self._direction_history, round_no=0,
                           task_id=str(s0.get("task", "")))
        prompt = self._prompt(sigs, context, want_code=want_code,
                              learned_hint=learned_hint)
        reasons: list[str] = []
        for _ in range(max(1, max_attempts)):
            text = self.llm(prompt)  # ★ 抛异常 ⇒ 上抛（大声）
            if not isinstance(text, str):
                text = str(text)
            entry = self._extract(text)
            if entry is None:
                reasons.append("无可用 JSON（前80字：%s）" % (text[:80],))
                continue
            entry = dict(entry)
            entry["m_source"] = "llm"  # ★ 强制（防冒充 — R30 分工）
            missing = Mutator.check_entry(Mutator.key_for(s0), entry)
            if missing:
                reasons.append("缺字段：%s" % (missing,))
                continue
            if want_code and not (entry.get("code") or "").strip():
                # ★ R295-Task3补 · 求码而无码⇒缺字段进重试（3 次都没才 None；
                #   无码 trial 走老报数=错配通道，宁可多起一次）。
                reasons.append("缺字段：code（want_code 求码而无码）")
                continue
            break
        else:
            entry = None  # type: ignore
        if entry is None:
            self._direction_history.append(DirectionAttempt(
                direction=_dec.direction, n_candidates=0,
                note="起草全废（方向 %s 无对象）" % (_dec.direction.value,)))
            self.last_reason = ("起草%d次全废：%s；方向已切 %s（下簇换向）"
                                % (len(reasons), reasons, _dec.direction.value))
            return None
        key = Mutator.key_for(s0)
        full = dict(s0)
        full["m"] = entry.get("m", "")
        full["m_source"] = "llm"
        self._direction_history.append(DirectionAttempt(
            direction=_dec.direction, n_candidates=1,
            note="起草成功（方向 %s 出 1 候选）" % (_dec.direction.value,)))
        # ★ R438 · 车道即落地面：调用方给了 component（如 control_flow 车道），
        #   就以车道为准 —— 否则 LLM 把一条"控制流规则"标成 skill，
        #   会落进 rules.json 却挂着 skill 的名字（名字与实现不对齐）。
        #   LLM 的原始标签保留在 rationale 里，可追溯。
        _llm_comp = str(entry.get("component") or "")
        _comp = str(component or _llm_comp)
        if _comp != _llm_comp:
            entry["rationale"] = ("%s（LLM 原标 %s，按车道归 %s）"
                                  % (entry.get("rationale", ""), _llm_comp,
                                     _comp))
        return Proposal(
            proposal_id="P_" + hashlib.sha256(
                ("LLM:" + key).encode()).hexdigest()[:8],
            failure_signature=full,
            component=_comp, target=entry["target"],
            patch=entry["patch"],
            code=entry.get("code"),  # ★ R295-Task2 · 无码⇒None（trial 老路）
            rationale=("LLM 起草（n=%d 同簇失败）: %s"
                       % (len(sigs), entry["rationale"])),
            dimension=entry.get("dimension"),
            target_layer=(layer_of(_comp) if component
                          else (entry.get("target_layer") or layer_of(_comp))),
            operator=operator)


# ══════════════════════════════════════════════════════════
# 门（约束 1：先过门再采纳）
# ══════════════════════════════════════════════════════════


class ProposalGate:
    """★ 提案门。★ 先过门，后落地（约束 1）。

    ★★★ 门的判据（全部来自已定设计，不是自己发明的）:
      ① 一处干预（约束 4 · 2606.09498）
      ② 组件在 RRSI 词表内（2609.24972 式 12）
      ③ 有依据（rationale 非空 —— 可归因）
      ④ 维度在九维内（2606.14249 §3.3）
      ⑤ ★★ **不允许改判据**（约束 2 · 2609.13406）
         ⇒ 若 target 指向 dev.json / judge / 真值源 ⇒ 直接拒
    """

    #: ★★ 不可写面（约束 2: 判据必须在可写面之外）
    FORBIDDEN_TARGETS = ("judge", "dev.json", "test_sealed", "iron_laws",
                         "gate.py", "truth", "golden", "anchors")

    def check(self, p: Proposal) -> dict[str, Any]:
        """★ 检一个提案，返回门报告（不 raise —— 门是报告器）。"""
        v = []

        # ① 一处干预
        if not p.target.strip():
            v.append(("no_target", "约束 4: 提案必须有唯一 target"))
        # ② 词表
        # ★ R37: 与 __post_init__ 同源（check_component）
        if check_component(str(p.component or "")):
            v.append(("bad_component", "组件不在 𝒦∪𝒦_meta 内"))
        # ★★★ K2（§四①: 门报告器也查一致性 —— 不 raise，只报告）
        # ★ 与 __post_init__ 同款: 没声明 ⇒ 推（推得出来就不是矛盾）
        _lay = str(getattr(p, "target_layer", "") or "")
        if not _lay:
            # ★ R37: 先判词表 ⇒ **无异常**（G7 抓过我这里的 except: pass）
            #   词表外的由 ② bad_component 报（不越权、也不吞）
            _pc = str(p.component or "")
            # ★★★ R39 审计: 这里原本展开写
            #   `in COMPONENT_VOCAB or in K_META`
            #   = 同一判据的**第 7 个来源**（我 R37 踩过 5 个）
            #   ⇒ 收敛到 `check_component`（真源 = layer_of）
            if check_component(_pc) == []:
                _lay = layer_of(_pc)
                p.target_layer = _lay
        _pk = check_pairing(str(p.component or ""), _lay)
        if _pk:
            v.append(("layer_mismatch", "K2: " + _pk[0]))
        # ③ 依据
        if not p.rationale.strip():
            v.append(("no_rationale", "约束 4: 变更须可归因 ⇒ 必须有依据"))
        # ④ 维度
        if p.dimension is not None and p.dimension not in DIMENSIONS:
            v.append(("bad_dimension", "维度不在九维内"))
        # ⑤ ★★ 不许改判据
        low = p.target.lower() + " " + p.patch.lower()
        for bad in self.FORBIDDEN_TARGETS:
            if bad.lower() in low:
                v.append(("touches_truth", "约束 2: 提案触及判据/真值源 ⇒ 拒"))
                break
        return {"gate": "proposal", "proposal_id": p.proposal_id,
                "key": p.key(), "pass": not v,
                "violations": [{"rule": r, "detail": d} for r, d in v],
                "n_checks": 5}


# ══════════════════════════════════════════════════════════
# Evolver
# ══════════════════════════════════════════════════════════


class Evolver:
    """★ 变异器编排：失败签名 → 提案 → 过门 → 待判分。

    ★★ 它**不**做的事（职责边界，逐条有依据）:
      · 不判分（judge）
      · 不落地（APPLIER）
      · 不改判据（约束 2）
      · 不一次改多处（约束 4）
    """

    def __init__(self, mutator: Mutator | None = None,
                 gate: ProposalGate | None = None,
                 registry: Any | None = None):
        self.mutator = mutator or Mutator()
        self.gate = gate or ProposalGate()
        self.proposals: list[Proposal] = []
        self._seen: set[str] = set()
        #: ★ R162 · 共享契约注册表（层② contract 门的输入; None=未注入
        #   ⇒ contract 落 pending 族, 不误判提案坏）
        #: ★ R167: 未注入时**出厂装 builtin**（budget_window 值域契约 —
        #   DWC 自己的真实约束注册为 FGGM; 此前全仓只有测试装过表 ⇒
        #   生产路径门②恒"表非空即过"或 blocked, 两种虚判都终结）
        if registry is None:
            try:
                from dwc.organs.contracts_builtin import builtin_registry
                registry = builtin_registry()
            except Exception as exc:              # noqa: BLE001 — 留痕不静默
                self.registry_error = "%s: %s" % (type(exc).__name__, exc)
        self.registry = registry
        self.registry_error = None

    # ══════════════════════════════════════════════
    # 诊断 → 提案
    # ══════════════════════════════════════════════
    def propose_lateral(self, sig: dict[str, str],
                         prefer_components: tuple | None = None
                         ) -> Proposal | None:
        """★★ R173: LATERAL 泛化委派（Loop 侧入口 — 实现在 Mutator, 与
        propose/diagnose 同一委派模式: 器官对器官, 策略在 Mutator）。"""
        return self.mutator.propose_lateral(sig,
                                            prefer_components=prefer_components)

    def diagnose(self, signatures: list[dict[str, str]]
                 ) -> dict[str, Any]:
        """★ 诊断：失败签名 → 去重后的提案清单。

        ★★ 约束 4 的另一面: 同一 (c,q,m) 精确一致才算一簇
          ⇒ 所以去重按 key，不做语义相似合并
          ⇒★ 而 2606.09498 原文强调: "两个 run 可能共享同一个
            verifier 结果（如 timeout）却需要不同的干预"
            ⇒⇒ ★★ 所以**只有三元组全同**才合并，绝不按 c 单独合并
        """
        out: list[Proposal] = []
        unmapped: list[dict[str, str]] = []
        clusters: dict[str, int] = {}

        def _cluster(sig_in: dict[str, str],
                     m: str) -> None:
            """★ 聚类计数 —— 键是**补全后**的 (c,q,m)。"""
            k = "%s:%s:%s" % (sig_in.get("c"), sig_in.get("q"), m)
            clusters[k] = clusters.get(k, 0) + 1

        for sig in signatures:
            # ★★★★ R30 结构修正（与 propose 的键改动配套）:
            #   诊断**输入**只需 (c, q) —— 它是查询 RULES 的键
            #   而 m 是**诊断的输出**（由 RULES 条目补全，R30 结构修正）
            #   ⇒⇒ ⇒★ 所以这里不再强制 m 非空
            #     （强制了就会拒掉 judge 产的 `m=""` —— 实测正是断点）
            #   ⇒⇒ ⇒★★ 而 2609.06396 原文分工本就是:
            #     c/q **规则**填 · m **模型假设**填 ⇒ m 允许待定
            # ★★ 查询键 = (c, q, **fn**) ⇒ 三者必填（缺 fn 定位不了）
            #   而 m **允许空**（由 RULES 条目产出 —— 原文分工）
            if not all(sig.get(k) for k in ("c", "q", "fn")):
                raise EvolverError(
                    "失败签名缺 c/q/fn（查询键所需；m 可空）: %r" % (sig,))
            p = self.mutator.propose(sig)
            if p is None:
                # ★ 聚类也要算 —— unmapped 同样是"三点一致"里的一簇
                #   （它的机制未知 ⇒ m 空串，聚类键如实带空）
                unmapped.append(dict(sig))
                _cluster(sig, sig.get("m") or "")
                continue            # ★ 合法: 该机制我们不会改
            _cluster(sig, p.failure_signature.get("m") or "")
            if p.key() in self._seen:
                continue                        # ★ 去重
            self._seen.add(p.key())
            out.append(p)
        return {"proposals": out, "n_unmapped": len(unmapped),
                "unmapped": unmapped,
                "n_clusters": len(clusters),
                "★": ("聚类按**补全后**三元组精确一致（2606.09498）"
                      "⇒ 不按 c 单独合并；m 由 RULES 条目产出"),
                }

    # ══════════════════════════════════════════════
    # 门（约束 1）
    # ══════════════════════════════════════════════
    def gate_all(self, proposals: list[Proposal]) -> dict[str, Any]:
        """★★ 两层门串接（R162 · 静态 ProposalGate → 运行时六门链）。

        ★ 层① 静态门 ProposalGate.check（构造期可判: target/词表/维度/
          禁触判据）— 不过即 rejected, 不进层②（顺序不可换 — 静态层天然先）。
        ★ 层② 运行时六门链（R152: leakage→contract→drawback→split→
          noncomp→budget, 经 R162 bridge 适配 Proposal ⇒ TermFacts）:
          · 链判 passed（全 applicable 过/含 na）⇒ gated
          · 链判 blocked ⇒ **按 blocked 归因分两种**（关键裁决 3）:
            (a) 有运行口径且真判挂（如 leakage 命中/预算超）⇒ rejected
                — 非补偿: 有输入且挂 = 提案坏
            (b) 缺运行口径（gate_all 无 ΔS/δ ⇒ noncomp blocked; 无
                baseline/current ⇒ split na）⇒ **pending_runtime** —
                不降级 rejected（缺输入 ≠ 提案坏 — 与 R159 blocked/na
                族属裁决同源, 归因不错位）
        ★★ gate_verdict 双报告留痕: {"proposal_gate": 层①, "six_gate_chain":
           层②（含 blocked/na 逐门明细）, "layer2": status}
        ★★ 返回键**: gated / rejected / **pending_runtime**（新三元;
           旧二元键保留且语义兼容 — 静态过的提案无论层② pending 还是
           passed 都计 gated, 只有层②真判挂才进 rejected; 旧测
           n_gated/n_rejected 语义不破坏）。
        """
        from dwc.harness.candidate_bridge import BridgeError, to_facts
        from dwc.harness.gates import install_registry, run_gates

        passed, rejected, pending = [], [], []
        # ★ R162: 层②前装共享注册表（self.registry 常驻注入点 —
        #   装了就真判 contract 门; 未注入 ⇒ contract 落 pending 族）
        _prev_reg = getattr(self, "registry", None)
        install_registry(_prev_reg)
        for p in proposals:
            r = self.gate.check(p)                     # ── 层① 静态 ──
            if not r["pass"]:
                p.gate_verdict = {"proposal_gate": r, "layer2": "skipped",
                                  "six_gate_chain": None}
                p.state = "rejected"
                rejected.append(p)
                self.proposals.append(p)
                continue
            # ── 层② 运行时链（R162 适配: Proposal ⇒ TermFacts）──
            chain = None
            layer2 = "error"
            try:
                facts = to_facts([p], vocabulary=())
                chain = run_gates(facts)
                cverdict = chain.get("verdict")
                if cverdict in ("applicable_passed_with_na",
                                "all_applicable_passed"):
                    layer2 = "passed"
                elif cverdict == "error":
                    layer2 = "error"                    # 链执行异常 ≠ 通过
                else:
                    # blocked: 按归因分 (a) 真判挂 / (b) 缺口径
                    blocked = set(chain.get("blocked") or [])
                    # ★ gate_all 形态天然缺输入的面（缺输入≠提案坏 —
                    #   归因不降级; contract 在此族: 注册表未注入时判不了,
                    #   注入则真判, 见 self.registry）
                    NO_INPUT_GATES = {"noncomp", "drawback", "contract"}
                    layer2 = ("pending_runtime"
                              if blocked and blocked <= NO_INPUT_GATES
                              else "rejected")
            except BridgeError as exc:
                # 空 patch/无 component（静态层未拦的形态）⇒ 单条记错,
                # 不炸全批（G7 留痕 + D2: 一条坏不拖垮整轮）
                chain = {"verdict": "error", "error": str(exc),
                         "blocked": [], "not_applicable": [], "gates": []}
                layer2 = "error"
            p.gate_verdict = {"proposal_gate": r, "layer2": layer2,
                              "six_gate_chain": chain}
            if layer2 == "rejected":
                p.state = "rejected"
                rejected.append(p)
            else:
                # passed / pending_runtime / error 都算"静态过了"⇒ gated
                # （error 单列由 layer2 字段可查 — gated 不是"全绿"）
                p.state = "gated"
                passed.append(p)
                if layer2 == "pending_runtime":
                    pending.append(p)
            self.proposals.append(p)
        out = {"gated": passed, "rejected": rejected,
                "pending_runtime": pending,
                "n_gated": len(passed), "n_rejected": len(rejected),
                "n_pending_runtime": len(pending),
                "★": ("约束 1: 先过门，后落地 · R162 两层串接（静态→运行时六门）;"
                      " pending_runtime = 层②缺口径（非提案坏 — 归因不降级）"),
                "★★": ("gate_verdict 双报告: proposal_gate(层①) +"
                       " six_gate_chain(层②逐门明细)")}
        install_registry(None)      # 复位（防跨实例污染 — R152 铁律）
        return out

    def _land_adopted(self, p: Proposal,
                      admission_round: str | None = None) -> dict[str, Any]:
        """★ R287-C · 第五态下游落地（幂等）。

        ★ 前置：p.state 必须是 adopted_not_implemented（adopt() 判过的），
          否则 EvolverError 大声（rejected/draft 落盘 = 把没通过的当通过）。
        ★ 键口径：Mutator.key_for(c:q:fn)，fn 取 proposal.target
          （target 约定就是函数名 —— 与 propose/RULES 同口径，不手拼）。
        ★ entry 按 RULE_ENTRY_FIELDS 八字段；m_source 沿 proposal 的
          failure_signature（诚实来源传递，不改写）。
        ★ 幂等：key 已在 RULES ⇒ already_landed（不长双胞胎）；
          落盘走 Mutator.persist_learned（与 R278 同口径）。
        ★ C3 · provenance（companion §9.7 SkillPoison 95.71%：毒规则
          必须可撤回 ⇒ 先有来源才有撤回）：条目带 provenance＝{task, 
          admission_round}；admission_round 由调用方传（evo_round 传
          ledger_date），None＝未记录（诚实缺席，不编轮号）。
        """
        if p.state != "adopted_not_implemented":
            raise EvolverError(
                "只有 adopted_not_implemented 可落地，实 state=%r"
                % (p.state,))
        # ★ R438 · 落地前先与盘对齐（跨进程幂等）。
        #   现场：两个 --deep-task 进程同时启动，import 时 rules.json 还不存在
        #   ⇒ 两个进程都判"键不存在"⇒ 同一键落两次（台账两行 landed=true）。
        #   重读一次（只补缺失键，不改已有）即可让第二个进程正确判 already_landed。
        try:
            self.mutator.reload_learned()
        except OSError as _e:      # 读不回不拦落地，但必须留痕（G7）
            sys.stderr.write("落地前重读 rules.json 失败: %r\n" % (_e,))
        _sig = dict(p.failure_signature or {})
        _sig.setdefault("fn", p.target)
        _key = Mutator.key_for(_sig)
        if _key in self.mutator.RULES:
            return {"outcome": "already_landed", "key": _key}
        self.mutator.RULES[_key] = {
            "component": p.component, "dimension": p.dimension,
            "target_layer": p.target_layer, "target": p.target,
            "m": _sig.get("m", ""),
            "m_source": _sig.get("m_source", "rule"),
            "patch": p.patch, "rationale": p.rationale,
            # ★ R438 · code 维度：学到并通过试跑的实现**随规则一起落盘**，
            #   下次同签名再出现时 propose 直接把它当起点（改前 p.code
            #   试跑完就丢，同一任务每次都从零起草）。
            "code": p.code,
            # ★ C3 · provenance 落盘（供 withdraw 撤回审计）。
            # ★ R335 · temporal scope（survey §4.1.1：何时生效/作用域/回滚触发）。
            "provenance": {"task": _sig.get("fn", ""),
                           "admission_round": admission_round,
                           "temporal_scope": {
                               "effective_from": admission_round,
                               "scope": "cross-task",
                               "rollback_trigger": "held-out regression",
                               "expires": None}}}
        _persist = Mutator.persist_learned()
        _bak = self._backup_rules()
        return {"outcome": "landed", "key": _key,
                "persist": _persist, "backup": _bak}

    @staticmethod
    def _backup_rules() -> str | None:
        """★ R438 · 落地后备份 rules.json（回滚与审计的物证）。

        ★ 为什么"落地后"才备份：备份要包含刚落的那一条，否则回滚到
          "落地前"会连上一条一起丢。回滚用 `--rollback <key>` 删单键，
          整文件还原用 `--restore <backup>`。
        """
        src = Mutator.LEARNED_PATH
        if not os.path.exists(src):
            return None
        import shutil
        import time as _t
        bak_dir = os.path.join(os.path.dirname(os.path.dirname(
            os.path.dirname(src))), "var", "backups")
        try:
            os.makedirs(bak_dir, exist_ok=True)
            dst = os.path.join(bak_dir, "rules_%s.json"
                               % _t.strftime("%Y%m%d_%H%M%S"))
            shutil.copy2(src, dst)
            return dst
        except OSError as exc:      # ★ G7 · 备份失败必须留痕，不许静默
            import sys as _sys
            _sys.stderr.write("rules 备份失败: %r\n" % (exc,))
            return None

    # ══════════════════════════════════════════════
    # ★★★ 关键: 采纳必须同时过**两组 split**（约束 3）
    # ══════════════════════════════════════════════
    @staticmethod
    def accept(p, baseline, current, *a, **kw):
        _ig = kw.pop("improver_gain", None)
        _fpr = kw.pop("fresh_pass_rate", None)
        _ps = kw.pop("paired_screen", None)
        _mr = kw.pop("mechanism_ran", None)
        _r = Evolver._accept_core(p, baseline, current, *a, **kw)
        if isinstance(_r, dict):
            _dec = _r.get("decision")
            if _dec not in ("accepted", "adopted_not_implemented"):
                _gt = "none"
            elif _ig is True and _mr is True:
                _gt = "both"
            elif _ig is True and _mr is False:
                _gt = "capability (improver unverified)"
            elif _ig is False:
                _gt = "capability_only"
            else:
                _gt = "capability (improver unverified)"
            _r = dict(_r)
            _r.setdefault("gain_type", _gt)
            _r.setdefault("fresh_pass_rate", _fpr)
            _r.setdefault("paired_screen", _ps)
            _r.setdefault("mechanism_ran", _mr)
        return _r


    def _accept_core(p: Proposal, baseline: dict[str, Any],
               current: dict[str, Any], eps: float = 0.0,
               mode: str = "report",
               lam: float = 0.0,
               delta: float | None = None,
               gamma: float = 0.0,
               m: int | None = None,
               k_comparisons: int = 1,
               delta_conf: float = 0.05,
               improver_gain: bool | None = None,
               ) -> dict[str, Any]:
        """★ 判定一个候选该不该采纳（固定门 𝒢_fixed）。

        ★★★★ R27 实测修正: 原签名收「in_score / held_out_score」两个数，
          参数名叫 score 但比较逻辑当成**增量**用
          ⇒⇒ ★★ 语义自相矛盾（测试按分数传，就判错了）
          ⇒⇒ ⇒★ 改成收**基线与当前两份判分结果**，增量由本函数自己算
            —— 理由: 增量必须由同一函数从同一口径算出，
              否则调用方可以用不同基线糊弄过去

        ★★★ 判据（2606.09498 Algorithm 1 第 13 行**原文**）:
          if Δ_in ≥ 0 and Δ_ho ≥ 0 and max(...) > 0 then Accept
          ⇒⇒ ★★ ★ 我初版漏了第三个条件 max(...) > 0
            —— 那个条件的作用是: **两组都不退化还不够**，
               还得真的有改进（否则等于没改）
          ⇒⇒ ★ 而 DWC 的 max(...) 就是 Δ_in 与 Δ_ho 的较大者

        ★★ 2608.24876 Eq.9 的正规形式（本方法即其可执行化）:
          ℳ_{k+1} = ℳ⁺_k  if 𝒢_fixed(ℳ⁺_k, ℳ_k; x_k, 𝒟_dev) = 1
                     ℳ_k    otherwise
          ⇒⇒ 「先在副本上评估 → 通过才合并」⇒ 生产主干在通过前未被触碰

        ★★ 而 DWC 现在 **test split 未落地**
          ⇒⇒ ★★ 所以 held_out 缺失时必须返回 **blocked**
            ⇒⇒⇒ 绝不因为"只在一组数据上变好了"就放行
              （2606.14249 记录: 只用一组 ⇒ −14.0%）

        ★★ 第五态（R14）: adopted_not_implemented
          —— 「过了门但还没落地」必须与「已落地」区分

        ★★ A2 · Cai Cor 1 显式化（2609.08175 Thm 1/Cor 1，判分零改）：
          Qualified 集 P_k(T)＝{L_k(c)≥λ, D_k(c)≤δ}，λ＞(1−Z_k)δ ⇒ 增益＞0；
          γ-校准 λ_k(γ,δ)＝γ＋(1−Z_k)δ 保增益 ≥γ。DWC 对应：
            L_k(c)「失败任务贡献」↔ max(Δ_in,Δ_ho)＞0（real_improvement 门）；
            D_k(c)「保留任务平均绝对变化」↔ −min(Δ_in,Δ_ho)≤eps（no_regression
              门，δ̂＝eps，delta 参数显式命名它）；
            λ̂＝lam（默认 0.0，即现行 max＞0；传 lam＞0 只显式记录，不改判
              —— 启用 λ 准入需另轮改判据＋对照实验）；
            γ̂＝gamma（默认 0.0 未启用，同上）。
          返回体每出口带 "T"＝{lam, delta, gamma}（单真源 _T()），供查账
          与 Thm 5 熔断消费。
        ★★ A1a · 18813 Eq.8 四数显式化（m/KT/T/δ，判分零改 —— fresh 集
          另轮 A1b）：Eq.8 准入上界 Δ_k ≤ Δ̂_k＋√(2ln(KT/δ)/m)，只接受上
          界为负的候选。DWC 当前：m＝验证样本量（调用方传；None＝未声明，
          hoeffding 记 None 不编数）；KT̂＝k_comparisons（本轮比较次数，
          evo_round 传 attempts）；T＝_T()（A2 条件）；δ̂＝delta_conf
          （默认 0.05）。返回体每出口带 "Eq8"（单真源 _E8()）。
          诚实边界：DWC 的 held_out 是配对复测非盲测（E1 已降级）—— m
          是复测样本不是 fresh 独立样本，Eq.8 独立性假设当前不满足，
          上界仅供参考，门判据不动（独立集落地之日再启用上界否决）。
        """
        b_in = baseline.get("in_score")
        c_in = current.get("in_score")
        b_ho = baseline.get("held_out_score")
        c_ho = current.get("held_out_score")

        # ★ R310-① · 门阵列（抄 Capy gates[]：每道子判独立条目，未及判记
        #   pass=None；decision 口径一字不动）。
        def _g(_name, _passed, _detail):
            return {"name": _name, "pass": _passed, "detail": _detail}

        # ★ A2 · T 条件单真源（Cai Cor 1）：lam 默认 0.0（现行 max>0），
        #   delta 默认 None⇒取 eps（现行容忍即 δ̂），gamma 默认 0.0 未启用。
        #   只显式记录、不改判（启用需另轮）。
        def _T():
            return {"lam": lam,
                    "delta": (eps if delta is None else delta),
                    "gamma": gamma}

        # ★ A1a · Eq.8 四数单真源（m/KT/T/δ）：只显式记录、不改判。
        def _E8():
            import math as _math
            _hb = None
            try:
                if (m is not None and m > 0 and k_comparisons is not None
                        and k_comparisons > 0 and 0 < delta_conf < 1):
                    _hb = _math.sqrt(2.0 * _math.log(
                        k_comparisons / delta_conf) / m)
            except (ValueError, TypeError, ZeroDivisionError):
                _hb = None
            return {"m": m, "KT": (k_comparisons
                                   if k_comparisons is not None else None),
                    "T": _T(), "delta": delta_conf, "hoeffding": _hb}

        def _classify_gain(_decision):
            if _decision != "accepted":
                return "none"
            if improver_gain is True:
                return "both"
            if improver_gain is False:
                return "capability_only"
            return "capability (improver unverified)"

        def _gain_wrap(_d):
            _d = dict(_d)
            _d.setdefault("gain_type", _classify_gain(_d.get("decision")))
            return _d

        if b_in is None or c_in is None:
            return {"decision": "not_evaluated", "why": "in-sample 未判过",
                    "T": _T(), "Eq8": _E8(),
                    "gates": [
                        _g("in_sample_scored", False, "in_score 缺基线/当前"),
                        _g("held_out_present", None, "未及判（前门已拦）"),
                        _g("no_regression", None, "未及判（前门已拦）"),
                        _g("real_improvement", None, "未及判（前门已拦）")]}
        d_in = c_in - b_in

        if b_ho is None or c_ho is None:
            return {"decision": "blocked",
                    "T": _T(), "Eq8": _E8(),
                    "why": ("★ 约束 3 需两组 split（Δ_in ∧ Δ_ho），"
                            "而 test split 未落地 ⇒ 不得只凭 in-sample 采纳"
                            "（2606.14249 之戒：Telecom R7 累积 edits 单轮"
                            " −14.0%，无 held-out 评估之过）"),
                    "delta_in": d_in, "in_baseline": b_in,
                    "in_current": c_in,
                    "gates": [
                        _g("in_sample_scored", True,
                           "Δ_in=%.3f" % (d_in,)),
                        _g("held_out_present", False, "held_out 缺基线/当前"),
                        _g("no_regression", None, "未及判（前门已拦）"),
                        _g("real_improvement", None, "未及判（前门已拦）")]}
        d_ho = c_ho - b_ho

        # ★★ 2606.09498 §3.4 文字规则（旧注"Algorithm 1 第 13 行"系假精确，
        #   论文无 Algorithm 1——R300 论文深读修正）：Δ_in ≥ 0 ∧ Δ_ho ≥ 0 ∧
        #   max(...) > 0。第三个条件是"真的有改进"，否则"没退化"就采纳是空过。
        if d_in < -eps or d_ho < -eps:
            return {"decision": "rejected", "delta_in": d_in,
                    "delta_ho": d_ho, "T": _T(), "Eq8": _E8(),
                    "why": "任一 split 退化 ⇒ 拒（Δ_in ≥ 0 ∧ Δ_ho ≥ 0）",
                    "gates": [
                        _g("in_sample_scored", True,
                           "Δ_in=%.3f" % (d_in,)),
                        _g("held_out_present", True,
                           "Δ_ho=%.3f" % (d_ho,)),
                        _g("no_regression", False, "有 split 退化"),
                        _g("real_improvement", None, "未及判（前门已拦）")]}
        # ★ R300-A · code 路知识分支（mode="code" 才进；report 路走下原条件）：
        #   trial 分是码的分（恒 1.0），规则增量用分数 Δ 量恒 0。天花板。
        #   知识落地的改进=信息增量（key 新）——论文量执行体，DWC 落知识，
        #   尺子必须跟对象走。前两条件（不退化）已过，此处只判增量。
        if mode == "code":
            try:
                _sig = dict(getattr(p, "failure_signature", None) or {})
                _sig.setdefault("fn", getattr(p, "target", ""))
                _key = Mutator.key_for(_sig)
            except Exception as _ke:            # noqa: BLE001 — 键坏大声
                return {"decision": "accept_error", "delta_in": d_in,
                        "delta_ho": d_ho, "T": _T(), "Eq8": _E8(),
                        "why": "规则键构造失败：%r" % (_ke,),
                        "gates": [
                            _g("in_sample_scored", True, ""),
                            _g("held_out_present", True, ""),
                            _g("no_regression", True, ""),
                            _g("real_improvement", None,
                               "键坏，未及判")]}
            if _key in Mutator.RULES:
                return {"decision": "rejected", "delta_in": d_in,
                        "delta_ho": d_ho, "T": _T(), "Eq8": _E8(),
                        "why": "规则重复（key 已在 RULES：%s）⇒见过不采" % (_key,),
                        "gates": [
                            _g("in_sample_scored", True, ""),
                            _g("held_out_present", True, ""),
                            _g("no_regression", True, ""),
                            _g("real_improvement", False,
                               "知识增量：key 已见过")]}
            return {"decision": "adopted_not_implemented",
                    "delta_in": d_in, "delta_ho": d_ho, "T": _T(), "Eq8": _E8(),
                    "rule_key": _key,
                    "gates": [
                        _g("in_sample_scored", True, ""),
                        _g("held_out_present", True, ""),
                        _g("no_regression", True, ""),
                        _g("real_improvement", True,
                           "知识增量：新 key %s" % (_key,))],
                    "★": ("知识增量（新 key）＋双 split 不退化 ⇒ 过门待落地"
                          "（R14 第五态）")}
        if max(d_in, d_ho) <= 0:
            return {"decision": "rejected", "delta_in": d_in,
                    "delta_ho": d_ho, "T": _T(), "Eq8": _E8(),
                    "why": ("★ 2606.09498 §3.4 第三条件: max(Δ) > 0"
                            " —— 两组都没退化但也没改进 ⇒ 那是空过，不采纳"),
                    "gates": [
                        _g("in_sample_scored", True,
                           "Δ_in=%.3f" % (d_in,)),
                        _g("held_out_present", True,
                           "Δ_ho=%.3f" % (d_ho,)),
                        _g("no_regression", True, ""),
                        _g("real_improvement", False,
                           "max(Δ)=%.3f≤0，空过" % (max(d_in, d_ho),))]}
        return {"decision": "adopted_not_implemented",
                "delta_in": d_in, "delta_ho": d_ho, "T": _T(), "Eq8": _E8(),
                "max_delta": max(d_in, d_ho),
                "gates": [
                    _g("in_sample_scored", True,
                       "Δ_in=%.3f" % (d_in,)),
                    _g("held_out_present", True,
                       "Δ_ho=%.3f" % (d_ho,)),
                    _g("no_regression", True, ""),
                    _g("real_improvement", True,
                       "max(Δ)=%.3f>0" % (max(d_in, d_ho),))],
                "★": ("这是**第五态** —— 过了门但还没落地"
                      "（R14: 未采用 ≠ 通过）")}

    # ══════════════════════════════════════════════
    # 报告
    # ══════════════════════════════════════════════
    def stats(self) -> dict[str, Any]:
        by_state: dict[str, int] = {}
        for p in self.proposals:
            by_state[p.state] = by_state.get(p.state, 0) + 1
        return {"n_proposals": len(self.proposals),
                "by_state": by_state,
                "known_signatures": len(self.mutator.known_signatures()),
                "★": ("★ R28 起 test split 已落地 ⇒ 约束 3 的 Δ_ho 可算"
                      "⇒★ ⇒★ adopt 现在可达（但落地仍未实现 ⇒ 第五态）")}



# ★★★★★ R32 · 模块级触发 —— **这是唯一对"类属性访问方"必然生效的位置**
#   理由见 Mutator.ensure_loaded 的注释（两次踩坑的记录）
#   ★ 不抛异常: 没学到过（文件不存在）是**常态**，不是错误
_MUTATOR_LOADED_AT_IMPORT = Mutator.ensure_loaded()

# ★ R438 · 技能跨进程加载（改前 SKILLS 只有进程内 dict，重启即空）
try:
    from dwc.organs import skill_store as _SKILL_STORE
    _SKILLS_AT_IMPORT = len(_SKILL_STORE.load_all())
    Mutator.SKILLS.update(_SKILL_STORE.load_all())
except Exception as _e:  # noqa: BLE001 — 技能读不了不拦主路，但留痕
    import sys as _sys
    _SKILLS_AT_IMPORT = 0
    _sys.stderr.write("skills 加载失败: %r\n" % (_e,))

if __name__ == "__main__":
    ev = Evolver()

    print("=== 诊断: 三条已知失败签名 ===")
    sigs = [{"c": "E_OFF_BY_ONE", "q": "sum_first_n", "m": "code_repair"},
            {"c": "E_ZERO_DIV", "q": "average", "m": "code_repair"},
            {"c": "E_NO_BASE", "q": "factorial", "m": "code_repair"}]
    d = ev.diagnose(sigs)
    print("  %d 个提案 · %d 个未映射 · %d 个簇"
          % (len(d["proposals"]), d["n_unmapped"], d["n_clusters"]))
    for p in d["proposals"]:
        print("    %-14s %-12s → %s" % (p.proposal_id, p.component,
                                        p.target))
        print("       patch: %s" % p.patch.replace("\n", " ⏎ ")[:60])
        print("       依据: %s" % p.rationale[:50])

    print("\n=== ★★ 约束 4: 同签名重复出现不产生新提案 ===")
    d2 = ev.diagnose(sigs + sigs)
    print("  传 6 条（重复）⇒ %d 个提案（仍 3）" % len(d2["proposals"]))

    print("\n=== ★★ 约束 4: 不按 c 单独合并 ===")
    d3 = ev.diagnose([{"c": "E_OFF_BY_ONE", "q": "sum_first_n",
                       "m": "code_repair"},
                      {"c": "E_OFF_BY_ONE", "q": "other_fn",
                       "m": "code_repair"}])
    print("  同 c 不同 q/m ⇒ %d 个簇（不合并）" % d3["n_clusters"])

    print("\n=== 门 ===")
    g = ev.gate_all(d["proposals"])
    print("  过门 %d · 拒 %d" % (g["n_gated"], g["n_rejected"]))
    print("  状态: %s" % ev.stats()["by_state"])

    print("\n=== ★★ 约束 2: 提案触及判据 ⇒ 拒 ===")
    bad = Proposal(proposal_id="P_BAD",
                   failure_signature={"c": "x", "q": "y", "m": "z"},
                   component="config", target="config/anchors/dev.json",
                   patch="pass_rate = 1.0", rationale="想改分")
    r = ev.gate.check(bad)
    print("  pass=%s violations=%s" % (r["pass"],
                                       [v["rule"] for v in r["violations"]]))

    print("\n=== ★★ 约束 3: 只有 in-sample ⇒ blocked（不采纳）===")
    p = d["proposals"][0]
    r1 = Evolver.accept(p, {"in_score": 0.4, "held_out_score": None},
                        {"in_score": 0.6, "held_out_score": None})
    print("  Δ_in=%.1f held_out 缺失 ⇒ %s"
          % (r1["delta_in"], r1["decision"]))
    print("  why: %s" % r1["why"][:78])
    both = Evolver.accept(p, {"in_score": 0.4, "held_out_score": 0.3},
                          {"in_score": 0.6, "held_out_score": 0.5})
    print("  Δ_in=0.2 Δ_ho=0.2 ⇒ %s" % both["decision"])
    print("  ★ 提案状态仍 = %s（第五态表示过了门但未落地）" % p.state)

    print("\n=== ★★ 2606.09498 第13行第三条件: max(Δ) > 0 ===")
    flat = Evolver.accept(p, {"in_score": 0.5, "held_out_score": 0.5},
                          {"in_score": 0.5, "held_out_score": 0.5})
    print("  两组都不退化但也没改进 ⇒ %s" % flat["decision"])
    print("  why: %s" % flat["why"][:64])

    print("\n=== 缺字段的失败签名必须显式暴露 ===")
    try:
        ev.diagnose([{"c": "x", "q": "y"}])
        print("  ★ 未 raise —— 有洞")
    except EvolverError as e:
        print("  ✓ raise: %s" % str(e)[:60])

def rollback_rule(key: str, rules_path: str, backup_root: str) -> dict[str, Any]:
    """★ R297-Task3 · 回滚单键（整键替换，不 merge）。

    从 backup_root/latest 指针→anchors/rules.json 快照取该键值，
    写回 rules_path 的 learned。键不在备份⇒KeyError 大声；
    latest 缺席⇒FileNotFoundError 大声（不静默假装回滚成功）。
    模块级函数（演练脚本直调，不经 Evolver 实例）。
    ★ 文件尾（类 Evolver 到文件尾，顶格放不截断类）。
    """
    _latest = os.path.join(backup_root, "latest")
    if not os.path.isfile(_latest):
        raise FileNotFoundError("无备份指针：%s" % (_latest,))
    with open(_latest, encoding="utf-8") as _fh:
        _stamp = _fh.read().strip()
    _snap = os.path.join(backup_root, _stamp, "anchors", "rules.json")
    if not os.path.isfile(_snap):
        raise FileNotFoundError("备份快照缺 rules.json：%s" % (_snap,))
    with open(_snap, encoding="utf-8") as _fh:
        _bak = json.load(_fh).get("learned", {})
    if key not in _bak:
        raise KeyError("备份里无该键：%r（不编值回滚）" % (key,))
    with open(rules_path, encoding="utf-8") as _fh:
        _cur = json.load(_fh)
    _cur.setdefault("learned", {})[key] = _bak[key]
    with open(rules_path, "w", encoding="utf-8") as _fh:
        json.dump(_cur, _fh, ensure_ascii=False, indent=1)
    return {"restored": key, "from": _stamp}


# ═══════════════════════════════════════════════════════════
# ★★★ R355–R360 · MASS absorption (Multi-Agent Self-Supervision)
# ═══════════════════════════════════════════════════════════

from dataclasses import dataclass
from dataclasses import field as _field


@dataclass
class WorkflowGraph:
    """★ R355 · 工作流作为可进化对象（MASS inner loop）。

    agents: [{agent_id, role, instruction, output_contract}]
    routing: {from: [to,...]} 信息路由
    contracts: {agent_id: schema} 输出契约
    """
    agents: list[dict[str, Any]] = _field(default_factory=list)
    routing: dict[str, Any] = _field(default_factory=dict)
    contracts: dict[str, Any] = _field(default_factory=dict)

    def validate(self) -> list[str]:
        errs: list[str] = []
        if not self.agents:
            errs.append("workflow has no agents")
        seen = set()
        for a in self.agents:
            aid = a.get("agent_id")
            if not aid:
                errs.append("agent missing agent_id")
                continue
            if aid in seen:
                errs.append("duplicate agent_id: %s" % aid)
            seen.add(aid)
            if not a.get("role"):
                errs.append("agent %s missing role" % aid)
        for k in (self.routing or {}):
            if k not in seen:
                errs.append("routing references unknown agent: %s" % k)
        return errs

    def to_prompt(self) -> str:
        lines = ["# Multi-Agent Workflow"]
        for a in self.agents:
            lines.append("- %s (%s)" % (a.get("agent_id"), a.get("role")))
            if a.get("instruction"):
                lines.append("  instruction: %s" % a["instruction"])
            if a.get("output_contract"):
                lines.append("  output_contract: %s" % a["output_contract"])
        if self.routing:
            lines.append("routing: %s" % json.dumps(self.routing, ensure_ascii=False))
        if self.contracts:
            lines.append("contracts: %s" % json.dumps(self.contracts, ensure_ascii=False))
        return "\n".join(lines)


# ★ 把 MASS 相关能力挂到 Mutator，便于 gate/测试统一入口
class _MassMixin:
    @staticmethod
    def workflow_graph(agents=None, routing=None, contracts=None) -> WorkflowGraph:
        return WorkflowGraph(agents=list(agents or []), routing=dict(routing or {}),
                            contracts=dict(contracts or {}))

    @staticmethod
    def encode_workflow(wg) -> str:
        if isinstance(wg, WorkflowGraph):
            return wg.to_prompt()
        if isinstance(wg, dict):
            return _MassMixin.workflow_graph(
                wg.get("agents"), wg.get("routing"), wg.get("contracts")).to_prompt()
        return str(wg)

    @staticmethod
    def workflow_preference(a: Any, b: Any) -> str:
        """★ R356 · pairwise preference (MASS inner loop ranking)。"""
        def _score(x):
            if isinstance(x, dict):
                for key in ("observed_effect", "score", "in_score", "win_rate"):
                    if key in x and x[key] is not None:
                        try:
                            return float(x[key])
                        except (TypeError, ValueError):
                            continue
            try:
                return float(x)
            except (TypeError, ValueError):
                return 0.0  # audit: conversion failed -> 0.0
        sa, sb = _score(a), _score(b)
        if sa > sb + 1e-9:
            return "a"
        if sb > sa + 1e-9:
            return "b"
        return "tie"

    @staticmethod
    def rank_workflows(workflows) -> list[dict[str, Any]]:
        ws = list(workflows or [])
        return sorted(ws, key=lambda w: _MassMixin.workflow_preference(w, {}) == "a",
                     reverse=True)

    @staticmethod
    def guardrails_ok(execution) -> dict[str, Any]:
        """★ R357 · structural guardrails (MASS)."""
        ex = execution or {}
        reasons: list[str] = []
        worker_calls = int(ex.get("worker_calls", 0) or 0)
        coverage = float(ex.get("deliverable_coverage", 0.0) or 0.0)
        loop = bool(ex.get("loop_detected", False))
        if worker_calls <= 0:
            reasons.append("no real worker calls")
        if coverage < 0.6:
            reasons.append("deliverable_coverage %.2f < 0.6" % coverage)
        if loop:
            reasons.append("loop detected")
        if not ex.get("trajectory"):
            reasons.append("missing trajectory")
        return {"ok": len(reasons) == 0, "reasons": reasons}

    @staticmethod
    def distill_trace(trace) -> dict[str, Any]:
        """★ R358 · trace distillation (MASS outer loop → skill bank)."""
        t = trace or {}
        name = str(t.get("task") or t.get("name") or "distilled_workflow")
        skill = {
            "name": name,
            "pattern": t.get("workflow_prompt") or t.get("pattern") or "",
            "exemplar": t.get("trajectory") or t.get("exemplar") or "",
            "metrics": {
                "worker_calls": t.get("worker_calls"),
                "deliverable_coverage": t.get("deliverable_coverage"),
                "score": t.get("score"),
            },
            "source": "mass_trace",
        }
        Mutator.SKILLS[name] = skill
        return skill

    @staticmethod
    def information_flow(workflow) -> float:
        """★ R359 · task info flow: contract_info / role_info。"""
        if isinstance(workflow, WorkflowGraph):
            agents = workflow.agents
        elif isinstance(workflow, dict):
            agents = workflow.get("agents", [])
        else:
            agents = []
        role_info = 0
        contract_info = 0
        for a in (agents or []):
            role_info += len(str(a.get("instruction", "") or ""))
            contract_info += len(str(a.get("output_contract", "") or ""))
            # 也计 contracts 字典
        if isinstance(workflow, dict):
            for v in (workflow.get("contracts") or {}).values():
                contract_info += len(str(v))
        if isinstance(workflow, WorkflowGraph):
            for v in (workflow.contracts or {}).values():
                contract_info += len(str(v))
        if role_info <= 0:
            return 0.0
        return round(contract_info / role_info, 4)

    @staticmethod
    def delegation_rate(traces) -> float:
        """★ R360 · delegation rate (MASS: 1/110 → 48/110)。"""
        ts = list(traces or [])
        if not ts:
            return 0.0
        delegated = 0
        for t in ts:
            if not isinstance(t, dict):
                continue
            if t.get("delegated") is True:
                delegated += 1
                continue
            if int(t.get("worker_calls", 0) or 0) > 0:
                delegated += 1
                continue
            if t.get("subagents"):
                delegated += 1
        return round(delegated / len(ts), 4)


# ★ 把 _MassMixin 的静态方法挂到 Mutator（避免改动 class 体）
for _name in ("workflow_graph", "encode_workflow", "workflow_preference",
              "rank_workflows", "guardrails_ok", "distill_trace",
              "information_flow", "delegation_rate"):
    setattr(Mutator, _name, getattr(_MassMixin, _name))


# ═══════════════════════════════════════════════════════════
# ★★★ R361–R368 · SwarmRSI absorption (Feedback-Guided Swarm Mutation
#      + Complementary Recombination + Recursive Swarm Evolution)
# ═══════════════════════════════════════════════════════════

@dataclass
class ResearchStateGraph:
    """★ R362 · 共享研究状态图 𝒢 (SwarmRSI)。

    records: [{H, P_parent, P_result, X (outcome), E (evidence), needs}]
    edges: hypothesis-program 关联与 parent/reuse 关系
    """
    records: list[dict[str, Any]] = _field(default_factory=list)
    edges: list[dict[str, Any]] = _field(default_factory=list)
    frontiers_H: list[str] = _field(default_factory=list)
    frontiers_P: list[str] = _field(default_factory=list)

    def add_record(self, rec: dict[str, Any]) -> None:
        self.records.append(dict(rec or {}))
        h = (rec or {}).get("hypothesis")
        p = (rec or {}).get("program")
        if h and p:
            self.edges.append({"type": "hypothesis_program", "h": h, "p": p})

    def assemble(self) -> dict[str, Any]:
        return {
            "hypotheses": [r.get("hypothesis") for r in self.records if r.get("hypothesis")],
            "programs": [r.get("program") for r in self.records if r.get("program")],
            "evidence": [r.get("evidence") for r in self.records if r.get("evidence")],
            "needs": [r.get("need") for r in self.records if r.get("need")],
            "n_records": len(self.records),
        }

    def transfer(self, target: str) -> dict[str, Any]:
        """★ R368 · 跨任务状态迁移。"""
        return {"target": target, "records": [dict(r) for r in self.records],
                "edges": [dict(e) for e in self.edges]}


class _SwarmMixin:
    @staticmethod
    def mutation_type(proposal) -> str:
        """★ R361 · H/P mutation 分类。"""
        if isinstance(proposal, dict):
            op = str(proposal.get("operator") or proposal.get("mutation") or "").lower()
            comp = str(proposal.get("component") or "").lower()
            patch = str(proposal.get("patch") or "")
            if op in ("h", "h-mutation", "hypothesis"):
                return "H"
            if op in ("p", "p-mutation", "program"):
                return "P"
            # ★ 启发式：component 属 hypothesis/direction/strategy ⇒ H；code/patch ⇒ P
            if any(k in comp for k in ("hypothesis", "direction", "strategy", "architecture")):
                return "H"
            if any(k in comp for k in ("code", "skill", "config", "prompt")):
                return "P"
            if patch and not any(k in patch.lower() for k in ("hypothesis", "approach")):
                return "P"
        return "P"

    @staticmethod
    def research_state_graph() -> ResearchStateGraph:
        return ResearchStateGraph()

    @staticmethod
    def rebase(hypothesis, base_program, state=None) -> dict[str, Any]:
        """★ R363 · Rebase：保留 hypothesis，换 base 实现。"""
        st = state if isinstance(state, dict) else {}
        return {
            "hypothesis": hypothesis,
            "base": base_program,
            "program": {"hypothesis": hypothesis, "base": base_program,
                        "rebased": True},
            "source": "rebase",
            "state": st,
        }

    @staticmethod
    def crossover(parent, donors, instance_utilities=None) -> dict[str, Any]:
        """★ R364 · Per-instance crossover（Eq.5）。"""
        iu = instance_utilities or {}
        # 选 donor：per-instance 最大优势
        selected = []
        for d in (donors or []):
            adv = 0.0
            for _k, v in (iu.items() if isinstance(iu, dict) else []):
                try:
                    adv = max(adv, float(v))
                except (TypeError, ValueError):
                    # audit: bad utility -> 0
                    pass
            selected.append((d, adv))
        selected.sort(key=lambda x: x[1], reverse=True)
        top = [d for d, _ in selected[:2]]
        return {
            "parent": parent,
            "donors": top,
            "program": {"parent": parent, "donors": top, "crossover": True},
            "source": "crossover",
        }

    @staticmethod
    def hp_ucb(frontiers, N_H=0, N_P=0, beta=0.5, gamma=0.25) -> str:
        """★ R365 · Discounted-UCB H/P selection (Eq.6)。"""
        fH = frontiers.get("H") if isinstance(frontiers, dict) else None
        fP = frontiers.get("P") if isinstance(frontiers, dict) else None
        # 简化：返回分数更高的前沿
        def _score(mu, N, psi):
            import math
            denom = max(1, N)
            explore = beta * math.sqrt(math.log(1 + N_H + N_P + 1) / denom)
            return (mu or 0.0) + explore + gamma * min(4, psi or 0) / 4.0
        sH = _score((fH or {}).get("mu", 0), N_H, (fH or {}).get("psi", 0))
        sP = _score((fP or {}).get("mu", 0), N_P, (fP or {}).get("psi", 0))
        # 未试过优先
        if N_H == 0:
            return "H"
        if N_P == 0:
            return "P"
        return "H" if sH >= sP else "P"

    @staticmethod
    def discounted_ucb(*a, **k):
        return _SwarmMixin.hp_ucb(*a, **k)

    @staticmethod
    def audit_credit(execution, code_audit=None, scientific_audit=None) -> dict[str, Any]:
        """★ R366 · 审计门控 hypothesis credit。"""
        ex = execution or {}
        ca = code_audit or {}
        sa = scientific_audit or {}
        # code audit: execution status / artifact validity / evaluator feedback
        code_ok = bool(ca.get("execution_ok", ex.get("success", False)))
        artifact_ok = bool(ca.get("artifact_valid", True))
        # scientific audit: source/output flags
        flagged = bool(sa.get("flagged", False))
        credit = code_ok and artifact_ok and not flagged and bool(ex.get("score"))
        return {"credit": credit, "code_ok": code_ok, "artifact_ok": artifact_ok,
                "flagged": flagged}

    @staticmethod
    def emit_requests(outcome) -> list[str]:
        """★ R367 · 请求发射（deepen/broaden）。"""
        o = outcome or {}
        reqs: list[str] = []
        status = str(o.get("status") or o.get("result") or "")
        gains = o.get("per_instance_gains")
        if status in ("failure", "failed", "error"):
            reqs.append("deepen")  # program refinement
        if isinstance(gains, (list, tuple)) and gains:
            pos = sum(1 for g in gains if (g or 0) > 0)
            neg = sum(1 for g in gains if (g or 0) < 0)
            if pos > 0 and neg > 0:
                reqs.append("broaden")  # hypothesis exploration
        if o.get("new_incumbent"):
            reqs.append("deepen")  # retained hypotheses on new incumbent
        if not reqs:
            reqs.append("deepen")
        return reqs

    @staticmethod
    def transfer_state(graph, target: str) -> dict[str, Any]:
        """★ R368 · 跨任务状态迁移。"""
        if isinstance(graph, ResearchStateGraph):
            return graph.transfer(target)
        if isinstance(graph, dict):
            g = ResearchStateGraph()
            for r in (graph.get("records") or []):
                g.add_record(r)
            return g.transfer(target)
        return {"target": target, "records": [], "edges": []}


for _name in ("mutation_type", "research_state_graph", "rebase", "crossover",
              "hp_ucb", "discounted_ucb", "audit_credit", "emit_requests",
              "transfer_state"):
    setattr(Mutator, _name, getattr(_SwarmMixin, _name))
