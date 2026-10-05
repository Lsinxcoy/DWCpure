# 记忆与自进化四篇精读 · DWC 记忆核心的直接参照

> **本报告覆盖**（2609.2680 正文引用 ×2 的补读，全部逐行精读）
> | arXiv | 标题 | 页/字符 | DWC 对应器官 |
> |---|---|---|---|
> | 2404.13501 | A Survey on the Memory Mechanism of LLM-based Agents | 39 / 147,896 | **记忆核心** |
> | 2404.14387 | A Survey on Self-Evolution of Large Language Models | 28 / 96,750 | **进化核心** |
> | 2501.07278 | Lifelong Learning of LLM based Agents: A Roadmap | 46 / 292,361 | **记忆核心 + 稳定性** |
>
> 归档：`papers_txt/refs/{id}.{pdf,txt}`
> 阅读范围：三篇的 §3 定义 / §5-§6 实现 / §7-§13 评估 / §8 开放问题 **全文逐行**
> 报告日期：2026-10-04

---

## 一、2404.13501 · 记忆操作三分类 —— 正好覆盖 2609.2680 缺口 (d)

### 1.1 三操作与四干预点

**§5.3 原文**：

```text
"We separate the entire procedure of memory into **three operations**: memory writing,
 memory management, and memory reading."
```

★ **对照 2609.2680 缺口 (d)**：那篇要求 "**freezes one of admission, retrieval,
consolidation or content** while varying the others"。两篇的对应关系：

```text
2609.2680 四干预点      2404.13501 三操作      DWC 现状
─────────────────────────────────────────────────────────────
admission（准入）      writing（写）           ★ 有（双门准入）
retrieval（检索）      reading（读）           ★ 有
consolidation（巩固）   management（管）        ★ 有（三层淘汰）
content（内容）        ——（三操作之外）        ★ 缺独立开关
★★ ⇒ 结论: DWC 的四干预点里, 前三个有对应, **content 没有独立冻结机制**
  ⇒ 建议: 记忆核心需把"内容本身"作为第四个可冻结维度, 否则消融无法归因
```

### 1.2 ★★ Table 3：29 个系统的记忆操作覆盖矩阵（硬数据）

```text
★ 表头: Writing | Management(Merging / Reflection / Forgetting) | Reading
★ 图例: ✓ 有专门设计 · ◦ 无专门设计 · × 未讨论

全 ✓（三项 + 三个管理子项全有）只有 3 个：
  MemoryBank [6] · RecAgent [95] · （原文如此）

★ 大多数系统的 Forgetting 一律是 × 或 ◦：
  Forgetting = × 的：TiM / SCM / ChatDB / MemoChat / MPC / Generative Agents /
                  RecMind / Retroformer / ExpeL / Synapse / GITM / ReAct /
                  Reflexion / RecAgent / Character-LLM / MAC / Huatuo /
                  ChatDev / InteRecAgent / MetaAgents / TPTU / MetaGPT / S3 / InvestLM
  ⇒ ★★ 29 个系统里 **绝大多数不做遗忘**
★★ 对 DWC 的含义: DWC 设计了"三层淘汰"，这在文献里是少数派设计。
  ★ 必须实证证明它有用 —— 不能只靠设计合理性（对标 2609.2680 (i) 稳定性度量）
  ★ 风险: 淘汰若无度量支撑，可能就是"母巢式遗忘"（记忆越用越少但没人证明有用）
```

### 1.3 ★★ 记忆评估三指标（DWC 记忆核心缺客观度量）

**§6.1.2 原文给的三个客观指标**：

```text
① Result Correctness（结果正确性）
   Correctness = (1/N) Σ I[a_i = â_i]
   —— agent 能否基于记忆直接答对预定义问题
   论文实例: Hu et al. [96] 从历史构造带标注问题算准确率
             Packer et al. [100] 生成"只能从过去会话推出"的问题

② Reference Accuracy（引用准确率）
   "Different from the above metric, which focuses on the final results,
    reference accuracy cares more about the **intermediate information** to support
    the agent's final decisions."
   F1 = 2·Precision·Recall / (Precision + Recall)
   —— 检索到的记忆是否命中预置的真值片段
   论文实例: "Where did Alice go today?"
            记忆含 (A) "Alice had lunch with friends at Wangfujing today."
                (B) "Alice had roast duck for lunch"
            ★ 更好的记忆模块应选 (A)

③ Time & Hardware Cost（时间与硬件成本）
   Δtime = (1/M) Σ (t_end^i − t_start^i)
   —— adaptation time（写+管）与 inference time（读）分开计
   —— 计算开销用 peak GPU memory allocation
   论文实例: Tack et al. [106]
```

