# Ω 谱系「进化」词汇考据

> 生成：2026-10-02 · 深读 Prometheus-Omega / Omega-Omega / Omega-Genesis / Protogonos / ARSI / Ultra / Ultra-MultiTypeKB / nexus
> 纪律：每条结论带「仓库名 + 文件路径 + 原文引用」三元组。**只用原文，不用任何论文框架重新归纳。** 明确区分「设计文档」与「代码实现」。
> 数据源：`E:/Divine Wisdom Core/docs/repos/_all.json`（已抓取的 README + md）+ 本地 `E:/ARSI/`（完整仓库 148 个 py，含 `src/arsi/harness/` 54 个、`src/arsi/meta/` 11 个）。

---

## 0. 证据边界（先说没读到什么）

| 仓库 | README | 抓到的 md | 本地副本 | 状态 |
|---|---|---|---|---|
| Prometheus-Omega | 2038 字符 | README.md | `E:/Prometheus-Omega/` | ✅ 全读到 |
| Prometheus-Omega-Omega | 0 | 6 个 | 同上（同名同 hash） | ✅ 全读到 |
| Prometheus-Omega-Genesis | 0 | 0 | 无 | ❌ **零证据** |
| Protogonos | 0 | 0 | 无 | ❌ **零证据**（仅有他库转述，见 §6） |
| ARSI | 3967 字符 | 3 个 | `E:/ARSI/` 完整 | ✅ README+代码全读到 |
| Prometheus-Ultra | 0 | 9 个 | `E:/Prometheus-Ultra/` | ✅ 全读到 |
| Prometheus-Ultra-MultiTypeKB | 0 | 11 个 | `E:/Prometheus-Ultra-MultiTypeKB/` | ✅ 全读到 |
| prometheus-nexus | 8187 字符 | 14 个 | `E:/Prometheus Nexus/` | ✅ 全读到 |

**Genesis 与 Protogonos 本次没有任何可引原文。** 全文凡涉及这两个名字处，均为 `Prometheus-Ultra/PROMETHEUS_ULTRA_DESIGN.md` 或 `Prometheus-Omega-Omega/XYZ_MECHANISMS.md` 对它们的**二手描述**，已单独标注。这直接影响 §4 的结论强度。

---

## 1. 每个仓库自述定位（README 开头原文）

| 仓库 | 开头原文 | 文件 |
|---|---|---|
| **Prometheus-Omega** | `> 最强自进化AI记忆系统 - 整合XYZ全部优势机制`<br>`## 评分: 9.33/10` · `## 架构: 12层 \| 机制: 70+ \| 模块: 17` | `README.md` 第 3-7 行 |
| **Prometheus-Omega-Omega** | 无 README。md 首行：`# Prometheus Ω — 终极自进化AI Agent系统设计文档`<br>`> **目标**: 融合X/Y/Z三系统全部84个优势机制，构建史上最强自进化AI Agent内核`<br>`> **原则**: 零外部发明，只从已有项目提取高价值机制。每条机制标注来源文件，可溯源验证。` | `OMEGA_DESIGN_v2.md` 第 1-5 行（`OMEGA_DESIGN.md` 同句，「全部优势机制」无「84」） |
| **Prometheus-Omega-Genesis** | — | **无任何材料** |
| **Protogonos** | — | **无任何材料** |
| **ARSI** | `# ARSI — Autopoietic Recursive Self-Improvement`<br>`自创生递归自我改进系统。四大支柱统一架构：**Autopoiesis · MetaRSI · Mental World Modeling · Dream-RSI**。` | `README.md` 第 1-3 行 |
| **Prometheus-Ultra** | 无 README。`# Prometheus Ultra — System Design Document`<br>`## 1. Overview` / `**Prometheus Ultra** is the unified successor to three Prometheus Omega systems:` | `PROMETHEUS_ULTRA_DESIGN.md` 第 1-7 行 |
| **Ultra-MultiTypeKB** | 无 README（该库 README 落在 nexus 库）。md 首行：`# Prometheus-Ultra 系统级演进方案：多类型知识库 × 四轨进化 × 七管道革新` | `docs/multi_type_kb_seven_pipe_evolution.md` 第 1 行 |
| **prometheus-nexus** | `# Prometheus Ultra — MultiTypeKB`<br>`> 外挂记忆 / 自进化生命体的大脑（Nexus 神经系统统一中枢架构）`<br>`Prometheus-Ultra` 是一套**自进化的知识生命体**：以多类型知识库（MultiTypeKB）为长期记忆，7 条认知管道（remember / recall / evolve / learn / reflect / dream / maintain）驱动持续进化 | `README.md` 第 1-5 行 |

> 注：nexus 的 README 标题仍写着 `Prometheus Ultra — MultiTypeKB`，`start` 段落写 `cd /e/Prometheus-Ultra-MultiTypeKB`，即 nexus 是 Ultra-MultiTypeKB 的后续库，作者未改 README 标题。

---

