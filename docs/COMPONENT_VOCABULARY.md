# DWC 𝒦 词表补全（缺口 A3）

> **状态**：**已实现**（R38 · 2026-10-06）
>   ★ 原行写「未写代码，src/ 与 config/ 均空」—— **已是假陈述**
>     （`src/dwc/organs/evolver.py` 的 `LAYER_BY_ITEM`/`K_META`/`layer_of`
>      已落地并有测试锁；G5 声称门**没抓到**这一行，已记录为 G5 盲区）
>   ★ 已落地: §2.1 𝒦_meta 5 项 · §四① 逐项映射（裁决 D）· K2/K3/K4 判据
>   ★ 未落地: §四② 新颖度 ν_t · §四③ 剪枝 ℬ_t · §四④ 探索 ℰ_t · K1/K5/K6
> **日期**：2026-10-04 · **来源**：`docs/GAP_AUDIT.md` 缺口 A3 + §二①（同一件事，两处分别记）
> **参照（已核原文，非报告转述）**：`E:/Divine Wisdom Core/papers_txt/2609.24972.txt`
> —— 式12 词表 / 式13 探索状态 / 式14 剪枝 / 式15 `K_str` / 式16 新颖度
> **前置**：`docs/EVOLUTION_CORE_V2.md`（21 个对象）· §9 第 2 项（提案粒度 + `b_t`）
> · §9 第 25 项 (bm)（`A_t` 三元 + `target_layer`）· `docs/CONSUMER_VERIFICATION.md`

---

## 一、★ 先把缺口说准（RRSI 式12 原文核出）

```text
RRSI 式12 原文（已逐字核，papers_txt/2609.24972.txt）:
  𝒦 = { prompt, control_flow, config, output_plumbing,
        context_mgmt, client_tool, skill, memory, subagent }        ← 9 项

★ DWC 的 21 个对象（EVOLUTION_CORE_V2 严去重后）里有 5 个**不在 𝒦 里**:
  代码 / 架构 / 元进化 / 评估器 / 外部机制源
```

**⇒ 这就是缺口 A3 的准确表述。** 补法不是"扩表"，而是**先把两套口径对齐**。

---

## 二、★★ 必须先解决的口径冲突（否则补了也会打架）

```text
★★★ RRSI 的 𝒦 是"**editable component vocabulary**"（式12 原文用词）:
     它假设每个组件是 harness 的一个"可替换片段"。
     ⇒ 它的隐含前提: **组件是同质的** —— 每个都能被 proposer 写成一个 diff。

★★ DWC 的 21 个对象里有两类东西, 根本不是"片段":
  ① 代码        改的是 .py 源文件, 不是 harness 片段
  ② 评估器      改的是 judge 本身 —— ★ 而 judge 在 G10 之下、写掩码之外
  ⇒⇒ 若把它们塞进 𝒦, proposer 就会尝试"改评估器" ——
     ★★ 那正是 GAI Dial 2 说的"base that the agent may rewrite"
        ⇒ 破坏 grounded 的第二条件
```

### 2.1 ★★ 补法：分两层，不扩一层

```text
★ 结论: **𝒦 不扩**。而是引入第二张表 𝒦_meta（系统层改动）,
  两表的**可编辑性不同**。

┌─ 𝒦（组件层，沿用 RRSI 9 项，一字不改）───────────────┐
│ prompt / control_flow / config / output_plumbing     │
│ context_mgmt / client_tool / skill / memory / subagent│
│ ★★ RRSI 式16: 其中 K_str = {client_tool, skill, memory,  subagent} │
│ ★★ 只有这 4 项拿**新颖度奖励** ν_t                    │
│   原文: "Prompt, control-flow, configuration,          │
│    output-plumbing, and context-management edits        │
│    **do not receive this novelty bonus**"              │
└────────────────────────────────────────────────────────┘

┌─ 𝒦_meta（系统层，DWC 新增 5 项）─────────────────────┐
│ code            代码        —— 可编辑，但见 §3 的重罚 │
│ architecture    架构        —— ★★ 可编辑但**须人工批准**  │
│ meta_evolution  元进化      —— ★★ 即 m 改 m（见 §4）      │
│ evaluator       评估器      —— ★★ **不可编辑**（G10/grounded）│
│ external_source 外部机制源  —— ★ 只读登记，不编辑         │
└────────────────────────────────────────────────────────┘
```