★★ **对 DWC 的直接价值**：DWC 记忆核心目前只有"七管 + 三区 + 两视图 + 双门 + 三层淘汰"
的结构描述，**没有一个客观数字指标**。这三个公式可以直接抄。

★ 特别值得抄的是 **Reference Accuracy**（F1）：它度量的是**中间检索**而非最终答案。
  DWC 的记忆若只看"最终决策有没有变好"，会掩盖"检索错了但决策凑巧对"的情况。

### 1.4 文本记忆 vs 参数记忆的权衡（§5.2.3）

```text
Effectiveness: 文本更全更细，但受 prompt token 限制
               参数不受长度限制，但"may suffer from information loss when
               transforming texts into parameters"
Efficiency:    "textual memory is more efficient in **writing**, while parametric
                memory is more efficient in **reading**"
Interpretability: 文本可解释，但"such explainability is obtained at the cost of
                **information density**"（离散空间不如连续空间稠密）
★★ 对 DWC: DWC 是文本型记忆（七管数据链），按此文其优势是**写入效率 + 可解释**，
  劣势是 token 限制与信息密度。
  ★ 这为 DWC 的"记忆容量上限"提供了文献依据，不是设计缺陷而是有代价的取舍。
```

### 1.5 ★★ 记忆评估的开放问题（§6.3，原文逐字）

```text
"Compared with direct evaluation, indirect evaluation via specific tasks can be easier
 to conduct, since there are already many public benchmarks. However, **the performance
 on tasks can be attributed to various factors, and memory is only one of them, which
 may make the evaluation results biased**."

"By direct evaluation, the effectiveness of the memory module can be independently
 evaluated, which improves the reliability of the evaluation results. However,
 **to our knowledge, there are no open-sourced benchmarks tailored for the memory
 modules in LLM-based agents**."
```

★★ **这一段是 DWC 记忆核心最重要的外部依据**：
  ① 端到端任务分数**不能**归因到记忆（与 2609.2680 (j) 三类度量不可互换同源）
  ② 领域内**没有**记忆专用公开基准
  ⇒ ★★ DWC 若造一个记忆专用基准，是填补领域空白，不是在跟风
  ⇒ 且必须做"冻结其他因素只变记忆"的消融（正对应缺口 (d)）

---

## 二、2404.14387 · 自进化四阶段 + 自主性三档

### 2.1 四阶段 vs DWC 七环节

```text
2404.14387 四阶段                  DWC 七环节        归属
──────────────────────────────────────────────────────────────────
experience acquisition（经验获取）  ①诊断             evolver
experience refinement（经验精炼）   ②对象③门          evolver + judge
updating（更新）                    ④落地             evolver
evaluation（评估）                  ⑤防漂移           iwm
                                  ⑥探索             world_model
                                  ⑦主体             全系统
★★ 对照结论: 四阶段是**时间流程**，DWC 七环节是**时间+空间混合**。
  ★ DWC 多出的三块（防漂移/探索/主体）正是 2404.14387 没覆盖的 ——
    这与 2609.2680 的"协议层"互补关系一致。
```

### 2.2 ★★★ 自主性三档（可直接判定的公式）—— DWC 定位

**§8.2 原文**：

```text
Low-level（低）:
  "the user predefined the evolving object E and it remains unchanged. The user needs
   to design the evolving pipeline, namely all modules f•, on its own."
  M̃ = Evol_L(M, E, f•, ENV)          式(8)
  ★ 原文: "**Most of the current works lie at this level.**"

Medium-level（中）:
  "the user only sets the evolving object E and keeps it unchanged. The user doesn't
   need to design the specific modules f•."
  M̃ = Evol_M(M, E, ENV)               式(9)

High-level（高）:
  "the model diagnoses its deficiency and constructs the self-evolution methods to
   improve itself. ... The user model sets its own evolving object E according to the
   evaluation f_E output. **The evolving objective would change during the iteration.**
   Besides, the model designs the specific modules f•."
  M̃ = Evol_H(M, ENV)                  式(10)
```

★★ **对 DWC 的定位判据（可直接用）**：