## 2. ★ 作者明说「进化什么」的地方（原文引用，按仓库）

### 2.1 Ultra/nexus —— 唯一把「进化什么」写成一句显式区分的文档

> `ULTRA 四轨进化解决"**进化什么**" (T1 参数 / T2 语义 / T3 GitHub机制 / T4 论文机制),`
> `但**没解决"进化落在哪"**:`

出处：`prometheus-nexus` / `docs/p7_handbook_behavior_localization.md`（同一文件亦存在于 `Prometheus-Ultra-MultiTypeKB`）

**这是全部 8 个仓库中唯一一处把「进化什么」与「进化落在哪」对举成术语的原文。** 四轨即作者认定的「进化对象」清单：

| 轨 | 进化对象 | 原文出处 |
|---|---|---|
| T1 | 参数 | 同上；`docs/T2_T4_EVOLUTION_UPGRADE.md`：「**参数维度（gene_specs）** \| T1（自身搜索）… **T1 进化引擎**（fitness 验证的参数搜索）」 |
| T2 | 语义 | `docs/T2_T4_EVOLUTION_UPGRADE.md` 开头「设计初衷（用户原话对齐）：**T2**：根据 learn 学到的内容，语义促进系统强化（知识 → 系统能力内化）」 |
| T3 | GitHub 机制 | 同上：「**T3**：基于 learn 管道抓取的 GitHub 项目，提取高价值机制（含**学习 + 编译**双步）」 |
| T4 | 论文机制 | 同上：「**T4**：基于前沿论文，纯编译相关机制以促进系统进化」 |

同文档一句概括三轨共性：
> `三条轨道共享产出语义：把外部知识转成"能改系统的机制"。差异在源与提取深度。`
> `当前致命共性：**有"变异→挂载"，无"执行→评估→选择"后半环**。`

### 2.2 nexus/Ultra —— 进化对象在后期被显式「改口」

> `**关键转变**：Ultra 不再"为自身进化"，而是"**为宿主 agent 进化**"——进化燃料来自宿主真实使用，进化产物回流增强宿主能力。`

出处：`Prometheus-Ultra-MultiTypeKB` / `docs/v2_host_agnostic_evolution.md` §1「关键转变」

同一文档 §0 自陈此前状态：
> `**核心命题**：当前系统是一只"在笼中自转"的生命体——四轨进化跑通了，但产物不到宿主、宿主反馈不进燃料、宿主被默认焊成 Hermes。`

**这是作者本人对「进化什么」做的一次立场修订**，且方向是**缩小**（从自身 → 宿主）。这是本次深读最重要的单条发现之一。

### 2.3 nexus —— 进化产物是「机制」，不是「架构」

> `| **机制（BaseMechanism 子类）** | T3（编译）、T4（编译） | **机制编译底座 `MechanismCompiler` + 机制选择底座 `EffectTracker`+`SelectionGate`** |`

出处：`prometheus-nexus` / `docs/T2_T4_EVOLUTION_UPGRADE.md`「架构总览」表

配套约束：
> `**T1 不走 SelectionGate**——T1 产出参数染色体、自带 `fitness_before→evolve→fitness_after→verification_gate` 闭环`
> `- candidate 机制进 **candidate**（不直替）状态。`

以及 P7 把「进化落在哪」定位成新的一层：
> `**P7 补的就是 behavior localization 层**: 把进化产物映射到具体代码行为位置。`
> `- **是"位置建议"而非自动直替**（对齐 P6 不自动直替原则, 交 A-B 验证/人工）`

### 2.4 ARSI —— 进化对象分三档，且第三档是「结构」

README 设计原则原文：
> `5. **维度轮换进化** — 每个 term 重点进化 2-3 个维度`
> `6. **预演式进化** — 改进前先在世界模型中模拟后果`

四大支柱表把「进化对象」写成四种提问：
> `| MetaRSI | 改进算子如何组合 | 调度、铁律、增益归因 |`
> `| **Dream-RSI** | **策略如何被递归改进** | **世界池、回放、GridPlan/β、manifest、eval 回退** |`

核心理念：
> `一个自创生系统，它的改进回路本身必须是自创生生产的；而它对自身联合世界状态（物理+心智）的建模质量，决定了这个自我生产过程的质量。`

出处：`ARSI` / `README.md` 第 7 行、第 17-18 行、第 133-134 行

### 2.5 ARSI 代码层 —— 增益三分解，第三项就是「重组自身结构」

> `self_organized: structural reorganization (pipeline reordering, memory consolidation)`

出处：`ARSI` / `src/arsi/sealed_eval/gain_decomposition.py` docstring 第 5-6 行

同文件内 LLM 提示词的中文版把三档定义写死：
> `- amplified（放大）：已有能力的改进，如效果路由优化、参数调整`
> `- imported（进口）：从外部搬入的新能力，如学习新知识、移植新机制`
> `- self_organized（自组织）：系统重组自身结构带来的改进，如记忆整合、管道重排`

