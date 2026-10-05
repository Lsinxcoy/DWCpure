# Prometheus Z — 自进化AI Agent完整闭环系统

> **目标**: 让AI Agent自己发现自己哪里不够好，自己修改自己，自己验证修改有效，自己把改进固化成本能——这个循环必须端到端闭合，不需要人类介入。
>
> **原则**: 只从已有项目中提取高价值/超前机制，零外部发明。机制当前实现状态不重要，只看机制本身的价值和超前性。

---

## 一、全部项目高价值机制总表

### 1.1 记忆层（存储+生命周期）

| # | 机制 | 来源 | 价值 | 超前性 | 核心思想 |
|---|------|------|------|--------|----------|
| M1 | **Minerva三引擎存储** (SQLite+sqlite-vec+FTS5) | Minerva V2 | ★★★★★ | ★★★★ | 关系+向量+全文三路索引，ACID事务，msgpack+xxhash压缩校验，UUIDv7时序ID |
| M2 | **34 NodeType + 46 EdgeType 统一本体** | Minerva V2 schema.py | ★★★★★ | ★★★★ | 覆盖时间/因果/结构/语义/进化/空间6大类关系，不用枚举膨胀 |
| M3 | **双时态MVCC** (valid_from/to + tx_from/to) | Minerva V2 schema.py | ★★★★★ | ★★★★★ | 业务时间+事务时间分离，支持时间旅行和分支记忆，AI记忆的git |
| M4 | **Hallway跨Agent记忆转移** | Minerva V2 store.py | ★★★★★ | ★★★★★ | Agent间选择性记忆迁移，多Agent协作的记忆基础协议 |
| M5 | **7步事件驱动巩固流水线** | Minerva V2 lifecycle.py | ★★★★ | ★★★★ | Capture→Extract→Link→Compress→Index→Validate→Promote，替代批处理 |
| M6 | **Dream Cycle图重组** | V10 lifecycle.py | ★★★★ | ★★★ | 睡眠时记忆重排：去重+SHMR信念合成+模式发现+远见生成 |
| M7 | **Weibull遗忘曲线** | V10/V3 | ★★★★★ | ★★★★ | 5层记忆各用不同Weibull参数(k<1加速遗忘/k>1巩固保留)，数学驱动而非启发式 |
| M8 | **DualTrack双轨隔离** | Minerva V2/V3 | ★★★★ | ★★★ | Agent记忆vs User记忆隔离存储，防止自我偏见 |
| M9 | **HybridSearch三路RRF** | V9/Minerva | ★★★★ | ★★★ | FTS+Vector+Graph三路Reciprocal Rank Fusion + MMR多样性 |
| M10 | **Community Detection + Hallway桥接** | Minerva V2 graph.py | ★★★★ | ★★★★ | Louvain社区发现 + 跨社区Hallway桥接，发现记忆的隐含连接 |
| M11 | **零LLM生命周期** | V11 | ★★★★★ | ★★★★★ | 巩固/遗忘/晋升全部用计数器+时间戳驱动，不依赖LLM调用，避免巩固陷阱 |
| M12 | **DopamineWriteGate乘法门控** | V11 write_gate.py | ★★★★★ | ★★★★★ | 写入=效用×惊喜×强化计数，乘法门控让低价值+无惊喜+无强化的信息自然写不进去 |
| M13 | **Tree-sitter多语言代码理解** | Minerva V2 understanding.py | ★★★★ | ★★★ | AST级代码解析，提取函数/类/依赖/复杂度，代码作为一等记忆公民 |

### 1.2 进化层（变异+选择+验证）

| # | 机制 | 来源 | 价值 | 超前性 | 核心思想 |
|---|------|------|------|--------|----------|
| E1 | **AST安全代码变换** | V7 | ★★★★★ | ★★★★★ | 唯一真正用ast.parse/ast.walk做代码进化的版本，8种变换(重命名/日志/交换/错误处理/类型注解/提取常量/简化/文档) |
| E2 | **EvalDrivenEngine** (Grill→DefineEval→WritePlan→Execute→Grade→Apply→Compile) | V11 | ★★★★★ | ★★★★★ | 7步进化流程，pass@k组合数公式精确，进化必须通过评估门槛 |
| E3 | **pass@k + pass^k** | V11 | ★★★★★ | ★★★★★ | `1-C(n-c,k)/C(n,k)` 和 `min(1,(c+1)/(n+1))*min(1,c/k)`，采样理论驱动的进化评估 |
| E4 | **VerificationIronLaw** (5步门控+拒绝模糊声明) | V11 | ★★★★★ | ★★★★★ | IDENTIFY→RUN→READ→VERIFY→APPLY，拒绝"should/probably/seems"，不可跳步 |
| E5 | **Thompson Sampling超参优化** | V8/V9Pro | ★★★★ | ★★★★ | Beta分布采样mutation_rate/crossover_rate，贝叶斯优化替代规则调整 |
| E6 | **UCB1多臂赌博机方向选择** | V8/V9Pro | ★★★★ | ★★★★ | Forward/Lateral/Reverse三方向用UCB1选择，探索-利用平衡 |
| E7 | **ThreeStageFitness** (静态20%+动态40%+LLM Judge 40%) | V8 | ★★★★ | ★★★ | 三阶段渐进验证：AST语法→compile+coverage→LLM评分 |
| E8 | **SkillEcosystem (Lotka-Volterra动力学)** | V9Pro/V10 | ★★★★★ | ★★★★★ | 技能生态用微分方程建模：du/dt=r*u*(1-u/K)+Σα_ij*u_i*u_j，协同/冲突量化 |
| E9 | **Pareto前沿多样性保护** | V9Pro | ★★★★ | ★★★★ | 实例级Pareto前沿+按uniquely-best权重采样，防止进化收敛到局部最优 |
| E10 | **AntiEvolutionGate** (4硬性前置) | V11 | ★★★★★ | ★★★★★ | 去重+洞察+应用+连续增益4前置，任何一个不满足就不允许进化 |
| E11 | **compile_to_rule** (fitness>0.95→确定性规则) | V11 | ★★★★★ | ★★★★★ | 高置信度进化结果编译为确定性规则，不需要每次重新推理，从概率到确定性的跃迁 |
| E12 | **Crossover函数/类块级交换** | V7/V8Pro | ★★★★ | ★★★ | AST安全的函数/类级别交叉，比行级拼接更安全 |
| E13 | **EvolutionLoop+Checkpoint** (持续运行+崩溃恢复) | V8Pro | ★★★★ | ★★★ | start/stop/pause/resume + 原子写入checkpoint + 停滞重启 |
| E14 | **CANTANTE对比信用归因** | MSTAR V4.0 | ★★★★ | ★★★★ | 多Agent对比rollout归因：同query不同配置→分解系统奖励为per-agent信号 |
| E15 | **Bootstrap CI扰动鲁棒性** | MSTAR V4.0 | ★★★★ | ★★★★ | Bootstrap置信区间+受控噪声扰动测试，适应度评估的统计严谨性 |
| E16 | **EvolveMem自进化检索** | MSTAR V4.0 | ★★★★ | ★★★★ | 检索配置(top_k/threshold/rerank)自身也进化，UCB1选择最优检索配置 |
| E17 | **MARS三层信念** | MSTAR V4.0 | ★★★★ | ★★★★ | Event(高保真噪声)→Preference(细粒度可变)→Profile(自然语言叙事)，6操作LLM驱动 |
| E18 | **FGGM形式化验证变异** | MSTAR V4.0 | ★★★★ | ★★★ | 每个mutation必须通过形式化验证(内存安全+类型安全+语义保持)才执行 |
| E19 | **RuleBasedPredictor三路径** | MSTAR V4.0 | ★★★ | ★★★ | RuleBased(零成本)→LLMJudge(利用现有LLM)→Trained(积累数据后)，渐进升级 |