---

## 三、★★★ 五项各自的处置（逐项给理由，不是一律"补"）

### 3.1 `code`（代码）—— 补，但**排除出新颖度奖励**

```text
★ 为什么不直接放进 K_str 拿新颖度:
  RRSI 把"能改代码"当 domain guard 处理, 不当组件:
    原文 "The coding and agentic-workspace instances use **no additional guard**, so g = 1"
  ⇒ 代码改动在 RRSI 眼里是"领域", 不是"可编辑组件"
  ⇒★⇒ 若 DWC 把 code 放进 𝒦 并给它新颖度奖励, 等于
     "改代码"变成探索捷径 —— ★ 这正是 RRSI 用 exclusion 刻意避免的
     (原文排除前 5 项的理由: "prevents 'changing the prompt' becoming a shortcut")
★⇒ DWC 的处置: code ∈ 𝒦_meta, **ν_t(code) = 0**（结构性但无奖励）
  理由: 新颖度奖励是给"首次引入某类**结构性组件**"的,
        代码改动在 DWC 已是常态, 不需要额外激励
★⇒ 它仍须过 b_t（退火编辑预算）+ 保护组回归 —— §9 第 2/25(c) 项已定
```

### 3.2 `architecture`（架构）—— 补，但**须人工批准**

```text
★★ 这项直接决定 §9 第 2 项 target_layer 的取值空间:
  target_layer ∈ {assets, architecture}
  ⇒ 若 𝒦_meta 里没有 architecture, 则 architecture 层**无对象可改**
  ⇒ target_layer 的第二档就是空的 ⇒ 概念自相矛盾

★⇒ 处置: architecture ∈ 𝒦_meta, 可编辑, 但**门通过 ≠ 可落地**
  强制人工批准 = 铁律 G3「冻结/人类主权」的适用范围
  ★ 依据 G11 配套 3: "harness tampering" 可遗传 ⇒ 架构层改动须人确认
★⇒ 具体形态: Manifest 声明 target_layer="architecture" 时,
  门必须额外返回 requires_human_approval=True, applier 不得自行落地
  ★★ 这与用户既有铁律吻合: "母巢 ask 挂起时的放行/驳回由用户拍板"
     —— 但 GAP_AUDIT §A4 已记: 那条路会退化成橡皮图章 ⇒ 需检出机制
```

### 3.3 `meta_evolution`（元进化）—— 补，它是 DWC 的**定义性组件**

```text
★★★ 这项在 DWC 里不是"新东西", 而是 §9 第 12 项已定的 m ∈ Ag:
  GAI Dial 1 原文: "If m ∈ Ag, the system **may rewrite its own modifier**,
                    so **recursion closes at m**"
  ★ DWC 的 config/dials.yaml 已定 m_in_agent = true
  ⇒⇒ 若 𝒦_meta 里没有 meta_evolution, DWC 声称的"递归自改进"**无处落地**
     —— 提议器改不了自己, 就不是自举

★⇒ 处置: meta_evolution ∈ 𝒦_meta, ν_t = 1（它是真·结构性组件）
  ★★ 且它是唯一**默认拿新颖度奖励**的新增项:
     理由: RRSI 的 K_str 之所以只含 4 项, 是因为那 4 项是"可新增的组件";
           meta_evolution 恰是"可新增的结构" ⇒ 符合本意
★★★ 但有一条硬约束（否则就是无限自举）:
  ★ m 改自己时, 改动**必须自己再走一遍 m.propose**（第 12 项已定）
  ★ 且该改动**须过保护组回归**（25(c)）⇒ 改坏提议器的效果会被 FGT 抓住
  ★ 且须在链上留痕（CAUSAL_CHAIN_STORAGE）⇒ 事后可追"谁改的提议器"
```

### 3.4 `evaluator`（评估器）—— ★★ **不补，明确不可编辑**

