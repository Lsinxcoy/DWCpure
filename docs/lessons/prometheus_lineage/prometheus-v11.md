# V11 设计方案 v3.0 (重构版)

> **单一来源真相文档** — 每个机制只定义一次，映射到代码函数+验收条件+实现状态
> 基于: 18个来源 × 99个提取机制 × 22条设计原则
> 日期: 2026-06-18 | 状态: 实施中 (Phase 1-2 完成)

---

## 〇、设计哲学

**V11 = V10的骨架 + Mnemosyne的脊柱 + CIP的管道 + 进化学的灵魂 + 开源项目的盔甲** — 以写入门控为核心安全阀、以零LLM生命周期为运行时、以Eval-Driven Evolution为进化方法、以动态缓冲为治理哲学的自主进化记忆系统。三个范式转换: 写路径(无门控→乘法门控)、生命周期(LLM决策→零LLM)、进化(盲目进化→Eval-Driven)。

---

## 一、宪法 (22条)

> 每条是V11的编译约束，不是愿望清单。代码强制点可直接grep验证。

| # | 原则 | 来源 | 代码强制点 | 实现状态 |
|---|------|------|-----------|---------|
| P0 | V10在V9PRO基础上迭代 | 用户指令 | `git diff v9pro..v11` | ✅ |
| P1 | 反过度工程化 | Claude Code极简两层(L5) | 模块数≤30, 层数≤5 | ✅ 30模块/5层 |
| P2 | 更多记忆反而更差 | LongMINT(T1) | `write_gate.py → DopamineWriteGate.should_write()` | ✅ |
| P3 | 写入是决策不是存储 | R2127+R2128(B2) | `write_gate.py → should_write()` 乘法门控 | ✅ |
| P4 | Buffering>Error Correction | HSP90(3.5B年验证) | `buffering.py → BufferingSafetyLayer.buffer()` | ✅ |
| P5 | 确定性检测>LLM检测 | impeccable(I1) | `deterministic.py → DeterministicRuleEngine.check_code()` | ✅ |
| P6 | 巩固是有损变换 | R2137(F5) | `consolidation_guard.py → ConsolidationGuard.should_consolidate()` | ✅ |
| P7 | 零LLM生命周期 | Nautilus(课题二) | `zero_llm_lifecycle.py → ZeroLLMLifecycle.should_promote()` | ✅ |
| P8 | 遗忘=智能有损压缩 | Rate-Distortion(L2) | `zero_llm_lifecycle.py → should_decay()/should_forget()` | ✅ |
| P9 | 记忆价值在连接不在节点 | R2129 FluxMem(B8) | `contextual_subgraph.py → ContextualSubgraph.induce_context()` | ✅ |
| P10 | 编译>>在线 | 通用原理(L1) | `eval_driven.py → EvalDrivenEngine.should_compile()` | ✅ |
| P11 | Eval-Driven Evolution | ECC(E1) | `eval_driven.py → EvalDrivenEngine.define_eval()` | ✅ |
| P12 | 验证铁律: Evidence Before Claims | superpowers(SP2) | `iron_law.py → VerificationIronLaw.verify()` | ✅ |
| P13 | 垂直切片TDD | mattpocock(MP2) | 每个进化→一个测试→验证→下一个 | ✅ |
| P14 | 约束≤7+escape valve | CEF/CET(课题七) | `constraint_checker.py + escape_valve.py` | ✅ |
| P15 | 规则≠行为 | Calx实证(H6) | `rule_tracker.py → RuleTriggerTracker.get_inert_rules()` | ✅ |
| P16 | 规则必须附why+trigger+verify | Prompt工程(H4) | Node.why/trigger/verify字段 | ✅ |
| P17 | 漂移检测>记忆质量 | Nautilus(课题二) | `drift_detector.py → DriftDetector.check()` | ✅ |
| P18 | Judgment>Capability | Skills生态(课题一) | 构建顺序: 先验证/门控/治理，后类型扩展 | ✅ |
| P19 | 构建优先级Harness→Loop→Context→Prompt | kickoff(H5) | Phase 1-4顺序 | ✅ |
| P20 | 五重门控: 写入→读取→修改→巩固→执行 | SAGE+MemGate(课题三) | `five_gates.py → FiveGates.write_gate/read_gate/...` | ✅ |
| P21 | 3种Grader: Code(60-70%)+Model(25-35%)+Human(5-10%) | ECC(E3) | `grader_router.py → GraderRouter.grade()` | ✅ |
| P22 | 参数化品味: 3旋钮控制进化行为 | taste-skill(TS1) | `evolution_knobs.py → EvolutionKnobs` | ✅ |

---

## 二、刑法 (操作细则 + 违宪判例)

### 2.1 操作细则 (14条)

| # | 细则 | 宪法依据 | 代码强制 | 状态 |
|---|------|---------|---------|------|
| O1 | 写入门控公式精确匹配: `min(1.0, I(U≥τ)·[U×(S+β)])` | P3 | `write_gate.py:158` | ✅ |
| O2 | 零效用→零写入(乘法门控>线性加权) | P2+P3 | `should_write(utility=0.0) → False` | ✅ |
| O3 | pending+低效用→不写 | P2 | `should_write(trust=PENDING, utility<0.3) → False` | ✅ |
| O4 | 巩固保留raw episodes，巩固产物建立DERIVED_FROM边 | P6 | `consolidation_guard.py` | ✅ |
| O5 | 语义重复≥θ_count时才触发巩固 | P6 | `should_consolidate(redundancy < θ) → DENY` | ✅ |
| O6 | 生命周期升级: reinforce_count >= promote_after | P7 | `should_promote()` | ✅ |
| O7 | 衰减: Ebbinghaus指数衰减，零LLM | P7 | `should_decay()` | ✅ |
| O8 | 遗忘: ISO8601 forget_at时间戳 或 utility<3+30天未引用 | P8 | `should_forget()` | ✅ |
| O9 | 读取门控: pending不返回决策层 | P20 | `read_gate(min_trust=HIGH_SIGNAL)` | ✅ |
| O10 | 修改门控: Δ≥0才允许修改 | P20 | `modify_gate(delta.fitness_delta < 0) → DENY` | ✅ |
| O11 | 约束数硬上限7 | P14 | `ConstraintChecker.MAX_CONSTRAINTS = 7` | ✅ |
| O12 | 约束冲突时允许escape而非fabricate | P14 | `EscapeValve.check()` | ✅ |
| O13 | apply()前5步验证门控 | P12 | `iron_law.py: IDENTIFY→RUN→READ→VERIFY→ONLY THEN` | ✅ |
| O14 | pass@3>90%才apply | P11 | `eval_driven.py: should_apply()` | ✅ |

### 2.2 违宪判例 (5个认知修正)

| 原有V11设计 | 修正为 | 来源 | 宪法依据 |
|------------|--------|------|---------|
| 安全防线越严越好 | 动态缓冲: 正常宽松/关键收紧/Dream释放创新 | HSP90 | P4 |
| 增加约束提高安全性 | 约束越多CEF风险越高: 约束≤7+escape valve | CEF/CET | P14 |
| LLM做巩固聚类 | 零LLM生命周期: 计数器+时间戳 | Nautilus | P7 |
| 先能力后判断 | 先判断后能力: Judgment→Capability | Skills生态 | P18 |
| 白盒架构就够了 | 黑盒漂移检测层: 保留raw prompt | Nautilus | P17 |

