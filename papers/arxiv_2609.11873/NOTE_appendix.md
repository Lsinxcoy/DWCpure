# 附录深读笔记：附录 A《RSI Landscape》与附录 B《Industry Landscape》

- 源文件：`E:/Divine Wisdom Core/papers/arxiv_2609.11873/2609.11873.txt`（单行，318,000 字符，arXiv v1 HTML 转纯文本）
- 附录 A 起点 **@290508**（`Appendix A: RSI Landscape`）；附录 B 起点 **@297447**（`Appendix B: Industry Landscape`）；正文 References 起点 @228927（附录在 References **之后**，位于全文末尾）
- 方法：以 arXiv v1 HTML（`https://arxiv.org/html/2609.11873v1`，与本地 txt 同版本）解析表格单元格 → 逐格回查本地 txt 定位字符偏移 → **Table 11 全部 44 行、Table 12 全部 142 个数据行（含 6 个分节行 = 149 行）均逐格 100% 匹配本地 txt**（0 行部分匹配/失配），因此下方每行偏移可信。
- 偏移口径：该行**首个非空单元格**在 txt 中的字符位置；同公司续行（HTML 空 td，共 70 行）以产品名起算。
- 转录纪律：公司名、产品名、级别标签、数字全部照抄原文；本地 txt 中 `&` 以 HTML 实体 `&amp;` 存储（如 `Prompt &amp; Context`），笔记中还原为 `&`。

## 一、附录 A：RSI Landscape（@290508）

### 1.0 结构勘误（与任务预设不同，重要）

附录 A **不是** “按 L1–L5 × 改进目标逐格列出系统”的网格大表。附录 A 只有两个对象：

1. **Figure 16**（sunburst 三层环形图，@290617）：491 篇被综论文的分布，内/中/外环 = 自主级别 L1–L5 / 一级改进目标 / 子目标；
2. **Table 11**（@291094）：改进目标分类法，3 列 × 44 个子目标行（外层 10 个一级目标以分组行给出，HTML 中为嵌套表）。

因此 “系统名 × 自主级别” 的逐格表**在附录 A 中不存在**：按系统标级别的是附录 B Table 12 的 `RSI relation` 列（B0–L5），以及正文 Table 2–7。下文 1.1–1.3 逐格转录附录 A 实际内容，1.4–1.5 给出各级数量统计与 L5 系统清单（来源已标注）。

### 1.1 Figure 16 逐格数据（@290617）

原文题注：*“RSI Landscape: Autonomy Levels and Improvement Targets. Distribution of **491** surveyed papers. The inner, middle, and outer rings represent autonomy levels (L1–L5), primary improvement targets, and sub-targets, respectively. Autonomy-level percentages are based on paper counts. Papers associated with multiple improvement targets contribute fractional weights to the target categories.”*

内环（自主级别）图例数值——自图内 SVG 文本 `data-text` 提取，非估算：

| 自主级别 | 论文数 | 占比 |
|---|---|---|
| L1 | 215 | 43.8% |
| L2 | 155 | 31.6% |
| L3 | 64 | 13.0% |
| L4 | 28 | 5.7% |
| L5 | 29 | 5.9% |
| **合计** | **491** | 100.0% |

中环一级目标（10 个，与 Table 11 一一对应）：1 Prompt & Context、2 Memory & Knowledge、3 Harness / Workflow & Control、4 Tools & Skills、5 Model、6 Trainer / Optimization System、7 Evaluator & Feedback System、8 Data & Environment、9 External Artifact、10 Full-system / Co-evolution，另有 `Other` 桶。中环/外环的逐目标百分比仅以图形形式存在，文本层未给出数值（已核对：全文无 “L1 …%” 形式的第二处数字）。

### 1.2 Table 11 逐格转录（表题 @291094；44 行 × 3 列，全格已核对）

列：Primary Target（一级目标，分组行）｜Sub-target（子目标）｜Modified Component（被改组件，原文）｜中文一句。