### 1.3 安全层（治理+约束）

| # | 机制 | 来源 | 价值 | 超前性 | 核心思想 |
|---|------|------|------|--------|----------|
| S1 | **5级自治控制器** (L0全自动→L4禁止) | V8/V9 | ★★★★★ | ★★★★★ | 15条规则+时间窗口+频率限制+确认/审批回调，真正的安全治理 |
| S2 | **DriftDetector 4维漂移** | V11 | ★★★★ | ★★★★ | 行为/结构/语义/时间4维检测 + 25正向锚点+35负向模式 + 趋势追踪 |
| S3 | **CircuitBreaker 3态Per-Tool** | V10+CIP | ★★★★ | ★★★ | CLOSED→OPEN→HALF_OPEN + 每工具独立熔断 + 滑动窗口 + 半开探测 |
| S4 | **AntiPattern反模式记忆** | V10 | ★★★★ | ★★★★ | 记住过去的失败进化路径，防止重复犯错，进化系统的"免疫系统" |
| S5 | **EquilibriumGuard (Lyapunov+ε-Nash)** | V10 | ★★★★★ | ★★★★★ | Lyapunov稳定性+ε-Nash均衡检测，防止进化发散，数学保证安全 |
| S6 | **动态约束≤7** | V11 | ★★★★ | ★★★ | 工作记忆约束不超过7个(人类认知限制)，超出自动归档最弱约束 |
| S7 | **InstructionPatternDetector** (指令注入检测) | MSTAR V4.0 | ★★★ | ★★★ | 正则+编码注入+权限升级检测，Zombie Agent攻击防护 |
| S8 | **ChainValidator 7维** | V10 | ★★★★ | ★★★ | 7个维度链式验证，每个维度可添加自定义规则 |
| S9 | **3层计划验证器** (单步→组合→拓扑) | V9Pro | ★★★★★ | ★★★★★ | 单步合法≠组合合法：Layer1单步检查，Layer2步骤组合不构成攻击向量(read+send=数据泄露)，Layer3匹配已知攻击链 |
| S10 | **RL病态检测器** (Reward Hacking+Catastrophic Forgetting+Under-Exploration) | V9Pro | ★★★★★ | ★★★★★ | 将进化映射为RL问题，检测3种系统性病态：reward hacking、灾难性遗忘、探索不足 |
| S11 | **确定性门控** (manifest完整性→配置归一化→冒烟测试→跷跷板约束) | V9Pro | ★★★★★ | ★★★★★ | LLM propose + deterministic dispose：LLM探索假设，确定性规则裁决交付 |
| S12 | **变体池+Fork而非Reject** | V9Pro | ★★★★★ | ★★★★★ | 改进A退行B时不是reject而是fork新变体，自然选择决定胜者。GAIA +13.6%无退化 |
| S13 | **4级动态安全姿态** (LOW→MEDIUM→HIGH→CRITICAL) | V9Pro | ★★★★★ | ★★★★★ | 违规率驱动的自动escalation + cooldown降级，类免疫系统的发炎反应 |
| S14 | **适应性地形+Gagarin通道** | V9Pro | ★★★★ | ★★★★ | 追踪编辑类型分布+集中度风险，探索比<20%时Gagarin注入结构性编辑建议 |

### 1.4 协作层（多Agent+编排）

| # | 机制 | 来源 | 价值 | 超前性 | 核心思想 |
|---|------|------|------|--------|----------|
| C1 | **5器官管线** (饕餮→女娲→达尔文→进化池→守卫) | CIP | ★★★★ | ★★★ | 摄入→候选→变异→沙盒→晋升，生物隐喻的进化管线 |
| C2 | **CAS原子claim** | hermes-kanban-cip | ★★★★★ | ★★★★ | Compare-And-Swap原子任务领取，多进程安全，生产级验证 |
| C3 | **Worker上下文构建器** | hermes-kanban-cip | ★★★★ | ★★★ | 自动构建Agent执行上下文(代码+文档+历史)，每个字段有cap防溢出 |
| C4 | **3方向进化** (Forward/Lateral/Reverse) | CIP | ★★★★ | ★★★ | 渐进改进/多样性探索/简化回溯三方向 |
| C5 | **GoalDriven目标驱动** | CIP | ★★★★ | ★★★ | Objective+Constraint+Milestone组合驱动进化方向 |
| C6 | **CoEvolutionLayer双归因** | V9Pro/V10 | ★★★★ | ★★★★ | 垂直归因(skill_defect vs tool_deficiency) + 水平归因(single vs multi_skill_conflict) |
| C7 | **SpeculativeEvolution推测分叉** | V10 | ★★★★ | ★★★★ | 同时探索多个进化方向，选择最优结果合并 |
| C8 | **45%天花板检查** | V8 | ★★★★ | ★★★★ | MiMo论文洞察：单agent成功率>45%时加更多agent反而降低效率 |

### 1.5 认知层（元认知+监控）

