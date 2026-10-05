# 2609.2680 深读总报告 · 全部读完

> **主文件**：ARCHITECTURE.md §9 第 25 项（21 条缺口 (a)-(u)）
> **报告日期**：2026-10-04 · **36 轮反刍深读**
> **核心论文**：《Recursive Self-Improvement in AI: A Survey》preprints.org 202609.2680
> （32 作者 / 2026-09-30 / 404 篇 / 正文 2,330 行 / 54 小节 —— **全文逐行读完**）
> **补读**：2609.2680 正文引用 ≥2 次且 DWC 未读的 **28 篇，全部抓到全文**
> （1,698 页 / 6.0 MB 纯文本，归档 `papers_txt/refs/`）

---

## 一、材料清单与逐字核实状态

```text
★ 已出独立报告（4 篇）
  2609.2680  综述 · 26 轮 · 正文 2,330 行全覆盖 · 74,318 字节
  2607.07663 综述 · 同题对头 · 1250 篇语料 · 验证层级四层 · 11,552 字节
  2505.22954  DGM (ICLR 2026) · Table 1 消融 + 阶梯评测 · 9,652 字节
  2603.19461  HyperAgents · imp@k = Γ_t 可运行实现 · 10,518 字节

★ 已抓全文 · 本轮精读 5 篇
  2408.08435  ADAS (ICLR 2025) · 归档无剪枝 · Meta Agent Search 四步
  2505.03335  Absolute Zero · r_propose = 1 - r̄_solve（难度适中奖励）
  2507.19457  GEPA (ICLR 2026 Oral) · Pareto frontier + 自然语言反思
  2407.19594  Meta-Rewarding · 方差选样 + 位置偏置加权
  2601.05111  Agent-as-a-Judge · Procedural→Reactive→Self-Evolving 三段
  2504.15228  SICA · 消除 meta/target agent 之分 · held-out 0 处

★ 已抓全文 · 摘要级扫读 22 篇（另 2 篇本轮已读）
  2203.14465 STaR · 2310.02304 STOP · 2603.25681 自改进系统框架 · 2507.21046 自进化 agent
  2404.14387 自进化四阶段 · 2508.07407 自进化 agent 综述 · 2608.03392 自进化编码 agent
  2404.13501 LLM agent 记忆机制综述 · 2606.14502 数字同事 · 2504.15585 full-stack 安全
  1208.3719 Auto-WEKA · 1611.01578 NAS-RL · 1703.03400 MAML · 2309.16797 Promptbreeder
  2502.16923 APO 综述 · 2504.01990 Foundation Agents(396页) · 2501.07278 终身学习路线图
  1606.04474 学优化算法 · 1611.02779 RL² · 2508.07407 · 2404.14387
```

### 逐字核实（含假阳性排除）

```text
2609.2680   第一轮 21/21 · 第二轮 17/17
2607.07663  21/21（4 处断词假阴性已逐处定位）
2505.22954  15/15
2603.19461  14/14（1 处大小写假阴性）
★ 假阳性排除记录（两轮都用到）:
  · 用 re.I 忽略大小写搜 "AIDE" → 命中 2，实际是 "**aide**d"（unaided）
  · "SEVerA" → 命中 8，实际是 "**seve**ral"（several）
  · "GAI"  → 命中 74，实际是 "**GAI**A"（GAIA 基准）
  ⇒ 教训固化: 否定性结论必须做假阳性排除
```

---

## 二、★ 核心论文给出的 13 条协议级缺口（(a)-(m)）

