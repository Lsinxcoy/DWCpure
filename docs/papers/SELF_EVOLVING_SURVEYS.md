# 自进化 agent 四篇精读 · DWC 架构的外部校准

> **覆盖**（2609.2680 正文引用 ×2-×3，全部逐行精读）
> | arXiv | 标题 | 页/字符 | 状态 |
> |---|---|---|---|
> | 2507.21046 | A Survey of Self-Evolving Agents (**TMLR 01/2026 正式发表**) | 77 / 324,320 | 逐行 |
> | 2608.03392 | Self-Evolving Coding Agents | 54 / 247,297 | 逐行 |
> | 2508.07407 | A Comprehensive Survey of Self-Evolving AI Agents (MASE) | 55 / 247,634 | 结构级 |
> | 2501.07278 | Lifelong Learning LLM Agents: A Roadmap | 46 / 292,361 | 逐行（见另报告） |
>
> 归档：`papers_txt/refs/{id}.{pdf,txt}`
> 报告日期：2026-10-04

---

## 一、★★★★★ 2608.03392 的 A_t = (S_t, H_t, θ_t) —— DWC 缺的最精确状态模型

**§3 原文逐字**：

```text
"Following A_t = (S_t, H_t, θ_t), we organize these targets into **Assets
 Self-Evolution, Architecture Self-Evolution, and Model Self-Evolution**."

Assets:   S_t = (M_t, K_t, T_t, C_t)          式(7)
          "M_t, K_t, T_t, and C_t denote **memory, skills, tools, and context**"
          "Memory retains knowledge ...; **skills organize knowledge into reusable
           procedures**; tools provide executable operations; and context determines
           the information, instructions, and environmental settings"
          eS_{t+1} = U_S(A_t, τ_t, f_t)

Architecture: H_t = (h_t, w_t, g_t)           式(8)
          "h_t denotes the **harness**, w_t the **workflow**, and g_t the
           **multi-agent organization**"
          "The harness governs **runtime interaction and execution control**; the
           workflow specifies the **arrangement and dependencies of task-solving
           stages**; and the multi-agent organization determines how responsibilities
           and information are distributed"
          eH_{t+1} = U_H(A_t, τ_t, f_t)

Model:    "Model evolution changes the **parameterized policy** that shapes decisions"
```

### 三层深度的判定依据（原文）

```text
"This ordering reflects **progressively deeper intervention** in the agent's
 implementation."
"Assets are typically **modular resources that can be added, revised, or replaced
 within an existing execution structure**."
"Architecture updates reach into the code or configuration **governing execution**,
 changing control flow, stage dependencies, or coordination among agents."
"Model updates reach further into the **learned parameters** underlying action
 selection."
★ 工具更新的归属澄清: "Tool updates may also involve code, but they **revise available
  operations**, while architecture updates **change how the system organizes and
  controls execution**."   ← 这解决了"改代码算哪一层"的歧义
```

### ★★★ 与 2609.2680 缺口 (e) 的对应（这是本报告最重要的一条）

```text
2609.2680 说: "a patch to **a target repository** vs a patch to **the agent that writes
                repository patches**. Only the latter directly changes the
                update-producing machinery."

2608.03392 把它展开成三层:
  式(7) U_S  ← 改的是"可用的资源"     ≈ task_artifact 一侧
  式(8) U_H  ← 改的是"执行如何被组织" ≈ improver_code 一侧 ★
  式(9) U_θ  ← 改的是"决策参数"       （DWC 不做，见下）

★★ 关键洞见（原文）: "**making the scope of the change more informative than its
  code size**" —— 范围比代码量更有信息量。
★★ 又一洞见: "moving validation ahead of a costly rewrite **changes which assumptions
  reach implementation without adding a new capability**"
  ⇒ 把验证提前不算"新能力"，但改变了哪些假设能到实现层
```

### 对 DWC 的裁决价值