| # | 偏移 | Primary Target | Sub-target | Modified Component（原文） | 中文一句 |
|---|---|---|---|---|---|
| 1 | @291449 | 1. Prompt & Context | 1.1 Instruction | System prompts, role specifications, behavioral rules, constraints, and high-level instructions | 系统提示、角色规格、行为规则、约束与高层指令。 |
| 2 | @291561 | 1. Prompt & Context | 1.2 Task Prompt / Template | Task descriptions, problem formulations, prompt templates, and reusable task specifications | 任务描述、问题形式化、提示模板与可复用任务规格。 |
| 3 | @291680 | 1. Prompt & Context | 1.3 Reasoning Prompt / Protocol | Explicit reasoning instructions and protocols, including chain-of-thought, reflection, critique, and debate | 显式推理指令与协议：思维链、反思、批评、辩论。 |
| 4 | @291820 | 1. Prompt & Context | 1.4 Demonstrations / Exemplars | Few-shot examples, demonstrations, successful trajectories, and worked solutions included in context | 上下文中的少样本示例、成功轨迹与示范解答。 |
| 5 | @291952 | 1. Prompt & Context | 1.5 Context Composition | Context selection, ordering, compression, summarization, and allocation of the available context budget | 上下文的选择、排序、压缩、摘要与上下文预算分配。 |
| 6 | @292106 | 2. Memory & Knowledge | 2.1 Episodic / Experience Memory | Records of prior interactions, execution trajectories, successful and failed attempts, and task-specific reflections | 记录历史交互、执行轨迹、成败尝试与任务级反思。 |
| 7 | @292256 | 2. Memory & Knowledge | 2.2 Semantic / Knowledge Memory | Persistent factual, conceptual, and domain knowledge, including structured or external knowledge stores | 持久事实/概念/领域知识，含结构化或外部知识库。 |
| 8 | @292392 | 2. Memory & Knowledge | 2.3 Procedural Memory | Reusable strategies, experience-derived rules, heuristics, procedures, and playbooks | 可复用策略、经验规则、启发式、流程与操作手册。 |
| 9 | @292499 | 2. Memory & Knowledge | 2.4 Memory Representation / Organization | Memory schemas, hierarchical structures, summaries, graphs, indexes, and vector representations | 记忆 schema、层级结构、摘要、图、索引与向量表示。 |
| 10 | @292636 | 2. Memory & Knowledge | 2.5 Memory Operations | Policies governing memory writing, retrieval, updating, consolidation, prioritization, and forgetting | 记忆写入、检索、更新、固化、优先级与遗忘策略。 |
| 11 | @292796 | 3. Harness / Workflow & Control | 3.1 Workflow / Graph | Agent graphs, pipelines, nodes, edges, and execution dependencies between computational stages | Agent 图、流水线、节点边与计算阶段间执行依赖。 |
| 12 | @292912 | 3. Harness / Workflow & Control | 3.2 Planning / Decomposition | Task decomposition, planning modules, subgoal structures, and execution order | 任务分解、规划模块、子目标结构与执行顺序。 |
| 13 | @293019 | 3. Harness / Workflow & Control | 3.3 Routing / Scheduling | Model routing, agent routing, tool routing, execution scheduling, and computational resource allocation | 模型/agent/工具路由、执行调度与算力资源分配。 |
| 14 | @293148 | 3. Harness / Workflow & Control | 3.4 Verification / Reflection Loop | Control loops for checking and revising intermediate or final outputs, including critic–revise, verify–retry, and reflection procedures | 校验与修订中间或最终输出的控制环（critic–revise、verify–retry、反思）。 |
| 15 | @293319 | 3. Harness / Workflow & Control | 3.5 Multi-agent Structure / Protocol | Agent population, role assignment, interaction topology, coordination mechanisms, and communication protocols | agent 群体、角色分配、交互拓扑、协调机制与通信协议。 |
| 16 | @293466 | 3. Harness / Workflow & Control | 3.6 Harness Implementation / Scaffold Code | Source code implementing the agent scaffold, orchestration logic, workflow controller, and runtime coordination mechanisms | 实现 agent scaffold、编排逻辑、工作流控制器与运行时协调的源码。 |
| 17 | @293654 | 4. Tools & Skills | 4.1 Tool Set / Inventory | The collection of tools, APIs, external services, and callable capabilities available to the system | 系统可用的工具、API、外部服务与可调用能力集合。 |
| 18 | @293779 | 4. Tools & Skills | 4.2 Tool Definition / Interface | Tool descriptions, function signatures, schemas, API wrappers, and input–output specifications | 工具描述、函数签名、schema、API 封装与 I/O 规范。 |
| 19 | @293906 | 4. Tools & Skills | 4.3 Tool Implementation | Executable code and internal logic implementing tools or callable external functions | 实现工具或可调用外部函数的可执行代码与内部逻辑。 |
| 20 | @294015 | 4. Tools & Skills | 4.4 Skill / Macro Library | Reusable skills, macros, subroutines, procedures, and higher-level behavioral modules | 可复用技能、宏、子程序、流程与高层行为模块。 |
| 21 | @294127 | 4. Tools & Skills | 4.5 Skill Composition | Rules and structures for combining lower-level skills into higher-level procedures or capabilities | 组合低层技能成更高层过程或能力的规则与结构。 |
| 22 | @294257 | 5. Model | 5.1 Model Weights | Trainable parameters of the backbone model | 骨干模型的可训练参数。 |
| 23 | @294318 | 5. Model | 5.2 Adapter / Auxiliary Module | Parameters of LoRA modules, adapters, memory modules, and other trainable auxiliary components | LoRA、适配器、记忆模块等可训练辅助组件的参数。 |
| 24 | @294444 | 5. Model | 5.3 Architecture | Network architecture, module composition, connectivity patterns, and computational structure | 网络结构、模块组合、连接模式与计算结构。 |
| 25 | @294554 | 5. Model | 5.4 Inference Policy / Configuration | Persistent decoding strategies, test-time policies, inference configurations, and runtime model settings | 持久解码策略、测试时策略、推理配置与运行时模型设置。 |
| 26 | @294729 | 6. Trainer / Optimization System | 6.1 Training Objective | Loss functions, training rewards, learning objectives, and optimization criteria | 损失函数、训练奖励、学习目标与优化准则。 |
| 27 | @294833 | 6. Trainer / Optimization System | 6.2 Optimizer / Update Rule | Optimizers, parameter-update algorithms, learning-rate policies, and associated hyperparameters | 优化器、参数更新算法、学习率策略及相关超参。 |
| 28 | @294957 | 6. Trainer / Optimization System | 6.3 Training Schedule / Pipeline | Ordering, configuration, and interaction of training stages such as fine-tuning, reinforcement learning, and distillation | 微调、强化学习、蒸馏等训练阶段的排序、配置与交互。 |
| 29 | @295112 | 6. Trainer / Optimization System | 6.4 Data Selection / Curriculum | Training-sample selection rules, data mixtures, difficulty schedules, and curriculum policies | 训练样本选择规则、数据配比、难度调度与课程策略。 |
| 30 | @295238 | 6. Trainer / Optimization System | 6.5 Search / Meta-optimization Procedure | Evolutionary, search, selection, and meta-optimization procedures used to generate and select candidate improvements | 生成并择优候选改进的进化/搜索/选择/元优化程序。 |
| 31 | @295431 | 7. Evaluator & Feedback System | 7.1 Evaluator / Judge | Evaluators, critics, graders, judge models, and related components for assessing candidate outputs or system variants | 评估候选输出或系统变体的评估器、批评者、评分器与评委模型。 |
| 32 | @295571 | 7. Evaluator & Feedback System | 7.2 Reward / Fitness Function | Reward models, fitness functions, utility functions, preference models, and scoring rules | 奖励模型、适应度函数、效用函数、偏好模型与打分规则。 |
| 33 | @295691 | 7. Evaluator & Feedback System | 7.3 Verifier | Correctness verifiers, test generators, proof checkers, consistency checks, and validation mechanisms | 正确性验证器、测试生成器、证明检查器、一致性检查与验证机制。 |
| 34 | @295806 | 7. Evaluator & Feedback System | 7.4 Feedback / Credit Assignment | Mechanisms that transform observed outcomes into localized, aggregated, or temporally assigned improvement signals | 把观测结果转成局部/聚合/时序分配的改进信号的机制。 |
| 35 | @295980 | 8. Data & Environment | 8.1 Training / Experience Data | Training datasets, replay buffers, experience pools, interaction trajectories, and other data used for subsequent learning | 供后续学习的训练集、回放池、经验池与交互轨迹。 |
| 36 | @296134 | 8. Data & Environment | 8.2 Task / Curriculum Generator | Components that generate tasks, problems, challenges, or training episodes for subsequent improvement cycles | 生成任务、问题、挑战或训练 episode 的组件。 |
| 37 | @296275 | 8. Data & Environment | 8.3 Environment / Simulator | Environment dynamics, simulators, interaction rules, task worlds, and structures governing system–environment interaction | 环境动力学、模拟器、交互规则、任务世界与系统—环境结构。 |
| 38 | @296425 | 8. Data & Environment | 8.4 World Model | Learned models used to represent, predict, generate, or simulate environmental states and dynamics | 表示、预测、生成或模拟环境状态与动力学的学习模型。 |
| 39 | @296561 | 9. External Artifact | 9.1 Program / Solution Code | Task-level programs, patches, or solution code produced by the system, excluding code implementing the agent itself | 系统产出的任务级程序、补丁或解答代码（不含实现 agent 自身的代码）。 |
| 40 | @296705 | 9. External Artifact | 9.2 Algorithm | Algorithms, kernels, mathematical procedures, symbolic methods, and computational techniques | 算法、内核、数学过程、符号方法与计算技术。 |
| 41 | @296812 | 9. External Artifact | 9.3 Scientific / Design Artifact | Scientific hypotheses, experimental designs, architectures, circuits, engineering designs, and related research artifacts | 科学假设、实验设计、架构、电路、工程设计等研究产物。 |
| 42 | @296998 | 10. Full-system / Co-evolution | 10.1 Multi-target Harness | Multiple harness-level components jointly modified within the same improvement process, such as prompts, memory, workflows, and tools | 同一改进过程中联合修改多个 harness 级组件（提示、记忆、工作流、工具）。 |
| 43 | @297158 | 10. Full-system / Co-evolution | 10.2 Model–Harness Co-evolution | Model parameters and surrounding harness or scaffold components jointly modified across improvement cycles | 跨改进周期联合修改模型参数与其周边 harness/scaffold。 |
| 44 | @297297 | 10. Full-system / Co-evolution | 10.3 Improvement-loop / Meta-RSI | The mechanism that generates, evaluates, selects, and applies candidate changes across successive improvement cycles | 跨多轮生成、评估、选择并应用候选改动的机制本身（元 RSI）。 |

### 1.3 Table 11 一级目标 → 子目标数（结构统计）

| # Primary Target | 子目标数 | 子目标编号 |
|---|---|---|
| 1. 1. Prompt & Context | 5 | 1.1–1.5 |
| 2. 2. Memory & Knowledge | 5 | 2.1–2.5 |
| 3. 3. Harness / Workflow & Control | 6 | 3.1–3.6 |
| 4. 4. Tools & Skills | 5 | 4.1–4.5 |
| 5. 5. Model | 4 | 5.1–5.4 |
| 6. 6. Trainer / Optimization System | 5 | 6.1–6.5 |
| 7. 7. Evaluator & Feedback System | 4 | 7.1–7.4 |
| 8. 8. Data & Environment | 4 | 8.1–8.4 |
| 9. 9. External Artifact | 3 | 9.1–9.3 |
| 10. 10. Full-system / Co-evolution | 3 | 10.1–10.3 |
| **合计** | **44** | 1.1–10.3 |

### 1.4 各级数量统计（两个口径，勿混用）

- **论文口径（附录 A Figure 16，n=491）**：L1 215 (43.8%)、L2 155 (31.6%)、L3 64 (13.0%)、L4 28 (5.7%)、L5 29 (5.9%)。
- **工业系统口径（附录 B Table 12，n=142 个产品/代表作，72 家公司/团队）**，按 `RSI relation` 标签首段归类：

| 级别 | 行数 | 占 142 行 |
|---|---|---|
| B0 | 5 | 3.5% |
| L1 | 47 | 33.1% |
| L2 | 72 | 50.7% |
| L3 | 7 | 4.9% |
| L4 | 3 | 2.1% |
| L5 | 5 | 3.5% |
| adj | 1 | 0.7% |
| unverified | 2 | 1.4% |
| **合计** | **142** | 100% |

全部 26 种标签原文分布（`RSI relation` 列原样）：