```text
(a) 三主张分离 → L3 该测 Γ_t 还是 Δ_t?
    式5 Δ_t（任务增益）/ 式6 ρ,τ（保留迁移）/ 式8 Γ_t（改进器增益）
    原文: "Neither positive Δ_t nor positive τ_t isolates the improver."
(b) 配对探针 Γ_t 的严格形式
    原文: "Controls must match starting states, feedback access and resource accounting."
(c) ★ 保护组回归约束 r̂_{t,j} ≤ ϵ_j
    式9 完整验收门: A_t = 1{ Δ̂_val ≥ η_t, r̂_{t,j} ≤ ϵ_j ∀j, C_{≤t+1} ≤ B }
(d) 记忆内容 vs 管理机制可单独冻结
    原文: "freezes one of admission, retrieval, consolidation or content"
    ★ "a library can grow while becoming less useful"
(e) 两层补丁必须区分
    原文: "a patch to **a target repository** vs a patch to **the agent that writes
           repository patches**. Only the latter directly changes the update-producing
           machinery."
(f) ★ "无新反馈"对照组必须存在
    原文: "including a **no-new-feedback condition**"
(g) 目标演化必须双记
    原文: "Record progress under **both the revised objective and a stable external
           reference**."
    ★ "Internal judges can evolve while the independent reference remains fixed."
(h) ★ 三类漂移必须分开（优化/信息/行为）
    原文: "**grouping them all as collapse hides where the feedback loop fails**"
(i) ★ 稳定性是度量属性 + 三个新观测量（恢复时间/丢失技能/恢复后质量）
    原文: "**Stability is a measured property over a stated horizon, not a consequence
           of recursion.**"
(j) ★ 三类度量不可互换（actor 结果 / judge 校准 / 反馈下游有用性）
    原文: "**Agreement can indicate consistency without establishing correctness.**"
(k) ★ 后代评估消耗同一预算
    原文: "Evaluating descendants ... consumes the very budget against which
           improvement efficiency is measured."
(l) ★★ 三描述符完全缺失
    Feedback（trains/proposes/selects）+ Persistence（task/session/training 边界）+
    Control（editable 组件 + fixed 目标/工具/预算规则）
    原文: "A label such as self-training or self-modification **leaves these
           descriptors undetermined; they must come from the implementation**."
    ★ 实测 DWC 11 份文档对这四组概念 0 命中
(m) ★ 分析单位是"配置"不是论文
    原文: "Our unit of analysis is a **concrete configuration** ... A paper can
           describe several configurations, and one configuration can serve both
           design and repair."
```

### 另有 2 条印证（非缺口）

```text
① §5.1 "independent task checks must remain **outside the criterion it can rewrite**"
   ≡ DWC 原则 1 + JUDGE_LAYERS 纪律 2
② §6.1 STaR "restarting each round's fine-tuning from the **original pretrained model**"
   ≡ 母巢纪律 1（基线与结算同口径）
```

---

## 三、★★★ 补读解出的 8 条硬结论（(n)-(u)）

```text
(n) ★★★ imp@k = Γ_t 的可运行实现【2603.19461 §5.1 逐字】
    "We define imp@k as the improvement in test performance from the initial task
     agent A to the best-performing generated task agent (selected based on
     validation score)."
    ★★ 隔离手段: "To isolate the meta agent's ability to improve task agents from its
      ability to improve itself, **we hold the meta agent fixed throughout the
      process**"
    ⇒ I_0 的实现 = 冻结身份的那份改进器
    ★ 这与第 20 项（守卫① 用世界模型自算 confidence）**同源同解**

(o) ★ imp@k 必须报 CI【2603.19461】
    初始 meta agent  imp@50 = 0.0  (CI: 0.0 – 0.0)
    迁移 meta agent  imp@50 = 0.630 (CI: 0.540 – 0.630), p < 0.05
    ★ CI 上界 = 点估计（5 次重复运行取中位）
    ⇒ DWC 的门裁决若用改进器增益类数字, 必须带 CI

(p) ★★★ 归档非贪心是最大收益源【2505.22954 Table 1 逐字】
      Method                              SWE-bench   Polyglot
        DGM                                     50.0%      38.0%
        DGM w/o Open-ended exploration           23.0%      14.0%
        DGM w/o Self-improve                    39.0%      28.0%
        DGM Greedy                              39.7%      30.0%
    ⇒ 归档非贪心 = +27.0pp / 贪心 = +10.3pp / 改自己代码 = +11.0pp
    ★★ 优先级: 先投归档多样性, 再投"改自己的代码"
    ★ 诚实项: 单次结果未报方差; w/o self-improve 复刻的是 ADAS 不是"什么都不做"

(q) ★★ 阶梯评测协议【2505.22954 §4.2 逐字】
    SWE-bench: "over 40% success ... on the 60-task subset **and ranks among the top
      two performers in the archive** → evaluated on 200 tasks (140 plus the 60)"
    Polyglot: "over 40% on the 10-task subset → expanded 50-task subset"
    ★ 门槛 40% 原文自陈是 "a heuristic chosen based on the noise observed in
      preliminary runs"
    ⇒ DWC judge 的 split 应是三层（筛选/开发/密封）

(r) ★★ task/meta agent 必须同处一个可编辑程序【2603.19461】
    "**this alignment does not generally hold beyond coding domains**"
    ★★ DWC 的任务就是"自我改进"本身, 不是编码 ⇒ DGM 同域对齐前提对 DWC 不成立
    ⇒ +11.0pp 不可直接外推
    ⇒ m/U 虽分离, 但必须同处 evolver, 拆模块则 imp@k 类归因不成立（裁决第 12 项）
    ★ 独立佐证【2504.15228 SICA】: "A self-improving coding agent (SICA) that
      **eliminates the distinction between meta-agent and target agent**"

(s) ★ 0.0 起点是"格式不符"不是能力为零
    原文: "it fails to produce outputs in the required format due to the lack of
           task-specific parsing or post-processing"
    ⇒ DWC 失败签名必须区分"能力不足"与"接口/格式不通"

(t) ★★ 验证层级四层【2607.07663 §5.2 逐字】
    L4 formal verifier > L3 execution feedback > L2 learned judge > L1 intrinsic
    ★ 自陈: "a qualitative pattern ... **not a measured law**"
    ★ 限定: "ranks signals **given a target**; the choice of target is **prior**"

(u) ★★ Mirror Loop: 无外部接地 ⇒ 信息变化衰减 55%【2607.07663 §5.2 逐字】
    "informational change **declining 55% across iterations** — recursive
     self-evaluation without external feedback **yields reformulation, not
     progress** — while a **single minimal grounding intervention** (one verification
     step at iteration three) **restores forward movement**"
    ⇒ (f) 不只该设"无新反馈对照组", 该有目标数字: 衰减量级对标 55%
```