| # | 机制 | 来源 | 价值 | 超前性 | 核心思想 |
|---|------|------|------|--------|----------|
| K1 | **CORAL心跳** (Reflect→Consolidate→Redirect) | V9 | ★★★★ | ★★★★ | 周期性自我反思+巩固+方向切换，Agent的"心跳" |
| K2 | **Preflection预反思** | V10 | ★★★★ | ★★★★ | 行动前的预判：预测可能结果→与实际对比→修正模型 |
| K3 | **OperationalMirror** | V10 | ★★★★ | ★★★ | 运行时行为镜像，实时观察自己的决策模式 |
| K4 | **Curiosity好奇心驱动** | V10/V9Pro | ★★★★ | ★★★ | 主动探索未知区域，不只是被动响应任务 |
| K5 | **ReasoningBudget推理预算** | V10 | ★★★★ | ★★★ | 限制推理资源消耗，防止过度思考 |
| K6 | **SafeHarbor安全港** | V10 | ★★★★ | ★★★ | 危险操作前的安全回滚点 |
| K7 | **CORAL心跳+UCB1重定向** | V9 | ★★★★★ | ★★★★★ | Reflect→Consolidate→Redirect三拍，重定向用UCB1 Bandit选策略(非random)，从成功提炼技能+从失败提炼AVOID规则 |
| K8 | **好奇心队列+Gagarin通道** | V9/V9Pro | ★★★★★ | ★★★★★ | 优先级探索队列 + 刻意注入"试试完全不同方法"的Gagarin通道，探索未知的未知 |
| K9 | **记忆代谢引擎** | V9/V11 | ★★★★★ | ★★★★ | 引力公式G=importance×(1+log(1+access))×retention×freshness，5级分诊(PROMOTE/KEEP/DECAY/DELETE/ARCHIVE)+审计日志 |
| K10 | **6维知识缺口检测** | V9 | ★★★★ | ★★★★ | coverage/depth/freshness/consistency/diversity/accuracy 6维量化诊断+自动填充 |
| K11 | **σ异常检测器** | V9 | ★★★ | ★★★ | Z-score+趋势双层异常检测，异常→好奇心队列P1+CORAL redirect |

### 1.6 数据层（版本+追踪）

| # | 机制 | 来源 | 价值 | 超前性 | 核心思想 |
|---|------|------|------|--------|----------|
| D1 | **Provenance 14字段完整溯源** | Minerva V2 | ★★★★★ | ★★★★★ | source+confidence+agent_id+session_id+project_id+parent_id+why+trigger+verify等14字段，每个记忆可追溯到来源 |
| D2 | **分支记忆** (branch_create/merge) | Minerva V2 | ★★★★★ | ★★★★★ | 记忆的git分支：并行探索不同假设，merge时合并最佳结果 |
| D3 | **VersionControl+回滚** | MSTAR V4.0 | ★★★★ | ★★★ | MutationVersion完整历史+FGGM验证+自动回滚 |
| D4 | **TraceStore** | V10 | ★★★★ | ★★★ | 独立的执行轨迹存储，与记忆存储分离 |
| D5 | **经验轨迹召回+拼接** | MSTAR V4.0 | ★★★★ | ★★★★ | 记录完整执行轨迹(state→action→reasoning→outcome→utility)，推理时召回相似轨迹，拼接多轨迹成推理链。存"怎么想到的"而非只存结果 |
| D6 | **RSPL/SEPL双协议语言** | MSTAR V4.0 | ★★★★★ | ★★★★★ | Skill注册/注销/查询/心跳(RSPL) + 进化生命周期Propose→Verify→Apply→Commit/Rollback(AEPL)，Agent进化的"操作系统接口" |
| D7 | **FiveGates写→读→改→巩→执** | V11(five_gates.py) | ★★★★★ | ★★★★★ | 6个独立系统收敛的架构(Write→Read→Modify→Consolidate→Execute)，每层都是级联熔断器，一个门失败就短路 |
| D8 | **ConsolidationGuard保原始** | V11(consolidation_guard.py) | ★★★★★ | ★★★★ | 巩固是有损的→GPT-5.4巩固54%失败率→永远保留原始episode，只创建语义节点+CONSOLIDATES_TO边 |
| D9 | **CascadingFetch 6级瀑布** | V11(cascading_fetch.py) | ★★★★ | ★★★★ | 本地缓存→向量搜索→图遍历→LLM生成→外部API→人类升级，逐级尝试，便宜操作够了就不碰贵的 |
| D10 | **ContextualSubgraph上下文子图** | V11(contextual_subgraph.py) | ★★★★ | ★★★★ | 记忆价值在连接不在节点→图搜索返回子图而非孤立节点→上下文文本生成给LLM消费 |
| D11 | **BufferingSafetyLayer 缓冲>纠正** | V11(buffering.py) | ★★★★★ | ★★★★★ | HSP90验证:不修复变异，缓冲它→PENDING节点存在但不影响recall()→类似分子伴侣帮突变蛋白正确折叠 |
| D12 | **DeterministicRuleEngine 44规则零LLM** | V11(deterministic.py) | ★★★★ | ★★★ | 44条正则+结构+视觉规则检测代码腐烂/架构腐烂/安全腐烂，零API key依赖 |
| D13 | **WriteHook前置/后置钩子** | V11(write_hook.py) | ★★★★ | ★★★ | Pre-hook在DopamineWriteGate之前拦截(可拒绝/修改内容)，Post-hook在写入后审计(不可撤销) |

---

## 二、Prometheus Z 架构设计

### 2.1 核心洞察：为什么过去所有版本都没建成

过去30个仓库的根本问题：**闭环始终没闭合**。

```
发现弱点 → 设计改进 → [断裂] → 验证有效 → [缺失] → 固化能力 → [未接]
```

每个环节你都有过好的实现，但从未串起来端到端跑通。Prometheus Z的核心设计目标就是**强制闭合这个循环**。

### 2.2 架构原则（5条，来自你自己项目的教训）

1. **闭环铁律**：每个进化步骤必须产出可验证的产物。没有验证输出的步骤 = 没发生。
2. **写入门槛**：信息进入记忆必须通过DopamineWriteGate(M12)。低价值信息写不进去，写进来的都是值得保留的。
3. **零LLM生命周期**：巩固/遗忘/晋升(M11)全部用计数器+时间戳，不依赖LLM调用。LLM只用于理解和生成，不用于管理。
4. **进化需要门槛**：AntiEvolutionGate(E10) 4前置必须全部通过才允许进化。不允许无意义的变异。
5. **安全数学保证**：EquilibriumGuard(S5)用Lyapunov稳定性检测。如果进化导致系统不稳定，自动回滚。