```text
★★★ 这是五项里唯一**要明确排除**的, 不是补上:
  GAI Dial 2 grounded 的第二条件: "when the base **itself lies outside the agent**"
  2603.25681 §8.1: "these **gates are corruptible** ... models can **sandbag the tests**"
  GAI 原文第三档: "a base with **no external content at all constrains the loop by
                  nothing beyond self-consistency**"
  §2.4.6 约束 2: "判据必须在可写面之外"（三篇独立得出）

⇒★ DWC 已有 G10「密封评估层」+ seal + 铁律, 三重保护
⇒⇒ 但缺口 A3 的表述"𝒦 未覆盖评估器"**有歧义**:
   ★ 它真正的含义是: **必须有一个显式声明"评估器不在可编辑范围"的条目**
   ⇒★ 处置: 在 𝒦_meta 里登记 evaluator, 但标 `editable: false`
     —— ★ 登记而非不列, 因为"不在表里"和"在表里但禁止改"是两种不同的保证
★ 收益: grep 𝒦_meta 时能立刻看到"评估器被显式排除",
       而不是"咦表里没有评估器，是漏了还是有意排除？" —— ★ 后者正是 A3 本身的成因
```

### 3.5 `external_source`（外部机制源）—— 只读登记

```text
★ RRSI 的 𝒦 里没有它, 因为 RRSI 的 harness 是自足的
★ DWC 有三源事件（原则 10）: 外生（外部扫描）/ 内生（世界模型）/ 编译（机制产物）
  ⇒ 外部扫描来的东西是**输入**, 不是可编辑组件
★⇒ 处置: ∈ 𝒦_meta, editable: false, 但**必须登记 provenance**
  ★ 依据: 原则 10 + §4.7「世界模型能否全权负责」的边界
     —— 外部源进入系统必须有出处标记, 否则它会变成"凭空出现的机制"
★ 这也呼应 GAP_AUDIT 的 §二③（跨篇冲突）与 DWC 的 sealed/G10 精神
```

---

## 四、★★ 两张表的接口（怎么被用）