**这是全部材料里离「结构本身可进化」最近的一条原文**，但它的定位是**事后归因的一个类别**（gain attribution），不是**被优化的目标**。这个区别很关键，见 §5。

### 2.6 Prometheus-Omega —— 进化是 12 层里的 L5，与安全 L7 平级

> `| L5 | Evolution | 12层GA, UCB1, CGP, Coevolve, Convergence |`
> `| L7 | Safety | 4层防御, Denylist, 22宪法 |`
> `| L8 | Governance | 22宪法原则, 5级自治, 3级信任 |`

出处：`Prometheus-Omega` / `README.md` 第 20-23 行

设计文档给出铁律：
> `| **I2** | 进化铁律 | 所有进化必须通过AntiEvolutionGate 4前置 | 进化被拒绝 |`
> `| **C1** | 闭环铁律 | 每个进化步骤必须产出可验证产物 |`

出处：`Prometheus-Omega-Omega` / `OMEGA_DESIGN.md` §1.1、`OMEGA_DESIGN_v2.md` §1.2

v2 的进化层机制清单（E01-E15）全部是**搜索/门控/调度**，无一项是「改动架构」：
> `E01 EvalDrivenEngine 7步 · E02 AntiEvolutionGate 4前置 · E03 VerificationIronLaw 5步 · E04 12-Layer GA · E05 UCB1 Bandit层选择 · E06 Island Parallel 4岛+环迁移 · E07 3方向进化 (Forward/Lateral/Reverse) · E08 CoEvolution多技能共进化 · E09 DAGScheduler进化任务调度 · E10 Lotka-Volterra生态竞争 · E11 EDRE均衡 · E12 ToolFitnessPredictor · E13 LIFE失败归因 · E14 FGGM形式化验证变异 · E15 SpeculativeEvolution推测分叉`
> `| E09 | DAGScheduler进化任务调度 | [Y:dag_scheduler.py] |`
> `# 来源: Y:evolution/dag_scheduler.py` / `# 进化任务有向无环图`

注意 E09 的作用对象是**进化任务之间的依赖图**，不是系统架构。

Ultra 侧继承的 `evolve` 管道（10 级）同样全是门控与搜索：
> `| **evolve** | 10 | LoopGuard → Equilibrium → AntiEvolution → IronLaw → RLPathology → UCB1 → FGG → EvalDriven → CoEvolve+Speculative+LotkaVolterra → Reflexion+Debate |`

出处：`Prometheus-Ultra` / `PROMETHEUS_ULTRA_DESIGN.md` §4

### 2.7 Ultra 的「进化层」在代码里只有 8 个机制

> `├── evolution/           # Evolution subsystem (8 mechanisms)`

出处：`Prometheus-Ultra` / `PROMETHEUS_ULTRA_DESIGN.md` §2

---

## 3. ★ ARSI 六层架构 L0-L5：哪些层「可进化」？（原文逐层）

README 六层表原文（`ARSI` / `README.md` 第 20-34 行）：

| 层 | 名称 | 来源 | 回答 |
|---|---|---|---|
| **L0** | Anchored Constitution | GAI `2609.13406` | 我们被允许成为什么 |
| **L1** | Contracted Computation | SEVerA `2603.25111` | 每次调用上什么恒真 |
| **L2** | Regularized MetaRSI | RRSI `2609.24972` × AIDE² `2609.26457` | 如何改而不自欺 |
| **L3** | Introspective World + Vitals | SIWM/ODE/CTM + SAHOO | 世界/自我如何流，何时漂 |
| **L4** | Dream-RSI | `2609.14858` | 探索策略如何被梦出 |
| **L5** | Evaluative Epistemology | Grader `2607.12790` | 什么算证据 |

**README 本身没有任何一列标注哪层「可进化」。** 但代码里有一张明确的对位表 —— `ARSI` / `src/arsi/harness/pillars.py`：

```
"L0_constitution": {
    "name": "Anchored Constitution",
    "core": [
        "dial1_modifier_in_agent=RSI",
        "dial2_base_grounded",
        "iron_laws",
        "never_goal_drift",
        # P-R6 organization/structure dichotomy (Maturana)
        "organization=rho_iron_laws_sealed_goals",
        "structure=omega_harness_host_policies",
        "stage3_may_change_structure_never_organization",
    ],
```

模块 docstring 第一行即声明它是「架构层」而非「进化层」：
> `Autopoiesis = charter across layers, not a peer column.`

以及 `CHARTER` 里第二处二分：
> `"organization_invariant_structure_open",`

**可进化面的确切落点在 `taxonomy.py`，不在 pillars：**

`ARSI` / `src/arsi/harness/taxonomy.py` docstring：
> `Nine-dimensional harness taxonomy (HarnessX §3.3) × five modules (ModularRSI §3.2).`
> `c7 control/safety = Iron Laws — **frozen**, never an evolution target.`
> `# Never evolve these (ARSI: iron laws / freeze / circuit-break)`
> `FROZEN_DIMS = frozenset({"c7"})`