| 标签（原文） | 行数 |
|---|---|
| L1-L2 | 36 |
| L2 | 29 |
| L2-L3 | 27 |
| L2 adj. | 6 |
| L1-L2 adj. | 5 |
| L2-L3 adj. | 4 |
| L5 cand. | 4 |
| B0 | 3 |
| L2; L5 vision | 3 |
| L3 cand. | 3 |
| L1 adj. | 2 |
| L1 enabler | 2 |
| L1-L3 enabler | 2 |
| L2-L3 enabler | 2 |
| L3 enabler | 2 |
| L4 | 2 |
| B0-L1 adj. | 1 |
| B0-L2 adj. | 1 |
| L2 cand. | 1 |
| L3 | 1 |
| L3-L4 cand. | 1 |
| L4 cand. | 1 |
| L5 target | 1 |
| RSI claim; unverified | 1 |
| adj.; entity TBD | 1 |
| unverified | 1 |

> 注意：区间标签（如 `L1-L2`）按首段计入上表主级别；`L2-L3` 共 27 行、`L1-L2` 共 36 行，是出现最多的两种写法。

### 1.5 L5 系统清单（两个来源）

**来源 1：附录 B Table 12 中含 `L5` 的全部 8 行（逐行原文）**

| 偏移 | 公司 | 产品/代表作 | 子场景 | 改进目标/产物 | AI 控制部分 | RSI relation |
|---|---|---|---|---|---|---|
| @299083 | Anthropic | When AI builds itself | RSI roadmap | AI-development process | code; experiments; future successor design | L5 target |
| @301394 | Meta | HyperAgents | meta-agent self-modification | task agent; meta agent; program | solve; self-edit; evaluate; archive | L5 cand. |
| @304343 | Ricursive Intelligence | AI-chip co-design | AI systems / chips | EDA designs; compute stack | design search; verify; iterate | L2; L5 vision |
| @304822 | Weco AI | AIDE2 | meta-improvement of researcher | research harness; improver code | rewrite improver; eval; inheritance | L5 cand. |
| @304944 | Sakana AI | Darwin Godel Machine | self-editing agents / AI research | agent source; research pipeline | self-modify; benchmark; archive; experiments | L5 cand. |
| @305095 | Sakana AI | AI Scientist | self-editing agents / AI research | agent source; research pipeline | self-modify; benchmark; archive; experiments | L5 cand. |
| @305605 | MetaCircle | ComfyResearch | AI4AI / autoresearch | training workflows; research hypotheses | experiment compose; code; hypothesis; scoring | L2; L5 vision |
| @305751 | MetaCircle | OPHIS | AI4AI / autoresearch | training workflows; research hypotheses | experiment compose; code; hypothesis; scoring | L2; L5 vision |

其中真正打到 L5 标签的 5 行：**Anthropic《When AI builds itself》= `L5 target`（明确的未来目标，非已证能力）**；**Meta HyperAgents、Weco AI AIDE2、Sakana AI Darwin Godel Machine、Sakana AI AI Scientist = `L5 cand.`（可信但未充分演示）**。另有 3 行 `L2; L5 vision`（Ricursive Intelligence AI-chip co-design、MetaCircle ComfyResearch、MetaCircle OPHIS）= 当前 L2 + L5 愿景。

**来源 2：正文 §3.6 Table 7《L5 mechanisms and external controls》（表题 @137126）——L5 机制侧的 8 项工作，含回环闭合点/继承状态/外部控制**

| 分组 | Work（原文） | 偏移 | Loop closes at | Inherited state | External controls |
|---|---|---|---|---|---|
| Search and self-revision | STOP Zelikman et al. [2024] | @137252 | Next program search | Improver code | Utility; base LM; budget |
| Search and self-revision | Gödel Agent Yin et al. [2025] | @137339 | Next self-revision | Task and update code | Task objective; runtime access |
| Search and self-revision | DGM Zhang et al. [2026b] | @137440 | Descendant search | Agent code; archive | Parent selection; benchmark |
| Search and self-revision | HyperAgents Zhang et al. [2026c] | @137531 | Next agent generation | Task and meta-agent code | Main-study selection; evaluation |
| Successor evaluation | RQGM Iacob et al. [2026] | @137665 | Next-epoch selection | Evaluator; agent code | Anchor; replacement schedule |
| Research policies and harnesses | A-Evolve-Training Shi et al. [2026b] | @137794 | Next research round | Search policy; discovery log | Constitution; benchmark; substrate |
| Research policies and harnesses | AIRA2 Hambardzumyan et al. [2026] / AAR Chen et al. [2026c]（本地 txt 写作 `AIRA 2 Hambardzumyan et al. [2026] / AAR Chen et al. [2026c]`） | @137915 | Task experiments | Research artifacts | Research harness; evaluation |
| Research policies and harnesses | AIDE2 Weco Team [2026]（本地 txt 写作 `AIDE 2 Weco Team [2026]`） | @138041 | Later research runs | Research-agent harness | Private scores; cost budget |

> 注：分组行在原表中是跨列分组标题（`Search and self-revision` / `Successor evaluation` / `Research policies and harnesses`），此处置于首列。

正文对 L5 的判定（§3.6，@135933/@136048 附近）区分 **structural L5**（AI 改动持久存在并控制了后续改进轮）与 **effective L5**（改动确实提升了改进过程）；并明确 “L5 claims are qualified in the text”（Table 7 表注）。

## 二、附录 B：Industry Landscape（@297447）

### 2.1 表头与口径（原文，@297574 / @297953 / @316235）

- 副标题原文：*Company Archetypes in the Emerging RSI / Self-Improvement Landscape — One row per product or representative work; **72 distinct companies/teams**; public-source snapshot: **September 2026**; Organization principle: company archetype, not geography. The RSI tag is a compact mapping to the B0–L5 scheme and is not a claim that the company itself uses that label.*
- 表题原文：*Table 12 : RSI / self-improvement company landscape organized by company archetype.*
- 6 列：`Company | Product / representative work | Sub-scenario | Improvement target / artifact | AI-controlled part | RSI relation`（第 7 列为原文的“可点击一手来源”链接列，纯文本中为空）。
- 行数核对：149 行 = 1 表头 + **6 个分节行** + **142 个数据行**；142 行 = **72 家公司首行 + 70 行同公司续行**（HTML 空 td，非 rowspan 属性），与题注 “72 distinct companies/teams” 精确吻合。
- 阅读指南（原文 @316235）：*B0 denotes task-local autonomy only. L1–L5 follow the review's increasing autonomy scale. “adj.” marks RSI-adjacent infrastructure or behavior; “cand.” marks a plausible but not fully demonstrated level; “target” marks an explicit future objective rather than a demonstrated current capability. Asterisks indicate entries whose company identity or public technical boundary still requires stronger verification.*

### 2.2 分节统计（A–F，共 6 节）

| 节 | 偏移 | 分节标题（原文，节名 + 导语） | 数据行数 | 公司数 |
|---|---|---|---|---|
| A | @298150 | A. Frontier foundation-model & general-agent labs Broad model/platform labs; RSI appears as one capability frontier rather than the sole company thesis. | 50 | 17 |
| B | @304198 | B. RSI-native / AI4AI companies Self-improvement, AI-for-AI, self-evolution, or recursive improvement is central to the company/research thesis. | 27 | 14 |
| C | @307758 | C. Autonomous R&D & scientific-discovery companies Primary product is automated research/discovery; RSI relevance comes from automating experiment and knowledge-production loops. | 20 | 14 |
| D | @310313 | D. Agent optimization, evaluation & learning infrastructure Infrastructure for feedback, skills, RL, evaluation, simulators, training data, or production-agent improvement. | 21 | 15 |
| E | @313018 | E. Embodied, world-model & continual-adaptation companies Persistent adaptation is tied to world models, robotics, environments, or test-time/continual learning. | 17 | 8 |
| F | @315285 | F. Persistent-memory & personal-AI companies Cross-task memory, identity, or reusable skills are the main substrate of adaptation. | 7 | 4 |
| — | — | **合计** | **142** | **72**（6 节相加即等于全局去重数，无公司跨节） |

### 2.3 逐行转录（142 行，逐格原文 + 机制一句话 + 源偏移）

列含义：`序号 | 源偏移 | 公司 | 产品/代表作 | 子场景 | 改进目标/产物 | AI 控制部分 | RSI relation | 机制一句话`。公司列为 `〃` 者是同公司续行（原文该格为空）。

#### A. Frontier foundation-model & general-agent labs Broad model/platform labs; RSI appears as one capability frontier rather than the sole company thesis.