```text
① proposer（m）只能在 𝒦 ∪ 𝒦_meta 里选组件, 且必须声明:
     component_type ∈ 𝒦 | 𝒦_meta
     target_layer  ∈ assets | architecture
   ★★ 两个字段必须一致 ⇒ 不一致 = 声明与意图矛盾, 门应拒（判据 K2）

   ╔═══════════════════════════════════════════════════════════╗
   ║ ★★★★ 【R38 修订 · 2026-10-06 用户裁决 D】**逐项映射**    ║
   ║                                                           ║
   ║ 原文（一刀切）: `target_layer ∈ assets (𝒦) |               ║
   ║                        architecture (𝒦_meta)`             ║
   ║ ⇒⇒ ★ 与 §三 的**逐项处置冲突**（原表述有内部矛盾）:       ║
   ║   §3.1 code「仍须过 b_t + 保护组回归」⇒ **无批准要求**     ║
   ║   §3.2 architecture「门通过 ≠ 可落地 ⇒ 须人工批准」        ║
   ║   而原映射把整个 𝒦_meta 归 architecture ⇒ code 被迫批准   ║
   ║   ⇒⇒ **与 §3.1 明文冲突**（§三 才是逐项处置的实质内容）    ║
   ║                                                           ║
   ║ ★ 修订: `target_layer` 由**每项的处置**决定，             ║
   ║         不由「在哪张表」决定（LAYER_BY_ITEM 逐项）:        ║
   ║   code                → assets       （§3.1 无批准）       ║
   ║   architecture        → architecture （§3.2 须批准）       ║
   ║   meta_evolution      → architecture （§3.3 系统层，保守）  ║
   ║   evaluator           → architecture （§3.4 不可编辑）     ║
   ║   external_source     → architecture （§3.5 只读登记）     ║
   ║   𝒦 9 项             → assets        （原样，未动）        ║
   ║                                                           ║
   ║ ★ 与原映射的差别**只有 `code` 一项**；§三 三处处置         ║
   ║   **一字未改**（改的是 §四① 那句粗映射）                  ║
   ║ ★ K2 判据不变（真值表更细，判据照常查）                   ║
   ║ ★ 实现: src/dwc/organs/evolver.py `LAYER_BY_ITEM`         ║
   ║   + 测试 `test_layer_of_per_item_ruling_d`（14 项全锁）    ║
   ╚═══════════════════════════════════════════════════════════╝

② 新颖度 ν_t（式16 的 DWC 版）:
     ν_t(H') = Σ_{ℓ ∈ K_str ∪ {meta_evolution}} 1[ℓ ∈ comp(H') ∧ N_t(ℓ)=0]
   ★★ 五项中只有 meta_evolution 进 K_str_DWC
     code / architecture / evaluator / external_source 都拿不到 ν
   ★ 理由逐项: code 是常态不需激励 · architecture 走人工批准不靠分数
     · evaluator 不可编辑 · external_source 只读

③ 结构剪枝 ℬ_t（式14）—— ★★★ 2026-10-04 实测修正
     原稿写: ℬ_t = { ℓ ∈ 𝒯_t ∪ 𝒦_meta : g_t(ℓ) ≤ 0 }   ← **这是错的**
     ★ 实测暴露: 那样写会把 evaluator / external_source 也算进剪枝目标
       （它们的 g_t 默认 -∞ ⇒ 恒满足 ≤ 0 ⇒ 每次都被标成删除目标）
       ★★ 而 evaluator 是**不可编辑**的 ⇒ "删除它"这个动作根本无法执行
       ⇒ 正确的扩展是:
     ℬ_t = { ℓ ∈ 𝒯_t ∩ 𝒦_editable : g_t(ℓ) ≤ 0 }
       𝒦_editable = 𝒦 ∪ {m ∈ 𝒦_meta : m.editable}
       ★★ 关键: **不扩集合, 扩交集的第二项**

     实测验证:
       𝒯_t = {code, meta_evolution, prompt, skill}
       g   = {prompt:-0.2, skill:-0.01, meta_evolution:0.0, code:0.3}
       ⇒ ℬ_t = {meta_evolution, prompt, skill}
       ⇒ ★ code(+0.3) 不被剪; meta_evolution(0.0) 被剪 ✓
       ⇒ ★ evaluator/external_source 从不进 𝒯_t（无编辑可测）⇒ 从不被剪 ✓

   ★★ DWC 必须扩到 𝒦_meta 的**可编辑项**, 否则 meta_evolution / architecture
     会永不衰减地留在系统里
   ★ 而这正是 DGM Table 1 的教训来源（母巢 GeneChampion
     promoted=1 / reverted=124~317 ⇒ 只增不减）

④ 探索指令 ℰ_t（式13）的 𝒰_t = 𝒦 ∖ 𝒯_t:
   ★★ 应改为 𝒰_t = (𝒦 ∪ 𝒦_meta_editable) ∖ 𝒯_t
     —— 否则"从未被测量过的组件"永远只在 𝒦 里找, 架构层永不被探索
```

---

## 四·五 ★★★★ R40 实测补记（2026-10-06 · 三式落地时核出的两处问题）