### 2.3 五层架构

```
┌─────────────────────────────────────────────────────────────┐
│                    Prometheus Z                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Layer 0: 基石 (Foundation)                                 │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Minerva三引擎存储 (M1)                                │   │
│  │ 34+46统一本体 (M2) + 双时态MVCC (M3)                  │   │
│  │ DopamineWriteGate (M12) + 零LLM生命周期 (M11)         │   │
│  │ Provenance溯源 (D1) + 分支记忆 (D2)                   │   │
│  │ Weibull遗忘 (M7) + HybridSearch (M9)                  │   │
│  │ EventBus + Hallway跨Agent (M4)                        │   │
│  └─────────────────────────────────────────────────────┘   │
│                          ↕                                  │
│  Layer 1: 生命周期 (Lifecycle)                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 7步事件驱动巩固 (M5) + Dream Cycle (M6)               │   │
│  │ DualTrack双轨 (M8) + Community+Hallway (M10)          │   │
│  │ Tree-sitter代码理解 (M13)                              │   │
│  │ MARS三层信念 (E17)                                     │   │
│  └─────────────────────────────────────────────────────┘   │
│                          ↕                                  │
│  Layer 2: 进化 (Evolution)                                  │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ EvalDrivenEngine 7步 (E2)                             │   │
│  │   Grill → DefineEval → WritePlan → Execute            │   │
│  │   → Grade(pass@k) → Apply → Compile                   │   │
│  │ AntiEvolutionGate (E10) + compile_to_rule (E11)       │   │
│  │ VerificationIronLaw (E4)                              │   │
│  │ AST安全变换 (E1) + Crossover (E12)                    │   │
│  │ Thompson Sampling (E5) + UCB1 (E6)                    │   │
│  │ SkillEcosystem (E8) + Pareto (E9)                     │   │
│  │ Bootstrap CI (E15) + EvolveMem (E16)                  │   │
│  │ SpeculativeEvolution (C7) + CoEvolution (C6)          │   │
│  │ CANTANTE信用归因 (E14)                                 │   │
│  └─────────────────────────────────────────────────────┘   │
│                          ↕                                  │
│  Layer 3: 安全 (Governance)                                 │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 5级自治 (S1) + EquilibriumGuard (S5)                  │   │
│  │ DriftDetector (S2) + AntiPattern (S4)                 │   │
│  │ CircuitBreaker (S3) + ChainValidator (S8)             │   │
│  │ FGGM验证 (E18) + 动态约束≤7 (S6)                      │   │
│  │ 45%天花板 (C8) + SafeHarbor (K6)                      │   │
│  └─────────────────────────────────────────────────────┘   │
│                          ↕                                  │
│  Layer 4: 认知 (Cognition)                                  │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ CORAL心跳 (K1) + Preflection (K2)                     │   │
│  │ OperationalMirror (K3) + Curiosity (K4)               │   │
│  │ ReasoningBudget (K5)                                  │   │
│  │ 3方向进化 (C4) + GoalDriven (C5)                      │   │
│  │ CAS任务协调 (C2) + Worker上下文 (C3)                   │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 2.4 闭环如何闭合——核心设计

过去所有版本的问题是"断裂"。Prometheus Z通过**数据流强制闭合**：

```
                    ┌──────────────────────┐
                    │   CORAL心跳触发       │
                    │   (K1: 每N个session)  │
                    └──────────┬───────────┘
                               │
                    ┌──────────▼───────────┐
                    │  Reflect: 发现弱点    │
                    │  (MARS信念+DriftDetector)│
                    │  产出: WeaknessReport  │
                    └──────────┬───────────┘
                               │
                    ┌──────────▼───────────┐
                    │  AntiEvolutionGate    │
                    │  (E10: 4前置检查)     │
                    │  去重? 洞察? 应用?    │
                    │  连续增益?            │
                    │  全部通过才继续       │
                    └──────────┬───────────┘
                               │ 通过
                    ┌──────────▼───────────┐
                    │  EvalDrivenEngine     │
                    │  (E2: 7步进化)        │
                    │  Grill→DefineEval→    │
                    │  WritePlan→Execute    │
                    └──────────┬───────────┘
                               │
                    ┌──────────▼───────────┐
                    │  VerificationIronLaw  │
                    │  (E4: 5步门控)        │
                    │  IDENTIFY→RUN→READ→   │
                    │  VERIFY→APPLY         │
                    │  拒绝模糊声明         │
                    └──────────┬───────────┘
                               │ 验证通过
                    ┌──────────▼───────────┐
                    │  Grade: pass@k评估    │
                    │  (E3: 组合数公式)     │
                    │  fitness = w1*pass@k  │
                    │  + w2*pass^k + ...    │
                    └──────────┬───────────┘
                               │
                    ┌──────────▼───────────┐
                    │  Apply: 写入记忆      │
                    │  DopamineWriteGate    │
                    │  (M12: 效用×惊喜×     │
                    │   强化计数)            │
                    │  低价值写不进去       │
                    └──────────┬───────────┘
                               │ 写入成功
                    ┌──────────▼───────────┐
                    │  Compile: 固化能力    │
                    │  fitness>0.95 →       │
                    │  compile_to_rule (E11)│
                    │  从概率跃迁到确定性   │
                    └──────────┬───────────┘
                               │
                    ┌──────────▼───────────┐
                    │  Consolidate: 巩固    │
                    │  (M5: 7步+Weibull)   │
                    │  (M11: 零LLM驱动)    │
                    │  巩固后触发下一轮CORAL│
                    └──────────────────────┘