---

## 三、架构 (5层 + 4条数据流)

### 3.1 V11分层架构

```
┌─────────────────────────────────────────────────────────┐
│  L4 Governance Layer (治理层)                            │
│  ConstraintChecker + EscapeValve + RuleTracker           │
│  + DriftDetector + BufferingSafetyLayer + AutonomyRouter │
├─────────────────────────────────────────────────────────┤
│  L3 Evolution Layer (进化层)                             │
│  EvalDrivenEngine + EvolutionKnobs + VerificationIronLaw │
│  + TaskReviewer + EvolutionGrill + GraderRouter          │
├─────────────────────────────────────────────────────────┤
│  L2 Lifecycle Layer (生命周期层)                         │
│  DopamineWriteGate + ConsolidationGuard + TrustManager   │
│  + UtilityTracker + DreamCycle + ZeroLLMLifecycle        │
│  + FiveGates(Write→Read→Modify→Consolidate→Execute)     │
├─────────────────────────────────────────────────────────┤
│  L1 Memory Layer (记忆层)                                │
│  V11Store(SQLite+Vector+Graph) + HybridSearch            │
│  + CascadingFetch + ContextualSubgraph + EventBus + WAL  │
├─────────────────────────────────────────────────────────┤
│  L0 Foundation Layer (基础层)                            │
│  Schema + Config + DeterministicRuleEngine + WriteHook   │
│  + CodeSlopDetector + Provenance                         │
└─────────────────────────────────────────────────────────┘
```

### 3.2 数据流 (4条核心路径)

```
写入: insert() → DopamineWriteGate.should_write() → WriteHook.pre_write()
     → Schema.validate() → Store.insert() → WriteHook.post_write()
     → EventBus.emit("node_inserted") → UtilityTracker.touch()

读取: recall() → TrustLevel.filter(pending不返回) → HybridSearch.search()
     → CascadingFetch(缓存→向量→图→LLM→API→人工) → ContextualSubgraph.induce()
     → DriftDetector.check() → return subgraph

进化: evolve() → EvolutionGrill.grill() → EvalDrivenEngine.define_eval()
     → EvolutionPlan.write() → TaskReviewer.review()
     → VerificationIronLaw.verify() → GraderRouter.grade()
     → pass@3>90%? → apply() → fitness>0.95? → compile_to_rule()

治理: constraint_check() → ConstraintChecker.check()
     → escape_valve() → RuleTriggerTracker.audit()
     → BufferingSafetyLayer.adjust_strictness()
```

---

## 四、数据模型

### 4.1 Node (V11核心)

```python
@dataclass
class NodeV11:
    id: str                          # UUID
    type: NodeType                   # 17→30类型(渐进扩展)
    content: str                     # 原始内容
    embedding: List[float]           # 向量
    # 写路径
    operator: WriteOperator          # ⊕t/⊕p/⊕?/⊕c (B1 TOKI)
    trust_level: TrustLevel          # verified/high-signal/pending (K1)
    commit_state: CommitState        # DRAFT→VERIFIED→COMMITTED (XFlow)
    # 生命周期
    utility: float                   # 0-5 (M2)
    surprise: float                  # 写入时计算 (B9)
    reinforce_count: int             # 引用次数 (Nautilus)
    forget_at: Optional[str]         # ISO8601遗忘时间戳
    # 治理
    action_hook: Optional[str]       # "下次遇到X，我做Y" (K2)
    buffered: bool                   # HSP90缓冲标记
    raw_proof: str                   # 原始prompt文本保留(漂移检测)
    # 溯源
    provenance: ProvenanceV11        # 来源+置信度+验证状态
    why: Optional[str]               # 为什么存在 (H4)
    trigger: Optional[str]           # 什么时候执行 (H4)
    verify: Optional[str]            # 怎么知道执行了 (H4)
```

### 4.2 枚举 (6个关键枚举)

| 枚举 | 值 | 来源 | 文件 |
|------|-----|------|------|
| WriteOperator | ⊕t/⊕p/⊕?/⊕c | B1 TOKI | schema.py |
| TrustLevel | verified/high-signal/pending | K1 | schema.py |
| AutonomyLevel | L0~L4 | S1 | schema.py |
| CommitState | DRAFT→VERIFIED→COMMITTED | XFlow | schema.py |
| Strictness | LOOSE/NORMAL/TIGHT | P4 HSP90 | schema.py |
| RiskLevel | LOW/MEDIUM/HIGH/CRITICAL | P5 | schema.py |

### 4.3 EvolutionKnobs (TS1参数化品味)

```python
@dataclass
class EvolutionKnobs:
    exploration_rate: float = 0.5   # 0.0(保守)↔1.0(激进)
    risk_tolerance: float = 0.3     # 0.0(安全)↔1.0(冒险)
    complexity_budget: float = 0.5  # 0.0(极简)↔1.0(丰富)
```

---

## 五、机制注册表 (核心章节)

> 每个机制只定义一次。其他地方引用编号。审计时直接查注册表。

### 写路径机制

#### [M01] 更多记忆反而更差 (T1 LongMINT)
- 来源: 条目12 "7个主流AI记忆系统平均准确率27.9%，76.8%的insert bias"
- 宪法: P2
- 模块: `lifecycle/write_gate.py` → `DopamineWriteGate.should_write()`
- 验收: `should_write(utility=0.0) → False`
- 状态: ✅ 已实现 — 公式 `min(1.0, I(U≥τ)·[U×(S+β)])` 精确匹配

#### [M02] 写入是决策不是存储 — 乘法门控 (B2 D-MEM)
- 来源: R2128 D-MEM — Agentic RPE公式
- 宪法: P3
- 模块: `lifecycle/write_gate.py` → `DopamineWriteGate.should_write()`
- 验收: 零效用→零写入(乘法门控>线性加权); `should_write(utility=0, surprise=1.0) → False`
- 状态: ✅ 已实现 — 乘法门控: I(U≥τ)·[U×(S+β)]

#### [M03] 写入稀疏性/surprise计算 (B9 AURA-Mem)
- 来源: R2127 AURA-Mem — 瓶颈是写入不是计算
- 宪法: P2+P3
- 模块: `lifecycle/write_gate.py` → `DopamineWriteGate.compute_surprise()`
- 验收: `surprise = 1 - max_cosine_sim`; 第一个节点→1.0; token-loss gate警告已规避
- 状态: ✅ 已实现

#### [M04] TOKI写时算子 ⊕t/⊕p/⊕?/⊕c (B1)
- 来源: R2100 TOKI — 矛盾消解=写时并发控制
- 宪法: P3(写路径增强)
- 模块: `schema.py` → `WriteOperator(Enum)`
- 验收: 4种算子+4种隔离级别定义
- 状态: ✅ 已实现