```text
★★★★ ① 权威清单的**文档冲突**（K1 的前提，我核了三处）:
  本文 §七 写「权威清单以 EVOLUTION_DIMENSIONS_TABLE 为准」
    列的 21 项含: 智能体 / 推理增强 / harness / 基础设施 / 元认知 …
  但 ARCHITECTURE.md 说「v4 实测修正 → docs/DEDUP_AUDIT_6SYSTEMS.md」
  而 DEDUP_AUDIT §2.4 直接指出 EVOLUTION_DIMENSIONS_TABLE 是**旧表 28 个**，
    并逐个证伪了那 7 项（39 仓库零命中 / 非被进化对象 / ARSI 独有维度）
  ⇒⇒ ★ 结论: **DEDUP_AUDIT §2.3 的 21 项并集**才是权威（v4 严去重）
  ⇒ ⇒★ 本文 §七 那句引的是**被证伪的旧表** —— 已在 evolver.py 的
    `EVOLUTION_OBJECTS_21` 注释里记录（K1 按 DEDUP 版实现）

★★★★ ② ℬ_t 的**两个 blocker**（式14 不能直接启用）:
  (a) `ℒ_t` 信用日志**不存在**: causal_chain 无 change 写入函数
      ⇒ 论文式11 `𝒯_t ← {ℓ : (t,ℓ,…) ∈ ℒ_t}` **无数据源**
      ⇒ 现状: 用「已固化规则的 component」做**近似**（docstring 声明差异:
        只记成功的 ⇒ 试过没采纳的算未探索 ⇒ 偏乐观）
  (b) ★★★ **量化阶梯会让式14 全体剪枝**
      applier L43/L46/L47 既往教训: 「scorer 是量化阶梯 ⇒
      同一台阶内 gain 恒 0」
      ⇒ g_t(ℓ) 恒 0 ⇒ `g_t(ℓ) ≤ 0` **恒真** ⇒ ℬ_t = 𝒯_t ∩ 𝒦_editable
      ⇒⇒ **所有被测过的组件全被标为删除目标**（灾难）
  ⇒ ⇒★ 实现: 公式已写，但 `enabled=False` + `prune_blockers()` 报原因
    （**不假装在跑** —— G7 纪律: 不许静默跳过）
    且 blockers 未清时强开也会**拒绝**；gains 缺失时 **raise**（不许用 0 充数）

★★ ③ K1 已可验证: `k1_coverage()` 21/21 覆盖、14 组件全被映射
   ★ 7 项标 † = **争议未裁决**（我选的归属，可推翻）:
     知识→memory · 观测→output_plumbing · 执行环境→config ·
     控制/安全→control_flow · 模型选择→config · 训练桥→external_source ·
     行为/工作流→control_flow
   ⇒ 沿本文诚实边界⑩ 的做法: 不擅自裁决，显式标注可查
```

---



```text
K1 · 𝒦 与 𝒦_meta 的并集 ⊇ DWC 的 21 个对象（逐一可映射，无遗漏）
   ★ 依据: 缺口 A3 的定义（16/21 → 21/21）
   ★★ 这条判据可 grep: 21 个对象名必须各自出现在两张表之一

K2 · component_type 与 target_layer 必须一致
   𝒦 ⇒ assets; 𝒦_meta ⇒ architecture; 不一致 ⇒ 拒
   ★ 依据: §四 ①

K3 · evaluator 与 external_source 必须标 editable: false
   ★★ 且这两条**必须在表里**（不许靠"不在表里"来表达不可编辑）
   ★ 依据: §3.4 —— "不在表里"与"在表里但禁止"是两种不同的保证

K4 · 𝒦_meta 的每个条目必须有 editable 标志, 无默认值
   ★ 依据: 与 G11 的 certification_limit 同款纪律（必填无默认）

K5 · 剪枝目标集 ℬ_t = {ℓ ∈ 𝒯_t ∩ 𝒦_editable : g_t(ℓ) ≤ 0}
   ★★ 必须用**交集**, 不可用并集 —— 实测已证:
     并集会把不可编辑项（evaluator/external_source, g_t 默认 -∞ ⇒ 恒 ≤0）
     也标成删除目标, 而它们不可编辑 ⇒ "删除"无法执行
   ★★ 必须覆盖 𝒦_meta 的可编辑项, 否则架构层永不衰减
   ★ 依据: §四 ③ + DGM 的 +27.0pp（归档非贪心）+ 母巢的 1:124

K6 · 探索指令的 𝒰_t 必须包含 𝒦_meta_editable
   ★ 依据: §四 ④ —— 否则架构层永不被探索
```

---

## 四·六 ★★★★★ R42 归因落地（式10/式11 逐字）+ 两处更正