| # | 偏移 | 公司 | 产品/代表作 | 子场景 | 改进目标/产物 | AI 控制部分 | RSI relation | 机制一句话 |
|---|---|---|---|---|---|---|---|---|
| 1 | @298307 | OpenAI | Research acceleration / automated research intern | AI-for-AI research | research code; experiments; evals | code; experiments; candidate integration | L2 | AI 自研代码、跑实验与评测，并把候选改动合入主线（AI-for-AI 研发）。 |
| 2 | @298461 | 〃 | GPT-Red | self-play robustness | red-team policy; adversarial data | attack; defend; train; evaluate | L2 | AI 自攻自防生成对抗数据，训练并评估红队策略。 |
| 3 | @298559 | 〃 | Self-improving tax agents | production adaptation | agent code; prompts; eval set | mine failures; patch; evaluate | L4 cand. | AI 从生产环境挖失败、打补丁并自评，更新 agent 代码/提示/评测集。 |
| 4 | @298677 | 〃 | Harness Engineering | agent-first software R&D | repo; CI; agent instructions | code; test; PR; repair | L1-L2 adj. | AI 写码、跑 CI、提 PR 并自修复，直接改仓库与 agent 指令。 |
| 5 | @298789 | 〃 | Symphony | agent orchestration | task state; repo; workflows | schedule; execute; handoff | L1 adj. | AI 调度任务状态与工作流，执行并向下游交接。 |
| 6 | @298881 | 〃 | AgentKit / prompt optimizer / RFT | agent optimization stack | prompts; graders; weights | optimize; grade; fine-tune | L1-L2 | AI 优化提示、评分器与权重，形成优化—打分—微调闭环。 |
| 7 | @298999 | 〃 | Deep Research | autonomous research | task-local evidence | search; browse; synthesize | B0 | AI 检索浏览任务级证据并综述成结论。 |
| 8 | @299083 | Anthropic | When AI builds itself | RSI roadmap | AI-development process | code; experiments; future successor design | L5 target | AI 写码做实验、设计未来后继模型，直接改进 AI 研发流程本身（L5 目标）。 |
| 9 | @299203 | 〃 | Automated Weak-to-Strong Researcher | automated alignment research | hypotheses; code; experiment logs | propose; train; evaluate; share | L2 | AI 提假设、写码留实验日志，训练评估并共享对齐研究成果。 |
| 10 | @299337 | 〃 | Tool optimization with Claude | tool self-optimization | tool specs; implementations | analyze traces; rewrite; evaluate | L2 | AI 分析调用轨迹，重写工具规格与实现并复评。 |
| 11 | @299455 | 〃 | Harness design for long-running apps | autonomous software R&D | harness; evaluator; app code | plan; generate; evaluate; iterate | L2 adj. | AI 规划—生成—评估—迭代，同时改 harness、评估器与应用代码。 |
| 12 | @299591 | 〃 | Effective long-running agent harnesses | cross-context persistence | progress files; git state | initialize; code; handoff | L1 adj. | AI 用进度文件与 git 状态跨上下文初始化、续写并交接。 |
| 13 | @299716 | 〃 | Agent Skills | persistent skill substrate | skills; scripts; resources | discover; load; reuse | L1 enabler | AI 发现、加载并复用技能脚本与资源（持久技能基座）。 |
| 14 | @299816 | 〃 | Multi-agent Research | autonomous research | task-local findings | plan; spawn; search; synthesize | B0 | AI 规划并派生子代理检索综合，产出任务级发现。 |
| 15 | @299912 | 〃 | Managed Agents | long-horizon agent infrastructure | stable interface; harness | run; resume; supervise | L1 enabler | AI 运行、恢复并监管长时程任务，维护稳定接口与 harness。 |
| 16 | @300021 | 〃 | Parallel Claude compiler project | autonomous software engineering | shared codebase; tests | decompose; code; test; coordinate | B0-L1 adj. | AI 分解任务、编码测试并协调多个 Claude 并行改共享代码库。 |
| 17 | @300154 | Google DeepMind | AlphaEvolve | task-specific program search | algorithms; kernels; system code | generate; mutate; evaluate; select | B0 | AI 生成变异候选程序，评估后择优（进化式程序搜索）。 |
| 18 | @300282 | 〃 | AI Co-Scientist | scientific hypothesis search | hypotheses; research proposals | generate; debate; rank; refine | L2 adj. | AI 生成假设并组织辩论、排序、精炼研究提案。 |
| 19 | @300397 | 〃 | AlphaChip | AI-for-hardware co-design | chip layouts; design policy | place; score; learn; transfer | L2 adj. | AI 布局打分、学习并跨芯片设计迁移（AI-for-硬件协同设计）。 |
| 20 | @300499 | NVIDIA | Eureka | reward / policy design | reward code; robot policies | reward synthesis; simulation; policy training | L2 | AI 合成奖励函数、仿真验证并训练机器人策略。 |
| 21 | @300613 | 〃 | ASPIRE | reward / policy design | reward code; robot policies | reward synthesis; simulation; policy training | L2 | AI 合成奖励函数、仿真验证并训练机器人策略。 |
| 22 | @300720 | Microsoft | Agent Lightning | agent reinforcement learning | policy weights; experience traces | collect; credit; train; evaluate | L2 | AI 收集经验轨迹做信用分配，训练并评估策略权重。 |
| 23 | @300845 | 〃 | Agent Lightning v1.0 | harnessed agentic RL | harness traces; policy weights | interact; retokenize; train; benchmark | L2 | AI 交互产生 harness 轨迹、重分词后训练策略并跑基准。 |
| 24 | @300960 | 〃 | SkillOpt | skill optimization | skill files; instructions | edit; evaluate; optimize | L2 | AI 编辑技能文件与指令，评测后优化技能。 |
| 25 | @301042 | 〃 | ReVeal | self-verifying code agents | code; tests; verifier policy | generate; verify; revise; scale | L2 | AI 生成代码与测试、自验证、修订并规模化扩产。 |
| 26 | @301140 | 〃 | Universal Verifier / auto-research | agent verification R&D | rubrics; verifier; eval pipeline | design; test; compare; refine | L2 adj. | AI 设计评分细则与验证器，测试对比并精化评测流水线。 |
| 27 | @301273 | Meta | Self-Taught Evaluator | evaluator self-training | judge model; synthetic preferences | generate; judge; train; iterate | L2 | AI 合成偏好数据、打分、训练评委模型并迭代（评委自训练）。 |
| 28 | @301394 | 〃 | HyperAgents | meta-agent self-modification | task agent; meta agent; program | solve; self-edit; evaluate; archive | L5 cand. | AI 求解任务后自改写元代理程序、评估并归档（元层自改）。 |
| 29 | @301512 | Alibaba / Qwen | Qwen-Agent | agent training / synthetic environments | training data; environments; post-training | simulation; data synthesis; tool use; RL | L1-L2 | AI 合成环境与训练数据，做工具使用与 RL 后训练。 |
| 30 | @301668 | 〃 | AgentWorld | agent training / synthetic environments | training data; environments; post-training | simulation; data synthesis; tool use; RL | L1-L2 | AI 合成环境与训练数据，做工具使用与 RL 后训练。 |
| 31 | @301809 | 〃 | Qwen-Scope | agent training / synthetic environments | training data; environments; post-training | simulation; data synthesis; tool use; RL | L1-L2 | AI 合成环境与训练数据，做工具使用与 RL 后训练。 |
| 32 | @301950 | DeepSeek | R1 | reasoning self-bootstrapping | reasoning policy; verifier | self-generated reasoning; RL; verifier iteration | L2 | AI 自生成推理样本，RL 训练并与验证器迭代互验。 |
| 33 | @302070 | 〃 | Math-V2 | reasoning self-bootstrapping | reasoning policy; verifier | self-generated reasoning; RL; verifier iteration | L2 | AI 自生成推理样本，RL 训练并与验证器迭代互验。 |
| 34 | @302186 | Tencent AI Lab | R-Zero | self-play reasoning | tasks; pseudo-labels; policy weights | challenge generation; solve; vote; RL | L2-L3 | AI 出题、解题、投票造伪标签，再 RL 训练策略。 |
| 35 | @302309 | ByteDance Seed | Seed-Thinking | model / agent post-training | data; reward; policy weights | data filtering; reward verification; RL | L1-L2 | AI 筛数据、验证奖励，再做模型/agent 后训练。 |
| 36 | @302441 | 〃 | Seed1.5-VL | model / agent post-training | data; reward; policy weights | data filtering; reward verification; RL | L1-L2 | AI 筛数据、验证奖励，再做模型/agent 后训练。 |
| 37 | @302555 | MiniMax | M2 | persistent cloud agents | memory; skills; agent policy | tool use; long-run execution; skill reuse | L1-L2 | AI 长时执行、复用技能与记忆，调用工具网关在云端驻留。 |
| 38 | @302667 | 〃 | MaxHermes | persistent cloud agents | memory; skills; agent policy | tool use; long-run execution; skill reuse | L1-L2 | AI 长时执行、复用技能与记忆，调用工具网关在云端驻留。 |
| 39 | @302778 | 〃 | MaxClaw | persistent cloud agents | memory; skills; agent policy | tool use; long-run execution; skill reuse | L1-L2 | AI 长时执行、复用技能与记忆，调用工具网关在云端驻留。 |
| 40 | @302887 | Moonshot AI | Kimi K3 | long-horizon agents | agent orchestration; tool policy | planning; tool use; swarm coordination | L1-L2 adj. | AI 规划工具策略并群聚协调，完成长时程任务。 |
| 41 | @303010 | 〃 | Agent Swarm | long-horizon agents | agent orchestration; tool policy | planning; tool use; swarm coordination | L1-L2 adj. | AI 规划工具策略并群聚协调，完成长时程任务。 |
| 42 | @303125 | Zhipu AI / Z.AI | AutoGLM | computer-use agent training | policy weights; virtual-phone environments | perception; planning; action; RL | L2 | AI 在虚拟手机环境中感知—规划—行动并做 RL 训练。 |
| 43 | @303256 | 〃 | AgentRL | computer-use agent training | policy weights; virtual-phone environments | perception; planning; action; RL | L2 | AI 在虚拟手机环境中感知—规划—行动并做 RL 训练。 |
| 44 | @303371 | Deep Cogito | Cogito v2 | reasoning post-training | reasoning policy; weights | search; distill; iterative alignment | L1-L2 | AI 搜索蒸馏并对齐迭代，改进推理策略与权重。 |
| 45 | @303486 | 〃 | IDA | reasoning post-training | reasoning policy; weights | search; distill; iterative alignment | L1-L2 | AI 搜索蒸馏并对齐迭代，改进推理策略与权重。 |
| 46 | @303583 | Poolside | Model Factory | automated model R&D | synthetic data; RL; architecture | eval; code-exec RL; ablations; data mix | L1-L2 | AI 跑评测、代码执行 RL、消融实验并调配数据（自动模型研发）。 |
| 47 | @303709 | Thinking Machines Lab | Tinker Agent RL | model customization / agent RL | policy weights; tool-use policy | RL; LLM-judge grading; tool discovery | L1-L2 | AI 用 LLM 评委打分做 RL，并自动发现工具。 |
| 48 | @303854 | 〃 | Inkling | model customization / agent RL | policy weights; tool-use policy | RL; LLM-judge grading; tool discovery | L1-L2 | AI 用 LLM 评委打分做 RL，并自动发现工具。 |
| 49 | @303969 | Nous Research | Hermes Agent | persistent agents | skills; memory; tool gateway | memory; skill reuse; tool orchestration | L1-L2 | AI 管理记忆、复用技能、编排工具网关，支撑持久 agent。 |
| 50 | @304089 | 〃 | skills / memory | persistent agents | skills; memory; tool gateway | memory; skill reuse; tool orchestration | L1-L2 | AI 管理记忆、复用技能、编排工具网关，支撑持久 agent。 |