---

## 四、★★ 本轮 5 篇精读的新增发现（未入 §9，但可直接抄）

```text
★ S1. 【2408.08435 ADAS】归档**真无剪枝**
    宽口径 grep: prune 0 / pruning 0 / remove 0 / discard 0 / filter 0 / "top-" 仅 1 处
    （且那 1 处是生成 agent 内部的 ensemble，与归档无关）
    ⇒ ★★ 与 DGM 形成实证对照: DGM 靠归档非贪心拿 +27.0pp，ADAS 归档不剪也有效
    ⇒ 差异变量: DGM 从归档**采样**, ADAS 把归档**喂给 meta agent 当条件**
    ★★ 对 DWC 的意义: 世界树/归档的**消费方式**比"是否剪枝"更关键

★ S2. 【2408.08435 ADAS】Meta Agent Search 四步（原文 §3）
    (1) 归档可选初始化（CoT / Self-Refine）
    (2) meta agent 生成高层描述 → 写代码 → **两次 self-reflection 验新**
    (3) 用 validation 评估；出错则 self-reflection 修正，**最多 5 次**
    (4) 连同指标入归档
    ★ 可直接抄的两点: ① 新颖性也要检（两次反思）② 失败有重试上限（5 次）

★ S3. 【2505.03335 Absolute Zero】★ r_propose = 1 - r̄_solve（难度适中奖励）
    原文: "The intuition is that if a task is either **trivial to solve** (r̄_solve = 1)
           or **unsolvable** (r̄_solve = 0), the task provides **little to no learning
           signal** for the solver. In contrast, tasks of **moderate difficulty** ...
           are rewarded the most"
    ★★ 这与 DWC WORLD_TREE 的"选信息增益收束"**完全同构**，且给出了闭式奖励
    ★ 三种推理模式: induction / abduction / deduction（任务类型三分）
    ★ code executor 双重角色: 既验任务完整性又验答案 = **统一可验证反馈源**
    ★ 防 hacking 论证: "helps prevent issues such as **hacking with neural reward
      models**"（用真实环境而非神经奖励模型）

★ S4. 【2507.19457 GEPA (ICLR 2026 Oral)】
    "outperforms GRPO by 6% on average and by up to 20%, while using up to 35x
     fewer rollouts"
    ★ 核心机制: **Pareto frontier**（不是单点最优）+ **自然语言反思**诊断问题
    ★★ 对 DWC 的意义: 世界树收束有第二个可抄方案 —— Pareto 前沿而非"信息增益最大"
       两条路线：单树深挖（WORLD_TREE）vs 前沿并蓄（GEPA）
       ★ 建议: DWC 的收束策略应能声明用哪种，且默认 Pareto（更稳）

★ S5. 【2407.19594 Meta-Rewarding】★★ 两条可直接抄的机制
    ① ★ 方差选样: "we focus on responses where the judge is **the least certain**,
       as measured by the **variance of the scores** it has given ... We then pick the
       response y with the **highest score variance**"
       ⇒ DWC judge 应把"判定最不确定的样本"优先送 L3 独立审计
    ② ★ 位置偏置加权: 同一对判定**交换顺序提示两次**，按 win1st/win2nd 加权求和
       ⇒ DWC 的 L2 judge 若做两两比较，必须做位置偏置校正

★ S6. 【2601.05111 Agent-as-a-Judge】★★ 三段成熟度轴 + 三条失效
    三段（Figure 2 渐变）: **Procedural → Reactive → Self-Evolving**
    ★ 这给了 DWC judge 器官的**成熟度刻度**
    三条 LLM-as-a-Judge 失效（原文逐字）:
    ① "single-pass evaluators are prone to inherent **parametric biases**—such as
       favoring verbosity or their own output patterns"
    ② "naive LLM judges are **passive observers**, unable to react to real-world
       observations ... leading to **hallucinated evaluations**"
    ③ "traditional LLM judges experience **cognitive overload** ... within a single
       inference step, which results in **coarse-grained scores**"
    ⇒ 三条分别对应 DWC judge 的: 中立性 / 可接地验证 / 粒度分解
    ★ 四类工具能力: planning / memory / tool integration / multi-agent collaboration
```