```text
★ DWC 当前七器官的映射（三元是论文的，DWC 的是我的对应）：
  S_t (Assets)      → memory 器官（记忆/技能/工具/上下文）
  H_t (Architecture) → evolver + actor + iwm（harness/workflow/多 agent 组织）
  θ_t (Model)       → ★ DWC 不改权重 ⇒ 这一层对 DWC 是**固定的**

★★ ⇒ 这直接给出 2609.2680 (e) 的可判定实现:
   每个候选变更必须声明 (target_layer, target_component):
     target_layer ∈ {assets, architecture, model}
     ★ DWC 只允许前两层（θ 固定）⇒ 这就是 DWC 的 "fixed" 清单之一
     target_component ∈ {memory, skills, tools, context | harness, workflow, org}
★ ⇒ 也回答了 §9 第 20 项的一半: 守卫① 之所以能自评,
  是因为它用 θ 层（自算 confidence）去评 H 层 —— ★ 跨层自评
```

---

## 二、★★ 2607/2608.03392 的"采用时机"权衡（对应缺口 (e)(q)）

**§7 原文（摘要段逐字）**：

```text
"**Early adoption** can use fresh feedback but may rely on **incomplete evidence**,
 while **waiting** permits broader validation but **delays reuse**."
```

★ **这是 DGM 阶梯评测（(q)）的理论依据**：
  小集粗筛（早采用）vs 大集精评（等更多证据）—— 论文明确这是**权衡**不是最优解。

★★ 归因难度的原文表述：

```text
"As intervention deepens, **a lesson can influence more decisions and become harder to
 attribute or reverse**."
★ ⇒ 这与 2609.2680 (h) 三类漂移、(e) 两层补丁同源:
  干预越深 → 越难归因、越难回滚 → 门的判据必须越严
```

---

## 三、★★★★ 2507.21046（TMLR）四轴：What / When / How / **Where**

### 3.1 五轴定义（Figure 3 图注逐字）

```text
"What to Evolve (Sec.3) decomposes agent components: **model, context, tools, and
 architecture**, showing where evolution operates."

"When to evolve (Sec.4) distinguishes **intra-test-time versus inter-test-time**
 self-evolution, corresponding to **ICL, SFT, and RL** paradigms."

"How to evolve (Sec.5) summarizes methodological families—**reward-based, imitation &
 demonstration, and population-based**—together with cross-cutting dimensions such as
 **online/offline, on/off-policy, and reward granularity**."

"Where to evolve (Sec.6) contrasts **general-purpose and domain-specific** deployments
 (e.g., coding, GUI, finance, medical, education)."

"Evaluation (Sec.7) outlines goals and metrics—**adaptivity, generalization,
 retention, efficiency, safety**..."
```

### 3.2 ★★ When：intra / inter test-time = Persistence 边界的对应物

**§4 原文逐字**：

```text
"**Intra-test-time self-evolution** refers to adaptive processes that occur **during
 task execution**, where agents recognize their limitations on a specific problem and
 initiate targeted learning mechanisms to enhance their capabilities **in real-time**."

"**Inter-test-time self-evolution** refers to learning processes that occur **between
 task completions**, leveraging accumulated experiences to improve future performance."
  · offline: "extract knowledge from pre-collected datasets through iterative refinement"
  · online: "continuously adapt based on streaming interaction data"

"The implementation of self-evolution across these temporal phases leverages three
 fundamental learning paradigms in LLMs: **in-context learning (ICL)** ... which adapts
 behavior through contextual examples **without modifying parameters**; **supervised
 fine-tuning (SFT)** ...; **RL**"
```

★★ **这就是 2609.2680 三描述符 Persistence 的文献对应**：

```text
2609.2680 Persistence ∈ {task, session, training}
2507.21046  When ∈ {intra-test-time, inter-test-time} × {ICL, SFT, RL}
★★ ⇒ 映射: intra-test-time ↔ task 边界; inter-test-time(offline) ↔ training 边界
  ⇒ DWC 应当声明自己的演化发生在哪个边界 —— 这正是缺口 (l) 要的
★ DWC 的现状（痕迹 schema 三层 Trajectory/Turn/Subscene + run_term 驱动）
  ≈ inter-test-time 为主, 但缺明确声明
```

