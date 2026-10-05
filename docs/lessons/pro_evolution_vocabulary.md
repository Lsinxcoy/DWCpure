# Prometheus 主线 12 代 + XYZ 变体：作者自己怎么定义「进化」

> 数据源：`E:/Divine Wisdom Core/docs/repos/_all.json`（repo 字段逐个筛选）
> 覆盖仓库：`prometheus`(v1 cip), `prometheus-v3`, `prometheus-v4`, `prometheus-v5`, `prometheus-v6`, `prometheus-v7`,
> `prometheus-v8`, `prometheus-v8pro`, `prometheus-v9`, `prometheus-v9pro`, `prometheus-v10`, `prometheus-v11`,
> `Prometheus-X`, `Prometheus-Y`, `Prometheus-Z`
> 纪律：每条结论带「仓库名 + 文件路径 + 原文引用」三元组。只报原文写了什么，不引入任何外部分类框架。
> 「设计文档写了」与「代码实现了」分列，不混。

**抓取完整度声明**：`prometheus-v9pro`、`prometheus-v10` 在 `_all.json` 中 readme_len=0 且 md=0（**未抓到任何文档**，非"仓库里没写"）。`prometheus-v8pro` 的 README 与 `prometheus-v8` 逐字节相同（均 2367 字符）。`prometheus`(v1) 仅抓到 `cip/README.md`（CIP Hermes v2），非主仓 README。

---

## 一、逐代定位

| 仓库 | 自述定位（原文引用） | 来源文件 |
|------|----------------------|---------|
| **prometheus (v1/CIP)** | `Advanced Evolution System for CIP Hermes - A goal-driven evolution framework with 12-layer architecture and 3-direction optimization.` | `cip/README.md` 第 3 行 |
| **prometheus-v3** | `Self-Evolving AI Agent Memory Platform.` + `Evolution Layer (12-layer genetic algorithm)` / `5-organ AI pipeline (Taotie/Nuwa/Darwin/Pool/Guard)` / `3-direction strategy (Forward/Lateral/Reverse)` / `Goal-driven evolution` | `README.md` 第 3 行、Architecture 块 |
| **prometheus-v4** | `Self-Evolving AI Agent Memory Platform — Unified fusion of Prometheus v3 + Protogonos.` + `Real CodeMutator from Protogonos (refactor/optimize/simplify/type hints)` | `README.md` 第 3 行、What's New |
| **prometheus-v5** | `Adaptive memory system with cognitive evolution capabilities.` | `README.md` 第 3 行 |
| **prometheus-v6** | `统一自进化AI智能体记忆平台 - 终极版本` + `融合V1器官系统 + V5记忆层 + EVO V2监控 + Nexus子代理 + MiMo行为规则 + 研究高价值机制` | `README.md` 第 3-5 行 |
| **prometheus-v7** | `Production-Grade Self-Evolving AI Agent Memory Platform` + `V7在V6基础上进行了全面架构重构` | `README.md` 第 3-5 行 |
| **prometheus-v8** | `Self-Evolving AI Agent Memory Platform — 7-Generation Fusion` / `Architecture (9 Layers)` / `L3 Evolution 12-Layer Unified Engine + 3-Stage Fitness + CORAL Heartbeat` | `README.md` 第 3 行、9 Layers 表 |
| **prometheus-v8pro** | 与 v8 **逐字节相同**（标题仍是 `# Prometheus V8`）。README 中**没有任何 pro 专属内容，也没有任何 v8→v8pro 的变化说明** | `README.md`（2367 字符，与 v8 一致） |
| **prometheus-v9** | `基于 V3-V8pro 全版本经验教训，融合2025-2026最新论文成果，从零构建的生产级自进化AI代理记忆平台。` | `README.md` 第 5 行 |
| **prometheus-v9pro** | **无文档可引**（未抓到） | — |
| **prometheus-v10** | **无文档可引**（未抓到） | — |
| **prometheus-v11** | `V11 = V10的骨架 + Mnemosyne的脊柱 + CIP的管道 + 进化学的灵魂 + 开源项目的盔甲 … 以Eval-Driven Evolution为进化方法` + `单一来源真相文档` | `V11_DESIGN.md` 〇、一 |
| **Prometheus-X** | `The Ultimate Self-Evolving AI Agent Memory System` + `70+ mechanisms unified from 34 source projects into one coherent architecture.` | `README.md` 第 3-5 行 |
| **Prometheus-Y** | `不是"更好的框架"，是一个能自己进化自己的有机体。有新陈代谢、有记忆寿命、有社会性、能自己改自己架构。` | `DESIGN.md` 〇、设计声明 |
| **Prometheus-Z** | `目标: AI Agent自己发现问题 → 修改 → 验证 → 固化，全程无需人类介入` / `让AI Agent自己发现自己哪里不够好，自己修改自己，自己验证修改有效，自己把改进固化成本能` | `README.md` 第 3 行、`Z_DESIGN.md` 引言 |