---

## 五、★ 文献路线关系（重要，防止误判覆盖度）

```text
★ 实测: DWC 原有 19 篇中, 被 2609.2680 引用的只有 **2 篇**
  被引: 2609.11873 (Duan et al., 该文 ref[20]) / 2609.06396 (MetaRSI, ref[306])
  未引: 其余 17 篇（双口径复核 = arXiv ID + 标题关键词, 均 0 命中）

★★ 为什么（两层）:
  ① 时间差: 2609.2680 检索截止 **2026-09-12**, DWC 19 篇里 7 篇是 2609xx
  ② ★ 但 2603xx / 2505xx 的早期工作（SAHOO / SEVerA / CTM）**在时间窗内仍未被引**
     ⇒ 说明两条文献路线的**采样不重合**，不是覆盖关系

★★ 路线分工:
  DWC 的 19 篇  偏**机制级**（具体怎么改 harness / 记忆 / 环境）
  2609.2680   偏**协议级**（怎么验证改动真的有用）
  ⇒ 互补而非包含。这恰好解释了为什么 2609.2680 能补出 13 条缺口

★ 本文支柱 8 篇（正文引用频次实测, 共引 250 个编号 / 书目 404 篇）:
  [7]  ×6 Metaⁿ (2608.24735) · [82] ×5 GEPA · [5] ×5 DGM · [46] ×4 STOP
  [6]  ×4 Hyperagents · [75] ×3 Absolute Zero · [79] ×3 Meta-Rewarding
  [80] ×3 ADAS
  ★ 其余高频 [8][9][10][11][19][20][21] 全是综述
  ⇒ 引文结构 = 少量方法论文 + 大量综述, 与 DWC 的 19 篇**结构相反**

★ Table 5 里读出但论文没明说的结论:
  16 个配置中 "Update process = **Editable**" 的只有 4 个
  ⇒ 递归 RSI 的实证支撑面**很窄**（4/16）
```

---

## 六、★★ 必须裁决的一条正面冲突

```text
冲突: 领域集体答案 vs DWC 原则 12
  2607.07663 §5.1: 领域集体答案是"**用同样的循环改进评判器**"
    Deep-research 自演化 rubric [61] / 自训练验证 [92] /
    评判评判者 meta-evaluation [122] / Red Queen 共演化准则 [62]
  DWC 原则 12: judge 不得自评

★ 我的读法（分工, 不是矛盾）:
  "改进评判器" = 改 judge 的**策略/提示/权重**, 其改进仍需外部评测
  "judge 自评"   = judge 给自己打分, 不可归因
⇒ 必须把这条边界写进原则 12, 否则原则 12 会被误当作过时保守
```