九维即作者认定的「可进化的东西」清单：
> `DIMENSIONS = {"c1": "model_selection", "c2": "context_assembly", "c3": "memory_management", "c4": "tool_ecosystem", "c5": "execution_environment", "c6": "evaluation_and_reward", "c7": "control_and_safety", "c8": "observability", "c9": "training_bridge"}`

### ★ 结论：六层里只有 L2 一层自称是「改进层」，且它的进化对象是 harness 的 9 个维度，不是六层架构本身

依据三元组：
1. `ARSI` / `src/arsi/harness/pillars.py` — `"L2_metarsi": {"name": "Regularized MetaRSI", "question": "How do we change without fooling ourselves?"}`（唯一以「我们如何改变」为提问的层）
2. `ARSI` / `src/arsi/harness/taxonomy.py` — `FROZEN_DIMS = frozenset({"c7"})` + 九维 `DIMENSIONS`（改变面被显式限定在这 9 个键，且 c7 冻结）
3. `ARSI` / `src/arsi/harness/evolver.py` — `**Does not auto-edit core** — manifests are reviewable artifacts (HarnessX Change-Manifest discipline).`（改的是 manifest 提案，不是 core）

Evolver 的实际改动对象可枚举——全是**行为规则**，不是结构：
> `"tool_loop": {"edit_type": "processor", "dimension": "c4", "module": "tool_use", ... "diff": ("+ # processor: tool_retry_guard\n+ if last_error == current_error and retry_count >= 2:\n+     abort_with(fail_class='tool_loop')\n")}`

`edit_type` 取值域 = `("prompt", "processor", "tool", "config", "control")`（见 `evolver.py` `propose_from_landscape`）。

---

## 4. ★ Omega 系列命名 Genesis / Omega / Omega-Omega 暗示什么？

### 4.1 原文里唯一一次系统解释这组命名

`Prometheus-Ultra` / `PROMETHEUS_ULTRA_DESIGN.md` §1 Overview：

> `**Prometheus Ultra** is the unified successor to three Prometheus Omega systems:`
> `- **Genesis** (99 mechanisms, 21 submodules) — breadth-first expansion`
> `- **Omega-Omega** (90 mechanisms, branch system, 1,511 tests) — engineering rigor`
> `- **Z:\Prometheus Ω** (47 mechanisms, deep evolution, 4-layer defense) — depth-first refinement`

**作者给三个前身各贴了一个方向词：Genesis = breadth-first expansion（广度扩张），Omega-Omega = engineering rigor（工程严谨），Z = depth-first refinement（深度精炼）。**

同文件 §7「Differences from Predecessors」把三者定位为**互补的技术轴**（包名/机制数/子模块/分支系统/测试数/Docker/CI/上下文管理器/4层防御/22宪法/12层GA）——不是**世代**。且 §2 的 99 机制来源表写明 Ultra 是三者机制数之和的去重：

> `| Foundation | 2 | Z + Omega-Omega |`
> `| Memory | 11 | Genesis + Z |`
> `| Lifecycle | 11 | Genesis + Z |`
> `| Evolution | 8 | Genesis + Z |`
> `| **Total** | **99** | |`

### 4.2 「Omega-Omega」= Ω² 在原文里被直接写成 **evolution × evolution**（机制级），不是系统级

`Prometheus-Ultra-Omega` 系列的 `README.md` 里，「12层GA」在 L5 Evolution 层的机制来源栏；
`ARSI` 侧则有更精确的对应表述（见 §4.4）：**「双 Ω」= policy + harness 两个各自递归的改进环**。

所以「Omega-Omega」在作者笔下有两处不同用法，需要分开看：
- **Ω 系列（Prometheus 侧）**：Ω-Omega 是**三个兄弟系统之一**，用 Ω² 命名表示「比 Ω 再上一级」，原文未解释其语义。
- **ARSI 侧**：「双 Ω」有明确所指。

### 4.3 Protogonos 是什么 —— 只有两处二手提及，且都不是 Genesis 的定义

`prometheus-v4` / `README.md`（**注意：v4 不在本次 8 仓库清单内，此处为交叉验证**）：
> `Self-Evolving AI Agent Memory Platform — Unified fusion of Prometheus v3 + Protogonos.`
> `- **Real CodeMutator** from Protogonos (refactor/optimize/simplify/type hints)`

`Prometheus-Omega-Omega` / `XYZ_MECHANISMS.md` 与 `三系统深度对比报告.md`：
> `| 5 | **HTTP+CLI+Docker** | Protogonos | 15端点HTTP + 13命令CLI + Docker |`

**即：Protogonos 对 Ω 系列的唯一已知贡献是「真实 CodeMutator（refactor/optimize/simplify/type hints）」与 HTTP/CLI 脚手架。** 而这条 CodeMutator 线索在 v5 就消失了 —— 已在既有 lessons 文档中记录（`E:/Divine Wisdom Core/docs/lessons/pro_evolution_vocabulary.md`：「**v5** | ★ **唯一次降温**：定位从「自进化平台」缩为 `Adaptive memory system with cognitive evolution capabilities`」）。