---

## 二、文档里明确写的「进化什么」

### 2.1 v1/CIP — 12 层"全面进化"（最早的全量清单）

| # | 原文引用 | 来源 |
|---|---------|------|
| 1 | `12-Layer Evolution Architecture: Comprehensive evolution across meta-parameters, strategies, skills, configuration, code, memory, communication, perception, reasoning, learning, adaptation, and integration.` | `prometheus` / `cip/README.md` Features 第 1 条 |
| 2 | `3-Direction Optimization: Performance, capability, and robustness evolution directions.` | 同上 |

### 2.2 v3 — 进化 = 遗传算法 + 器官管道 + 方向

| # | 原文引用 | 来源 |
|---|---------|------|
| 1 | `Evolution Layer (12-layer genetic algorithm)` | `prometheus-v3` / `README.md` Architecture |
| 2 | `5-organ AI pipeline (Taotie/Nuwa/Darwin/Pool/Guard)` | 同上 |
| 3 | `3-direction strategy (Forward/Lateral/Reverse)` / `Goal-driven evolution` / `Multi-signal direction selector` | 同上 |

### 2.3 v4 — 进化首次含"改代码"

| # | 原文引用 | 来源 |
|---|---------|------|
| 1 | `Real CodeMutator from Protogonos (refactor/optimize/simplify/type hints)` | `prometheus-v4` / `README.md` What's New |

### 2.4 v5 — 进化降级为"自适应记忆 + 认知进化"

| # | 原文引用 | 来源 |
|---|---------|------|
| 1 | `Adaptive memory system with cognitive evolution capabilities.` | `prometheus-v5` / `README.md` 第 3 行 |
| 2 | CLI 暴露的进化面仅两项：`prometheus evolve         # Evolve genome` | `prometheus-v5` / `README.md` CLI Commands 块 |

### 2.5 v6 — 12 层进化架构全表（★ 唯一一次把"架构"列为进化对象的显式清单）

| # | 原文引用 | 来源 |
|---|---------|------|
| 1 | `### 12层进化架构` 全表：`L0 MetaParams 元参数进化 / L1 Strategy 策略进化 / L2 Skill 技能进化 / L3 Config 配置进化 / L4 Code 代码进化 / L5 MetaEvolution 元进化 / L6 Prompt 提示词进化 / L7 Tool 工具进化 / L8 Memory 记忆进化 / L9 Knowledge 知识进化 / L10 Collaboration 协作进化 / L11 Architecture 架构进化` | `prometheus-v6` / `README.md` 进化系统章节 |
| 2 | `### 3方向系统`：`Forward 正向进化 - 优化当前轨迹 / Lateral 横向迁移 - 探索替代方案 / Reverse 逆向回滚 - 恢复历史版本` | 同上 |
| 3 | 核心理念原文：`Agent的进化不是模型能力问题，是架构设计问题。给一个普通模型好的架构，它能进化；给一个强模型差的架构，它会退化。` | `prometheus-v6` / `PROJECT_FINAL_SUMMARY.md` §1.2 |
| 4 | 设计原则第 4 条：`进化可验证 — 每条规则必须有触发场景` | `prometheus-v6` / `PROJECT_FINAL_SUMMARY.md` §1.3 |
| 5 | 未来工作（未实现）：`12.2 研究方向 1. 自适应进化 - 根据环境自动调整进化策略` | `prometheus-v6` / `PROJECT_FINAL_SUMMARY.md` §12.2 |

### 2.6 v7 — 12 层"统一"，逐层点名

| # | 原文引用 | 来源 |
|---|---------|------|
| 1 | `进化层 (统一12层)`：`L0 MetaParams → L1 Strategy → L2 Direction → L3 Select → L4 Mutation → L5 Crossover → L6 Fitness → L7 AST → L8 Validation → L9 Memory → L10 Quota → L11 Budget` | `prometheus-v7` / `README.md` 架构图 |
| 2 | V6→V7 明说的取舍：`进化引擎 \| 双引擎并行，9/12层 \| **统一引擎，12/12层完整**` | `prometheus-v7` / `README.md` 对比表 |
| 3 | 器官管道进化：`器官管道 \| 关键词匹配 \| **LLM驱动 + AST安全变异**` | 同上 |
| 4 | 无限进化语义：`**V7支持持续进化，不会在100代停止！**` `generations: 0  # 0 = 无限进化` | `prometheus-v7` / `CONTINUOUS_EVOLUTION.md` |
| 5 | 停滞重启：`max_stale_generations: 50` + `连续50代无改善时重启` | 同上 |