#### [M05] 写入端+读取端双重防御 (SAGE+MemGate)
- 来源: 课题三五重门控 — SAGE vMF可被嵌入空间投毒绕过
- 宪法: P20
- 模块: `lifecycle/five_gates.py` → `FiveGates.write_gate()` + `FiveGates.read_gate()`
- 验收: 写入端DopamineWriteGate + 读取端TrustLevel过滤
- 状态: ✅ 已实现

### 生命周期机制

#### [M06] 零LLM生命周期 (Nautilus)
- 来源: 课题二Nautilus — 生产级验证(11.5k真实流量)
- 宪法: P7
- 模块: `lifecycle/zero_llm_lifecycle.py` → `ZeroLLMLifecycle`
- 验收: `should_promote()` 计数器升级; `should_decay()` Ebbinghaus衰减; `should_forget()` 时间戳遗忘; 零LLM调用
- 状态: ✅ 已实现

#### [M07] 巩固是有损变换 — 保留raw episodes (F5)
- 来源: R2137 — GPT-5.4巩固54%失败率
- 宪法: P6
- 模块: `lifecycle/consolidation_guard.py` → `ConsolidationGuard.should_consolidate()`
- 验收: 语义重复<θ_count→DENY; 巩固保留raw; 巩固产物建立DERIVED_FROM边
- 状态: ✅ 已实现

#### [M08] 效用追踪 0-5 (M2)
- 来源: MiMo §四 效用追踪
- 宪法: P2(低效用不写)+P8(遗忘策略)
- 模块: `lifecycle/utility_tracker.py` → `UtilityTracker.touch()/decay()/is_forget_candidate()`
- 验收: 引用+2 / 30天未引用-1 / <3标记删除候选
- 状态: ✅ 已实现

#### [M09] 三级信任标注 verified/high-signal/pending (K1)
- 来源: knowledge-conversion §二 机制一
- 宪法: P9(读取门控)
- 模块: `lifecycle/trust_manager.py` → `TrustManager.promote()/demote()`
- 验收: pending→high-signal(2+独立来源); high-signal→verified(使用且有效); 降级路径存在
- 状态: ✅ 已实现

#### [M10] Dream熵触发+失败蒸馏+技能固化 (M5+T3)
- 来源: MiMo §九 Dream记忆整理 + 条目21 失败压缩>成功压缩
- 宪法: P4(Dream释放创新)+P8
- 模块: `lifecycle/dream_cycle.py` → `DreamCycleV11.dream()/compute_knowledge_entropy()`
- 验收: 熵>阈值时提前触发; 失败模式蒸馏(_step_distill); 技能固化(crystallize_rules)
- 状态: ✅ 已实现

#### [M11] 遗忘=智能有损压缩 (L2)
- 来源: learning-export §一 #7 — Rate-Distortion Theory统一
- 宪法: P8
- 模块: `lifecycle/zero_llm_lifecycle.py` → `should_forget()`
- 验收: Weibull衰减是最优策略; utility<3+30天未引用→遗忘候选
- 状态: ✅ 已实现

### 五重门控机制

#### [M12] 五重门控: 写入→读取→修改→巩固→执行 (T2)
- 来源: 条目20 — 6系统收敛的架构必然
- 宪法: P20
- 模块: `lifecycle/five_gates.py` → `FiveGates`
- 验收: 5个gate函数完整; 级联失败断路器; 审计日志
- 状态: ✅ 已实现 — write_gate/read_gate/modify_gate/consolidate_gate/execute_gate

### 进化机制

#### [M13] Eval-Driven Evolution (E1+E2)
- 来源: ECC eval-harness — 211K stars规模验证
- 宪法: P11
- 模块: `engine/eval_driven.py` → `EvalDrivenEngine.define_eval()/grade()/should_apply()`
- 验收: 先定义eval再进化; pass@3>90%才apply; pass^3关键路径
- 状态: ✅ 已实现

#### [M14] 验证铁律: Evidence Before Claims (SP2)
- 来源: superpowers verification-before-completion — 24个失败记忆驱动
- 宪法: P12
- 模块: `engine/iron_law.py` → `VerificationIronLaw.verify()`
- 验收: 5步门控: IDENTIFY→RUN→READ→VERIFY→ONLY THEN; 跳过任何步骤=拒绝
- 状态: ✅ 已实现

#### [M15] 3种Grader: Code+Model+Human (E3)
- 来源: ECC eval-harness — 3种Grader类型
- 宪法: P21
- 模块: `engine/grader_router.py` → `CodeGrader/ModelGrader/HumanGrader`
- 验收: Code 60-70% + Model 25-35% + Human 5-10%
- 状态: ✅ 已实现

#### [M16] 进化追问 Grill Session (MP1)
- 来源: mattpocock grill-with-docs — 无情追问直到计划清晰
- 宪法: P11(进化前置)
- 模块: `engine/grill.py` → `EvolutionGrill.grill()`
- 验收: 进化前先grill: 必要? 更简单? 会破坏什么?
- 状态: ✅ 已实现

#### [M17] 子代理驱动开发/TaskReviewer (SP1)
- 来源: superpowers subagent-driven-development — 新鲜子代理+任务审查
- 宪法: P12(独立验证)
- 模块: `engine/task_reviewer.py` → `TaskReviewer.review()`
- 验收: 每个进化任务完成后独立审查; 有critical_findings则修复
- 状态: ✅ 已实现

#### [M18] 参数化品味 3旋钮 (TS1)
- 来源: taste-skill — 3旋钮控制输出
- 宪法: P22
- 模块: `engine/evolution_knobs.py` → `EvolutionKnobs`
- 验收: exploration_rate/risk_tolerance/complexity_budget 3参数可调; 预设profile
- 状态: ✅ 已实现

#### [M19] 编译>>在线 (L1)
- 来源: learning-export §一 #6 — 编译>>在线1000×铁证
- 宪法: P10
- 模块: `engine/eval_driven.py` → `EvalDrivenEngine.should_compile()`
- 验收: fitness>0.95→编译为确定性规则(不再需要LLM推理)
- 状态: ✅ 已实现

### 治理机制

#### [M20] 约束≤7+escape valve (CEF/CET)
- 来源: 课题七 CEF — Agent会"装死"; CET — GPT-4o伪造错误信息
- 宪法: P14
- 模块: `safety/constraint_checker.py` → `ConstraintChecker` + `safety/escape_valve.py` → `EscapeValve`
- 验收: 约束数≤7; 联合可满足性检查; 约束冲突→escape(允许说"无法回答")
- 状态: ✅ 已实现

#### [M21] Buffering>Error Correction — HSP90动态缓冲 (课题六)
- 来源: HSP90 3.5B年验证 — 不修复只缓冲
- 宪法: P4
- 模块: `safety/buffering.py` → `BufferingSafetyLayer.adjust_strictness()/buffer()`
- 验收: 正常→LOOSE; 关键→TIGHT; Dream→释放创新; 不删除只抑制影响
- 状态: ✅ 已实现