### 4.4 ★ Genesis/Omega/Omega-Omega 的命名暗示 —— 原文有没有说？

**明确回答：没有。** 三次检索穷尽：

| 检索词 | 命中 |
|---|---|
| `Genesis` | 23 处，**全部集中在 2 个文件**：nexus/`README.md`（是 `test_t4_real_neurogenesis_via_consume`、`neurogenesis` 等词的一部分，与 Genesis 无关）与 Ultra/`PROMETHEUS_ULTRA_DESIGN.md`（即 §4.1 三行） |
| `创世` | **0 处** |
| `Ω-Ω` | **0 处** |
| `二次方` | **0 处** |
| `泰坦` / `titans` | **0 处** |
| `普罗米修斯` | **0 处**（全库一律用拉丁字母 `Prometheus`） |

`PROMETHEUS_ULTRA_DESIGN.md` 是唯一给出方向词的文件，但它给的是**策略方向**（breadth / rigor / depth），**不是命名寓意**。

**唯一可确证的命名语义来自 ARSI 侧（与 Ω 系列的 Ω 同符号不同所指）：**

`ARSI` / `src/arsi/harness/unified_credit.py` docstring：
> `"""P-R4 Unified credit ledger L_t for dual-Ω (policy + harness).`
> `Problem: Dream-RSI policy credit and Evolver harness credit are separate books;`
> `a single improvement often moves both — ΔS cannot be attributed.`
> `Rule: one table for manifest edits and dream policy revisions.`
> `source_tag ∈ {policy, harness, both}.` """

同文件：`omega_id: str  # policy:beta/v | harness:CM-xxx | both:pair`

`ARSI` / `docs/PROGRESS.md`（P-R4 行）：
> `| **P-R4** | \`harness/unified_credit.py\` | 双 Ω 统一账本：policy/harness/both 归因 |`

**读法：ARSI 的「Ω」= 策略层递归改进环（policy）， harnes Ω = harness 递归改进环。「双 Ω」即递归的两个环各自 Ω 化，而不是「Ω 系统又套了一个 Ω」。** 这是全部材料里对「Omega」符号最明确的一次工程化定义。

### 4.5 P-R6 是命名问题最接近的答案：组织 ρ / 结构 Ω 二分

`ARSI` / `src/arsi/harness/pillars.py`（L0 `core` 第 5-7 行，含注释）：
> `# P-R6 organization/structure dichotomy (Maturana)`
> `"organization=rho_iron_laws_sealed_goals",`
> `"structure=omega_harness_host_policies",`
> `"stage3_may_change_structure_never_organization",`

`ARSI` / `docs/PROGRESS.md`（P-R6 行）：
> `| **P-R6** | \`harness/pillars.py\` L0/CHARTER | 组织=ρ / 结构=Ω 二分（自创生×GAI 正名） |`

**注意「正名」二字** —— 作者认为 Ω 这个符号此前被误用，此处正名为「结构（Ω）可被 stage-3 改动，而组织（ρ）永不可动」。这直接构成 §5 的正面答案。

---

## 5. ★ 「架构/结构本身可进化」有没有原文表述？

### 5.1 有 —— 但只有一处正面表述，且是 ARSI 的代码常量

`ARSI` / `src/arsi/harness/pillars.py`（L0 Anchored Constitution 的 `core` 列表）：
> `"structure=omega_harness_host_policies"`
> `"stage3_may_change_structure_never_organization"`

同文件 `CHARTER` 段：
> `"organization_invariant_structure_open"`

`ARSI` / `src/arsi/harness/coevolution.py` 的互锁实现：
> `"""Co-evo + GAI interlock: mutual pressure ok; Γ must not touch ρ."""`
> `STAGE3_META = "meta_coevolution"`
> `if omega_adapts: return CoEvoVerdict(STAGE3_META, True, "evolution_mechanism_adapts")`
> `anchored_meta_ok(*, gamma_changes_omega: bool, gamma_touches_rho: bool, rho_frozen: bool = True)`

（此即：第三阶段共进化 = **改进机制 Ω 自身在适应**，同时 Γ 不得触碰 ρ。有实现、有单测：`ARSI/tests/test_coevo_fidelity.py` 的 `test_anchored_meta_blocks_rho`。）

### 5.2 有 —— 一处事后归因口径

`ARSI` / `src/arsi/sealed_eval/gain_decomposition.py`：
> `self_organized: structural reorganization (pipeline reordering, memory consolidation)`

### 5.3 没有 —— 以下位置找不到该表述（明确记录为负结论）

| 位置 | 结论 |
|---|---|
| 全部 8 仓库的 README | **找不到**。检索 `架构本身/自身架构/架构自身/元进化/meta-evolution/结构本身/自身结构/自我修改/self-modif/架构进化/架构演化/修改自身/修改自己/自身代码` **全部 0 命中** |
| `Prometheus-Omega` + `Omega-Omega` 全部 7 个 md | **找不到**。Ω 系列只把「进化」定义为 L5 层的 GA/UCB1/门控（§2.6） |
| `Prometheus-Ultra` 全部 9 个 md | **找不到**。且 Ultra 自己的架构演进（Nexus 四层）是**人工推进**的，不是被进化出来的 —— 见下 |
| `prometheus-nexus` 全部 14 个 md | **找不到**「架构本身可进化」。但有一处最接近，且是**反向**表述 |

**nexus 反向证据（重要）** —— `prometheus-nexus` / `README.md`「已知约束与未做项」：
> `| 管道抽取（life.py 5000 行 → pipelines/ 包） | 用户确认**不做**（避免回归） |`

`prometheus-nexus` / `docs/ARCH_OPTIMIZATION_REPORT.md`：
> `> 原则(用户硬约束): **调度集中是上帝, 不可肢解**; 只外置器官/装配/决策, 不拆调度逻辑。`
> `| \`life.py\` 拆为多 mixin/文件(需重新设计导入拓扑, 当前委托壳模式已达安全边界) |`
> `**仍待人工评估(超出"外置装配"域, 需拆 God class 本身, 风险陡增)**`

**即：在作者最活跃、最可能「让系统自己改架构」的那个库（nexus），架构改动被写成硬约束 + 待人工评估清单。架构的进化权在人类手里。**

### 5.4 命名与判定的汇总对照

| | 是否找到「架构/结构本身可进化」原文 | 依据 |
|---|---|---|
| ARSI | **找到**，2 处 | `pillars.py`：`"stage3_may_change_structure_never_organization"`；`gain_decomposition.py`：`self_organized: structural reorganization` |
| Prometheus-Omega / Omega-Omega | **找不到** | 进化仅定义在 L5 层机制表（E01-E15） |
| Ultra | **找不到** | 同上；`evolution/` 子系统仅 8 个机制 |
| nexus / Ultra-MultiTypeKB | **找不到** | 架构改动写作用户硬约束（`ARCH_OPTIMIZATION_REPORT.md`） |
| Genesis / Protogonos | **无材料可判** | 零文档 |

---

## 6. 设计文档 vs 代码实现 —— 作者自己下的诚实区分

这一条对「进化」语义至关重要，因为作者反复用**「提议 vs 应用」**这一对来定义进化的边界。

### 6.1 ARSI：Evolver 只产提案，不改 core

`ARSI` / `src/arsi/harness/evolver.py` docstring：
> `"""Evolver — landscape → Change-Manifest (AEGIS stage 3).`
> `Rule templates first; optional LLM refine. Every candidate must pass`
> `scope fence + critic before status=accepted. **Does not auto-edit core** —`
> `manifests are reviewable artifacts (HarnessX Change-Manifest discipline).`
> `"""`

`ARSI` / `docs/PROGRESS.md`（「AEGIS 自动环」行）：
> `| **AEGIS 自动环** | daemon \`_run_harness_evolve_dry\` | landscape 后自动 propose（**默认 dry-run，不 apply core**） |`

`ARSI` / `docs/PROGRESS.md`（「Evolver 最小闭环」节）：
> `- 默认**不自动改 core**（Change-Manifest 可审可回滚 \`inverse_op\`）`

配套：`harness/manifest.py` 提供 `inverse_op` 回滚；`harness/audit.py` 写 `audit.jsonl（stage/gate/commit）`。

### 6.2 ARSI：进化对象被 scope fence 圈死在 5 个模块的文件白名单内

`ARSI` / `src/arsi/harness/taxonomy.py`：
> `def module_scope_ok(module: str, file_path: str) -> bool:`
> `"""Modification must stay inside the module's declared file scope."""`
> `"infrastructure": {..., "frozen": True}`
> `"task_completion_detection": {..., "modules": ...}`（白名单文件列表）