### 2.7 v8 / v8pro — 进化=12层引擎 + 3阶段适应度 + 治理层

| # | 原文引用 | 来源 |
|---|---------|------|
| 1 | `L3 \| Evolution \| 12-Layer Unified Engine + 3-Stage Fitness + CORAL Heartbeat` | `prometheus-v8` / `README.md` Architecture (9 Layers) |
| 2 | `L7 \| Governance \| Broadcast + Autonomy(L0-L4) + Curiosity + Initiative + Trust` | 同上 |
| 3 | `5-level autonomy control` / `7-layer governance for spontaneous initiative` | `prometheus-v8` / `README.md` Stats |
| 4 | `Evolution Kickoff: Close 6 open loops, compile inert rules to executable mechanisms` | `prometheus-v8` / `README.md` Key Innovations 第 5 条 |
| 5 | v8pro 与 v8 差异：**README 中无任何说明**（两文件逐字节相同） | `prometheus-v8pro` / `README.md` |

### 2.8 v9 — ★ 关键转折：从 12 层砍到 4 层，且明确点名"空壳"

| # | 原文引用 | 来源 |
|---|---------|------|
| 1 | 教训表：`12层进化10层空壳 \| V3-V6 \| 只实现4层进化，每层必须可运行` | `prometheus-v9` / `DESIGN.md` 一 |
| 2 | 教训表：`MBTI推断荒谬 \| V8pro persona.py \| 砍掉，用真实行为特征` / `配置循环论证 \| V8pro L3Config \| 砍掉，配置由外部指定` | 同上 |
| 3 | V9 四层进化全表：`### L2 Evolution (4文件，4层而非12层)` | `prometheus-v9` / `DESIGN.md` 三 |
| 4 | `L0: HyperParams — Thompson Sampling优化超参` `每代采样→应用→根据fitness_delta更新α/β` | `prometheus-v9` / `DESIGN.md` 五 |
| 5 | `L1: CodeEvolution — AST变异 + LLM精炼` `5种AST变异（常量/算子/条件/变量/表达式）+ LLM rewrite` | 同上 |
| 6 | `L2: PlaybookEvolution — ACE模式增量演化` `Generator→Reflector→Curator三角色` `规则增量演化（非全量重写）` | 同上 |
| 7 | `L3: ArchitectureHealth — 代码架构健康监控` `复杂度/模块化/可测试性/依赖度四维指标` `超阈值触发修复建议` | 同上 |
| 8 | 对比表：`进化层 \| 12层(10层空壳) \| 4层(全部实现)` | `prometheus-v9` / `README.md` 与V8pro对比 |
| 9 | 量化取舍：`120文件18,120行 → 26文件4,270行` `精简度: 文件数-78%，代码量-76%` `但每个文件都有血有肉，零空壳。` | `prometheus-v9` / `DESIGN.md` 七 |
| 10 | 层数缩减理由：`为什么6层而非9层？ V8pro的9层中L0(Comm)/L2(Organs)/L6(Monitor)/L7(Governance)职责模糊` | `prometheus-v9` / `DESIGN.md` 二 |

### 2.9 v11 — 进化 = Eval-Driven；进化对象窄化为"eval 门槛"

| # | 原文引用 | 来源 |
|---|---------|------|
| 1 | 三个范式转换原文：`三个范式转换: 写路径(无门控→乘法门控)、生命周期(LLM决策→零LLM)、进化(盲目进化→Eval-Driven)。` | `prometheus-v11` / `V11_DESIGN.md` 〇 |
| 2 | 宪法 P11：`Eval-Driven Evolution \| ECC(E1) \| eval_driven.py → EvalDrivenEngine.define_eval()` | `prometheus-v11` / `V11_DESIGN.md` 一 |
| 3 | 宪法 P22：`参数化品味: 3旋钮控制进化行为 \| taste-skill(TS1) \| evolution_knobs.py → EvolutionKnobs` | 同上 |
| 4 | 进化数据流：`进化: evolve() → EvolutionGrill.grill() → EvalDrivenEn…` | `prometheus-v11` / `V11_DESIGN.md` §3.2 |
| 5 | 机制 M13 原文：`#### [M13] Eval-Driven Evolution (E1+E2)` `- 验收: 先定义eval再进化; pass@3>90%才apply` `- 状态: ✅ 已实现` | `prometheus-v11` / `V11_DESIGN.md` 机制表 |
| 6 | 进化层构成（L3，无架构层）：`L3 Evolution Layer (进化层) EvalDrivenEngine + EvolutionKnobs + VerificationIronLaw + TaskReviewer + EvolutionGrill + GraderRouter` | `prometheus-v11` / `V11_DESIGN.md` §3.1 |
| 7 | 反过度工程：`P1 \| 反过度工程化 \| Claude Code极简两层(L5) \| 模块数≤30, 层数≤5` | 同上 一 |
| 8 | 编译优先：`P10 \| 编译>>在线 \| 通用原理(L1) \| eval_driven.py → should_compile()` | 同上 |