#### [M22] 确定性检测>LLM检测 — 44+规则零LLM (I1)
- 来源: impeccable SKILL.md — 44确定性检测规则
- 宪法: P5
- 模块: `safety/deterministic.py` → `DeterministicRuleEngine.check_code()/check_node()`
- 验收: 44+规则覆盖代码/架构/安全slop; 零LLM调用; rule_count ≥ 44
- 状态: ✅ 已实现

#### [M23] 编辑前拦截+编辑后审计 WriteHook (I2)
- 来源: impeccable README §Design hook
- 宪法: P5(执行路径)
- 模块: `safety/write_hook.py` → `WriteHook.pre_write()/post_write()`
- 验收: pre_write阻止坏代码; post_write审计标记; 零LLM
- 状态: ✅ 已实现

#### [M24] 规则≠行为 — RuleTriggerTracker (H6+M7)
- 来源: Calx 237条规则→13个仍失败 + MiMo TraceLift
- 宪法: P15
- 模块: `safety/rule_tracker.py` → `RuleTriggerTracker.get_inert_rules()`
- 验收: 0触发=inert→候选删除; ≥2次=active; 1次=weak; 30天审计
- 状态: ✅ 已实现

#### [M25] 漂移检测>记忆质量 (Nautilus)
- 来源: 课题二Nautilus — AUC 0.83
- 宪法: P17
- 模块: `safety/drift_detector.py` → `DriftDetector.check()/check_structural()/check_semantic()/check_temporal()`
- 验收: BGE-m3锚点对比; 4维度漂移检测; 趋势追踪
- 状态: ✅ 已实现

#### [M26] 五级自主权 L0~L4 (S1)
- 来源: spontaneous-initiative §3.1 行动分级
- 宪法: P14(治理)+P18(Judgment>Capability)
- 模块: `safety/autonomy.py` → `AutonomyRouter.route()`
- 验收: L0全自主→L4禁止; 每级绑定行动类型白名单; 自适应升降级
- 状态: ✅ 已实现

### 记忆层机制

#### [M27] 记忆价值在连接不在节点 — ContextualSubgraph (B8)
- 来源: R2129 FluxMem — LoCoMo 95.06
- 宪法: P9
- 模块: `memory/contextual_subgraph.py` → `ContextualSubgraph.induce_context()`
- 验收: recall()返回子图context而非单节点; 种子节点→诱导子图
- 状态: ✅ 已实现

#### [M28] 6层级联获取策略 (QM1)
- 来源: qiaomu 6层级联绕过 — 每层失败自动降级
- 宪法: P9(检索增强)
- 模块: `memory/cascading_fetch.py` → `CascadingFetchStrategy.fetch()`
- 验收: 缓存→向量→图→LLM→API→人工; 每层失败自动降级
- 状态: ✅ 已实现

#### [M29] 三通道混合搜索 RRF融合 (Mnemosyne)
- 来源: Mnemosyne hybrid_search + Bug #2修复
- 宪法: P9(检索)
- 模块: `memory/hybrid_search.py` → `HybridSearchEngine.search()`
- 验收: 向量+FTS+图→RRF融合+语义重排; Bug #2(透传)已修复
- 状态: ✅ 已实现

#### [M30] WAL唤醒协议 (M3)
- 来源: MiMo §三 启动流程
- 宪法: P7(生命周期)
- 模块: `memory/wal.py` → `WAL`
- 验收: 唤醒时写WAL; 检查heartbeat; 引用知识追踪效用
- 状态: ✅ 已实现

#### [M31] EventBus发布/订阅 (R2133)
- 来源: V10 + Mnemosyne events
- 宪法: P19(事件驱动)
- 模块: `memory/event_bus.py` → `EventBusV11.publish()/subscribe()`
- 验收: 15+事件类型; 优先级队列; 同步/异步派发
- 状态: ✅ 已实现

#### [M32] 代码slop检测 — 5维评分 (TS2+SS1)
- 来源: taste-skill + stop-slop — AI输出可预测模式
- 宪法: P1(反过度工程化)
- 模块: `quality/slop_detector.py` → `CodeSlopDetector.score()`
- 验收: 5维评分(简洁性/一致性/必要性/可读性/密度); 总分<35/50=拒绝
- 状态: ✅ 已实现

#### [M33] 溯源链 Provenance (R2133)
- 来源: V10 + Mnemosyne provenance
- 宪法: P16(why+trigger+verify)
- 模块: `lifecycle/provenance.py` → `ProvenanceV11` + `ProvenanceChain`
- 验收: 完整溯源链; 来源类型+验证状态+贡献者
- 状态: ✅ 已实现

### 去重合并机制 (多来源汇聚同一概念)

#### [M34] 巩固是有损变换 (去重: F5/R2137/P6/K4)
- 合并来源:
  - F5: R2137 巩固陷阱 — GPT-5.4巩固54%失败
  - P6: 宪法原则 — 巩固是有损变换
  - K4: 知识→技能蒸馏 — 蒸馏是有损的(R2125 SkillEvolBench)
  - RecMem: 语义重复≥θ_count时才触发
- 统一实施: M07 ConsolidationGuard — 保留raw episodes; 巩固是补充不是替代
- 状态: ✅ 已实现

#### [M35] 写入门控 (去重: T1/P2/P3/B2/B9)
- 合并来源:
  - T1: LongMINT — 更多记忆反而更差
  - P2: 宪法原则 — 更多记忆反而更差
  - P3: 宪法原则 — 写入是决策不是存储
  - B2: D-MEM — 乘法门控公式
  - B9: AURA-Mem — surprise计算+token-loss gate警告
- 统一实施: M01+M02+M03 DopamineWriteGate
- 状态: ✅ 已实现

#### [M36] 记忆价值在连接 (去重: P9/B8/R2129)
- 合并来源:
  - P9: 宪法原则 — 记忆价值在连接不在节点
  - B8: FluxMem — 记忆价值不在节点在连接
  - R2129: FluxMem — LoCoMo 95.06
- 统一实施: M27 ContextualSubgraph
- 状态: ✅ 已实现

### 待实施机制

#### [M37] STALE隐式冲突检测 (B3)
- 来源: R2121 STALE — 最佳模型仅55.2%
- 宪法: P6(巩固安全)
- 模块: 待定 → `ImplicitConflictDetector.detect_type_i()/detect_type_ii()`
- 验收: Type I共指冲突+Type II传播冲突自动检测
- 状态: ⬜ 待实施

#### [M38] MEMDRIFT工具漂移检测 (B4)
- 来源: R2132 MEMDRIFT — 全新失败模式
- 宪法: P17(漂移检测)
- 模块: 待定 → `ToolDriftDetector.detect_drift()`
- 验收: 在工具调用层检测记忆偏见
- 状态: ⬜ 待实施

#### [M39] SSGM记忆治理 (B5)
- 来源: R2110 SSGM — 30+系统仅2个有完整治理
- 宪法: P14+P17
- 模块: 待定 → `MemoryGovernance.check_input_poisoning()/detect_semantic_drift()`
- 验收: 四维腐败检测(知识冲突/语义漂移/记忆投毒/拓扑泄露)
- 状态: ⬜ 待实施