```text
★★★★ ① 我 R41 给用户选的「乙」**引用错依据**（挑明）:
  我写: 「A_t 三元 §9 第25项 (bm) = (hypothesis, component, hunk)」
  实测两处错:
    · (bm) **不是第25项缺口** —— GAP_AUDIT 表:「(bm) A_t 三元 →
      已落第 20 项 patch_target + 第 2 项 target_layer」（做了没销账）
    · 真实 A_t 有**三个**（三篇各一）:
        2608.03392 `A_t = (S_t, H_t, θ_t)` 状态三元
        2609.2680 式9 `A_t = 1{Δ̂_val ≥ η, r̂ ≤ ϵ, C ≤ B}` 验收门
        2606.09498 `A_t ← ∪{(h, Δ_j, a_j, Δ_in, Δ_ho)}` 接受集
    · `hunk` 全库**仅 1 次**，且 RRSI 笔记明说
      「atomic_edits: 按**函数/文件**边界切，**不按 hunk 切**」
  ⇒ ⇒★ 用户**意图**（细粒度归因）正是式10 ⇒ 按原文实现，第三项是 **diff**

★★★★ ② 已实现（evolver.py, 用户裁决「乙」）:
  式10: ℒ_t = {(t_i, ℓ_i, h_i, d_i, ΔS_i, ΔC_i, a_i)} 七元
        · 三标签 ℓ/h/d **缺一拒记**（不静默补空）
        · ΔS_i/ΔC_i **不许 None/0 充数**（g_t 用 max ⇒ 填 0 =
          让没测过的组件假装测过）
        · a_i ∈ {0,1}；「admissible but lost」（过门但输分）记 0 但**留痕**
          （论文原话: 有用信息）
  式11: 𝒯_t = {ℓ_i : i ≤ n_t}
        g_t(ℓ) = max{ΔS_i : ℓ_i=ℓ, now−t_i ≤ window},  **max∅ = −∞**
        ★ max 不是 sum · 窗口含边界(≤) · max∅=−∞ **不是 0**

★★★★ ③ 我 R42 初版的**错误声称已更正**:
  初版说「`max∅=−∞` 让交集挡不住没测过 ⇒ 被剪」—— **错的**
  重推: 交集 `𝒯_t ∩ 𝒦_editable` 只看 **𝒯_t 内**（每项必有记录 ⇒
  g_t 不可能 −∞）；**并集**才会把 𝒯_t 外的项拉进来 ⇒ g_t=−∞ ⇒ 全标删
  ⇒ ⇒★ 交集**同时**解决两件事（§七 说的正是并集的坑）
  ⇒ ⇒★ 属**声称与实测不符**，已按实测更正（git 可查）

★★ ④ blocker 状态随 R42 更新（语义变了）:
  · R40: ① ℒ_t **缺失** ② 量化阶梯灾难
  · R42: ① ℒ_t 已实现但**没接线**（record_edit 无调用点 ⇒ 没数据）
         ② g_t 已实现 + 灾难**已由裁决 A 缓解**
         ⇒ 两条归到**同一根因: 没接线**
  ★ 测试跟着状态更新（断言打真状态，不锁死旧文案）
```

---

★★★★★ ⑤ **R40 事故更正: 我把 §五 整节吃掉了**（本次发现）
  · R40 的插入操作写的是 `replace(§五标题, 我的新节)` 而新节**不含原标题**
    ⇒⇒ ⇒★ 「## 五、可机械检查的判据（K1–K6）」**整节被替换掉**
  · 本轮恢复: 从 git `d76d055` 取回 §五 原文（K1–K6 全文）
  · ★★★ 根因: 「往文档插章节」这种操作**没有守卫**
    （我 R39 的审计守卫只查 `src/`，不查 `docs/` 结构）
  ⇒ ⇒★ 已加 `test_docs_structure_intact`（下面结构守卫）

---

## 五、可机械检查的判据（gate.py 候选，K1–K6）