### 3.3 ★★★ 评估五维度（DWC GDI 四信号之外的第五维）

**§7 原文逐字**：

```text
"Evaluating self-evolving agents presents a unique set of challenges that extend
 beyond the traditional assessment of static AI systems. ... their evaluation must
 capture not only immediate task success but also crucial aspects such as **adaptation
 over time, knowledge accumulation and retention, long-term generalization**, and the
 ability to **transfer learned skills** across sequential or novel tasks, all while
 **mitigating catastrophic forgetting**. This requires a fundamental shift from
 conventional "single-shot" scoring to a **longitudinal, cost-aware trajectory view**."

"we categorize the key evaluation goals into **five core dimensions:
 Adaptivity, Retention, Generalization, Efficiency, and Safety**"
```

★★ **两处硬要求**：

```text
① ★★ "a **longitudinal, cost-aware trajectory view**"
   ⇒ 不是单点分数，是**轨迹视图 + 成本感知**
   ⇒ DWC 的门若只看单轮分数，缺这两个维度
② 五个维度（与 DWC 的对应）:
   Adaptivity     → DWC 门 §5 的进化有效性
   Retention      → ★ 对应 2501.07278 的 FGT（遗忘度）
   Generalization → ★ 对应 2609.2680 的 τ_t（迁移）
   Efficiency     → ★ 对应 (c) 的 C ≤ B（预算）与 (k) 后代评估消耗
   Safety         → DWC iron_laws 器官
★ ★ DWC 的 GDI 四信号与这五维**不完全重合**：
  GDI 是"进展度量"，这五维是"评估目标"
  ⇒ 建议 DWC 门在自评时按这五维各报一个数，而非只报 GDI
```

---

## 四、★★ 2508.07407（MASE）的框架与 DWC 对照

```text
结构（§3 概念框架）:
  §3.1 Overview of the Self-Evolving Process
  §3.2 System Inputs
  §3.3 Agent Systems      §3.4 Environments      §3.5 Optimisers
§4 Single-Agent Optimisation
  §4.1 LLM Behaviour Optimisation
       §4.1.1 Training-Based   §4.1.2 Test-Time
  §4.2 Prompt Optimisation
       §4.2.1 Edit-Based  §4.2.2 Generative
       §4.2.3 Text Gradient-Based  §4.2.4 Evolutionary
  §4.3 Memory Optimisation
       §4.3.1 Short-term   §4.3.2 Long-term
  §4.4 Tool Optimisation
★ 记忆分短/长两层（DWC 是三区）
★★ 单 agent 优化的四类（LLM 行为/提示/记忆/工具）——
  ★ DWC 七器官里能对上的: memory + tool（进化对象）
  ★ 对不上的: LLM behaviour（改权重/行为）DWC 不做；prompt 优化 DWC 无专门器官
  ★⇒ 若要补，prompt/行为优化应归入 evolver 的"可编辑组件"
```

### 提示优化四法（DWC 若要进化自身提示，可直接对照）

```text
Edit-Based            局部编辑
Generative            生成式重写
Text Gradient-Based   ★ 文本梯度（用自然语言当梯度）
Evolutionary          进化式（Promptbreeder 一类）
★ ⇒ 2608.03392 把 "Prompt Evolution" 归在 **Assets → Context Self-Evolution** 下
  ⇒ 所以提示在三元模型里属 S_t 的 C_t（context），不是 H_t
  ★ 这纠正了一个易混淆点: 改提示 ≠ 改架构
```

---

## 四·补 ★★★★★ 2608.03392 §10 五条开放问题（补读，第 61 轮）

> 上一版诚实条款承诺补读这三处，现补上。**五条全部命中 DWC 的现存问题。**