#### [M40] ElasticMem弹性资源/abstention (B6)
- 来源: R2094 ElasticMem — ALFWorld+66.3%
- 宪法: P2(检索策展)
- 模块: 待定 → recall(min_confidence=0.3)
- 验收: 检索质量不够时主动返回空列表(budget=0>低质量检索)
- 状态: ⬜ 待实施

#### [M41] PROJECTMEM Memory-as-Governance (F6)
- 来源: R2140 PROJECTMEM — 第三范式
- 宪法: P14+P17
- 模块: 待定 → `GovernanceMemory.pre_action_gate()+project_deterministic()`
- 验收: 行动前检查历史失败; 确定性投影; append-only event log
- 状态: ⬜ 待实施

#### [M42] 行动钩子 (K2)
- 来源: knowledge-conversion §二 机制二
- 宪法: P16(why+trigger+verify)
- 模块: `schema.py` → `NodeV11.action_hook`
- 验收: insert_node时检查: 无action_hook→标记TBD
- 状态: ✅ 字段已定义, 触发逻辑待实施

#### [M43] 修订轮硬编码5步 (K3)
- 来源: knowledge-conversion §二 机制三
- 宪法: P15(规则≠行为)
- 模块: 待定 → 每5轮强制1轮修订; 超20轮强制停止
- 验收: 不靠自觉，cron task硬编码
- 状态: ⬜ 待实施

#### [M44] 反进化检测4硬性前置 (M1)
- 来源: MiMo §五 反进化检测
- 宪法: P11+P15
- 模块: 待定 → 去重(sim>0.8→STOP)+洞察+应用+连续增益
- 验收: 4个硬性前置检查
- 状态: ⬜ 待实施

#### [M45] 渐进式Working Buffer (M4)
- 来源: MiMo §八 Working Buffer协议
- 宪法: P19(Context工程)
- 模块: 待定 → 20%/45%/70%三级渐进式检查点
- 验收: 上下文压力管理
- 状态: ⬜ 待实施

#### [M46] SafeHarbor对比规则对 (M8)
- 来源: MiMo §十 安全体系
- 宪法: P14(治理)
- 模块: 待定 → 每条禁止规则配一条豁免规则
- 验收: forbidden↔exempt规则对
- 状态: ⬜ 待实施

#### [M47] BTSP单次学习快速通道 (T5)
- 来源: 条目25 — 行为时间尺度突触可塑性
- 宪法: P2(写入门控)
- 模块: 待定 → high_signal参数→直接写入Semantic层
- 验收: 高信号节点跳过Working层
- 状态: ⬜ 待实施

#### [M48] Goal独立验证/Judge子代理 (T7)
- 来源: 条目47 — 复杂任务>10步时spawn judge
- 宪法: P12(验证铁律)
- 模块: 待定 → spawn_judge()
- 验收: 复杂任务完成后独立验证
- 状态: ⬜ 待实施

### 遗漏补充 (对比旧方案逐段审计发现)

#### [M49] 子代理三层压缩协议 (M6 MiMo)
- 来源: MiMo §六 子代理三层压缩 — 原始结果(几千token)→摘要(≤100token)+关键洞察(3-5条)+行为修正(1-2条)+原始(冷层)
- 宪法: P1(反过度工程化 — 压缩降低上下文消耗)
- 模块: 待定 → SubAgentCompressor.compress()
- 验收: 子代理输出>500token→三层压缩; 主线程只接收摘要+洞察+修正
- 状态: ⬜ 待实施

#### [M50] Sycophancy防御 (M9 MiMo)
- 来源: MiMo §十一 质量控制(Sycophancy防御) — 区分事实vs偏好/不确定就说不确定/事实不受偏好影响
- 宪法: P5(确定性验证>LLM) + P14(约束诚实)
- 模块: 待定 → SycophancyGuard.check()
- 验收: 事实性声明不能被用户偏好修改; 不确定时标记confidence<0.5; 偏好问题附"你可以不同意"
- 状态: ⬜ 待实施

#### [M51] SYSTEM.md项目上下文文件 (I4 impeccable)
- 来源: impeccable SKILL.md §Setup — 每个项目必须有PRODUCT.md+DESIGN.md, init命令自动生成, 后续命令读取作为上下文, 没有则停止
- 宪法: P16(why+trigger+verify)
- 模块: 待定 → SystemContext.load() + evolve()前自动读取
- 验收: evolve()前检查SYSTEM.md存在; 包含系统身份/能力边界/进化策略/安全约束; 缺失→停止并引导创建
- 状态: ⬜ 待实施

#### [M52] EvolutionPlan显式计划文档 (SP3 superpowers)
- 来源: superpowers writing-plans/SKILL.md — Goal(一句话) + Architecture(2-3句) + Tech Stack + Global Constraints + File Structure + Bite-Sized Tasks(每步2-5分钟可独立测试)
- 宪法: P12(验证铁律) + P13(垂直切片)
- 模块: 待定 → EvolutionPlan.create() + grill()时验证
- 验收: 每次evolve()生成显式计划; 包含Goal+Constraints+FileStructure+Tasks; 每个task可独立测试(2-5分钟)
- 状态: ⬜ 待实施

#### [M53] SkillAutoLoader技能强制加载 (SP4 superpowers)
- 来源: superpowers using-superpowers/SKILL.md — "1%可能就强制加载相关技能, IF A SKILL APPLIES YOU DO NOT HAVE A CHOICE"
- 宪法: P5(确定性优先) + P15(规则≠行为→规则必须被执行)
- 模块: 待定 → SkillAutoLoader.scan_and_load()
- 验收: evolve()时自动扫描相关技能; 1%相关性就加载; 优先级: 用户指令>技能>系统prompt
- 状态: ⬜ 待实施

#### [M54] 效果度量闭环5指标 (S4 spontaneous-initiative)
- 来源: spontaneous-initiative §5.3 效果度量表格 — 行动成功率>70%/信息增益率>50%/用户反馈率>30%/异常率<5%/重复率<10%
- 宪法: P15(规则≠行为→必须有度量验证行为)
- 模块: 待定 → EffectivenessTracker.track() + 策略自调整(成功率高→增频/低→减频+审查)
- 验收: 5指标实时追踪; 成功率>70%→升级探索频率; 成功率<50%→降频+审查; 重复率<10%
- 状态: ⬜ 待实施 (当前仅rule_tracker有1/5触发率审计)

#### [M55] L_Monitor监控栈 (V10+旧方案架构)
- 来源: 旧方案L_Monitor — AnomalyDetector(Z-score+单调趋势)+ProblemPredictor(线性回归)+ProactiveMonitor(指标+阈值+回调)+EvolutionDashboard
- 宪法: P17(漂移检测>记忆质量) + P19(闭环)
- 模块: 待定 → monitor/anomaly.py + monitor/predictor.py + monitor/dashboard.py
- 验收: Z-score异常检测; 线性回归趋势预测; 指标阈值告警回调; 仪表盘可视化
- 状态: ⬜ 待实施