### 2.10 X — 12 层进化引擎，L5MetaEvolution / L11Architecture 都在

| # | 原文引用 | 来源 |
|---|---------|------|
| 1 | `class L5MetaEvolution(EvolutionLayer): """元进化：进化策略本身的变异"""` | `Prometheus-X` / `DESIGN.md` §3.3.1 |
| 2 | `class L11Architecture(EvolutionLayer): """架构变异：模块化 + 依赖管理"""` | 同上 |
| 3 | `class L4Code(EvolutionLayer): """代码变异：AST 级 4 操作符 (refactor/optimize/simplify/add_types)"""` | 同上 |
| 4 | `class L8Memory: """记忆变异：检索参数自进化 (EvolveMem)"""` / `L9Knowledge: """知识变异：本体生成 + 图谱扩展"""` / `L10Collaboration: """协作变异：45% Agent Ceiling 检测"""` | 同上 |
| 5 | 三大自进化分面：`自进化记忆：4 层 Weibull 遗忘…自进化能力：12 层 GA 进化 + UCB1 Bandit 策略选择 + Lotka-Volterra 生态动力学…自进化治理：5 级自治 + 3 级信任 + 宪法约束 + 5 重门控` | `Prometheus-X` / `DESIGN.md` §1.2 |
| 6 | 机制溯源表：`19 \| AdaptiveLayer meta-evolution \| CIP_Hermes_v2 \| L5`、`22 \| L5 MetaEvolution interaction matrix \| CIP_Hermes_v2 \| L5` | `Prometheus-X` / `README.md` Mechanism Provenance |
| 7 | 设计哲学原文：`"让AI从被训练的模型变成能自我进化的生命体"` | `Prometheus-X` / `DESIGN.md` 引言 |
| 8 | ★ 自评原文（作者自己给 L11 判 5/10）：`\| 5 \| **L11Architecture** \| 5/10 \| 仅调整parallelism/cache_size/timeout参数 \|` | `Prometheus-X` / `FINAL_EVALUATION.md` §四 TOP 5 最弱机制 |
| 9 | 同表 L9：`\| 4 \| **L9Knowledge** \| 5/10 \| 仅调整min_confidence/max_results参数 \|`；L6Prompt：`\| 3 \| **L6Prompt** \| 5/10 \| 3种策略仅字符串替换（please→you must）\|` | 同上 |
| 10 | 空壳修复史：`第二轮 \| 9 \| DopamineWriteGate阻断、L9/L11空壳、L4死代码…` | `Prometheus-X` / `AUDIT_50_ROUNDS.md` §五 |

### 2.11 Y — ★ 唯一明确写"能自己改自己架构"的一代