```

**关键：每一步都有产物输出，每一步都必须通过门控才能继续。没有"断裂点"。**

### 2.5 与过去版本的本质区别

| 维度 | 过去所有版本 | Prometheus Z |
|------|-------------|-------------|
| 写入 | 任何信息都能写入 | DopamineWriteGate乘法门控 |
| 进化 | 允许任何变异 | AntiEvolutionGate 4前置 |
| 验证 | 启发式或缺失 | VerificationIronLaw 5步 + pass@k数学公式 |
| 巩固 | 依赖LLM或批处理 | 零LLM生命周期 + 事件驱动 |
| 稳定性 | 无保证 | EquilibriumGuard Lyapunov检测 |
| 固化 | 变异结果每次重算 | compile_to_rule确定性编译 |
| 闭环 | 断裂 | 数据流强制闭合，每步有产物 |

---

## 三、目录结构

```
E:\dream\Prometheus Z\
├── Z_DESIGN.md                    ← 本文件
├── pyproject.toml
├── src/prometheus_z/
│   ├── __init__.py                ← Z公共API
│   │
│   ├── foundation/                ← Layer 0: 基石
│   │   ├── __init__.py
│   │   ├── schema.py              ← M2: 34 NodeType + 46 EdgeType (Minerva V2)
│   │   ├── store.py               ← M1: 三引擎存储 + M3: 双时态MVCC + M4: Hallway
│   │   ├── vector.py              ← M1: sqlite-vec向量引擎 (Minerva V2, Bug修复)
│   │   ├── graph.py               ← M10: 社区发现+Hallway桥接 (Minerva V2)
│   │   ├── search.py              ← M9: HybridSearch三路RRF (Minerva V2, Bug修复)
│   │   ├── events.py              ← EventBus (Minerva V2)
│   │   ├── write_gate.py          ← M12: DopamineWriteGate乘法门控 (V11)
│   │   ├── five_gates.py           ← D7: 五门级联熔断器 Write→Read→Modify→Consolidate→Execute (V11)
│   │   ├── write_hook.py           ← D13: Pre/Post写入钩子 (V11)
│   │   ├── forgetting.py          ← M7: Weibull遗忘曲线 (V10)
│   │   ├── zero_llm_lifecycle.py  ← M11: 零LLM生命周期 (V11)
│   │   ├── provenance.py          ← D1: 14字段溯源 (Minerva V2)
│   │   └── branch.py              ← D2: 分支记忆 (Minerva V2)
│   │
│   ├── lifecycle/                 ← Layer 1: 生命周期
│   │   ├── __init__.py
│   │   ├── consolidation.py       ← M5: 7步事件驱动巩固 (Minerva V2)
│   │   ├── consolidation_guard.py ← D8: ConsolidationGuard保原始episode (V11)
│   │   ├── dream_cycle.py         ← M6: Dream Cycle图重组 (V10)
│   │   ├── dual_track.py          ← M8: 双轨隔离 (Minerva V2)
│   │   ├── understanding.py       ← M13: Tree-sitter代码理解 (Minerva V2)
│   │   ├── mars_belief.py         ← E17: MARS三层信念 (MSTAR V4.0)
│   │   ├── cascading_fetch.py     ← D9: 6级瀑布检索 (V11)
│   │   ├── contextual_subgraph.py ← D10: 上下文子图检索 (V11)
│   │   ├── trajectory.py          ← D5: 经验轨迹召回+拼接 (MSTAR V4.0)
│   │   └── embedding.py           ← 嵌入服务 (Minerva V2)
│   │
│   ├── evolution/                 ← Layer 2: 进化
│   │   ├── __init__.py
│   │   ├── eval_driven.py         ← E2: EvalDrivenEngine 7步 (V11)
│   │   ├── anti_evolution_gate.py ← E10: 4硬性前置 (V11)
│   │   ├── iron_law.py            ← E4: VerificationIronLaw (V11)
│   │   ├── pass_k.py              ← E3: pass@k + pass^k (V11)
│   │   ├── compile_rule.py        ← E11: compile_to_rule (V11)
│   │   ├── ast_mutator.py         ← E1: AST安全变换 (V7, 真正实现)
│   │   ├── crossover.py           ← E12: 函数/类块级交叉 (V7/V8Pro)
│   │   ├── bandit.py              ← E5+E6: Thompson Sampling + UCB1 (V8/V9Pro)
│   │   ├── ecosystem.py           ← E8: Lotka-Volterra动力学 (V9Pro/V10)
│   │   ├── pareto.py              ← E9: Pareto前沿 (V9Pro)
│   │   ├── population.py          ← Softmax种群+血缘多样性 (MSTAR V2.0)
│   │   ├── task_domain.py         ← 任务域特异适应度 (MSTAR V2.0)
│   │   ├── validation_set.py      ← k-means验证集Static/Rotating (MSTAR V2.0)
│   │   ├── reflector.py           ← LLM+规则双轨反思 (MSTAR V2.0)
│   │   ├── robustness.py          ← E15: Bootstrap CI (MSTAR V4.0)
│   │   ├── evolve_mem.py          ← E16: EvolveMem自进化检索 (MSTAR V4.0)
│   │   ├── speculative.py         ← C7: 推测分叉 (V10)
│   │   ├── coevolution.py         ← C6: 双归因 (V9Pro/V10)
│   │   ├── cantante.py            ← E14: 对比信用归因 (MSTAR V4.0)
│   │   ├── fggm.py                ← E18: 形式化验证变异 (MSTAR V4.0)
│   │   └── protocol.py            ← D6: RSPL/SEPL双协议语言 (MSTAR V4.0)
│   │
│   ├── governance/                ← Layer 3: 安全
│   │   ├── __init__.py
│   │   ├── autonomy.py            ← S1: 5级自治 (V8/V9)
│   │   ├── equilibrium.py         ← S5: Lyapunov+ε-Nash (V10)
│   │   ├── drift_detector.py      ← S2: 4维漂移检测 (V11)
│   │   ├── anti_pattern.py        ← S4: 反模式记忆 (V10)
│   │   ├── circuit_breaker.py     ← S3: 3态Per-Tool熔断 (V10+CIP合并)
│   │   ├── chain_validator.py     ← S8: 7维链式验证 (V10)
│   │   ├── plan_validator.py      ← S9: 3层计划验证(单步+组合+拓扑) (V9Pro)
│   │   ├── rl_pathology.py        ← S10: RL病态检测(Reward Hacking+Forgetting+Under-Explore) (V9Pro)
│   │   ├── deterministic_gate.py  ← S11: 确定性门控(LLM propose+规则dispose) (V9Pro)
│   │   ├── variant_pool.py        ← S12: 变体池+Fork而非Reject (V9Pro)
│   │   ├── dynamic_security.py    ← S13: 4级动态安全姿态 (V9Pro)
│   │   ├── landscape.py           ← S14: 适应性地形+Gagarin通道 (V9Pro)
│   │   ├── buffering.py           ← D11: BufferingSafetyLayer缓冲>纠正 (V11)
│   │   ├── deterministic.py       ← D12: 44规则零LLM检测引擎 (V11)
│   │   ├── constraint_guard.py    ← S6: 动态约束≤7 (V11)
│   │   ├── ceiling.py             ← C8: 45%天花板 (V8)
│   │   └── safe_harbor.py         ← K6: 安全港 (V10)
│   │
│   ├── cognition/                 ← Layer 4: 认知
│   │   ├── __init__.py
│   │   ├── coral.py               ← K7: CORAL心跳+UCB1重定向 (V9)
│   │   ├── preflection.py         ← K2: 预反思 (V10)
│   │   ├── mirror.py              ← K3: 运行时行为镜像 (V10)
│   │   ├── curiosity.py           ← K8: 好奇心队列+Gagarin通道 (V9/V9Pro)
│   │   ├── budget.py              ← K5: 推理预算 (V10)
│   │   ├── metabolism.py          ← K9: 记忆代谢引擎 (V9/V11)
│   │   ├── knowledge_gap.py       ← K10: 6维知识缺口检测 (V9)
│   │   ├── anomaly.py             ← K11: σ异常检测器 (V9)
│   │   ├── direction.py           ← C4: 3方向进化 (CIP)
│   │   ├── goal_driven.py         ← C5: GoalDriven (CIP)
│   │   └── context_builder.py     ← C3: Worker上下文构建 (kanban-cip)
│   │
│   └── adapters/                  ← 外部适配
│       ├── __init__.py
│       ├── hermes_llm.py          ← LLM调用适配器(httpx+retry+fallback)
│       └── hermes_plugin.py       ← Hermes Agent插件接口
│
└── tests/
    ├── test_foundation/
    ├── test_lifecycle/
    ├── test_evolution/
    ├── test_governance/
    ├── test_cognition/
    └── test_integration/