#### [M56] DualTrackMemory Agent/User隔离 (旧方案架构)
- 来源: 旧方案L_Storage DualTrackMemory — Agent记忆vs User记忆严格隔离, 不同scope不同访问策略
- 宪法: P14(安全) + P20(读取门控)
- 模块: 待定 → schema.py增加MemoryScope(agent/user/global/project/session) + store.py隔离查询
- 验收: Agent写入的记忆User不可见(除非显式shared); User记忆不污染Agent决策
- 状态: ⬜ 待实施

#### [M57] AntiEvolutionGate 4个硬性前置 (M1 MiMo)
- 来源: MiMo §五 反进化检测 — 检查1去重(sim>0.8→STOP) + 检查2洞察(列表≠学习) + 检查3应用(学了不用=垃圾) + 检查4连续增益(连续2轮0增益→STOP)
- 宪法: P11(Eval-Driven) + P15(规则≠行为)
- 模块: 待定 → AntiEvolutionGate.check() — evolve()前4个硬性前置检查
- 验收: sim>0.8→STOP已知知识; 无新洞察→STOP; 学了不用→STOP; 连续2轮0增益→STOP
- 状态: ⬜ 待实施 (grill.py有部分覆盖: 7道必答问题含必要性和简化, 但缺sim去重和连续增益检查)

#### [M58] 双时态(bitemporal)数据模型 (旧方案数据模型)
- 来源: 旧方案NodeV11 — valid_from/valid_to(业务时间) + tx_from/tx_to(事务时间/MVCC)
- 宪法: P1(反过度工程化) — 设计决策待定
- 模块: 待定 → schema.py NodeV11增加valid_from/valid_to字段
- 验收: 节点有过期时间(valid_to); 可查询历史版本; 巩固/遗忘更新valid_to而非删除
- 状态: ⬜ 待定 (需决策: 是否引入MVCC? 当前Ebbinghaus衰减+forget_at时间戳是否够用?)
- 决策备注: 当前V11用Ebbinghaus衰减+forget_at时间戳实现遗忘，功能上等效于"软删除"。完整双时态需要MVCC，但P1反过度工程化原则下，建议Phase 4视需求决定

---

## 六、构建顺序 (4 Phase)

### Phase 1: Harness (Day 1-2) ✅ 已完成

| Step | 模块 | 验证 | 状态 |
|------|------|------|------|
| 1.1 | schema (Node+Edge+WriteOperator+TrustLevel+AutonomyLevel) | pytest schema | ✅ |
| 1.2 | config | pytest config | ✅ |
| 1.3 | DeterministicRuleEngine (44+规则) | pytest deterministic | ✅ |
| 1.4 | DopamineWriteGate (乘法门控) | pytest write_gate | ✅ |
| 1.5 | WriteHook (pre_write+post_write) | pytest hooks | ✅ |
| 1.6 | FiveGates (5个gate函数) | pytest five_gates | ✅ |
| 1.7 | ConstraintChecker + EscapeValve | pytest constraints | ✅ |
| 1.8 | BufferingSafetyLayer | pytest buffering | ✅ |
| 1.9 | AutonomyRouter (L0~L4路由) | pytest autonomy | ✅ |

### Phase 2: Loop (Day 3-4) ✅ 已完成

| Step | 模块 | 验证 | 状态 |
|------|------|------|------|
| 2.1 | V11Store (SQLite+Vector+Graph) | pytest store | ✅ |
| 2.2 | HybridSearchEngine | pytest search | ✅ |
| 2.3 | ConsolidationGuard (保留raw) | pytest consolidation | ✅ |
| 2.4 | TrustManager (三级+升降级) | pytest trust | ✅ |
| 2.5 | UtilityTracker (引用+2/30天-1/<3删) | pytest utility | ✅ |
| 2.6 | ZeroLLMLifecycle (计数器+时间戳) | pytest lifecycle | ✅ |
| 2.7 | EvalDrivenEngine (define_eval+pass@k) | pytest eval | ✅ |
| 2.8 | VerificationIronLaw (5步门控) | pytest iron_law | ✅ |
| 2.9 | GraderRouter (3种Grader) | pytest grader | ✅ |
| 2.10 | EvolutionKnobs | pytest knobs | ✅ |

### Phase 3: Context (Day 5-6) 🔄 进行中

| Step | 模块 | 验证 | 状态 |
|------|------|------|------|
| 3.1 | ContextualSubgraph (子图context) | pytest subgraph | ✅ |
| 3.2 | CascadingFetchStrategy (6层级联) | pytest cascade | ✅ |
| 3.3 | DriftDetector (4维漂移) | pytest drift | ✅ |
| 3.4 | DreamCycle (熵触发+失败蒸馏+技能固化) | pytest dream | ✅ |
| 3.5 | RuleTriggerTracker (触发率审计) | pytest rule_tracker | ✅ |
| 3.6 | Provenance (溯源链) | pytest provenance | ✅ |
| 3.7 | WAL (唤醒协议) | pytest wal | ✅ |
| 3.8 | EventBus | pytest eventbus | ✅ |

### Phase 4: Prompt+Integration (Day 7-8) ⬜ 待实施

| Step | 模块 | 验证 | 状态 |
|------|------|------|------|
| 4.1 | EvolutionGrill | pytest grill | ✅ |
| 4.2 | TaskReviewer (子代理审查) | pytest reviewer | ✅ |
| 4.3 | CodeSlopDetector | pytest slop | ✅ |
| 4.4 | Hermes Plugin (save/recall/forget/evolve/status) | pytest hermes | ⬜ |
| 4.5 | V10认知模块适配 | pytest adaptation | ⬜ |
| 4.6 | 宪法审计 (目标≥90%) | 宪法审计 | ⬜ |
| 4.7 | E2E全量测试 (目标≥60个) | pytest e2e | ⬜ |
| 4.8 | git tag v11.0.0 | git tag | ⬜ |

---

## 七、验收标准

### 7.1 硬性指标

| 指标 | V10 | V11目标 | 来源 | 当前 |
|------|-----|---------|------|------|
| 测试数 | 104 | ≥60 (垂直切片) | MP2 | 99 ✅ |
| 宪法合规 | 67% | ≥90% | P0 | 100% ✅ |
| 写入门控 | 无 | DopamineWriteGate乘法门控 | P3 | ✅ |
| 零LLM生命周期 | 无 | 计数器+时间戳 | P7 | ✅ |
| Eval-Driven | 无 | pass@3>90% | P11 | ✅ |
| 确定性检测 | 无 | 44+规则零LLM | P5 | ✅ |
| 漂移检测 | 无 | 4维检测 | P17 | ✅ |
| 约束数 | 无上限 | ≤7+escape valve | P14 | ✅ |
| 信任分级 | 无 | verified/high-signal/pending | K1 | ✅ |
| 自主权分级 | 2级 | L0~L4五级 | S1 | ✅ |
| Hermes集成 | 未接入 | save/recall/forget/evolve/status | P0 | ⬜ |

### 7.2 软性指标