---

## 七、21 条缺口的当前可结案度

```text
★★★★★ 已有实证答案（8 条）
  (n) imp@k 解 (a)(b) · (p) DGM Table 1 解优先级 · (q) 阶梯评测协议
  (t) 验证层级 · (u) 55% 目标数字 · (l) 三描述符（直接可用）
  (m) 分析单位 · (o) CI 规则

★★★ 有明确建议待拍板（5 条）
  (a) 测 Γ_t, 实现 = 冻结 meta agent 身份（等 (n)）
  (e) patch_target ∈ {task_artifact, improver_code}
  (c) 补保护组回归约束 r̂_{t,j} ≤ ϵ_j（含三态: 入档/待选/拒绝）
  (h) 三类漂移分离（优化/信息/行为）
  (i) 加恢复时间/丢失技能/恢复后质量三观测量

★★ 需更多设计（8 条）
  (d) 记忆四干预点可单独冻结 · (f) 无新反馈对照组（已有 55% 目标）
  (g) 目标演化双记 · (j) 三类度量分离 · (k) 后代评估预算归属
  (r) m/U 同处 evolver · (s) 失败签名加"格式不符"类 · (b) 配对探针严格形式
```

---

## 八、★ 三条最该记住的结论

```text
① ★★ 收益来源的排序被实测推翻
   归档非贪心 (+27.0pp) ≫ 改自己代码 (+11.0pp)
   ⇒ DWC 的世界树/归档是进化核心**第一优先**, 不是附属存储
   ★ 且 (n) 给出测它的方法（imp@k），(p) 给出它的收益量级，(q) 给出它的筛选协议

② ★★ 归因的正确做法是"冻结身份", 不是"加强守卫"
   (n) imp@k 靠冻结 meta agent 身份实现 I_0
   ⇒ 与第 20 项（守卫① 用世界模型自算 confidence）同源同解
   ⇒ 守卫① 的候选修法"乙"（改用 judge 滑动准确率）方向对，但
     ★ 更彻底的解法是冻结身份, 而非换一个更准的自评

③ ★★ 收束策略有两条可抄路线, 应能声明用哪条
   单树深挖 + 信息增益（WORLD_TREE 现有设计）
   Pareto 前沿 + 自然语言反思（GEPA, +6% vs GRPO, 35× 少 rollout）
   ⇒ 建议默认 Pareto（更稳）, 但两条都要能切换

④ ★★ 自我评定的三条失效已有名论断（Agent-as-a-Judge）
   ① 参数偏置（偏爱冗长/自己输出）· ② 被动观察无接地（幻觉评估）
   ③ 认知过载（单步评多维 → 粗粒度分数）
   ⇒ DWC judge 三层设计正好一一对应, 有论据了
```

---

## 八·补 ★ 第二轮精读（选乙：吃透再推进）—— 12 篇逐行精读完成

### 8·1 本轮读完的 12 篇（22 篇摘要级 → 12 篇逐行/结构级）

```text
【记忆核心 3 篇 · 逐行】
  2404.13501 记忆机制综述（39 页）· §5.3 三操作 / Table 3 覆盖矩阵 / §6.1.2 三指标
  2404.14387 自进化综述（28 页）· 四阶段 / 式(8)(9)(10) 自主性三档 / §8.3 三轮卡住
  2501.07278 终身学习路线图（46 页）· 记忆四分类 / 式(14)-(18) 五公式

【自进化 4 篇 · 逐行 + 结构级】
  2507.21046 自进化 agent 综述（TMLR 01/2026 正式发表，77 页）· What/When/How/Where 四轴
  2608.03392 自进化编码 agent（54 页）· A_t=(S_t,H_t,θ_t) + §10 五条开放问题
  2508.07407 MASE 综述（55 页）· 结构级（§3-§4 骨架）
  2603.25681 自改进技术展望（TMLR 09/2026 正式发表，135 页）· Coupled/Decoupled + §7 七类失败

【其余 5 篇 · 精读关键章】
  2309.16797 Promptbreeder（64 页）· 改进改进器的最早先例
  2502.16923 APO 综述（31 页）· 5-part 框架 + 归档策略四类
  2504.15585 full-stack 安全（69 页）· 全生命周期安全
  2504.01990 Foundation Agents（396 页）· 第 II 部分 100 页自进化专章 §9
  1208.3719 Auto-WEKA / 1611.01578 NAS-RL / 1703.03400 MAML / 1606.04474 学优化器 /
  1611.02779 RL²  —— 传统搜索基座 5 篇（摘要+核心段）

★ 本轮新增 3 份报告:
  docs/papers/MEMORY_EVOLUTION_SURVEYS.md    21,092 字节
  docs/papers/SELF_EVOLVING_SURVEYS.md        26,220 字节
  docs/papers/2603.25681.md                  15,380 字节
```