| # | 原文引用 | 来源 |
|---|---------|------|
| 1 | ★ `设计目标：不是"更好的框架"，是一个能自己进化自己的有机体。有新陈代谢、有记忆寿命、有社会性、能自己改自己架构。` | `Prometheus-Y` / `DESIGN.md` 〇、设计声明 |
| 2 | ★ `\| M22 \| Harness元进化 \| V11 \| 9种架构操作(ADD/REMOVE/REORDER/MODIFY/ADD_ORGAN/RECONFIGURE/ADAPT/EXPAND/CONTRACT) \| ✅属实 \| L2 \| harness.apply(ADD_LAYER,config)` | `Prometheus-Y` / `MECHANISM_REGISTRY.md` 机制注册表 |
| 3 | 触发条件：`13. Harness元进化：如果连续3轮无改进，触发架构操作` | `Prometheus-Y` / `DESIGN.md` §五 数据流第 13 步（`DESIGN_v2.md` 同文） |
| 4 | 模块清单：`harness.py  # Harness元进化(M22) — 9种架构操作` | `Prometheus-Y` / `DESIGN.md` §四 |
| 5 | 进化层构成：`L2 Evolution │ CORAL心跳 + AST变异/交叉 + Thompson Sampling / Softmax种群 + 生态动力学 + Lyapunov稳定性 / **Harness元进化** + DopamineWriteGate + A/B验证` | `Prometheus-Y` / `DESIGN.md` §一 |
| 6 | 进化规则（旋钮式）：`E04 \| aggressive \| aggression > 7 时激进重写`；预设 `radical \| 9.0 \| 9.0 \| 7.0 \| 激进重设计` | `Prometheus-Y` / `prometheus_y/rules/evolution_rules.md` |
| 7 | 编译/淘汰规则：`C01 \| compile_instinct \| fitness > 0.95 时编译为instinct` / `C03 \|淘汰 \| fitness < 0.5 时淘汰` | 同上 |
| 8 | 代际判断：`V9已经证明：4层全实现 >> 12层10层空壳。` | `Prometheus-Y` / `DESIGN.md` §一 |
| 9 | AST 变异的负经验已被写成规则：`description: "避免在AST变异中使用swap类型——历史成功率仅12%"` | `Prometheus-Y` / `BREAKTHROUGHS_v2.md` |
| 10 | ★ 追溯链声明（与 §三 对照）：`利益冲突声明：我参与了V6-V11的设计与实现，存在确认偏差风险。` | `Prometheus-Y` / `DESIGN.md` 〇 |

### 2.12 Z — 进化 = 闭环四步，但没说改的是架构

| # | 原文引用 | 来源 |
|---|---------|------|
| 1 | ★ `目标: 让AI Agent自己发现自己哪里不够好，自己修改自己，自己验证修改有效，自己把改进固化成本能——这个循环必须端到端闭合，不需要人类介入。` | `Prometheus-Z` / `Z_DESIGN.md` 引言 |
| 2 | 闭环铁律：`1. 闭环铁律：每个进化步骤必须产出可验证的产物。没有验证输出的步骤 = 没发生。` | `Prometheus-Z` / `Z_DESIGN.md` §2.2 |
| 3 | 变的是什么：`\| E1 \| **AST安全代码变换** \| V7 \| …8种变换(重命名/日志/交换/错误处理/类型注解/提取常量/简化/文档) \|` | `Prometheus-Z` / `Z_DESIGN.md` §1.2 |
| 4 | `\| E2 \| **EvalDrivenEngine** (Grill→DefineEval→WritePlan→Execute→Grade→Apply→Compile) \| V11 \| 7步进化流程 \|` | 同上 |
| 5 | 历史诊断原文：`过去30个仓库的根本问题：闭环始终没闭合。发现弱点 → 设计改进 → [断裂] → 验证有效 → [缺失] → 固化能力 → [未接]` | `Prometheus-Z` / `Z_DESIGN.md` §2.1 |
| 6 | README 的进化面：`\| evolve() \| 触发进化引擎评估改进 \| pz.evolve() \|` | `Prometheus-Z` / `README.md` 核心API |

---

## 三、关于「架构本身可进化」的检索结果

> 检索方法：对 15 个仓库的全部 README + 全部已抓 md（合计 63 个文档单元）做穷尽扫描——正则组 A（`架构|结构|拓扑|模块|层次|分层`）× 正则组 B（`进化|变异|演化|改写|重构|重写|改造|自改|自己改|修改自己|变`）逐句共现，再对每个仓库单独核验。

### ★ 明确回答：**「架构/结构/拓扑本身会变」这句话，作者在 15 个仓库里只写过 3 处，其中只有 2 处是无条件主张，1 处是附条件的借用。**

#### (A) 明确写了 —— 3 处

**A1. v6 —— 架构进化是 12 层进化架构里的第 12 层（无条件主张）**
- 仓库 / 文件：`prometheus-v6` / `README.md`
- 原文：`| L11 | Architecture | 架构进化 |`（完整 12 层表见 §2.5 第 1 条）
- 佐证：v7 继承了同一份文档——`prometheus-v7` / `PROJECT_FINAL_SUMMARY.md` 同段列出 `12层架构 │ 3方向系统 │ 目标管理 │ 并行进化 │ 引导进化`；但 **v7 README 的「统一12层」清单把 L11 换成了 `Budget`（推理预算），架构进化从清单里消失**：
  - `prometheus-v7` / `README.md`：`L10 Quota → L11 Budget`
  - 对照 `prometheus-v6` / `README.md`：`L10 Collaboration | 协作进化 | L11 Architecture | 架构进化`
  - **即：架构进化在 v6→v7 这一代被从进化清单中移除，替换为配额/预算。这是一个可核对的实质变化。**