#### B. RSI-native / AI4AI companies Self-improvement, AI-for-AI, self-evolution, or recursive improvement is central to the company/research thesis.

| # | 偏移 | 公司 | 产品/代表作 | 子场景 | 改进目标/产物 | AI 控制部分 | RSI relation | 机制一句话 |
|---|---|---|---|---|---|---|---|---|
| 51 | @304343 | Ricursive Intelligence | AI-chip co-design | AI systems / chips | EDA designs; compute stack | design search; verify; iterate | L2; L5 vision | AI 搜索 EDA/算力栈设计，验证后迭代（芯片-系统协同）。 |
| 52 | @304475 | Recursive | Automated AI Research | model-training research | training recipes; kernels; code | ideas; experiments; branch merge | L2 | AI 提想法、做实验并合并分支，改进训练配方与内核。 |
| 53 | @304599 | Imbue | Catalyst | research search | recipes; code; hypotheses | population search; experiments; interpretation | L2-L3 | AI 以种群方式搜索配方与假设，做实验并解释结果。 |
| 54 | @304709 | 〃 | Darwinian Evolver | research search | recipes; code; hypotheses | population search; experiments; interpretation | L2-L3 | AI 以种群方式搜索配方与假设，做实验并解释结果。 |
| 55 | @304822 | Weco AI | AIDE2 | meta-improvement of researcher | research harness; improver code | rewrite improver; eval; inheritance | L5 cand. | AI 重写改进器自身代码，评测后遗传给下一轮（研究者自我改进）。 |
| 56 | @304944 | Sakana AI | Darwin Godel Machine | self-editing agents / AI research | agent source; research pipeline | self-modify; benchmark; archive; experiments | L5 cand. | AI 自改源码与研究流水线，跑基准、归档并做实验。 |
| 57 | @305095 | 〃 | AI Scientist | self-editing agents / AI research | agent source; research pipeline | self-modify; benchmark; archive; experiments | L5 cand. | AI 自改源码与研究流水线，跑基准、归档并做实验。 |
| 58 | @305228 | Evolvent AI | Org self-evolving agents | software-agent evolution | skills; memory; code; environments | tasks; feedback; refactor; skill updates | L2-L3 | AI 依据反馈重构并更新技能与记忆，演化软件代理。 |
| 59 | @305372 | 〃 | RSIBench | software-agent evolution | skills; memory; code; environments | tasks; feedback; refactor; skill updates | L2-L3 | AI 依据反馈重构并更新技能与记忆，演化软件代理。 |
| 60 | @305488 | 〃 | Terrarium | software-agent evolution | skills; memory; code; environments | tasks; feedback; refactor; skill updates | L2-L3 | AI 依据反馈重构并更新技能与记忆，演化软件代理。 |
| 61 | @305605 | MetaCircle | ComfyResearch | AI4AI / autoresearch | training workflows; research hypotheses | experiment compose; code; hypothesis; scoring | L2; L5 vision | AI 组装实验、写码并给研究假设打分（AI4AI 自动研究）。 |
| 62 | @305751 | 〃 | OPHIS | AI4AI / autoresearch | training workflows; research hypotheses | experiment compose; code; hypothesis; scoring | L2; L5 vision | AI 组装实验、写码并给研究假设打分（AI4AI 自动研究）。 |
| 63 | @305878 | Frontis AI / Xianyuan | OpenRSI | AI4AI / self-improving agents | skills; memory; harness; weights | experience; update search; eval; post-training | L2-L3 | AI 搜经验更新、评测并后训练，同时改技能/记忆/harness/权重。 |
| 64 | @306024 | 〃 | Frontis-MA1 | AI4AI / self-improving agents | skills; memory; harness; weights | experience; update search; eval; post-training | L2-L3 | AI 搜经验更新、评测并后训练，同时改技能/记忆/harness/权重。 |
| 65 | @306152 | EvoMap | Evolver | shared code evolution | genes / capsules; code assets | generate; test; publish; reuse; adapt | L2-L3 | AI 生成“基因/胶囊”代码资产，测试发布并复用适配。 |
| 66 | @306263 | 〃 | GEP | shared code evolution | genes / capsules; code assets | generate; test; publish; reuse; adapt | L2-L3 | AI 生成“基因/胶囊”代码资产，测试发布并复用适配。 |
| 67 | @306363 | 〃 | GeneBench | shared code evolution | genes / capsules; code assets | generate; test; publish; reuse; adapt | L2-L3 | AI 生成“基因/胶囊”代码资产，测试发布并复用适配。 |
| 68 | @306469 | Endless Frontier | BigBang-v1 | AI-research data generation | synthetic programs; training data; critic | generate; execute; critique; meta-critique | L2-L3 | AI 生成并执行合成程序，做批评与元批评，产出训练数据。 |
| 69 | @306616 | Mirendil | Self-accelerating AI | AI R&D automation | model code; experiments; research stack | experiment generation; execution; iteration | L2 | AI 生成—执行—迭代实验，自动化模型研发栈。 |
| 70 | @306755 | 〃 | AI Scientist | AI R&D automation | model code; experiments; research stack | experiment generation; execution; iteration | L2 | AI 生成—执行—迭代实验，自动化模型研发栈。 |
| 71 | @306877 | Chaoyan Intelligence* | TUMIX | self-evolving research models | research policy; tool-use policy | questioning; experiments; code; self-check | L2-L3 | AI 提问、做实验、写码并自检，演化研究与工具使用策略。 |
| 72 | @307017 | 〃 | R1-Code-Interpreter | self-evolving research models | research policy; tool-use policy | questioning; experiments; code; self-check | L2-L3 | AI 提问、做实验、写码并自检，演化研究与工具使用策略。 |
| 73 | @307149 | 〃 | AI Scientist | self-evolving research models | research policy; tool-use policy | questioning; experiments; code; self-check | L2-L3 | AI 提问、做实验、写码并自检，演化研究与工具使用策略。 |
| 74 | @307274 | Theseus | Argus | long-horizon self-evolving agents | experience; memory; environment setup | plan; code; review; experience writeback | L2-L3 | AI 规划—编码—评审并把经验回写记忆，长时程自演化。 |
| 75 | @307407 | 〃 | SetupX | long-horizon self-evolving agents | experience; memory; environment setup | plan; code; review; experience writeback | L3 | AI 规划—编码—评审并把经验回写记忆，长时程自演化。 |
| 76 | @307530 | Adaption Labs | AutoScientist | AI-research automation | training recipes; datasets; code | research plan; experiments; selection | L2 | AI 制定研究计划、跑实验并择优（数据集/配方/代码）。 |
| 77 | @307655 | 〃 | Forge | AI-research automation | training recipes; datasets; code | research plan; experiments; selection | L2 | AI 制定研究计划、跑实验并择优（数据集/配方/代码）。 |