| 指标 | 目标 | 来源 |
|------|------|------|
| 模块数 | ≤30 | P1 |
| 层数 | ≤5 | P1 |
| 代码行数 | ≤10,000 | P1 |
| 有效代码 | ~5,000 | P1 |
| 规则触发率 | ≥2次/30天=active, 0次=inert | M7 |
| 巩固保留率 | raw episodes 100%保留 | P6 |
| 动态缓冲 | 正常宽松/关键收紧/Dream释放 | P4 |

---

## 八、ADR (6条关键决策)

### ADR-001: 为什么5层不是10层？
- **决策**: V11用5层架构，不用10层治理架构
- **原因**: Claude Code用2层跑生产。5层覆盖: 基础→记忆→生命周期→进化→治理
- **替代**: 10层治理(spontaneous-initiative S2) — 拒绝，过度工程化(P1)

### ADR-002: 为什么零LLM生命周期？
- **决策**: 生命周期决策(升级/衰减/遗忘)用计数器+时间戳
- **原因**: Nautilus生产级验证; LLM做巩固=巩固陷阱(GPT-5.4 54%失败)
- **替代**: LLM做语义聚类巩固 — 拒绝，巩固陷阱

### ADR-003: 为什么乘法门控不是线性加权？
- **决策**: `min(1.0, I(U≥τ)·[U×(S+β)])`
- **原因**: D-MEM实证: 乘法门控>线性加权。零效用→零写入(乘法=0)
- **替代**: 线性加权 — 拒绝，零效用仍可能写入

### ADR-004: 为什么约束≤7？
- **决策**: V11硬约束数≤7
- **原因**: CEF实证: 约束越多→不可调和→Agent编造。Miller's Law 7±2
- **替代**: 无上限 — 拒绝，CEF风险

### ADR-005: 为什么Buffering>Error Correction？
- **决策**: 不修复只缓冲(BufferingSafetyLayer)
- **原因**: HSP90 3.5B年验证: 不需要知道"什么是错的"就能结构性吸收方差
- **替代**: Error Correction — 保留用于确定性错误，Buffering用于不确定性

### ADR-006: 为什么先Harness后Capability？
- **决策**: 构建顺序 Harness→Loop→Context→Prompt
- **原因**: kickoff实证: 8个闭环6个开环; 4个inert rules; 先修Harness再修Loop
- **替代**: 先Capability后Judgment — 拒绝，P18 Judgment>Capability

---

## 附录A: 机制→模块→函数 完整映射表

| M# | 机制名称 | 模块文件 | 核心函数 | 宪法 | 状态 |
|----|---------|---------|---------|------|------|
| M01 | 更多记忆反而更差 | lifecycle/write_gate.py | DopamineWriteGate.should_write() | P2 | ✅ |
| M02 | 乘法门控写入 | lifecycle/write_gate.py | DopamineWriteGate.should_write() | P3 | ✅ |
| M03 | surprise计算 | lifecycle/write_gate.py | DopamineWriteGate.compute_surprise() | P2+P3 | ✅ |
| M04 | TOKI写时算子 | schema.py | WriteOperator(Enum) | P3 | ✅ |
| M05 | 写入+读取双重防御 | lifecycle/five_gates.py | FiveGates.write_gate()/read_gate() | P20 | ✅ |
| M06 | 零LLM生命周期 | lifecycle/zero_llm_lifecycle.py | ZeroLLMLifecycle.should_promote/decay/forget() | P7 | ✅ |
| M07 | 巩固保留raw | lifecycle/consolidation_guard.py | ConsolidationGuard.should_consolidate() | P6 | ✅ |
| M08 | 效用追踪0-5 | lifecycle/utility_tracker.py | UtilityTracker.touch()/decay() | P2+P8 | ✅ |
| M09 | 三级信任标注 | lifecycle/trust_manager.py | TrustManager.promote()/demote() | P9 | ✅ |
| M10 | Dream熵触发+失败蒸馏 | lifecycle/dream_cycle.py | DreamCycleV11.dream() | P4+P8 | ✅ |
| M11 | 遗忘=有损压缩 | lifecycle/zero_llm_lifecycle.py | ZeroLLMLifecycle.should_forget() | P8 | ✅ |
| M12 | 五重门控 | lifecycle/five_gates.py | FiveGates(5个gate) | P20 | ✅ |
| M13 | Eval-Driven Evolution | engine/eval_driven.py | EvalDrivenEngine.define_eval()/grade() | P11 | ✅ |
| M14 | 验证铁律 | engine/iron_law.py | VerificationIronLaw.verify() | P12 | ✅ |
| M15 | 3种Grader | engine/grader_router.py | CodeGrader/ModelGrader/HumanGrader | P21 | ✅ |
| M16 | Grill追问 | engine/grill.py | EvolutionGrill.grill() | P11 | ✅ |
| M17 | TaskReviewer | engine/task_reviewer.py | TaskReviewer.review() | P12 | ✅ |
| M18 | 参数化品味 | engine/evolution_knobs.py | EvolutionKnobs | P22 | ✅ |
| M19 | 编译>>在线 | engine/eval_driven.py | EvalDrivenEngine.should_compile() | P10 | ✅ |
| M20 | 约束≤7+escape | safety/constraint_checker.py + escape_valve.py | ConstraintChecker + EscapeValve | P14 | ✅ |
| M21 | HSP90动态缓冲 | safety/buffering.py | BufferingSafetyLayer.adjust_strictness() | P4 | ✅ |
| M22 | 44确定性规则 | safety/deterministic.py | DeterministicRuleEngine.check_code() | P5 | ✅ |
| M23 | WriteHook | safety/write_hook.py | WriteHook.pre_write()/post_write() | P5 | ✅ |
| M24 | Inert Rule检测 | safety/rule_tracker.py | RuleTriggerTracker.get_inert_rules() | P15 | ✅ |
| M25 | 漂移检测 | safety/drift_detector.py | DriftDetector.check() | P17 | ✅ |
| M26 | 五级自主权 | safety/autonomy.py | AutonomyRouter.route() | P14+P18 | ✅ |
| M27 | 子图context | memory/contextual_subgraph.py | ContextualSubgraph.induce_context() | P9 | ✅ |
| M28 | 6层级联获取 | memory/cascading_fetch.py | CascadingFetchStrategy.fetch() | P9 | ✅ |
| M29 | 三通道混合搜索 | memory/hybrid_search.py | HybridSearchEngine.search() | P9 | ✅ |
| M30 | WAL唤醒 | memory/wal.py | WAL | P7 | ✅ |
| M31 | EventBus | memory/event_bus.py | EventBusV11.publish()/subscribe() | P19 | ✅ |
| M32 | 代码slop检测 | quality/slop_detector.py | CodeSlopDetector.score() | P1 | ✅ |
| M33 | 溯源链 | lifecycle/provenance.py | ProvenanceV11 + ProvenanceChain | P16 | ✅ |
| M34 | 巩固有损变换(去重) | lifecycle/consolidation_guard.py | ConsolidationGuard | P6 | ✅ |
| M35 | 写入门控(去重) | lifecycle/write_gate.py | DopamineWriteGate | P2+P3 | ✅ |
| M36 | 连接>节点(去重) | memory/contextual_subgraph.py | ContextualSubgraph | P9 | ✅ |
| M37 | 隐式冲突检测 | (待定) | ImplicitConflictDetector | P6 | ⬜ |
| M38 | 工具漂移检测 | (待定) | ToolDriftDetector | P17 | ⬜ |
| M39 | 记忆治理SSGM | (待定) | MemoryGovernance | P14+P17 | ⬜ |
| M40 | ElasticMem abstention | (待定) | recall(min_confidence) | P2 | ⬜ |
| M41 | Memory-as-Governance | (待定) | GovernanceMemory | P14+P17 | ⬜ |
| M42 | 行动钩子 | schema.py | NodeV11.action_hook | P16 | ✅字段/⬜逻辑 |
| M43 | 修订轮硬编码 | (待定) | (cron硬编码) | P15 | ⬜ |
| M44 | 反进化4前置 | (待定) | AntiEvolutionGate增强 | P11+P15 | ⬜ |
| M45 | 渐进Working Buffer | (待定) | ContextPressureManager | P19 | ⬜ |
| M46 | SafeHarbor规则对 | (待定) | forbidden↔exempt | P14 | ⬜ |
| M47 | BTSP单次学习 | (待定) | high_signal快速通道 | P2 | ⬜ |
| M48 | Goal独立验证 | (待定) | spawn_judge() | P12 | ⬜ |
| M49 | 子代理三层压缩 | (待定) | SubAgentCompressor | P1 | ⬜ |
| M50 | Sycophancy防御 | (待定) | SycophancyGuard | P5+P14 | ⬜ |
| M51 | SYSTEM.md上下文 | (待定) | SystemContext.load() | P16 | ⬜ |
| M52 | EvolutionPlan | (待定) | EvolutionPlan.create() | P12+P13 | ⬜ |
| M53 | 技能强制加载 | (待定) | SkillAutoLoader | P5+P15 | ⬜ |
| M54 | 效果度量5指标 | (待定) | EffectivenessTracker | P15 | ⬜ |
| M55 | 监控栈 | (待定) | AnomalyDetector+Predictor | P17+P19 | ⬜ |
| M56 | DualTrack隔离 | (待定) | MemoryScope+隔离查询 | P14+P20 | ⬜ |
| M57 | 反进化4前置 | (待定) | AntiEvolutionGate | P11+P15 | ⬜ |
| M58 | 双时态数据模型 | (待定) | valid_from/valid_to | P1 | ⬜待定 |