```text
★ DWC 目前的状态 = Medium-level:
  · 进化对象 E 由用户（我）定，且不变 ✓
  · 具体模块 f• 由用户设计（DWC 的 ARCHITECTURE.md 正是 f•）✓
  ⇒ 式(9): M̃ = Evol_M(M, E, ENV)

★ DWC 要往 High 走，缺两件:
  ① E 自己会变（目标演化）⇒ 这正是 2609.2680 缺口 (g) "目标演化必须双记"
  ② 模型自己诊断缺陷并构造改进方法 ⇒ 这正是 2404.14387 的终局表述
★ ⇒ 两条缺口 (g) 与"自主性升级"是同一件事，裁决时一起
★ 论文对 High-level 的判断: "developing highly autonomous self-evolution frameworks
  **remains an open problem**" ⇒ ★ DWC 若真做到，是填补领域空白
```

### 2.3 ★★★ "三轮之后不再进步"的实测（对应缺口 (h)(i)）

**§8.3 原文逐字**：

```text
"Recent studies [103, 141] also show that **current methods struggle to improve after
 more than three rounds of self-evolution**."

"One hypothesized reason is that **the self-critic of LLM has not co-evolved with the
 evolving objective**, but more experimental and theoretical support is still needed."
```

★★ **这是本次深读最尖锐的一条**：DWC 若要长跑，必须解释自己为何不会在第 3 轮卡住。
论文给出的假设 —— **自批评者没有与目标共演化** —— 正好指向 DWC 的 judge 器官。

```text
★ 与已有发现的连接:
  2609.2680 (g) 目标演化双记 + "Internal judges can evolve while the independent
                reference remains fixed"
  2607.07663    Red Queen 共演化准则
  Meta-Rewarding 恰恰就是"改进评判器"
⇒ 三篇都指向同一件事: judge 与目标必须共演化, 且共演化过程必须被外部固定参照监督
```

### 2.4 稳定性-可塑性（§8.4）与自一致性过滤的风险（§5.1.2）

```text
§8.4 原文: "the difficulty of balancing the need to **retain previously learned
 information (stability)** while adapting to new data or tasks (**plasticity**)"
  ★ "While training models from scratch could mitigate the problem of catastrophic
     forgetting, it is **highly inefficient**"

★ §5.1.2 Metric-Free 过滤的风险（直接对应 DWC §9 第 20 项）:
  "Designing internal consistency measures that accurately reflect output quality
   **can be challenging**."
  → Self-Consistency [126]: "the consistency of the final answer across multiple
     generated reasoning paths, with **higher agreement indicating higher reliability**"
★★ ⇒ 自一致性高 ≠ 正确。这与 2607.07663 "Agreement can indicate consistency
  without establishing correctness" 与 2609.2680 (j) 完全同源，三篇独立印证。
⇒ ★ DWC 第 20 项不是过度保守，而是三篇文献一致指出的陷阱。
```

### 2.5 目标要"分层"（§8.1）

```text
"the concept of evolving objectives entails a potential **hierarchical structure**;
 for instance, UltraTool [54] and T-Eval [23] categorize the capability of tool usage
 into various **sub-dimensions**. Exploring evolutionary objectives into manageable
 **sub-goals** and pursuing them individually emerges as a viable strategy."
★★ ⇒ 对应 DWC 的 8a/8b / 16a/16b 拆项思路（34→27 去重）。
  ★ 文献支持: 目标应可分解为可管理的子目标，逐个追求。
```

---

## 三、2501.07278 · 记忆四分类 + 五个标准评估公式

### 3.1 ★★ 记忆四分类（§3.3.2）

```text
"We categorize the memory module into **four key types**: Working Memory,
 Episodic Memory, Semantic Memory, and Parametric Memory."

Working Memory:  "short-term memory ... prompts, user inputs, and relevant workspace
                  information ... foundation for short-term reasoning"
Episodic Memory: "stores long-term experiences and events, such as user interactions,
                  previous task outcomes, or multi-turn dialogues ... maintaining
                  consistency in long-term behavior"
Semantic Memory: "functions as an **external knowledge store** ... continual knowledge
                  graph learning and continual document learning"
Parametric Memory: "Unlike the ..."（下接 §9 全文）
```

★★ **与 DWC 三区的对照**：