```

---

## 四、Z公共API

```python
class Z:
    """Prometheus Z — 自进化AI Agent完整闭环系统"""

    def __init__(self, db_path="prometheus_z.db", config=None):
        self.store = MinervaStore(db_path)          # Layer 0
        self.write_gate = DopamineWriteGate()        # M12
        self.forgetting = WeibullForgetting()        # M7
        self.lifecycle = ConsolidationPipeline()     # M5
        self.dream = DreamCycle()                    # M6
        self.ecosystem = SkillEcosystem()            # E8
        self.equilibrium = EquilibriumGuard()        # S5
        # ... 所有模块

    # ── 记忆API ──
    def remember(self, content, node_type, layer, tags=None,
                 utility=0.5, surprise=0.0, reinforce=0) -> str:
        """写入记忆，必须通过DopamineWriteGate"""

    def recall(self, query, limit=10) -> list[dict]:
        """三路RRF混合检索"""

    def forget(self, threshold=0.15) -> int:
        """Weibull遗忘，返回归档/删除数量"""

    # ── 进化API ──
    def evolve(self, steps=1) -> list[EvolutionResult]:
        """EvalDrivenEngine 7步进化，AntiEvolutionGate 4前置"""

    def reflect(self) -> WeaknessReport:
        """CORAL心跳反思"""

    def dream_cycle(self) -> DreamResult:
        """零LLM巩固+Dream Cycle"""

    # ── 治理API ──
    def status(self) -> SystemStatus:
        """系统状态+EquilibriumGuard检测"""

    def branch_create(self, name: str) -> bool:
        """创建记忆分支(并行探索)"""

    def branch_merge(self, source: str) -> int:
        """合并分支"""

    def hallway_transfer(self, to_agent: str, filter_fn=None) -> int:
        """跨Agent记忆转移"""
```

---

## 五、LLM调用架构

Z是Hermes Agent的内核库，LLM调用通过适配器模式接入，不自己实现provider逻辑。

```python
# adapters/hermes_llm.py
class LLMAdapter:
    """LLM调用统一接口 — httpx + retry + fallback"""
    
    def __init__(self, base_url: str, model: str, api_key: str | None = None,
                 max_retries: int = 3, timeout: float = 30.0,
                 fallback_models: list[str] | None = None):
        self._client = httpx.Client(base_url=base_url, timeout=timeout)
        self._model = model
        self._retries = max_retries
        self._fallbacks = fallback_models or []
    
    def call(self, messages: list[dict], *, tools: list | None = None,
             temperature: float = 0.7, max_tokens: int = 4096) -> dict:
        """调用LLM，失败自动retry+fallback"""
        # 1. 尝试主模型(最多max_retries次)
        # 2. 主模型全部失败→按序尝试fallback_models
        # 3. 全部失败→raise LLMUnavailableError(不静默返回stub)
    
    async def acall(self, messages: list[dict], **kwargs) -> dict:
        """异步版本"""