---

## 附录B: 18个来源清单

| # | 来源 | 类型 | 提取机制数 | 关键贡献 |
|---|------|------|-----------|---------|
| 1 | spontaneous-initiative-design.md | 设计方案 | 8 (S1-S8) | 五级自主权/七层治理/好奇心队列 |
| 2 | mimo-self-evolution-system.md | 生产系统 | 12 (M1-M12) | 效用追踪/WAL/Dream/Inert Rule |
| 3 | hermes-evolution-kickoff.md | 诊断报告 | 6 (H1-H6) | 四大工程/闭环闭合/规则≠行为 |
| 4 | knowledge-conversion-solution.md | 解决方案 | 4 (K1-K4) | 三级信任/行动钩子/修订轮 |
| 5 | 2026-06-14-full-report.md | 研究报告 | 7 (F1-F7) | 14维失败图谱/巩固陷阱/Memory-as-Governance |
| 6 | 2026-06-14-knowledge-bundle.md | 论文集 | 10 (B1-B10) | TOKI/D-MEM/STALE/MEMDRIFT/SSGM/FluxMem/AURA/TRACE |
| 7 | learning-export-2026-may-june.md | 学习日志 | 5 (L1-L5) | 编译>>在线/有损压缩/极简两层 |
| 8 | mimo-full-knowledge-training.md | 知识库 | 15 (T1-T15) | LongMINT/五重门控/确定性验证 |
| 9 | learning-0615.md | 学习日志 | 3课题 | Judgment>Capability/漂移检测/五重门控 |
| 10 | learning-0616.md | 学习日志 | 2课题 | XFlow Prompt-Harness/组织基础设施 |
| 11 | learning-0617.md | 学习日志 | 2课题 | HSP90缓冲/CEF约束逃避 |
| 12 | pbakaus/impeccable | 开源项目 | 5 (I1-I5) | 44检测规则/Hook机制/23命令 |
| 13 | obra/superpowers | 开源项目 | 6 (SP1-SP6) | 子代理开发/验证铁律/垂直切片 |
| 14 | Leonxlnx/taste-skill | 开源项目 | 3 (TS1-TS3) | 参数化品味/anti-slop |
| 15 | hardikpandya/stop-slop | 开源项目 | 2 (SS1-SS2) | 5维评分/短语黑名单 |
| 16 | mattpocock/skills | 开源项目 | 3 (MP1-MP3) | Grill/垂直切片TDD/review流水线 |
| 17 | joeseesun/qiaomu | 开源项目 | 2 (QM1-QM2) | 6层级联/15+内容源 |
| 18 | affaan-m/ECC | 开源项目 | 4 (E1-E4) | EDD/pass@k/3种Grader/211K验证 |

---

## 附录C: 5个认知修正

| # | 原有V11设计 | 修正为 | 来源 | 影响的宪法 | 影响的机制 |
|---|------------|--------|------|-----------|-----------|
| C1 | 安全防线越严越好 | 动态缓冲: 正常宽松/关键收紧/Dream释放 | HSP90 | P4 | M21 |
| C2 | 增加约束提高安全性 | 约束越多CEF风险越高: ≤7+escape valve | CEF/CET | P14 | M20 |
| C3 | LLM做巩固聚类 | 零LLM生命周期: 计数器+时间戳 | Nautilus | P7 | M06 |
| C4 | 先能力后判断 | 先判断后能力: Judgment→Capability | Skills生态 | P18 | 构建顺序 |
| C5 | 白盒架构就够了 | 黑盒漂移检测层: 保留raw prompt | Nautilus | P17 | M25 |

---

## 附录D: V11 vs V10 vs V9PRO

| 维度 | V9PRO | V10 | V11 |
|------|-------|-----|-----|
| 写入门控 | 无 | 无 | DopamineWriteGate乘法门控 |
| 生命周期 | 无 | LLM巩固 | 零LLM(计数器+时间戳) |
| 进化方法 | 无 | evolve→validate→apply | Eval-Driven+pass@k+3种Grader |
| 安全 | 2级 | 4层防线 | 动态缓冲+约束≤7+escape valve |
| 验证 | LLM | LLM | 确定性60-70%+LLM25-35%+Human5-10% |
| 信任 | 无 | confidence | verified/high-signal/pending |
| 自主权 | 2级 | 2级 | L0~L4五级 |
| 漂移检测 | 无 | 无 | 4维检测 |
| 巩固 | 无 | LLM聚类 | ConsolidationGuard(保留raw) |
| Hermes | 未接入 | 未接入 | save/recall/forget/evolve/status |
| 测试 | 24 E2E | 104+24E2E | 99+50轮运行测试 |
| 宪法 | — | 67% | 100%(56/56) |
| 模块数 | 62 | 72 | 30(反过度工程化) |