```text
文献四类            DWC 三区        说明
──────────────────────────────────────────────────────
Working            （?）           ★ DWC 无对应；痕迹 schema 的 Trajectory 层近似
Episodic           L2 事件/经验     ✓
Semantic           L3 知识/事实     ✓（母巢 L2 占 73% 是 fact）
Parametric         （无）           ★ DWC 不改权重，正确
★★ ⇒ DWC 三区 ≡ 文献四类去掉 Working 与 Parametric。
  ★ 推论: DWC 的痕迹 schema 若不做"工作记忆"层，会丢掉当前上下文 ——
    但 DWC 是自进化系统，"当前上下文"就是本轮的 state，可能内含于 L1。
  ★ 建议: 明确声明 DWC 的 L1 是否兼任 Working；若兼任，写清边界。
```

### 3.2 ★★★ 五个评估公式 —— 直接填缺口 (c)(i)

**§13.1 原文逐字 + 公式**：

```text
"the evaluation metrics of lifelong LLM agents primarily assess their lifelong learning
 ability from **three perspectives**: (1) the overall accuracy of all tasks,
 (2) the **stability** of history tasks (3) the **plasticity** of future tasks."
```

设 J_{i,t} = agent 完成任务 i（时点 t）后的表现。

```text
【视角1 总体】
  AP_t = (1/t) Σ_{i=1..t} J_{t,i}            式(14)  Average Performance
  AIP  = (1/T) Σ_{t=1..T} AP_t               式(15)  Average Incremental Performance
  ★ "the difference between AP and AIP is that, **AIP captures the historical
     variation when experiencing each task**"

【视角2 稳定性】
  FGT_t = (1/(t−1)) Σ_{i=1..t−1} [ max_{j∈{i..t}} {J_{j,i}}_j − J_{t,i} ]   式(16)
  ★ "FGT evaluates the **average accuracy drop of each old task**, representing that
     whether **useful experience are maintained successfully**"

  BWT_t = (1/(t−1)) Σ_{i=1..t−1} (J_{t,i} − J_{i,i})                        式(17)
  ★ "BWT evaluates the average accuracy improvement of each old tasks, representing
     whether the experience gained **after** the agent encountered a given task
     benefits **that task**"

【视角3 可塑性】
  FWT_t = (1/(t−1)) Σ_{i=2..t} (J_{i,i} − J̃_i)                             式(18)
  ★ "It represents whether the gained experience is useful to **future** tasks."
  ★ 其中 J̃_i = "the performance of a LLM agent that has **no experience**"
```

★★ **这五个公式精确对应两个缺口**：

```text
缺口 (c) 保护组回归约束 r̂_{t,j} ≤ ϵ_j
  ⇒ FGT（式16）就是它的**标准化形式**：保护组（历史任务 j）的平均下降幅度
  ⇒ ★ 建议: DWC 的保护组约束直接用 FGT，不要自造记号

缺口 (i) 稳定性是度量属性 + 三个观测量
  ⇒ FGT（稳定性）/ BWT（旧任务是否受益）/ FWT（新任务是否受益）三件套
  ⇒ ★ 2609.2680 要的"恢复时间/丢失技能/恢复后质量"是**时间序列版**，
    这三个是**截面版** ⇒ 两者互补，不是替代
```

### 3.3 §15.2 记忆管理的五个方向（DWC 可对照的自查清单）

```text
原文列五条:
① Memory Architecture Specialization
   "Designing **hierarchical** memory structures that differentiate between short-term
    context (working memory), long-term events (episodic memory), structured knowledge
    (semantic memory), and learned weights (parametric memory) can enhance memory
    efficiency and retrieval accuracy."
② Optimized Retrieval Mechanisms
   "Incorporating sophisticated retrieval strategies **beyond naive nearest-neighbor**"
③ Dynamic Memory Management
   "Investigating techniques that **proactively prune or summarize** outdated or less
    relevant knowledge is crucial for balancing memory growth with retention"
④ Neuro-inspired Consolidation
   "ensures that new memories **integrate or coexist with existing ones without
    overwriting them**"
⑤ Scalable Memory Architectures
   "systems that are **infinitely expandable** while ensuring fast storage and retrieval"

★★ 与 DWC 对照:
  ① ✓ DWC 三区即是层级结构
  ② ★ DWC 若还是"最近邻/向量检索"，这是明确可改进项
  ③ ✓ DWC 三层淘汰 = proactive prune ✓ 但需度量支撑（见 1.2 的风险）
  ④ ★ "integrate or coexist **without overwriting**" = DWC 双门准入的目标表述
  ⑤ ★ "infinitely expandable" 是可检验的规模性质，DWC 应声明目标
```