#### C. Autonomous R&D & scientific-discovery companies Primary product is automated research/discovery; RSI relevance comes from automating experiment and knowledge-production loops.

| # | 偏移 | 公司 | 产品/代表作 | 子场景 | 改进目标/产物 | AI 控制部分 | RSI relation | 机制一句话 |
|---|---|---|---|---|---|---|---|---|
| 78 | @307945 | Periodic Labs | Autonomous laboratory | AI for science | hypotheses; experiment data; models | experiment design; lab run; learning | L3 cand. | AI 设计实验、驱动实验室运行并从中实时学习。 |
| 79 | @308078 | FutureHouse | BixBench | AI-scientist evaluation | research tasks; benchmark frontier | bioinformatics workflows; open-ended eval | B0-L2 adj. | AI 跑生物信息学工作流，做开放式 AI 科学家评测。 |
| 80 | @308211 | Edison Scientific | Kosmos | autonomous science | hypotheses; code; scientific artifacts | literature; experiments; synthesis | L2-L3 | AI 读文献、做实验并综述成科学产物。 |
| 81 | @308335 | Axiom Math | Putnam 2025 | formal mathematics | proofs; verifier traces | conjecture; proof search; formal verification | L2 | AI 提猜想、搜证明并形式化验证（形式数学）。 |
| 82 | @308450 | 〃 | IMO 2026 | formal mathematics | proofs; verifier traces | conjecture; proof search; formal verification | L2 | AI 提猜想、搜证明并形式化验证（形式数学）。 |
| 83 | @308551 | Harmonic | Aristotle | theorem proving | formal proofs | translate; prove; verify | L1-L2 | AI 翻译命题、给出证明并验证（定理证明）。 |
| 84 | @308631 | Core Automation | AI systems-research stack | automated systems research | systems code; research hypotheses | design; code; benchmark; iterate | L2 cand. | AI 设计写码、跑基准并迭代，自动化系统研究。 |
| 85 | @308776 | Discovery Loop | Autonomous discovery loop | automated experimentation | protocols; findings | hypothesis; experiment; analysis; next-step | L3 cand. | AI 从假设→实验→分析→下一步方案的自动实验循环。 |
| 86 | @308916 | Lila Sciences | Autonomous Science platform | scientific discovery | hypotheses; experiments; post-training data | design; lab execution; real-time learning | L3 cand. | AI 设计并执行实验、实时学习，产出后训练数据。 |
| 87 | @309074 | Karpathy / autoresearch | autoresearch | narrow automated research | training code; configs | edit; train; measure; keep | L2 | AI 改训练代码与配置，训练—度量—保留最优（窄域自动研究）。 |
| 88 | @309190 | Prime Intellect | Autonomous research | model R&D | training recipe; optimizer; code | hypothesis; GPU runs; ablation | L2 | AI 提假设、跑 GPU 实验与消融，改进配方与优化器。 |
| 89 | @309307 | 〃 | Speedrun Frontier | model R&D | training recipe; optimizer; code | hypothesis; GPU runs; ablation | L2 | AI 提假设、跑 GPU 实验与消融，改进配方与优化器。 |
| 90 | @309406 | Analemma | FARS | autonomous research | proposals; code; logs; papers | topic; experiment; analysis; writing | L2-L3 | AI 选题、实验、分析并撰写论文（自主研究）。 |
| 91 | @309513 | Novix | AutoAgent | AI research agent | research workflow; eval harness | idea; tool use; experiments; reporting | L2 | AI 从想法到工具调用、实验再到报告的全流程研究代理。 |
| 92 | @309621 | 〃 | OpenHarness | AI research agent | research workflow; eval harness | idea; tool use; experiments; reporting | L2 | AI 从想法到工具调用、实验再到报告的全流程研究代理。 |
| 93 | @309725 | 〃 | AI-Researcher | AI research agent | research workflow; eval harness | idea; tool use; experiments; reporting | L2 | AI 从想法到工具调用、实验再到报告的全流程研究代理。 |
| 94 | @309831 | UniPat | UniScientist | research / evaluation agents | research traces; benchmarks | experiments; coding; multi-agent eval | L1-L2 | AI 做实验写码并多代理评测，沉淀研究轨迹。 |
| 95 | @309952 | 〃 | UniSwarm | research / evaluation agents | research traces; benchmarks | experiments; coding; multi-agent eval | L1-L2 | AI 做实验写码并多代理评测，沉淀研究轨迹。 |
| 96 | @310062 | 〃 | UniMath | research / evaluation agents | research traces; benchmarks | experiments; coding; multi-agent eval | L1-L2 | AI 做实验写码并多代理评测，沉淀研究轨迹。 |
| 97 | @310171 | Kai Chen / venture TBD* | Intern-S1 | AI for science models | scientific model; training data | model training; scientific reasoning | adj.; entity TBD | AI 训练科学模型并做科学推理。 |

#### D. Agent optimization, evaluation & learning infrastructure Infrastructure for feedback, skills, RL, evaluation, simulators, training data, or production-agent improvement.