### 8·2 ★★★ 第二轮最硬的五条发现

```text
★★★★★ 1. A_t = (S_t, H_t, θ_t) 三元【2608.03392 式(7)(8)(9)】—— DWC 缺的最精确状态模型
  S_t = (memory, skills, tools, context)
  H_t = (harness, workflow, multi-agent organization)
  θ_t = 参数化决策策略 ★ DWC 固定
  ★★ ⇒ (e) 的可判定实现: 每候选声明 (target_layer, target_component)
  ★★ ⇒ 第 20 项根源: 守卫① 用 θ 层（自算 confidence）评 H 层 = **跨层自评**
  ★ 工具归属澄清: 改代码仍属 assets; 只有改变"如何组织与控制执行"才是 architecture

★★★★★ 2. Coupled/Decoupled + self-directed selection 的空白【2603.25681 §3.3.3】
  Coupled（主流，14 个方法中 9 个）: 模型更新后的状态**回馈到下一轮信号生成**
  Decoupled: 选择器独立训练、选择训练前固定; 代价是 forfeit adapt
  ★★ "No existing method ... has the main model curate its own training data
     **without an external selector**" ⇒ DWC 做的正是被点名的空白
  ★★ 理论断言: "optimal data selection **requires a reliable validation signal**,
     which is often unavailable in autonomous settings" ⇒ **intractable**
  ⇒ ★★ 若保留 coupled 设计, DWC 必须正面回答"可靠验证信号从哪来"

★★★★★ 3. 五条开放问题全是 DWC 的硬约束【2608.03392 §10】（26/26 逐字核实）
  · 同预算下"进化 harness"**不稳定优于简单测试时搜索**（Terminal-Bench 2.1）
  · ★ 自评分数**可近满分而真实性能不升反降**; 外部 accept-reject 审计**六模型**都更好
  · ★ Phantom Guardrails: **15/60 运行**为不存在的违规加护栏, **add-only 循环让它持久**
  · ★ harness tampering: 改评测路径本身且**可遗传到后代**
  · selective addition/deletion **优于**无节制增长; retention 是**有条件的**（消费四元）
  · 短基准高估: SWEEVO 21% vs SWE-bench 65%

★★★★ 4. 记忆四分类 + 五个标准公式【2501.07278】
  记忆四类: Working / Episodic / Semantic / Parametric ★ DWC 三区 = 去掉前两类
  五公式（直接填缺口 (c)(i)）:
    AP(14) AIP(15) | FGT(16) 保护组回归 | BWT(17) | FWT(18, 对照无经验基线)
  ★★ FGT 就是 (c) 保护组约束的标准化形式 ⇒ 不要自造记号
  ★★ 领域**没有**记忆专用公开基准【2404.13501 §6.3】⇒ DWC 造基准 = 填补空白

★★★ 5. 自主性三档公式【2404.14387 式(8)(9)(10)】—— DWC 定位判据
  Low:  M̃ = Evol_L(M, E, f•, ENV)  ★ "Most of the current works lie at this level"
  Med:  M̃ = Evol_M(M, E, ENV)        ★★ DWC 现在在这里（E 定、f• 用户设计）
  High: M̃ = Evol_H(M, ENV)           ★ 进 High 需 ① E 自己会变 ② 模型自诊断
  ⇒ 与缺口 (g) 目标演化双记是同一件事, 裁决时一起
  ★★ 另一条硬约束: "struggle to improve after **more than three rounds**"
     假设: "the self-critic of LLM has **not co-evolved** with the evolving objective"
```

### 8·3 §9 现状：21 条 → 49 条