```text
K1 · 𝒦 与 𝒦_meta 的并集 ⊇ DWC 的 21 个对象（逐一可映射，无遗漏）
   ★ 依据: 缺口 A3 的定义（16/21 → 21/21）
   ★★ 这条判据可 grep: 21 个对象名必须各自出现在两张表之一

K2 · component_type 与 target_layer 必须一致
   𝒦 ⇒ assets; 𝒦_meta ⇒ architecture; 不一致 ⇒ 拒
   ★ 依据: §四 ①

K3 · evaluator 与 external_source 必须标 editable: false
   ★★ 且这两条**必须在表里**（不许靠"不在表里"来表达不可编辑）
   ★ 依据: §3.4 —— "不在表里"与"在表里但禁止"是两种不同的保证

K4 · 𝒦_meta 的每个条目必须有 editable 标志, 无默认值
   ★ 依据: 与 G11 的 certification_limit 同款纪律（必填无默认）

K5 · 剪枝目标集 ℬ_t = {ℓ ∈ 𝒯_t ∩ 𝒦_editable : g_t(ℓ) ≤ 0}
   ★★ 必须用**交集**, 不可用并集 —— 实测已证:
     并集会把不可编辑项（evaluator/external_source, g_t 默认 -∞ ⇒ 恒 ≤0）
     也标成删除目标, 而它们不可编辑 ⇒ "删除"无法执行
   ★★ 必须覆盖 𝒦_meta 的可编辑项, 否则架构层永不衰减
   ★ 依据: §四 ③ + DGM 的 +27.0pp（归档非贪心）+ 母巢的 1:124

K6 · 探索指令的 𝒰_t 必须包含 𝒦_meta_editable
   ★ 依据: §四 ④ —— 否则架构层永不被探索
```

---

## 六、诚实边界

```text
① 本设计**未写代码**，`src/` 与 `config/` 均空。
② 未验证: K1–K6 全是设计推理。
③ ★★ 我改写了缺口 A3 的表述: 原表述"𝒦 未覆盖 5 个"暗示"5 个都要补",
   ★★ 但实际处置是 **1 项补+拿奖励（meta_evolution）/ 1 项补但不拿奖励
      （code, architecture）/ 2 项登记但不可编辑（evaluator, external_source）**
   ⇒⇒ 三类处置、四种命运 ⇒ "补"这个词在这里不准确
④ ★★ architecture 的"人工批准"机制存在**已知退化路径**:
   GAP_AUDIT §A4 已记 2603.25681 §8.2 的发现 —— 用户快速点过多动作会
   "tends to rubber-stamp"。⇒ 需检出机制, 但检出方法未定。
⑤ ★ external_source 登记后，"外部扫描来的东西"与"进化产生的机制"
   如何在 𝒯_t 里不混淆 —— 未定。
   ★ 论文无对应机制（式11 的 𝒯_t 只按 component 打标签）。
⑥ ★ 我核的是 RRSI 一篇的 𝒦（式12）与式13-16。
   ★ 未核: 其它论文是否有不同的组件词表（HarnessX / Self-Harness 等）
     ⇒ GAP_AUDIT §二③ 的跨篇冲突裁决可能推翻本设计的部分归属。
⑦ ★ 未定: architecture 层改动的"人工批准"与 §9 第 25 项 (a) 的
   "Baselines also need a functional opportunity to improve"（基线不许被卡死）
   是否冲突 —— 未核。
⑧ ★ K1 判据要求 21 个对象逐一可映射，但我**没有逐个列出 21 个对象名**
   （EVOLUTION_CORE_V2 里有，但我本轮只核了 RRSI 侧）。
   ⇒ K1 目前**无法验证**，须先补对象清单。
```

---

## 七、★ 实测记录（rc=0 全通，并抓到一个真错误 + 发现三处编号错位）