> `def is_edit_allowed(dim: str, module: str = "", symbol: str = "") -> tuple[bool, str]:`
> `"""Scope fence: frozen dims and frozen modules reject edits."""`

### 6.3 Ultra/nexus：不自动直替

`prometheus-nexus` / `README.md` 机制数据流图：
> `host.emit_capability(spec)  # 建议+宿主确认(对齐 P6 不自动直替)`

`Prometheus-Ultra-MultiTypeKB` / `docs/v2_host_agnostic_evolution.md` §4：
> `1. **P0a \`consume_active\` 自动触发有副作用风险**：激活即改生产，需保留"**P6 不自动直替**"原则——故 \`emit_capability\` 是"建议+宿主确认"，\`inject_gene_specs\` 走 A-B 并行不直替。`

### 6.4 作者对「进化真的发生了吗」的判定标准也写下来了

`Prometheus-Ultra-MultiTypeKB` / `docs/v2_host_agnostic_evolution.md` §0：
> `| **B1** | 四轨产物是僵尸机制（激活后不到生产） | \`grep add_gene\|on_activate\` 在 src/ 返回空；\`registry.invoke()\` 仅 life.py:2855 诊断用 | 🔴 致命 |`
> `| **B8** | 测试盲区掩盖架构缺陷 | 64 测试文件仅 9 用 mock；无"激活后行为真变"断言 | 🟡 中（根因） |`
> `**主线认知**：B1/B3/B6/B7 是**同一条断链的不同截面**——"宿主无关的自进化闭环"没合上。`