**A2. Y —— 「能自己改自己架构」是 Y 的设计目标（无条件主张）**
- 仓库 / 文件：`Prometheus-Y` / `DESIGN.md` 〇、设计声明
- 原文：`设计目标：不是"更好的框架"，是一个能自己进化自己的有机体。有新陈代谢、有记忆寿命、有社会性、能自己改自己架构。`
- 落地机制原文（`Prometheus-Y` / `MECHANISM_REGISTRY.md`）：`M22 Harness元进化 | prometheus-v11 | 9种架构操作(ADD/REMOVE/REORDER/MODIFY/ADD_ORGAN/RECONFIGURE/ADAPT/EXPAND/CONTRACT) | ✅属实 | L2 | harness.apply(ADD_LAYER,config)`
- 触发条件（`Prometheus-Y` / `DESIGN.md` §五第 13 步）：`Harness元进化：如果连续3轮无改进，触发架构操作`
- ⚠️ **附条件标注**：Y 把它标为「✅属实」、来源标为 `prometheus-v11`。**该来源标注与 v11 自身文档矛盾，见 (C)。**

**A3. X —— `L11Architecture` 类存在，docstring 写「架构变异」（设计文档主张）**
- 仓库 / 文件：`Prometheus-X` / `DESIGN.md` §3.3.1
- 原文：`class L11Architecture(EvolutionLayer): """架构变异：模块化 + 依赖管理"""`
- ⚠️ **同仓库的自评把它判为名不副实**，见 (B)。

#### (B) 名不副实（设计文档写了，代码/自评否认）

**B1. ★ X 自己承认「架构变异」不是架构变异** —— 这是全部 15 个仓库里唯一一处作者亲自拆自己台的原文：
- 仓库 / 文件：`Prometheus-X` / `FINAL_EVALUATION.md` §四、TOP 5 最弱机制
- 原文：`\| 5 \| **L11Architecture** \| 5/10 \| 仅调整parallelism/cache_size/timeout参数 \|`
- 同表并列：`\| 4 \| **L9Knowledge** \| 5/10 \| 仅调整min_confidence/max_results参数 \|`、`\| 3 \| **L6Prompt** \| 5/10 \| 3种策略仅字符串替换（please→you must）\|`
- 修复史留痕（`Prometheus-X` / `AUDIT_50_ROUNDS.md` §五）：`第二轮 \| 9 \| DopamineWriteGate阻断、L9/L11空壳、L4死代码…`

**B2. v9 把「架构」从进化对象降级为「架构健康监控」（只测不改）**
- 仓库 / 文件：`prometheus-v9` / `DESIGN.md` §五 第 4 小节
- 原文：`### L3: ArchitectureHealth — 代码架构健康监控` `- 复杂度/模块化/可测试性/依赖度四维指标` `- 超阈值触发修复建议`
- 关键：产出是**修复建议**，不是变更动作。README 同步为 `L3 架构健康`（`prometheus-v9` / `README.md` 核心模块）。
- 这是 v6→v9 之间的**已明写的取舍**：v9 的教训表把 `12层进化10层空壳` 列为 V3-V6 的病根，而 v6 的 L11 架构进化正是这 12 层之一（`prometheus-v9` / `DESIGN.md` 一：`12层进化10层空壳 | V3-V6 | 只实现4层进化，每层必须可运行`）。

#### (C) ★★ 明确找不到 —— 以下 5 处**没有任何「架构可进化」的表述**，不得据此推断

| 仓库 | 检索结果（穷尽扫描 + 人工核读） |
|------|------------------------------|
| **prometheus-v11** | **V11_DESIGN.md 全文 32,614 字符，`元进化`/`架构操作`/`ADD_LAYER`/`ADD_ORGAN`/`preflection`/`tool_lifecycle`/`ADD/REMOVE` 全部 0 命中。** 5 层架构中进化层只有 6 个组件（`EvalDrivenEngine + EvolutionKnobs + VerificationIronLaw + TaskReviewer + EvolutionGrill + GraderRouter`，`V11_DESIGN.md` §3.1），无任何架构/结构变更算子。`Harness` 在文中仅指**构建优先级**（`P19 \| 构建优先级Harness→Loop→Context→Prompt`、`Phase 1: Harness (Day 1-2)`），与「架构操作」无关。 |
| **prometheus-v3 / v4 / v5 / v8 / v8pro** | 穷尽共现扫描 **0 命中**。架构词与进化词在同一句里从未同时出现。v4 的 `CodeMutator (refactor/optimize/simplify/type hints)` 是**函数体级代码变换**，非架构级。 |
| **prometheus-v9pro / prometheus-v10** | **未抓到任何文档**，无法判定（`readme_len=0, md=0`）。这是数据缺失，不是「文档里没写」。 |
| **Prometheus-Z** | 穷尽共现扫描仅 3 句，全部**不是**架构进化（`统一本体` 覆盖 `结构/语义/进化/空间6大类关系` 讲的是 EdgeType 分类；`Layer 3 全部14个模块` 讲的是实施验收；`分布式进化架构` 讲的是 Island 并行的部署形态）。Z 的 `自己修改自己` 未指明主语是架构。**Z 全文找不到 `自我修改`/`自己的架构`。** |