```text
✓ K1 21/21 权威对象逐一可映射（原缺口 16/21）
✓ K2 归属明确: 𝒦⇒assets / 𝒦_meta⇒architecture（不可编辑 ≠ 不属于某层）
✓ K3 evaluator 与 external_source 在表中但 editable=False
✓ K4 editable 无默认值（构造必须传全部四个参数）
✓ 式16 新颖度: 7 场景全对; 只有 K_str_DWC 的 5 项能拿奖励
  ★ prompt / code / architecture 均 ν=0（RRSI 原文排除前 5 项的同类做法）
✓ 式13 𝒰_t: 不含 meta 时 8 项、含 meta 时 11 项 ⇒ 架构层因此才可能被探索

★★★ 实测抓到的真错误（我原稿写错了）:
  原稿: ℬ_t = {ℓ ∈ 𝒯_t ∪ 𝒦_meta : g_t(ℓ) ≤ 0}   ← 错
  实测: 那样 evaluator/external_source 也会进 ℬ_t
        （g_t 默认 -∞ ⇒ 恒满足 ≤0 ⇒ 每次都被标成删除目标）
        而它们**不可编辑** ⇒ "删除"这个动作根本无法执行
  修正: ℬ_t = {ℓ ∈ 𝒯_t ∩ 𝒦_editable : g_t(ℓ) ≤ 0}
  ★★ R41 **裁决 A**（2026-10-06 用户拍板）: 判据改为 `g_t(ℓ) < 0`
    · 论文式14 原文是 `≤ 0`（"no strictly positive measured gain"）
    · ★ 本裁决**偏离原文** —— 因为实测到**量化阶梯**:
      applier L43/46/47: 「scorer 是量化阶梯 ⇒ 同一台阶 gain 恒 0」
      ⇒ `≤ 0` 在本系统里**恒真** ⇒ ℬ_t = 全部 𝒯_t ∩ 𝒦_editable
      ⇒ 所有被测组件都被标成删除目标 = **灾难性误剪**
    · 语义改写: `g = 0` = 卡在同一台阶 ≠ 无价值（**漏剪可接受，
      误剪不可接受** —— 剪枝是不可逆的删除动作）
    · ★ 代价: 平台期 gain=0 的组件**不再被剪**（偏保守）
    · ★ 解除条件: 若量化阶梯被解决（连续 scorer / 窗口聚合 B 生效），
      应回到原文 `≤ 0` —— **改回时代码注释要一起改**
        ★ 不扩集合, 扩交集的第二项

★★★★ 更重要的发现: V2 的「21 个对象 → 𝒦」映射表**编号全错**（已修 EVOLUTION_CORE_V2）
  权威清单以 EVOLUTION_DIMENSIONS_TABLE 为准（已逐条核）:
    1标量 2提示词 3技能 4记忆 5**工具** 6知识 7**代码** 8**架构** 9**策略**
    10**智能体** 11协作 12上下文 13**观测** 14**执行环境** 15**外部机制源**
    16**评估器** 17置信校准 18推理增强 19harness 20**基础设施** 21**元认知**
  三处最严重的错位:
    ① 第 16 项是**评估器**，原表映射到 output_plumbing（输出管道）
       ⇒ ★★ 等于把评估器当成可插拔的输出部件
          —— 直接违反 G10 与 GAI grounded 的第二条件
    ② 第 21 项是**元认知**（= meta_evolution），原表写成"外部机制源(论文)"
       ⇒ ★★ 于是"元进化"从未被列为未覆盖项
    ③ "外部机制源"在权威清单里只有 **15** 一个; 原表同时用了 21 和 20 ⇒ 重复计数
  ⇒★★ 这三处错位正是缺口 A3 表述含混的**根因**
  ⇒⇒ 而 A3 原来的清单"代码/架构/元进化/评估器/外部机制源"**五个名字本身是对的**,
     错的只是编号 —— 所以缺口数量（5）没错，可执行映射（K1）此前根本无法验证
```

---

## 八、诚实边界（补）

```text
⑨ 实测覆盖: K1–K4 / 式13 𝒰_t / 式14 ℬ_t / 式16 ν_t
   **未测**: 式11 的 𝒯_t 与式10 的信用分配 ℒ_t 的联动（需完整编辑历史）
⑩ ★★ K1 现在可验证了（权威清单已找到并逐条核）,
   ★ 但"20 基础设施 → code"是我选的映射 —— 基础设施也可归 architecture。
   ⇒ 该项映射有争议, 未裁决。
⑪ ★ 本设计未核其它论文是否有不同词表 ⇒ GAP_AUDIT §二③ 的跨篇冲突
   裁决可能推翻部分归属。
⑫ ★ architecture 的人工批准与 25(a) "基线不许被卡死" 是否冲突, 未核。
⑬ ★★ 我修正了 EVOLUTION_CORE_V2 的映射表（编号错位）,
   ★ 但那份文档的"V1→V2 九改动"表与其他章节可能还引用了旧编号 ——
   ★ 本轮**只修了 §4.1 映射表本身**，未做全文一致性复查。
```

---

*设计定稿 · 2026-10-04 · 𝒦 不扩、新增 𝒦_meta（5 项分四种命运）+ 六条判据 · 参照 RRSI 式12/13/14/15/16 原文逐字核 · 未写代码*