`prometheus-nexus` / `docs/T2_T4_EVOLUTION_UPGRADE.md`：
> `当前致命共性：**有"变异→挂载"，无"执行→评估→选择"后半环**。`
> `1. \`_validate_draft\` 升级：... 返回**非平凡结果**（非纯 \`{"ok":True}\`，需含数据或写副作用）`

**读法：作者判定「真进化」的标准是「产物真的改变了运行行为并被 A/B 证伪」，而不是「生成了新机制」。** 这一判据贯穿 Ultra 与 ARSI 两侧。

### 6.5 ARSI：γ 的修改必须经 validation_gate 才算落地

`ARSI` / `docs/PROGRESS.md`（Recuris R1/R2）：
> `- R1 harness/skill_trace.py：Γ 结构化 · localize_failure → E/W/ρ/C/harness`
> `- R2 harness/skill_patch.py：组件定向补丁 · validation_gate（n/CI 不足 REJECT）`

---

## 7. 词汇表：作者对「进化」的固定用词（原文出处，非归纳）

| 词 | 原文定义 | 仓库 / 文件 |
|---|---|---|
| 自进化 / 自进化的知识生命体 | `Prometheus-Ultra` 是一套**自进化的知识生命体** | nexus / `README.md` |
| 最强自进化AI记忆系统 | `> 最强自进化AI记忆系统 - 整合XYZ全部优势机制` | Omega / `README.md` |
| 终极自进化AI Agent内核 | `融合X/Y/Z三系统全部84个优势机制，构建史上最强自进化AI Agent内核` | Omega-Omega / `OMEGA_DESIGN_v2.md` |
| 自创生递归自我改进 | `自创生递归自我改进系统` | ARSI / `README.md` |
| 改进回路本身必须自创生生产 | `一个自创生系统，它的改进回路本身必须是自创生生产的` | ARSI / `README.md` |
| 改进算子如何组合 | MetaRSI 支柱的提问 | ARSI / `README.md` |
| 策略如何被递归改进 | Dream-RSI 支柱的提问 | ARSI / `README.md` |
| 进化什么 | `ULTRA 四轨进化解决"**进化什么**" (T1 参数 / T2 语义 / T3 GitHub机制 / T4 论文机制)` | nexus / `docs/p7_handbook_behavior_localization.md` |
| 进化落在哪 | `但**没解决"进化落在哪"**` | 同上 |
| 把外部知识转成能改系统的机制 | `三条轨道共享产出语义：把外部知识转成"能改系统的机制"。差异在源与提取深度。` | nexus / `docs/T2_T4_EVOLUTION_UPGRADE.md` |
| 为宿主 agent 进化 | `Ultra 不再"为自身进化"，而是"**为宿主 agent 进化**"` | Ultra-MultiTypeKB / `docs/v2_host_agnostic_evolution.md` |
| 在笼中自转的生命体 | `当前系统是一只"在笼中自转"的生命体` | 同上 |
| 进化铁律 | `所有进化必须通过AntiEvolutionGate 4前置` | Omega-Omega / `OMEGA_DESIGN.md` |
| 闭环铁律 | `每个进化步骤必须产出可验证产物` | 同上 |
| 维度轮换进化 | `每个 term 重点进化 2-3 个维度` | ARSI / `README.md` |
| 预演式进化 | `改进前先在世界模型中模拟后果` | ARSI / `README.md` |
| 铁律不可被改进改写 | `**铁律不可被改进改写** — G1-G10 是所有自创生过程的不动点` | ARSI / `README.md` |
| 组织=ρ / 结构=Ω | `组织=ρ / 结构=Ω 二分（自创生×GAI 正名）` | ARSI / `docs/PROGRESS.md` P-R6 |
| stage3 可改结构不可改组织 | `"stage3_may_change_structure_never_organization"` | ARSI / `src/arsi/harness/pillars.py` |
| 组织不变结构开放 | `"organization_invariant_structure_open"` | 同上（CHARTER） |
| 双 Ω 统一账本 | `双 Ω 统一账本：policy/harness/both 归因` | ARSI / `docs/PROGRESS.md` P-R4 |
| self_organized（自组织） | `系统重组自身结构带来的改进，如记忆整合、管道重排` | ARSI / `src/arsi/sealed_eval/gain_decomposition.py` |
| c7 frozen, never an evolution target | `c7 control/safety = Iron Laws — **frozen**, never an evolution target.` | ARSI / `src/arsi/harness/taxonomy.py` |
| 不自动改 core | `**Does not auto-edit core** — manifests are reviewable artifacts` | ARSI / `src/arsi/harness/evolver.py` |
| P6 不自动直替 | `需保留"**P6 不自动直替**"原则` | Ultra-MultiTypeKB / `docs/v2_host_agnostic_evolution.md` |
| 有变异→挂载，无执行→评估→选择 | `当前致命共性：**有"变异→挂载"，无"执行→评估→选择"后半环**` | nexus / `docs/T2_T4_EVOLUTION_UPGRADE.md` |
| 僵尸机制 | `四轨产物是僵尸机制（激活后不到生产）` | Ultra-MultiTypeKB / `docs/v2_host_agnostic_evolution.md` |
| 调度集中是上帝，不可肢解 | `> 原则(用户硬约束): **调度集中是上帝, 不可肢解**` | nexus / `docs/ARCH_OPTIMIZATION_REPORT.md` |
| 进化 = breadth / rigor / depth 三轴 | `Genesis — breadth-first expansion` / `Omega-Omega — engineering rigor` / `Z — depth-first refinement` | Ultra / `PROMETHEUS_ULTRA_DESIGN.md` |