#### (D) ★ 交叉验证：Y 声称的 v11 来源在 v11 自身文档与代码中均不存在

- Y 的主张：`Prometheus-Y` / `MECHANISM_REGISTRY.md`：`M22 | Harness元进化 | prometheus-v11 | 9种架构操作(...) | ✅属实`
- v11 自身设计文档：`prometheus-v11` / `V11_DESIGN.md` —— `ADD_LAYER`/`ADD_ORGAN`/`RECONFIGURE`/`EXPAND`/`CONTRACT`/`架构操作` **全部 0 命中**（见 (C)）
- Y 自己给出的代码路径：`Prometheus-Y` / `BREAKTHROUGHS_v2.md`：`### 算法架构（来自V11/preflection.py 19.6KB）`
- 该文件实测（`E:/dream/prometheus-v10/src/prometheus_v10/preflection.py`，19,173 字符）：**`ADD_LAYER`/`REMOVE_LAYER`/`REORDER`/`ADD_ORGAN`/`RECONFIGURE`/`EXPAND`/`CONTRACT`/`MODIFY`/`ADAPT`/`architecture` 全部 0 命中**；文件首行 docstring 自述为 `Prometheus V10 Preflection Engine — Proactive failure avoidance before action.`
- 结论：**Y 标注为「✅属实」的 M22（9 种架构操作），在其自报的来源文件里既无对应常量也无对应实现。作者在同一份 DESIGN.md 里已预先声明了这个风险：`利益冲突声明：我参与了V6-V11的设计与实现，存在确认偏差风险。`**（`Prometheus-Y` / `DESIGN.md` 〇）

---

## 四、代际变化趋势（各代关注点怎么移的）