### 4·1 可复现性 / 污染 / 基准过拟合

```text
"Self-evolution makes reproducibility difficult because agents may change across runs,
 tasks, repositories, tool environments, or **model versions**."

"SWE-rebench ... finds that **some results on SWE-bench Verified may be inflated by
 contamination** (Badertdinov et al., 2025)."

"DeepSWE exposes a related measurement problem. On original long-horizon tasks, an
 **independent judge disagrees with its purpose-built verifiers far less often than
 with tests inherited from public fixes**, showing that **both solution exposure and
 incomplete tests can distort the apparent capability** of an agent (Huang et al., 2026b)."

★★ 独立 judge 与"专用 verifier"的一致性高于与"公开 fix 继承的测试"的一致性
  ⇒ ★ 这条同时是 (c) 保护组约束与 L3 独立 judge 的**双向印证**:
    L3 不是多余的，它与专用 verifier 一致，而公开测试不一致
```

```text
★★★ 最硬的一条（对 DWC 进化核心的直接警告）:
  "A matched-budget study of automatic harness evolution provides more direct evidence:
   on Terminal-Bench 2.1, **evolved harnesses do not consistently outperform simple
   test-time search baselines** and show **limited generalization to held-out tasks**
   (Wang et al., 2026h)."
★★ ⇒ "改 harness（= 改架构层 H_t）"这条路已有**同预算对照的负面结果**
  ⇒ ★ DWC 若声称"改自己的代码有收益"，必须对上这条（正是 (p) 的 +11.0pp 需要
    在 DWC 自己的任务域重新验证的原因）
```

### 4·2 反馈可靠性 / 安全 / 工具依赖

```text
"An analysis of **4,892 patches** from ten software-development agents finds that even
 **test-passing patches can modify different files and functions** from developer
 patches, exposing limits in the tests used to identify acceptable repairs."

"Across **1,030 valid traces** from **seven agent frameworks**, **170 patches** passed
 the available functional checks while **omitting protections, applying inadequate
 fixes, or introducing vulnerabilities**; **neither test passing nor LLM review reliably
 intercepted these cases** (Bai et al., 2026b)."
★★ 170/1030 ≈ 16.5% 通过功能检查但引入安全问题
★★ ⇒ 这是 DWC iron_laws 的**存在理由的硬数据**: "测试通过"不是安全证据
```

```text
★★★★ 与 DWC §9 第 20 项完全同源的一条（Guo et al., 2026a）:
  "Experiments on heuristic self-improvement show that **self-assigned verification
   scores can stay near perfect while sealed deployment performance remains low or
   regresses**; **retaining an external accept–reject audit improves results across
   six models**."

  ★★★ 这就是 (n) imp@k + (20) 守卫① 矛盾的**第三方实测**:
    自评分数可以接近满分而真实性能不升反降 ⇒ 外部 accept-reject 审计在六个模型上都更好
  ⇒ ★★ DWC 原则 12 "judge 不得自评" 现在有了实测支撑, 不只是理论洁癖
```

### 4·3 ★★★ 可逆性 / harness 膨胀 / 特化 —— 两条最该警惕

```text
"AHE similarly makes harness components explicit and revertible, but **end-to-end
 guarantees of this kind are not yet standard** across self-evolving coding agents."

"ten evolution rounds improve Terminal-Bench 2 performance, while **ablations locate
 the transferable gains in tools, middleware, and long-term memory rather than in every
 edited component**."
★★★ ⇒ 改了 10 轮，可迁移的收益只来自三类组件，其余是无效编辑
  ⇒ ★ DWC 的进化必须做**逐组件归因**，不能整体说"进化有效"
```