```

### LLM使用边界（明确哪些用LLM，哪些不用）

| 功能 | 用LLM? | 理由 |
|------|--------|------|
| AST变异 | ❌ | 纯代码操作，ast.parse/ast.walk |
| 适应度评估 | ✅ ThreeStageFitness第3阶段 | LLM-as-Judge占40%，但不是唯一裁判 |
| 反思器 | ✅ LLM优先+规则兜底 | MSTAR V2.0双轨模式 |
| 巩固/遗忘/晋升 | ❌ | 零LLM生命周期(M11)，计数器+时间戳 |
| 写入门控 | ❌ | DopamineWriteGate是数学公式 |
| Dream Cycle | ❌ | 图重组是确定性操作 |
| CANTANTE归因 | ✅ | 需要LLM分析rollout差异 |
| MARS信念操作 | ✅ | Extraction/Resynthesis需要LLM |
| 安全检测 | ❌ | 44条确定性规则+7维链式验证 |
| DriftDetector | ❌ | 哈希+计数器，不需要LLM |
| 知识缺口检测 | ✅ | 6维量化后LLM辅助补缺 |
| 好奇心队列 | ❌ | 优先级计算是数学操作 |

---

## 六、测试体系

### 6.1 测试分层

```
tests/
├── unit/                    ← 每个模块独立测试
│   ├── test_store.py        ← MinervaStore: insert/get/search/branch/hallway
│   ├── test_schema.py       ← Node/Edge构造+序列化+双时态
│   ├── test_write_gate.py   ← DopamineWriteGate: 乘法门控+零效用拒绝+惊喜计算
│   ├── test_five_gates.py   ← 五门级联: 一门失败→短路
│   ├── test_forgetting.py   ← Weibull: 5层不同参数+衰减曲线
│   ├── test_zero_llm.py     ← 零LLM: 巩固/遗忘/晋升不调LLM
│   ├── test_eval_driven.py  ← 7步进化: Grill→DefineEval→...→Compile
│   ├── test_anti_evo.py     ← 4前置: 去重/洞察/应用/连续增益
│   ├── test_iron_law.py     ← 5步门控: IDENTIFY→RUN→READ→VERIFY→APPLY
│   ├── test_pass_k.py       ← pass@k: 组合数公式+边界值
│   ├── test_ecosystem.py    ← Lotka-Volterra: 协同/冲突+动态效用
│   ├── test_equilibrium.py  ← Lyapunov: 势函数非增+ε-Nash
│   ├── test_coral.py        ← CORAL: Reflect→Consolidate→Redirect
│   ├── test_bandit.py       ← Thompson+UCB1: 收敛性
│   └── ...
├── integration/             ← 跨模块数据流测试
│   ├── test_write_flow.py   ← WriteHook→FiveGates→WriteGate→Store 完整写入流
│   ├── test_evolve_flow.py  ← AntiEvoGate→EvalDriven→IronLaw→pass@k→Apply 完整进化流
│   ├── test_lifecycle.py    ← Consolidation→ConsolidationGuard→Weibull→Metabolism 完整生命周期
│   ├── test_coral_loop.py   ← CORAL→Reflect→Evolve→Verify→Consolidate→下一轮 完整闭环
│   └── test_multi_agent.py  ← CAS claim→Worker context→Hallway transfer 多Agent协作
├── regression/              ← 防止过去版本的功能退化
│   ├── test_no_ast_regression.py  ← AST变换不能退回正则替换(V7→V9教训)
│   ├── test_no_lru_loss.py        ← 不能丢失LRU缓存(V7→V8教训)
│   ├── test_no_formula_gap.py     ← 适应度公式必须实现(hermes-mstar教训)
│   └── test_no_stub_llm.py        ← LLM调用不能静默返回stub(CIP教训)
└── constitutional/          ← 设计原则合规测试
    ├── test_write_gate_only.py    ← 所有写入必须通过DopamineWriteGate
    ├── test_evo_gate_only.py      ← 所有进化必须通过AntiEvolutionGate
    ├── test_iron_law_only.py      ← 所有验证必须通过VerificationIronLaw
    └── test_zero_llm_lifecycle.py ← 巩固/遗忘/晋升不能调LLM