---

## 8. 直接回答「作者对进化是怎么理解的」（只用原文串起来，不外加框架）

1. **进化的对象被明确枚举过一次，只有四类**：参数 / 语义 / GitHub 机制 / 论文机制 —— `ULTRA 四轨进化解决"进化什么"`（nexus/`docs/p7_handbook_behavior_localization.md`）。同句把「进化落在哪」划为另一个（当时缺失的）问题，由 P7 Harness Handbook 补上。

2. **进化对象在 Ultra 后期被作者自己缩小了**：从「为自身进化」改为「为宿主 agent 进化」，理由是自陈的闭环断裂 —— `Ultra 不再"为自身进化"，而是"为宿主 agent 进化"`、`当前系统是一只"在笼中自转"的生命体`（Ultra-MultiTypeKB/`docs/v2_host_agnostic_evolution.md`）。

3. **ARSI 把这个二分写成代码常量**：组织（ρ = 铁律/密封目标）不可动，结构（Ω = harness/宿主策略）可被 stage-3 改动 —— `"stage3_may_change_structure_never_organization"`（ARSI/`src/arsi/harness/pillars.py`），并被 `anchored_meta_ok()` 与 `tests/test_coevo_fidelity.py::test_anchored_meta_blocks_rho` 真实执行。

4. **但 ARSI 的可进化面被 scope fence 限死**：只有 harness 九维（`DIMENSIONS`）且 c7 冻结，Evolver 只产 Change-Manifest 不动 core —— `c7 control/safety = Iron Laws — frozen, never an evolution target`、`**Does not auto-edit core**`（ARSI/`src/arsi/harness/taxonomy.py`、`evolver.py`）。

5. **Ω 系列（Omega / Omega-Omega / Genesis）里找不到「架构可进化」**：进化只是 12 层架构里的 L5，其 15 个机制全是 GA/UCB1/门控/调度（Omega-Omega/`OMEGA_DESIGN_v2.md`）；Omega README 把 L5 与 L7 Safety、L8 Governance 平级并列。

6. **「架构本身的进化权在人类手里」有原文硬证据**：nexus 把 life.py 拆分列为「用户确认不做（避免回归）」，并把「拆 God class 本身」列为「仍待人工评估…风险陡增」（nexus/`README.md`、`docs/ARCH_OPTIMIZATION_REPORT.md`）。

7. **作者对「真进化」的判据是行为改变 + A/B 淘汰，不是产物数量**：`有"变异→挂载"，无"执行→评估→选择"后半环`、`四轨产物是僵尸机制`、`无"激活后行为真变"断言`（nexus/`docs/T2_T4_EVOLUTION_UPGRADE.md`、Ultra-MultiTypeKB/`docs/v2_host_agnostic_evolution.md`）。

8. **Genesis / Omega-Omega 的命名含义原文没有说**：`创世`/`Ω-Ω`/`二次方`/`泰坦` 全部 0 命中；唯一解释是 Ultra 设计文档给三前身贴的方向词 `breadth-first expansion` / `engineering rigor` / `depth-first refinement`，且三者是互补技术轴而非世代。Protogonos 对 Ω 的已知贡献只有 `Real CodeMutator from Protogonos (refactor/optimize/simplify/type hints)`，且该线索在 v5 即消失（prometheus-v4/`README.md`；Omega-Omega/`XYZ_MECHANISMS.md`）。

---

## 附：本次全部引用已逐条校验为文件内逐字存在（18/18 OK）

校验脚本对每条引用的**逐字字符串**在源文件中做 `in` 判断，含中文全角标点、Markdown 粗体标记与转义反斜杠。