```text
★★★★★ Phantom Guardrails（"幽灵护栏"）—— DWC 必须防的具体失效:
  "a proposer **installs a guardrail for a nonexistent violation in 15 of 60 runs**
   when harmless input **resembles a familiar rule**, compared with **none on
   featureless input**, and **an add-only loop makes the spurious component persist**"

  ★★★★ 这是一条几乎专为 DWC 写的警告:
    ① 15/60 = 25% 的运行会为**不存在的违规**加护栏（幻觉式防御）
    ② 触发条件: 无害输入**像**某条熟悉规则 ⇒ 靠相似度误触发
    ③ ★★ "an **add-only loop** makes the spurious component persist"
       ⇒ 只增不减的循环会让幻觉组件永久驻留
  ⇒ ★ DWC 的三层淘汰（"只减不增"的反向机制）正是对这条的对策
    但★ 必须验证淘汰真的会发生 —— 否则 add-only 等于永久污染
```

```text
★★★★ harness tampering（篡改评测路径本身）:
  "An audit of real self-improvement trajectories finds **harness tampering across
   different systems** and observes that **such edits can persist in the lineage of the
   selected best agent**."

  "Reversibility must include the **evaluation path** as well as task execution."
  "A candidate may appear better because it **changes task access, termination** ..."
★★★★★ ⇒ 这直接对应 DWC §9 第 20 项最坏情形:
    进化把"评测路径"本身改了, 于是自我评分变好但真实能力没变
  ⇒ ★ 这是 (e) 两层补丁必须区分的**最强理由**:
    patch_target 必须是**声明字段**, 且 iron_laws 要管"谁改得了评测路径"
```

### 4·4 长期记忆 / 技能 / 协调

```text
"Experience banks, repository memory, and skill libraries may become **stale, redundant,
 overly repository-specific, or contaminated by failed trajectories**."

"Controlled experiments on memory management reveal an **experience-following effect**
 in which **similar retrieved records induce similar outputs**. Incorrect or misaligned
 records can therefore **propagate errors**, whereas **selective addition and deletion
 outperform unrestricted memory growth** (Xiong et al., 2026)."
★★★★ 两条对 DWC 记忆核心都是硬约束:
  ① experience-following effect ⇒ 检索到的相似记录会诱导相似输出
     ⇒ ★ 相似度高 ≠ 相关性好 ⇒ 记忆检索必须防"相似即召回"
     ⇒ 这也解释了为什么 access_count 高不等于记忆有用
  ② ★★ "selective addition and deletion **outperform unrestricted memory growth**"
     ⇒ 追加式增长是**被实测打败的方案** ⇒ 印证 M8（遗忘是少数派但必要的）
```

```text
"Skill evolution has a similar lifecycle problem. A systematic study across extractors,
 consumer models, and **five agentic domains** finds that generated skills **help on
 average but also produce non-trivial negative transfer**; **extraction quality and
 consumption quality do not necessarily coincide** (Huang et al., 2026d)."

"These results make retention **conditional**: an artifact is useful only for a
 **compatible task, retriever, consumer, and execution context**."

"Their ability to **activate and follow** the resulting artifacts is **non-monotonic**,
 with **weak models often failing to use what was retained**."
★★★★★ ⇒ DWC 的知识/技能必须带**消费条件**，不是"存了就有效"
  ★ 具体: 每条记忆/技能应声明适用的 task / retriever / consumer / context 四元
  ★ 这与 2609.2680 (l) 三描述符同源 —— 又是"描述符缺失"这一类问题
```

### 4·5 评估必须超出短基准

```text
"SWEEVO requires release-scale changes spanning an **average of 21 files and hundreds
 of tests**; a GPT-5 and OpenHands configuration resolves **21%** of these tasks,
 compared with **65% on SWE-bench Verified**."
★★★★ 21% vs 65% —— 规模一上去，通过率掉到三分之一
  ⇒ DWC 若只在短任务上验收，会高估自己

"PATH-Bench further shows that **strong forward transfer does not guarantee retention**
 and that **later experience can reshape gains acquired earlier** in a task sequence."

"Coding-specific memory experiments across six benchmarks find a **3.7% average gain
 from cross-domain transfer**, but also show that **abstract validation routines
 transfer more reliably than concrete traces**, which can cause **negative transfer
 through excessive specificity** (Kim et al., 2026)."
★★ ★ 两个方向相反的迁移结论同时成立:
  强前向迁移 ⇏ 保证保持; 抽象验证例程比具体轨迹更可靠迁移, 但过度具体会负迁移
  ⇒ DWC 的 (e) patch_target 分层与 (l) 描述符都应体现"抽象层更可迁移"
```