| # | 偏移 | 公司 | 产品/代表作 | 子场景 | 改进目标/产物 | AI 控制部分 | RSI relation | 机制一句话 |
|---|---|---|---|---|---|---|---|---|
| 98 | @310490 | Warp | Skill optimization loop | coding-agent skills | skills; instructions; examples | feedback mining; skill rewrite; eval | L2 | AI 挖失败反馈、重写技能与示例并评测（编码 agent 技能自优化）。 |
| 99 | @310610 | Factory | Signals | production coding agents | agent behavior; product code | session mining; failure clusters; patch PRs | L4 | AI 挖会话、聚失败簇并自动提补丁 PR（生产闭环改进）。 |
| 100 | @310727 | 〃 | Software Factory | production coding agents | agent behavior; product code | session mining; failure clusters; patch PRs | L4 | AI 挖会话、聚失败簇并自动提补丁 PR（生产闭环改进）。 |
| 101 | @310845 | LangChain | LangSmith self-improving evaluators | evaluator alignment | judge prompts; evaluator model | feedback ingest; judge update; eval | L1-L2 | AI 摄取反馈、更新评委模型与提示并复评（评估器自对齐）。 |
| 102 | @310984 | Replit | Agent 3 | software engineering | application code; tests | build; test; repair; long runs | L1-L2 | AI 构建、测试、修复并长时运行，改应用代码与测试。 |
| 103 | @311081 | MorphMind | Caliper | agent calibration / org memory | agent skills; shared experience | measure; route; reuse experience | L1-L2 adj. | AI 度量、路由并复用共享经验，校准 agent 技能与组织记忆。 |
| 104 | @311206 | DatologyAI | BeyondWeb | data optimization | training corpus; synthetic data | curate; filter; synthesize; benchmark | L1-L2 | AI 筛选、合成训练语料并跑基准（数据优化）。 |
| 105 | @311321 | 〃 | DatBench | data optimization | training corpus; synthetic data | curate; filter; synthesize; benchmark | L1-L2 | AI 筛选、合成训练语料并跑基准（数据优化）。 |
| 106 | @311424 | Ineffable Intelligence | RL infrastructure | RL / experience infrastructure | training environments; trajectories | rollouts; reward; distributed RL | L1-L3 enabler | AI 跑 rollout、算奖励并做分布式 RL（经验基础设施）。 |
| 107 | @311579 | Goodfire | Ember | interpretability-driven training | feature activations; reward signals | feature discovery; feedback; RL | L1-L2 | AI 发现特征、生成反馈信号并做 RL（可解释性驱动训练）。 |
| 108 | @311701 | 〃 | RLFR | interpretability-driven training | feature activations; reward signals | feature discovery; feedback; RL | L1-L2 | AI 发现特征、生成反馈信号并做 RL（可解释性驱动训练）。 |
| 109 | @311813 | Patronus AI | Generative Simulators | evaluation / simulation | simulators; eval suites | scenario generation; grading; failure analysis | L2-L3 enabler | AI 生成场景、打分并分析失败，造模拟器与评测集。 |
| 110 | @311956 | 〃 | Percival | evaluation / simulation | simulators; eval suites | scenario generation; grading; failure analysis | L2-L3 enabler | AI 生成场景、打分并分析失败，造模拟器与评测集。 |
| 111 | @312074 | Braintrust | Loop | production feedback / eval | prompts; evals; datasets | trace ingest; scoring; prompt optimization | L1-L2 | AI 摄取轨迹、打分并优化提示与数据集（生产反馈闭环）。 |
| 112 | @312191 | 〃 | Autoevals | production feedback / eval | prompts; evals; datasets | trace ingest; scoring; prompt optimization | L1-L2 | AI 摄取轨迹、打分并优化提示与数据集（生产反馈闭环）。 |
| 113 | @312302 | Mechanize | RL environments | experience / eval infrastructure | RL tasks; graders; environments | task design; grading; training signal | L3 enabler | AI 设计任务、评分打分器并产出训练信号（经验/评估基础设施）。 |
| 114 | @312442 | 〃 | GBA Eval | experience / eval infrastructure | RL tasks; graders; environments | task design; grading; training signal | L3 enabler | AI 设计任务、评分打分器并产出训练信号（经验/评估基础设施）。 |
| 115 | @312565 | Kando AI | Early company signal | undisclosed / early-stage | undisclosed | undisclosed | unverified | 信息未披露（早期信号）。 |
| 116 | @312656 | Entropy Order* | Data-expert platform | high-quality training data | expert data; eval assets | data production; benchmarking | L1-L3 enabler | AI 生产专家数据与评测资产并做基准测试。 |
| 117 | @312788 | Compounding Intelligence / CORAL* | CORAL | multi-agent research | shared notes; skills; logs | parallel experiments; knowledge sharing; eval | L2-L3 | AI 并行实验、共享笔记/技能/日志并互相评测。 |
| 118 | @312928 | Naive.ai* | Research-lab signal | early RSI lab | undisclosed | undisclosed | RSI claim; unverified | 宣称 RSI 但未验证（早期实验室信号）。 |

#### E. Embodied, world-model & continual-adaptation companies Persistent adaptation is tied to world models, robotics, environments, or test-time/continual learning.

| # | 偏移 | 公司 | 产品/代表作 | 子场景 | 改进目标/产物 | AI 控制部分 | RSI relation | 机制一句话 |
|---|---|---|---|---|---|---|---|---|
| 119 | @313184 | AI2 Robotics | FiS-VLA | embodied policy learning | VLA policy; action data | data; training; planning; control | L2-L3 adj. | AI 用数据训练 VLA 策略，做规划与控制（具身策略学习）。 |
| 120 | @313299 | 〃 | Video2Act | embodied policy learning | VLA policy; action data | data; training; planning; control | L2-L3 adj. | AI 用数据训练 VLA 策略，做规划与控制（具身策略学习）。 |
| 121 | @313403 | X Square Robot | WALL | world models / skill acquisition | world model; skills; action policy | video skill capture; world prediction; control | L2-L3 | AI 从视频捕获技能、预测世界并据以控制（世界模型+技能习得）。 |
| 122 | @313544 | 〃 | HOST | world models / skill acquisition | world model; skills; action policy | video skill capture; world prediction; control | L2-L3 | AI 从视频捕获技能、预测世界并据以控制（世界模型+技能习得）。 |
| 123 | @313670 | Galaxea AI | G0 / G0.5 | VLA R&D platform | VLA model; data; deployment stack | training; eval; real-robot deployment | L2 adj. | AI 训练评测 VLA 并部署到真机（VLA 研发平台）。 |
| 124 | @313792 | 〃 | GForge | VLA R&D platform | VLA model; data; deployment stack | training; eval; real-robot deployment | L2 adj. | AI 训练评测 VLA 并部署到真机（VLA 研发平台）。 |
| 125 | @313900 | TARS Robotics | AWE | tactile world models | tactile world model; manipulation policy | multimodal sensing; prediction; control | L2-L3 adj. | AI 多模态感知、预测触觉世界并控制操作（触觉世界模型）。 |
| 126 | @314031 | 〃 | TacForeSight | tactile world models | tactile world model; manipulation policy | multimodal sensing; prediction; control | L2-L3 adj. | AI 多模态感知、预测触觉世界并控制操作（触觉世界模型）。 |
| 127 | @314157 | Synapx Dynamics | SYNWorld | embodied data / model stack | data; world model; post-training | data synthesis; training; eval; control | L2-L3 | AI 合成数据、训练世界模型并评测控制（具身数据/模型栈）。 |
| 128 | @314289 | 〃 | OctoMind | embodied data / model stack | data; world model; post-training | data synthesis; training; eval; control | L2-L3 | AI 合成数据、训练世界模型并评测控制（具身数据/模型栈）。 |
| 129 | @314405 | 〃 | OctoSense | embodied data / model stack | data; world model; post-training | data synthesis; training; eval; control | L2-L3 | AI 合成数据、训练世界模型并评测控制（具身数据/模型栈）。 |
| 130 | @314522 | MirrOS | Code as Worlds | world models / test-time adaptation | world code; fast weights | environment modeling; eval; test-time update | L1-L2 | AI 建环境模型、评测并在测试时更新 fast weights（世界模型测试时适应）。 |
| 131 | @314656 | 〃 | Spatial-TTT | world models / test-time adaptation | world code; fast weights | environment modeling; eval; test-time update | L1-L2 | AI 建环境模型、评测并在测试时更新 fast weights（世界模型测试时适应）。 |
| 132 | @314780 | Wuya Zhiyuan* | SHINE | continual / test-time learning | LoRA; skill vectors; weights | context adaptation; skill transfer | L1-L2 | AI 按上下文适配、迁移技能（LoRA/技能向量的持续/测试时学习）。 |
| 133 | @314901 | 〃 | LIFT | continual / test-time learning | LoRA; skill vectors; weights | context adaptation; skill transfer | L1-L2 | AI 按上下文适配、迁移技能（LoRA/技能向量的持续/测试时学习）。 |
| 134 | @315007 | 〃 | PaST | continual / test-time learning | LoRA; skill vectors; weights | context adaptation; skill transfer | L1-L2 | AI 按上下文适配、迁移技能（LoRA/技能向量的持续/测试时学习）。 |
| 135 | @315113 | Singularity Escape / Nexus* | Nexus | collaborative self-evolving agents | shared state; org knowledge; harness | collaboration; experience capture; harness adaptation | L3-L4 cand. | AI 协作捕获经验并适配 harness 与组织知识（协作式自演化）。 |

#### F. Persistent-memory & personal-AI companies Cross-task memory, identity, or reusable skills are the main substrate of adaptation.