```

### 6.2 测试质量要求

| 规则 | 要求 | 验证方法 |
|------|------|---------|
| **pytest.raises ≥ 5%** | 异常测试不少于总测试5% | `grep -c "pytest.raises" tests/` / 总测试数 |
| **每个门控有拒绝测试** | WriteGate/EvoGate/IronLaw必须有"拒绝"路径测试 | 每个gate至少1个rejected测试 |
| **数据流闭合测试** | 每个闭环步骤必须产出下一步可消费的产物 | `test_coral_loop.py` 端到端 |
| **回归测试覆盖历史教训** | V7→V9 AST退化、V7→V8 LRU丢失、hermes-mstar公式落差 | `tests/regression/` |
| **宪法合规测试** | 三条铁律不能违反 | `tests/constitutional/` |
| **dataclass不用if not** | `if not result:` 对dataclass永远False | grep检测 |

---

## 七、性能基准

### 7.1 Layer 0 基石层基准

| 基准ID | 操作 | 指标 | 门槛 | 测量方法 |
|--------|------|------|------|---------|
| B01 | `remember()` 单条写入 | 延迟 | < 5ms | 1000次平均，含三路索引 |
| B02 | `recall()` 混合搜索 | 延迟 | < 50ms (1K节点) | FTS+Vector+Graph三路RRF |
| B03 | `recall()` 混合搜索 | 延迟 | < 200ms (10K节点) | 同上，数据量10x |
| B04 | `recall()` 混合搜索 | 召回率 | > 85% | 对标注数据集测3路vs单路 |
| B05 | WriteGate 拒绝率 | 比例 | 垃圾拒绝>90%，有效通过>80% | utility=0必须拒绝，utility>3必须通过 |
| B06 | Weibull遗忘 | 精度 | 衰减曲线与理论误差<5% | 对比公式计算vs实际衰减 |
| B07 | `branch_create()` | 延迟 | < 100ms (1K节点) | 复制活跃节点到新分支 |
| B08 | `branch_merge()` | 延迟 | < 500ms (1K节点) | 合并分支冲突解决 |
| B09 | `hallway_transfer()` | 延迟 | < 200ms (100节点) | 跨Agent选择性迁移 |
| B10 | FiveGates 级联 | 延迟 | < 1ms (全通过) | 5门串行检查 |
| B11 | FiveGates 短路 | 延迟 | < 0.1ms (第1门拒绝) | 第1门失败立即返回 |

### 7.2 Layer 1 生命周期层基准

| 基准ID | 操作 | 指标 | 门槛 | 测量方法 |
|--------|------|------|------|---------|
| B12 | 7步巩固流水线 | 延迟 | < 2s (100节点) | Capture→Extract→Link→Compress→Index→Validate→Promote |
| B13 | Dream Cycle | 延迟 | < 10s (1K节点) | 去重+SHMR+模式发现+远见生成 |
| B14 | ConsolidationGuard | 保真度 | 原始episode 100%保留 | 巩固后原始节点仍可查询 |
| B15 | CascadingFetch | 级联效率 | 缓存命中时<1ms，LLM调用时记录cost | 6级瀑布逐级升级 |
| B16 | 记忆代谢 | 分诊正确率 | > 90% | 对标注节点验证PROMOTE/KEEP/DECAY/DELETE/ARCHIVE分类 |
| B17 | 零LLM巩固 | LLM调用次数 | = 0 | mock LLM，巩固全程不触发 |

### 7.3 Layer 2 进化层基准

| 基准ID | 操作 | 指标 | 门槛 | 测量方法 |
|--------|------|------|------|---------|
| B18 | EvalDrivenEngine 7步 | 完整率 | 7步全部执行 | Grill→DefineEval→WritePlan→Execute→Grade→Apply→Compile |
| B19 | AntiEvolutionGate | 拒绝率 | 无洞察变异拒绝率>80% | 4前置至少1个不满足→拒绝 |
| B20 | VerificationIronLaw | 拒绝率 | 模糊声明拒绝率100% | "should"/"probably"/"seems"→拒绝 |
| B21 | pass@k | 精度 | 与公式误差<1% | 对比`1-C(n-c,k)/C(n,k)`计算vs采样估计 |
| B22 | AST变异 | 语法安全率 | = 100% | `ast.parse(ast.unparse(mutated))`不抛异常 |
| B23 | AST变异 | 有效变异率 | > 30% | 变异后fitness变化>0.01的比例 |
| B24 | Lotka-Volterra | 动态效用收敛 | 50轮内稳定 | 协同/冲突系数收敛到稳态 |
| B25 | EquilibriumGuard | Lyapunov检测 | 势函数非增 | 每轮进化后V(t+1)≤V(t)+ε |
| B26 | Thompson Sampling | 收敛性 | 100轮内最优超参选择率>60% | Beta分布采样收敛到最优 |
| B27 | Bootstrap CI | 覆盖率 | 95%CI包含真值比例>90% | 1000次重复实验 |
| B28 | compile_to_rule | 编译率 | fitness>0.95的规则100%编译 | 从概率跃迁到确定性 |

### 7.4 Layer 3 安全层基准

| 基准ID | 操作 | 指标 | 门槛 | 测量方法 |
|--------|------|------|------|---------|
| B29 | 5级自治 | 频率限制 | 超限操作100%被拒绝 | L2确认+L3审批操作超频→拒绝 |
| B30 | 3层计划验证 | 攻击链检测率 | 已知攻击链100%拦截 | read+send=泄露, write+exec=注入 |
| B31 | RL病态检测 | Reward Hacking检测率 | > 80% | 注入已知hacking模式→检测 |
| B32 | 确定性门控 | 拒绝率 | manifest不完整100%拒绝 | 缺changed_components→拒绝 |
| B33 | 变体池Fork | 跷跷板解决率 | 改进A退行B时fork成功率>90% | 不reject而是fork新变体 |
| B34 | 44规则检测 | 零LLM | API调用=0 | mock httpx，检测全程不触发 |
| B35 | BufferingSafetyLayer | PENDING隔离 | PENDING节点0次出现在recall()结果中 | 写入PENDING→recall不返回 |

### 7.5 Layer 4 认知层基准

| 基准ID | 操作 | 指标 | 门槛 | 测量方法 |
|--------|------|------|------|---------|
| B36 | CORAL心跳 | 闭环完整性 | Reflect→Consolidate→Redirect三拍全部执行 | 每N个session触发一次完整循环 |
| B37 | 好奇心队列 | Gagarin注入 | 每10次探索至少1次Gagarin通道 | 结构性编辑比例>20% |
| B38 | 6维知识缺口 | 检测准确率 | > 80% | 对标注缺口验证6维诊断 |
| B39 | σ异常检测 | 检测延迟 | < 1个session | fitness突降>2σ立即触发 |
| B40 | 推理预算 | 预算遵守率 | = 100% | 超预算操作0次执行 |

### 7.6 端到端闭环基准

| 基准ID | 操作 | 指标 | 门槛 | 测量方法 |
|--------|------|------|------|---------|
| B41 | 完整进化闭环 | 端到端成功率 | > 60% | CORAL→Reflect→EvoGate→EvalDriven→IronLaw→pass@k→WriteGate→Compile→Consolidate |
| B42 | 闭环无断裂 | 数据流完整性 | 每步产物被下一步消费 | 10轮闭环，0次None/空产物 |
| B43 | 50轮稳定性 | 无崩溃率 | = 100% | 50轮连续运行，0次异常退出 |
| B44 | 退化保护 | 功能不丢失 | 回归测试100%通过 | 每轮后跑regression/ |
| B45 | 进化实际效果 | fitness提升率 | 10轮内至少1次fitness提升>0.01 | 不允许10轮零改进 |

---

## 八、实施步骤（含验收标准）

| Phase | 任务 | 验收标准（可执行验证） | 基准覆盖 |
|-------|------|----------------------|---------|
| **P0: 基石** | Layer 0 全部14个模块 | ① `Z().remember("hello")` 返回node_id<br>② `Z().recall("hello")` 返回结果<br>③ WriteGate拒绝utility=0<br>④ FiveGates一门失败短路<br>⑤ `branch_create("test")` + `branch_merge("test")` 成功<br>⑥ B01-B11全部达标 | B01-B11 |
| **P1: 生命周期** | Layer 1 全部9个模块 | ① `Z().dream_cycle()` 返回DreamResult<br>② ConsolidationGuard保留原始episode<br>③ CascadingFetch 6级瀑布可运行<br>④ 零LLM巩固=0次LLM调用<br>⑤ B12-B17全部达标 | B12-B17 |
| **P2: 进化核心** | Layer 2 EvalDrivenEngine+IronLaw+pass@k+AntiEvoGate+AST | ① `Z().evolve()` 端到端7步<br>② AntiEvoGate拒绝无洞察变异<br>③ IronLaw拒绝模糊声明<br>④ AST变异100%语法安全<br>⑤ Lotka-Volterra 50轮收敛<br>⑥ B18-B28全部达标 | B18-B28 |
| **P3: 安全** | Layer 3 全部14个模块 | ① `Z().status()` 返回EquilibriumGuard结果<br>② 3层计划验证拦截攻击链<br>③ RL病态检测识别hacking<br>④ 变体池fork成功<br>⑤ B29-B35全部达标 | B29-B35 |
| **P4: 认知** | Layer 4 全部11个模块 | ① CORAL心跳触发完整闭环<br>② 好奇心队列Gagarin注入<br>③ 6维知识缺口检测<br>④ B36-B40全部达标 | B36-B40 |
| **P5: 集成** | 全部模块端到端 | ① B41-B45全部达标<br>② 50轮稳定运行无崩溃<br>③ 回归测试100%通过<br>④ 宪法合规测试100%通过 | B41-B45 |

---

## 九、不做什么

- ❌ 不发明新机制——所有机制均来自已有项目
- ❌ 不使用LLM做生命周期管理——巩固/遗忘/晋升全部零LLM
- ❌ 不允许无门控的写入——DopamineWriteGate是唯一的写入路径
- ❌ 不允许无前置的进化——AntiEvolutionGate是唯一的进化入口
- ❌ 不允许无验证的改进——VerificationIronLaw是唯一的验证路径