| 阶段 | 世代 | 关注点位移 | 出处 |
|------|------|-----------|------|
| 1 | **v1/CIP → v3** | 「进化」= 覆盖面最大化。12 层从 meta-parameters 一路铺到 integration，方向分 3 条，功能上开多枝。 | `prometheus` / `cip/README.md`：`Comprehensive evolution across meta-parameters, strategies, skills, configuration, code, memory, communication, perception, reasoning, learning, adaptation, and integration` |
| 2 | **v4** | 首次出现**代码本体**作为变异对象（CodeMutator），但仍是 v3 + Protogonos 的拼接。 | `prometheus-v4` / `README.md`：`Unified fusion of Prometheus v3 + Protogonos` |
| 3 | **v5** | ★ **唯一次降温**：定位从「自进化平台」缩为 `Adaptive memory system with cognitive evolution capabilities`，对外暴露的进化面只剩 `Evolve genome`。作者未写明原因。 | `prometheus-v5` / `README.md` 第 3 行 + CLI 块 |
| 4 | **v6** | 定位回到「终极版」，首次把**「架构」明列为第 12 个进化对象**（L11 架构进化），并给出架构层的第一句哲学：`Agent的进化不是模型能力问题，是架构设计问题`。 | `prometheus-v6` / `README.md` 12层表；`PROJECT_FINAL_SUMMARY.md` §1.2 |
| 5 | **v7** | ★ **架构进化在此代被悄悄替换**：12 层清单从 `L10 Collaboration/L11 Architecture` 改成 `L10 Quota/L11 Budget`。对外说法是「统一12层，12/12层完整」——**补齐的表述与被移除的对象同时发生，README 未说明这一取舍**。 | `prometheus-v7` / `README.md` 架构图 + 对比表 |
| 6 | **v8 / v8pro** | 进化从「12 层内部机制」上升到「9 层系统的治理与主动性」：新增 L7 Governance（5 级自治 + 好奇心队列 + 自发性）。8pro 与 8 的 README 逐字节相同，**无任何代际说明**。 | `prometheus-v8` / `README.md` 9 Layers 表 + Stats；`prometheus-v8pro` / `README.md`（与 v8 一致） |
| 7 | **v9** | ★ **最明确的一次自我否定**。教训表点名 `12层进化10层空壳 | V3-V6`，砍到 4 层全实现、文件数 -78%；`L11 架构进化` 变成 `L3 架构健康监控`，产出「修复建议」而非变更；关键词是「零空壳」。**这是作者第一次用自己的话否掉「架构进化」作为一个可交付的层。** | `prometheus-v9` / `DESIGN.md` 一、三、五、七；`README.md` 与V8pro对比 |
| 8 | **v11** | 进化对象进一步退到**评估协议**：`盲目进化→Eval-Driven`，`先定义eval再进化; pass@3>90%才apply`。5 层架构中无架构层。**全文无「元进化」「架构操作」任何表述。** | `prometheus-v11` / `V11_DESIGN.md` 〇、一、§3.1、M13 |
| 9 | **X** | 把散落机制重组成 12 层 L0-L11，并把 `L5MetaEvolution`/`L11Architecture` 都写进类骨架；但**自评亲手把 L11Architecture 判 5/10「仅调整参数」**，并记入「L9/L11空壳」修复史。定位从「融合」转为「逐函数读源码 + 运行时验证 + mutation testing」。 | `Prometheus-X` / `DESIGN.md` §3.3.1；`FINAL_EVALUATION.md` §一、§四；`AUDIT_50_ROUNDS.md` §五 |
| 10 | **Y** | ★ **唯一把「能自己改自己架构」写成设计目标的一代**，并挂上 9 种架构操作 + 「连续3轮无改进」触发条件。进化对象扩展到**进化方向本身**（`E04 aggressive → 激进重写`、`radical 预设 9/9/7`）。但其 9 种操作的自报来源（v11 `preflection.py`）实测为 0 命中，且作者自己已书面声明确认偏差风险。 | `Prometheus-Y` / `DESIGN.md` 〇、§一、§五；`MECHANISM_REGISTRY.md` M22；`prometheus_y/rules/evolution_rules.md`；`BREAKTHROUGHS_v2.md` |
| 11 | **Z** | 关注点从「架构能不能进化」彻底转向「闭环有没有接上」：`过去30个仓库的根本问题：闭环始终没闭合`。进化 = 发现→修改→验证→固化的端到端闭环，主语明确到 Agent 自己，但**始终没指名要改的是架构**。 | `Prometheus-Z` / `Z_DESIGN.md` 引言、§2.1、§1.2 |

### 一句话趋势（仅陈述原文可核对的方向）

从 v1 的「12 层全面进化」到 v11 的「Eval-Driven + pass@3>90% 才 apply」，**"进化"的可变对象是被逐代收窄的**：12 层枚举（v1/v6）→ 统一 12 层（v7）→ 4 层（v9）→ 评估协议（v11）。**「架构进化」作为一个被显式命名的进化对象，只在 v6/v7 的文档中以表格一行存在过，在 v7 的进化层清单里被替换为「预算」，在 v9 被降格为「架构健康监控（产出修复建议）」，在 v11 的设计文档中完全消失，在 X 的代码骨架中保留为类名但被自评为「仅调整参数」，在 Y 中以设计目标 + 9 种架构操作重新提出（来源不可核实）。**

---

## 附：检索覆盖与未决项

| 项 | 状态 |
|----|------|
| 已逐字读全文的文档 | v3/v4/v5/v8/v8pro README；v6/v7 README + CONTINUOUS_EVOLUTION + PROJECT_FINAL_SUMMARY + PROJECT_SUMMARY + ADR + CONTRIBUTING；v9 README + DESIGN；v11 V11_DESIGN(32.6KB)；X 全部 8 篇；Y 全部 12 篇；Z 全部 6 篇；v1 cip/README |
| **未抓到任何文档（无法判定）** | `prometheus-v9pro`、`prometheus-v10`（`readme_len=0, md=0`） |
| 未读全文、只做穷尽共现扫描 | `prometheus-v6`/`v7` 的 `PROJECT_SUMMARY.md`（内容与 FINAL_SUMMARY 高度重合，已核对核心段一致） |
| 代码级核验（超出文档，做了 1 处） | `E:/dream/prometheus-v10/src/prometheus_v10/preflection.py` —— 用于验证 Y 的 M22 溯源 |
| 明确「找不到」的表述 | v11 的「架构/元进化操作」；v3/v4/v5/v8/v8pro 的任何架构级进化句；Z 的「自己的架构」「自我修改」 |