| # | 偏移 | 公司 | 产品/代表作 | 子场景 | 改进目标/产物 | AI 控制部分 | RSI relation | 机制一句话 |
|---|---|---|---|---|---|---|---|---|
| 136 | @315420 | Engram | Knowledge Cartridges | persistent enterprise memory | knowledge modules; memory | extract; store; retrieve; adapt | L1-L2 adj. | AI 抽取、存储、检索并适配知识模块（持久企业记忆）。 |
| 137 | @315546 | Lemon AI / Hexdo | LemonAI Evolving | local persistent agents | workspace; memory; experience library | web / files / code; persistence; reuse | L1-L2 | AI 在本地工作区持久化经验库，跨网页/文件/代码复用。 |
| 138 | @315687 | EverMind | EverOS | agent memory / OS | long-term memory; skills | retrieve; skill forge; active tasks; eval | L2-L3 | AI 检索长期记忆、锻造技能并跑任务评测（agent 记忆操作系统）。 |
| 139 | @315794 | 〃 | Raven | agent memory / OS | long-term memory; skills | retrieve; skill forge; active tasks; eval | L2-L3 | AI 检索长期记忆、锻造技能并跑任务评测（agent 记忆操作系统）。 |
| 140 | @315891 | 〃 | EverMemOS | agent memory / OS | long-term memory; skills | retrieve; skill forge; active tasks; eval | L2-L3 | AI 检索长期记忆、锻造技能并跑任务评测（agent 记忆操作系统）。 |
| 141 | @315992 | Mindverse | Second Me | personal memory / adaptation | identity model; memory; LoRA | memory modeling; personalization; retrieval | L1-L2 | AI 建身份模型与记忆，做个性化检索与 LoRA 适配（个人记忆）。 |
| 142 | @316120 | 〃 | Me.bot | personal memory / adaptation | identity model; memory; LoRA | memory modeling; personalization; retrieval | L1-L2 | AI 建身份模型与记忆，做个性化检索与 LoRA 适配（个人记忆）。 |

### 2.4 附录 B 级别统计（同 1.4 工业口径，此处给区间视角）

- 首段归类：L1 47、L2 72、L3 7、L4 3、L5 5、B0 5、adj 1、unverified 2（合计 142）。
- 若按标签完整区间看：`L1-L2` 36 行、`L2-L3` 27 行、`L2` 29 行、`L1` 相关（`L1-L2 adj.` 5、`L1 adj.` 2、`L1 enabler` 2、`L1-L3 enabler` 2）等，共 26 种标签（见 1.4 完整表）。
- 显式 L4 仅 3 行：OpenAI《Self-improving tax agents》`L4 cand.`、Factory《Signals》`L4`、Factory《Software Factory》`L4`；另有 Singularity Escape《Nexus》`L3-L4 cand.`。

## 三、DWC 相关性：10 个直接相关系统（自进化 agent / 记忆 / 世界模型 / 评估器）

挑选标准：与 Divine Wisdom Core 的四条主线（自进化 agent 闭环、记忆系统、世界模型、评估器）之一**直接同构**，且在附录 B 中有完整行可回溯。

| # | 系统（公司 · 产品） | 相关维度 | 选择理由（含源偏移） |
|---|---|---|---|
| 1 | Sakana AI · Darwin Godel Machine | 自进化闭环 | 附录 B 唯一把 `self-modify; benchmark; archive; experiments` 四步写进同一行的系统：agent 自改源码→跑基准→归档→继续实验，且正文 Table 7 把 DGM 列为 L5（loop closes at = Descendant search，继承 agent code + archive）。这是 DWC“改进器自改写 + 归档选择”最直接的工业对照。@304944 |
| 2 | Weco AI · AIDE2 | 自进化闭环 | `rewrite improver; eval; inheritance`——改的不是任务解而是 improver 本身，且显式写 inheritance（跨轮继承）；正文 Table 7 中 AIDE2 的继承状态是 research-agent harness，外部控制是 private scores + cost budget，正对应 DWC 的“评估器/预算闸门”。@304822 |
| 3 | Meta · HyperAgents | 自进化闭环 + 评估器 | `solve; self-edit; evaluate; archive`：任务 agent 由元 agent 自改写并归档，是“元层自改 + 选择压力”的最小实现；正文 Table 7 亦列 HyperAgents 为 L5（loop closes at = Next agent generation）。@301394 |
| 4 | Anthropic · When AI builds itself | 自进化路线图 | 标签 `L5 target`，全表唯一以“目标”而非“已证能力”标注 L5 的行，AI 控制部分写到 `future successor design`（设计后继者）。可作为 DWC 长期目标与风险控制（人类保留 acceptance/authority）的对标物。@299083 |
| 5 | Nous Research · Hermes Agent | 记忆 + 技能 + 工具网关 | `skills; memory; tool gateway` / `memory; skill reuse; tool orchestration`——与 DWC 记忆—技能—工具三层同构，是表中最贴近“持久 agent 运行时”的条目；`L1-L2` 说明其自改进仍以技能/记忆复用为主、未触及权重。@303969 |
| 6 | Theseus · Argus | 经验回写记忆 | `experience; memory; environment setup` / `plan; code; review; experience writeback`——显式 experience writeback（经验回写），即 DWC 记忆管道的写入侧；同公司 SetupX 单列 `L3`（学习信号自主获取），说明该厂商在 L3 分界上有可验证证据。@307274 |
| 7 | EverMind · EverOS | 记忆操作系统 | `long-term memory; skills` / `retrieve; skill forge; active tasks; eval`：检索 + 技能锻造 + 主动任务 + 评测四位一体，是“记忆 OS”型架构（另有 Raven、EverMemOS 两行同构），可对照 DWC 的记忆固化/技能生成设计。@315687 |
| 8 | LangChain · LangSmith self-improving evaluators | 评估器自进化 | `judge prompts; evaluator model` / `feedback ingest; judge update; eval`——评估器自身按反馈更新（评委提示与评委模型双改），标签 `L1-L2 adj.`；与 Table 11 的 7.1/7.4（Evaluator/Judge、Feedback/Credit Assignment）两个子目标直接对应，是 DWC 评估器自我校准的可借鉴闭环。@310845 |
| 9 | Patronus AI · Percival | 评估环境 / 模拟器 | `simulators; eval suites` / `scenario generation; grading; failure analysis`，标签 `L2-L3 enabler`（enabler = 支撑性基础设施）：自造场景—打分—失败分析，等价于 DWC 评估器所需的“可生成、可评分的检验环境”。同公司 Generative Simulators 同构。@311956 |
| 10 | MirrOS · Code as Worlds | 世界模型 + 测试时适应 | `world code; fast weights` / `environment modeling; eval; test-time update`：把环境写成代码、以 fast weights 做测试时更新，正是 Table 11 的 8.4 World Model + 8.3 Environment/Simulator 组合；同组 X Square Robot（WALL/HOST，视频技能捕获+世界预测）可作具身侧补充。@314522 |

**顺带值得留意（不占 10 席）**：Frontis AI《OpenRSI》`skills; memory; harness; weights` 全栈自改进（@305878）；Evolvent AI《Org/RSIBench/Terrarium》三行技能-记忆-代码-环境演化（@305228起）；Singularity Escape《Nexus》`L3-L4 cand.` 协作式 harness 适配（@315113）；Engram《Knowledge Cartridges》抽取-存储-检索-适配的持久记忆（@315420）；Wuya Zhiyuan《SHINE/LIFT/PaST》LoRA+技能向量的测试时学习（@314780起）。

## 四、校验记录

| 检查项 | 结果 |
|---|---|
| Table 11 行数（含表头） | 45 行 = 1 表头 + 44 子目标行；44/44 逐格匹配本地 txt |
| Table 12 行数 | 149 行 = 1 表头 + 6 分节 + 142 数据；149/149 逐格匹配本地 txt |
| 公司数 | 72（142 行 = 72 首行 + 70 续行），与原文题注 “72 distinct companies/teams” 一致 |
| 分节行数 | A 50 + B 27 + C 20 + D 21 + E 17 + F 7 = 142 |
| 机制一句话覆盖 | 93 个唯一 (子场景, 改进目标, AI 控制部分) 组合 → 142 行全覆盖，0 行遗漏 |
| 级别统计 | 主级别合计 142；26 种标签合计 142 |
| Figure 16 数值 | 215+155+64+28+29 = 491，与 “Distribution of 491 surveyed papers” 一致 |
| 版本 | 本地 txt = arXiv **v1**（正文写 Figure 16；v3 已改为 Figure 18）；v1/v3 的 Table 11、Table 12 单元格逐格相同 |
| 附录位置 | Appendix A @290508、Appendix B @297447，均在 References @228927 **之后** |