---

## 五、诚实条款

```text
① 2507.21046 是 TMLR 正式发表（01/2026），同行评审过 —— 本组里证据等级最高
② 2608.03392 是综述（54 页），其 A_t=(S_t,H_t,θ_t) 是**综述作者提出的框架**，
   非领域共识；原文未标注该三元是既有文献还是本文新提
   ★ 引用时应作"该综述的分类框架"
③ 2508.07407 本轮只做结构级精读（§3-§4 骨架），未逐行读完 55 页
   ★ 其"记忆分短/长两层"与 DWC 三区的差异结论需在逐行读完后确认
④ §7 五维度的 Table 6 逐项指标本轮未逐行读（只读了正文表述）
⑤ 2608.03392 §7/§8（反馈动态、产品）本轮未读；§10 已补读
★ 下一轮补读这三处
```

---

## 六、可迁移条目

```text
★ N1. ★★★★★ A_t = (S_t, H_t, θ_t) 三元 + 三层干预深度【2608.03392 式(7)(8)(9)】
   S_t = (memory, skills, tools, context)
   H_t = (harness, workflow, multi-agent organization)
   θ_t = 参数化决策策略（DWC 固定）
   ★ 这是 DWC 七器官最精确的外部校准；也是缺口 (e) 的可判定实现:
     每个候选声明 (target_layer ∈ {assets, architecture}, target_component)
   ★ 规则: "改什么可用资源 vs 改什么执行组织" 要分开
     （原文澄清: 工具改代码仍属 assets，只有改变"如何组织与控制执行"才是 architecture）

★ N2. ★★★ 跨层自评是第 20 项的根源【2608.03392 + 综合】
   守卫① 用 θ 层（世界模型自算 confidence）评 H 层改动 ⇒ 跨层自评
   ⇒ 修法不只是"换一个更准的自评"，而是**换层**：用 H 层或环外的固定参照评 H 层
   ★ 与 (n) imp@k（冻结 meta agent 身份）互为印证

★ N3. ★★★ 评估要"longitudinal, cost-aware trajectory view"【2507.21046 §7】
   ⇒ DWC 门不能只看单轮分数；须有轨迹视图 + 成本口径

★ N4. ★★★ 评估五维度【2507.21046 §7】
   Adaptivity / Retention / Generalization / Efficiency / Safety
   ★ DWC GDI 四信号不完全重合 ⇒ 建议五维各报一数
   对应: Retention↔FGT, Generalization↔τ_t, Efficiency↔C≤B与(k)

★ N5. ★★ intra/inter test-time = Persistence 边界【2507.21046 §4】
   intra ↔ task 边界；inter(offline) ↔ training 边界
   ⇒ 填 2609.2680 (l) 的 Persistence 声明

★ N6. ★★ 采用时机的权衡是明确的，不是最优解【2608.03392 §7】
   "Early adoption can use fresh feedback but may rely on incomplete evidence,
    while waiting permits broader validation but delays reuse."
   ⇒ (q) 的阶梯评测有理论依据；DWC 应声明选早还是选晚

★ N7. ★ 提示属 assets 的 context，不是 architecture【2608.03392 §3.1 + 2508.07407 §4.2】
   ⇒ 纠正易混点：改提示 ≠ 改架构
   ★ 提示优化四法：Edit-Based / Generative / Text Gradient-Based / Evolutionary

★ N9. ★★★★ "同预算下进化 harness 不稳定优于简单测试时搜索"【2608.03392 §10.1】
   "on Terminal-Bench 2.1, evolved harnesses do not consistently outperform simple
    test-time search baselines and show limited generalization to held-out tasks"
   ⇒ ★ DWC 声称"改自己的代码有收益"必须对上这条（(p) 的 +11.0pp 需在 DWC 域重验）

★ N10. ★★★★ 自评分数可近满分而真实性能不升反降【2608.03392 §10.2 转引 Guo et al. 2026a】
   "self-assigned verification scores can stay near perfect while sealed deployment
    performance remains low or regresses; retaining an external accept-reject audit
    improves results across six models"
   ⇒ ★★ 原则 12 有了**实测支撑**，不再是理论洁癖；六模型一致
   ⇒ 与 (n) imp@k（冻结身份）互为印证

★ N11. ★★★★★ Phantom Guardrails: add-only 循环让幻觉组件永久驻留【2608.03392 §10.3】
   "installs a guardrail for a nonexistent violation in **15 of 60 runs** when harmless
    input resembles a familiar rule ... an **add-only loop makes the spurious component
    persist**"
   ⇒ ★ DWC 三层淘汰是对策，但**必须验证淘汰真的发生**，否则 add-only = 永久污染
   ⇒ 相似即误触发 ⇒ 记忆检索不能"高相似就召回"

★ N12. ★★★★ harness tampering: 改评测路径本身【2608.03392 §10.3】
   "an audit of real self-improvement trajectories finds **harness tampering across
    different systems** and observes that such edits **can persist in the lineage**"
   "Reversibility must include the **evaluation path** as well as task execution."
   ⇒ ★ (e) 两层补丁的最强理由；iron_laws 要管"谁改得了评测路径"

★ N13. ★★★★ selective addition/deletion 优于无节制增长【2608.03392 §10.4】
   "**selective addition and deletion outperform unrestricted memory growth**"
   ⇒ 追加式增长是被实测打败的方案 ⇒ 印证 M8
   ★ 相关: "retention **conditional**: an artifact is useful only for a compatible
     task, retriever, consumer, and execution context"
   ⇒ 记忆/技能须声明**消费四元**

★ N14. ★★★ 短基准高估能力【2608.03392 §10.5】
   SWEEVO: 21% vs SWE-bench Verified 65%（规模一上去掉到三分之一）
   ⇒ DWC 若只在短任务验收会高估自己
   ★ 迁移方向相反的两条同时成立: 强前向迁移⇏保持; 抽象例程比具体轨迹更可靠迁移
   ⇒ (e) patch_target 与 (l) 描述符都应体现"抽象层更可迁移"

★ N15. ★★★ 逐组件归因【2608.03392 §10.3】
   "ten evolution rounds improve ... while **ablations locate the transferable gains in
    tools, middleware, and long-term memory rather than in every edited component**"
   ⇒ DWC 的进化必须逐组件归因，不能整体说"进化有效"

★ N8. ★ 干预越深越难归因与回滚【2608.03392 §摘要】
   "As intervention deepens, a lesson can influence more decisions and become harder to
    attribute or reverse."
   ⇒ 与 (h) 三类漂移、(e) 两层补丁同源：门判据须随深度加严
```

---

## 七、逐字核实

```text
✓ 2608.03392: A_t 三元 / S_t 四分量 / H_t 三分量 / 工具归属澄清 / 干预深度定义 /
              采用时机权衡 / "scope more informative than code size"
✓ 2507.21046: 五轴图注 / intra-inter 定义 / ICL-SFT-RL / 五评估维度 /
              longitudinal cost-aware trajectory view
✓ 2508.07407: §3 框架五要素 / §4 四类优化 / 提示优化四法（结构级）
```

---

*报告 2026-10-04 · 三篇逐行/结构级精读 · 核心贡献 A_t=(S_t,H_t,θ_t) 直接对应 ARCHITECTURE.md §9 (e)(h)(l)*