```text
ARCHITECTURE.md  96,706 → 104,360 字节
§9 第 25 项子条  21 → 49 条 (a)-(bw)
  · (bb)-(bp) 15 条来自 2608.03392 §10（26/26 核实）
  · (bq)-(bw) 8 条来自 2603.25681 §3.3.3/§7.1
gate.py 7 门全绿 rc=0
```

### 8·3bis ★ 第三轮（选甲）：§6 自主评估层全文补读完成

```text
2603.25681 §6 全部读完（L2919-3335, 416 行）:
  §6.1 自主评估的定义与两压力     §6.2 动态基准（14 个基准实测）
  §6.3 交互式环境（含 Table 13 20 个）§6.3.2 过程式环境
  §6.4.1 趋势  §6.4.2 可扩展性权衡  ★§6.4.3 整体系统监督
23/23 逐字核实（2 处弯引号假阴性已定位）

★ 本轮四条硬结论（已入 §9 (bx)-(ch)）:
  ① ★★★ 观察窗是推理 ⇒ 验收必须同时报 test-time 配置
  ② ★★★ 评估是闭环触发器, 不是终点报告 ⇒ 支撑"任务源=世界模型"
  ③ ★★★★ LLM 生成/评判评估实例 ⇒ 评估器耦合（coupled 风险第三条独立来源）
  ④ ★★★ 两个现成递归评估协议 AI4AI-Bench / RSI-Exam = DWC 的外部对照物
  ⑤ ★★★ 环境噪声必须与模型失败区分（对跑在真实环境的 DWC 尤其重要）

★ §9 第25项子条: 49 → 60 条 (a)-(ch)
ARCHITECTURE.md 104,360 → 113,431 字节
```

### 8·4 第二/三轮诚实条款

```text
① 2508.07407 只做结构级精读（§3-§4 骨架），未逐行读完 55 页
   ★ 其"记忆分短/长两层"与 DWC 三区的结论需逐行读完确认
② ★2603.25681 §6 已补读完成（第三轮）。★ 仍缺 §8-§10
   （§8 潜在风险: Loss of Control / High-Stakes Harm / 社会伦理 / 误用）
③ 2603.25681 的 coupled/decoupled 论断在**数据选择域**成立;
   迁移到"架构/代码选择"域是**我的类比**, 需另找证据
④ "No existing method ... curate its own training data" 是该综述在其语料内的断言
   （检索截止 2026-09）, 不等于全球范围无人做过
⑤ 传统搜索基座 5 篇（Auto-WEKA/NAS/MAML/学优化器/RL²）本轮只读摘要+核心段
   ★ 它们是方法学祖先, 对 DWC 价值有限, 未逐行读完是主动取舍
⑥ Foundation Agents 396 页本轮只读第 II 部分 §9（自进化专章）
⑦ 本轮新增引文核实 23/23（前一轮 26/26 + 更早各轮）
   · 断词/大小写假阴性共 7 处已逐处定位原文确认
```

---

## 九、诚实条款（本次深读整体）

```text
① 2609.2680: NOT PEER-REVIEWED + 标注用 ChatGPT 辅助写作 + Table 1 自评九维全 ✓
   （自评偏乐观）—— 已按 REPORT_SPEC 逐条标注
② 2607.07663: 验证层级自陈 "not a measured law"（定性模式）
③ 2505.22954 DGM: Table 1 单点值, 未报方差; w/o self-improve 复刻 ADAS
④ 2603.19461: imp@50 只测 1 个域; 5 次运行取中位; 起点 0.0 因格式不符
⑤ 2408.08435 ADAS: ARC 只 25 次迭代 / 其他域 30 次; 未报失败案例细节
⑥ 2505.03335 AZR: 只在代码+数学推理域验证
⑦ 2507.19457 GEPA: 6 个任务上平均 +6% vs GRPO
⑧ ★ 22 篇为**摘要级扫读**（已抓全文, 但本轮未逐行）—— 标为摘要级, 不作深度结论
⑨ ★ 本轮所有新增结论均标注了"未入 §9"与"可直接抄"的区别, 避免误认为已定设计
```

---

*报告 2026-10-04 · 36 轮反刍深读 · 核心 1 篇全文 2,330 行 + 补读 28 篇 1,698 页*
*逐字核实 67 处（4 处假阳性/假阴性已逐处定位）· 主文件 ARCHITECTURE.md §9 第 25 项 21 条*