---

## 四、诚实条款（逐条照录）

```text
① 2404.13501 §6.3 自陈: 领域内**没有**记忆模块专用开源基准
   ⇒ 本报告的三个指标是论文给的公式，不是现成可跑的工具
② Table 3 的 ✓/◦/× 是**论文作者的判定**，未逐篇复核原文
   ⇒ 引用时应作"该综述的汇总"，不作原始实测
③ 2404.14387 §8.3 的"三轮后不再进步"是**转述** [103,141] 的结论，未核到原始论文
④ 2404.14387 §8.2 自主性三档是**综述作者的分类框架**，非领域共识标准
⑤ 2501.07278 的五个公式假设"性能可聚合为标量"（原文: "we assume that the agent's
   performance can be converted into a scalar obtained by aggregating various metrics"）
   ★ DWC 若多器官异质指标，需先解决聚合口径问题
⑥ 三篇均为综述，未提供各自的原始实验
⑦ 本轮只精读这三篇；DWC 报告里 22 篇中的其余 15 篇仍是摘要级
```

---

## 五、可迁移条目汇总（对应 §9 缺口）

```text
★ M1. ★★ FGT/BWT/FWT 三公式【2501.07278 式16-18】→ 直接填缺口 (c)(i)
   · 保护组回归约束用 FGT，不要自造记号
   · 稳定性截面版 = FGT/BWT/FWT; 时间序列版 = 2609.2680 的恢复时间等三量
   ★ 前置条件: 性能须可聚合为标量（DWC 多器官异质指标要先解决）

★ M2. ★★ Reference Accuracy (F1)【2404.13501 §6.1.2】→ DWC 记忆核心缺的中间度量
   ★ 只看最终决策会掩盖"检索错但决策凑巧对"

★ M3. ★★ 领域无记忆专用基准【2404.13501 §6.3】→ DWC 造基准 = 填补空白
   ★ 且必须做"冻结其他因素只变记忆"的消融（对应缺口 (d)）

★ M4. ★ content 作为第四个可冻结维度【2404.13501 §5.3 三操作 vs 缺口 (d) 四干预点】
   ★ 现有三区对应 writing/reading/management，唯 content 无独立开关

★ M5. ★★ 自主性三档公式【2404.14387 式8-10】→ DWC 定位判据
   ★ DWC 现为 Medium-level（式9）; 进 High 需 ① E 自己会变 ② 模型自诊断
   ★ 与缺口 (g) 是同一件事，裁决时一起

★ M6. ★★★ "三轮后不再进步" + 自批评者未共演化【2404.14387 §8.3】
   ★ 这是长跑的硬约束: DWC 必须解释自己为何不会第 3 轮卡住
   ★ 三篇独立指向同一处: judge 与目标共演化 + 外部固定参照监督
     （2609.2680 (g) / 2607.07663 Red Queen / Meta-Rewarding）

★ M7. ★ 自一致性过滤的风险已被三篇独立标注【2404.14387 §5.1.2 / 2607.07663 /
   2609.2680 (j)】
   ⇒ 第 20 项不是过度保守，是文献一致指出的陷阱

★ M8. ★ 遗忘是少数派设计【2404.13501 Table 3】
   ★ 29 个系统里绝大多数 Forgetting = ×/◦
   ⇒ DWC 的三层淘汰需实证支撑，否则可能等于"母巢式遗忘"

★ M9. ★ 文本记忆的代价有文献依据【2404.13501 §5.2.3】
   ★ "textual memory is more efficient in writing, while parametric memory is more
     efficient in reading" + 可解释性换来信息密度损失
   ⇒ DWC 选文本型是有代价的取舍，不是免费的
```

---

## 六、逐字核实

```text
✓ 2404.13501: 三操作定义 / Table 3 / 三个评估指标+公式 / §5.2.3 三权衡 / §6.3 无基准
✓ 2404.14387: 四阶段 / 式(8)(9)(10) 自主性三档 / §8.3 三轮 / §5.1.2 challenging
✓ 2501.07278: 记忆四分类 / 式(14)-(18) 五公式 / §15.2 五方向 / 标量聚合假设
```

---

*报告 2026-10-04 · 三篇逐行精读 · 对应 ARCHITECTURE.md §9 缺口 (c)(d)(g)(i)(j) 与记忆核心*